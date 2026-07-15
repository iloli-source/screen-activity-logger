"""OpenAI互換API（vllm-mlx等）経由のSceneDescriberポート実装（Issue #21）。

Issue #8実測でvllm-mlx（Qwen3-VL-8B-4bit）がOllama比約40倍と確定したため追加。
プロンプト・応答パース・リトライ判定・テレメトリはvlm_common経由でOllama版と同一。
サーバーはユーザー起動前提（vlm_factory.ensure_backend_availableが到達性を確認）。
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
)
from screen_activity_logger.infrastructure.vlm_common import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_ATTEMPTS,
    SLOW_CALL_THRESHOLD_SECONDS,
    build_prompt,
    is_retryable,
    parse_fields,
)

DEFAULT_VLLM_URL = "http://localhost:8991/v1"
DEFAULT_VLLM_MODEL = "mlx-community/Qwen3-VL-8B-Instruct-4bit"

_MAX_TOKENS = 512  # 構造化JSON出力には十分（長文生成はdecodeの無駄）


class OpenAIChatSceneDescriber:
    """OpenAI互換 /v1/chat/completions でフレームを説明する。"""

    def __init__(
        self,
        model: str = DEFAULT_VLLM_MODEL,
        base_url: str = DEFAULT_VLLM_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._warmed = False

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self._ensure_warm()
        image_b64 = base64.b64encode(Path(frame.path).read_bytes()).decode()
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_prompt(ocr, speech)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": _MAX_TOKENS,
        }
        content = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.monotonic()
            try:
                content = self._post_chat(payload)
            except Exception as error:  # noqa: BLE001 — バッチ継続を優先
                elapsed = time.monotonic() - started
                print(
                    f"VLM呼び出し失敗 t={frame.timestamp}"
                    f" attempt={attempt}/{MAX_ATTEMPTS} {elapsed:.1f}s:"
                    f" {type(error).__name__}: {error}",
                    flush=True,
                )
                if attempt < MAX_ATTEMPTS and is_retryable(error):
                    continue
                return ActivityDescription(
                    timestamp=frame.timestamp,
                    action=f"（VLM呼び出し失敗: {type(error).__name__}）",
                    app_guess=None,
                )
            if not (content or "").strip() and attempt < MAX_ATTEMPTS:
                # コールドスタート直後はHTTP成功でもcontent空が返ることがある
                # （Issue #28の実測）。第二防衛線としてリトライする
                print(
                    f"VLM空応答（リトライ） t={frame.timestamp}"
                    f" attempt={attempt}/{MAX_ATTEMPTS}",
                    flush=True,
                )
                continue
            elapsed = time.monotonic() - started
            slow = " SLOW" if elapsed > SLOW_CALL_THRESHOLD_SECONDS else ""
            print(
                f"VLM推論 t={frame.timestamp} attempt={attempt}"
                f" {elapsed:.1f}s{slow}",
                flush=True,
            )
            break
        fields = parse_fields(content or "")
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=fields["action"],
            app_guess=fields["app_guess"],
            resource=fields["resource"],
            location=fields["location"],
            focus=fields["focus"],
        )

    def _ensure_warm(self) -> None:
        """初回呼び出し前にサーバーを温める（Issue #28）。

        起動直後の初回リクエストはHTTP成功でもcontent空が返ることがある
        （コールドスタート中の応答）。Ollamaアダプタの_ensure_warmと対称。
        失敗しても本処理へ進む（本処理側のリトライが最終防衛線）。
        """
        if self._warmed:
            return
        self._warmed = True
        try:
            self._post_chat({
                "model": self._model,
                "messages": [{"role": "user", "content": "ok"}],
                "temperature": 0,
                "max_tokens": 8,
            })
        except Exception as error:  # noqa: BLE001
            print(
                f"VLMウォームアップ失敗（本処理は継続）:"
                f" {type(error).__name__}: {error}",
                flush=True,
            )

    def _post_chat(self, payload: dict[str, Any]) -> str:
        import httpx  # 遅延import（直接依存として宣言済み、4AIレビューR1）

        response = httpx.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])
