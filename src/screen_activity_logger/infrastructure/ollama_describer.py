"""Ollama経由でVLM（Qwen3-VL等）を呼ぶSceneDescriberポートの実装。"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
)

_PROMPT_TEMPLATE = """あなたはPC作業の記録係です。このスクリーンショットについて日本語で記録します:
1) app_guess: 使用中のアプリ（Excel/PowerPoint/Chrome/VS Code等）
2) resource: 開いているファイル名・ページタイトル・文書名。タイトルバーやタブに明確に読み取れる場合のみ。読み取れない・確信がない場合はnull。画面の説明文（"Web page titled..."等）や意味不明な文字断片は書かない
3) location: リソース内の位置（シート名・スライド番号・ページ番号・見出し・URLパス等）
4) focus: ユーザーが画面のどこを見て何を判断していそうか（カーソル位置・選択状態・強調から推測）
5) action: 今している操作の説明（1〜2文）

参考: この画面からOCRで抽出されたテキスト:
{ocr_text}

参考: この時間帯にユーザーが話していた内容（音声認識）:
{speech_text}

次のJSONのみを出力してください（説明文・コードフェンス不要。不明な項目はnull）:
{{"app_guess": "...", "resource": "...", "location": "...", "focus": "...", "action": "..."}}"""

_CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\n|\n?```$")

_FALLBACK_ACTION = "（この画面の説明を生成できませんでした）"

# 画像の視覚トークン＋プロンプトが収まるコンテキスト長（Ollama既定4096では不足）
_NUM_CTX = 8192

# VLM呼び出しのタイムアウト（秒）。実測: 応答が宙に浮くとsock_recvで
# 無限待ちになりバッチ全体が停止するため必須（実会議10本バッチで発覚）
DEFAULT_TIMEOUT_SECONDS = 300.0

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
        self._timeout_seconds = timeout_seconds
        self._warmed = False

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self._ensure_warm()
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
            print(
                f"VLM呼び出し失敗 t={frame.timestamp}: {type(error).__name__}: {error}",
                flush=True,
            )
            return ActivityDescription(
                timestamp=frame.timestamp,
                action=f"（VLM呼び出し失敗: {type(error).__name__}）",
                app_guess=None,
            )
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

    @staticmethod
    def _build_prompt(ocr: OcrText, speech: tuple[str, ...] = ()) -> str:
        lines = ocr.normalized_lines()
        ocr_text = "\n".join(lines) if lines else "(テキストなし)"
        speech_text = "\n".join(speech) if speech else "(発話なし)"
        return _PROMPT_TEMPLATE.format(ocr_text=ocr_text, speech_text=speech_text)

    @staticmethod
    def _response_content(response: Any) -> str:
        if isinstance(response, dict):
            return str(response["message"]["content"])
        return str(response.message.content)

    @staticmethod
    def _parse(content: str) -> dict[str, str | None]:
        empty: dict[str, str | None] = {
            "app_guess": None,
            "resource": None,
            "location": None,
            "focus": None,
        }
        cleaned = _CODE_FENCE_PATTERN.sub("", content.strip()).strip()
        if not cleaned:
            return {**empty, "action": _FALLBACK_ACTION}
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return {**empty, "action": cleaned}
        fields: dict[str, str | None] = {
            key: _normalize(payload.get(key)) for key in empty
        }
        fields["action"] = str(payload.get("action", "")).strip() or _FALLBACK_ACTION
        return fields


def _normalize(value: object) -> str | None:
    """JSONの空値表現（null/"null"/"none"/空文字）をNoneに正規化する。"""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in ("null", "none"):
        return None
    return stripped
