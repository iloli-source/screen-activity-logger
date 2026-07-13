"""Ollama経由でVLM（Qwen3-VL等）を呼ぶSceneDescriberポートの実装。"""

from __future__ import annotations

import time
from typing import Any, Protocol

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
)
from screen_activity_logger.infrastructure.vlm_common import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_ATTEMPTS as _MAX_ATTEMPTS,
    SLOW_CALL_THRESHOLD_SECONDS as _SLOW_CALL_THRESHOLD_SECONDS,
    build_prompt,
    is_retryable as _is_retryable,
    parse_fields,
)

# 画像の視覚トークン＋プロンプトが収まるコンテキスト長（Ollama既定4096では不足）
_NUM_CTX = 8192

# バッチ中（動画間のOCRフェーズ等）にOllama既定5分でアンロードされ、
# 再ロードのコールドスタートが繰り返されるのを防ぐ
_KEEP_ALIVE = "30m"


class ChatClient(Protocol):
    """ollama.Client互換の最小インターフェース。"""

    def chat(self, **kwargs: Any) -> Any: ...


class OllamaSceneDescriber:
    """フレーム画像＋OCRテキストから日本語の作業説明を生成する。"""

    def __init__(
        self,
        model: str,
        client: ChatClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._client = client
        self._owns_client = client is None  # 注入クライアントは再作成しない
        self._timeout_seconds = timeout_seconds
        self._warmed = False

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self._ensure_warm()
        response = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            started = time.monotonic()
            try:
                response = self._get_client().chat(
                    model=self._model,
                    messages=[
                        {
                            "role": "user",
                            "content": self._build_prompt(ocr, speech),
                            "images": [str(frame.path)],
                        }
                    ],
                    think=False,
                    options={"num_ctx": _NUM_CTX},
                    keep_alive=_KEEP_ALIVE,
                )
            except Exception as error:  # noqa: BLE001 — バッチ継続を優先しログに残す
                elapsed = time.monotonic() - started
                print(
                    f"VLM呼び出し失敗 t={frame.timestamp}"
                    f" attempt={attempt}/{_MAX_ATTEMPTS} {elapsed:.1f}s:"
                    f" {type(error).__name__}: {error}",
                    flush=True,
                )
                if attempt < _MAX_ATTEMPTS and _is_retryable(error):
                    # ハングしたコネクションの残骸を排除してから再試行
                    self._reset_client()
                    continue
                return ActivityDescription(
                    timestamp=frame.timestamp,
                    action=f"（VLM呼び出し失敗: {type(error).__name__}）",
                    app_guess=None,
                )
            elapsed = time.monotonic() - started
            slow = " SLOW" if elapsed > _SLOW_CALL_THRESHOLD_SECONDS else ""
            print(
                f"VLM推論 t={frame.timestamp} attempt={attempt}"
                f" {elapsed:.1f}s{slow}",
                flush=True,
            )
            break
        content = self._response_content(response)
        fields = self._parse(content)
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=fields["action"],
            app_guess=fields["app_guess"],
            resource=fields["resource"],
            location=fields["location"],
            focus=fields["focus"],
        )

    def _ensure_warm(self) -> None:
        """初回describe直前の遅延ウォームアップ（Issue #14）。

        コールドスタート（モデルロード込み）は画像推論と合わさると300秒
        タイムアウトを超え、先頭フレームがフォールバックになる。画像なしの
        軽量プロンプトでロードだけ先に済ませる。num_ctxは本番と一致必須
        （異なるとOllamaがモデルを再ロードして無意味になる）。
        """
        if self._warmed:
            return
        # 失敗しても再試行しない（サーバ停止時に300秒×N回の待ちを防ぐ）
        self._warmed = True
        try:
            self._get_client().chat(
                model=self._model,
                messages=[{"role": "user", "content": "ok"}],
                think=False,
                options={"num_ctx": _NUM_CTX},
                keep_alive=_KEEP_ALIVE,
            )
        except Exception as error:  # noqa: BLE001
            # タイムアウトしてもサーバ側のロードは継続する → 本番呼び出しへ続行
            print(
                f"VLMウォームアップ失敗（続行）: {type(error).__name__}", flush=True
            )

    def _get_client(self) -> ChatClient:
        if self._client is None:
            import ollama

            self._client = ollama.Client(timeout=self._timeout_seconds)
        return self._client

    def _reset_client(self) -> None:
        """ハング疑いのクライアントを破棄し次回遅延再生成する（Issue #15）。

        自己所有クライアントのみ対象（注入クライアントはテスト・DI用のため
        同一オブジェクトを再利用）。close()はChatClient Protocolにないため防御的に呼ぶ。
        """
        if not self._owns_client or self._client is None:
            return
        close = getattr(self._client, "close", None)
        if close is not None:
            try:
                close()
            except Exception:  # noqa: BLE001 — 破棄目的なので失敗は無視
                pass
        self._client = None

    @staticmethod
    def _build_prompt(ocr: OcrText, speech: tuple[str, ...] = ()) -> str:
        return build_prompt(ocr, speech)

    @staticmethod
    def _response_content(response: Any) -> str:
        if isinstance(response, dict):
            return str(response["message"]["content"])
        return str(response.message.content)

    @staticmethod
    def _parse(content: str) -> dict[str, str | None]:
        return parse_fields(content)

