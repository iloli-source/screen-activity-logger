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

_PROMPT_TEMPLATE = """あなたはPC作業の記録係です。このスクリーンショットについて:
1) 使用中のアプリ/画面を推定する
2) ユーザーが今している操作を1〜2文の日本語で説明する

参考: この画面からOCRで抽出されたテキスト:
{ocr_text}

次のJSONのみを出力してください（説明文・コードフェンス不要）:
{{"app_guess": "アプリ名 or null", "action": "操作の説明"}}"""

_CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\n|\n?```$")

_FALLBACK_ACTION = "（この画面の説明を生成できませんでした）"

# 画像の視覚トークン＋プロンプトが収まるコンテキスト長（Ollama既定4096では不足）
_NUM_CTX = 8192


class ChatClient(Protocol):
    """ollama.Client互換の最小インターフェース。"""

    def chat(self, **kwargs: Any) -> Any: ...


class OllamaSceneDescriber:
    """フレーム画像＋OCRテキストから日本語の作業説明を生成する。"""

    def __init__(self, model: str, client: ChatClient | None = None) -> None:
        self._model = model
        self._client = client

    def describe(self, frame: Frame, ocr: OcrText) -> ActivityDescription:
        response = self._get_client().chat(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": self._build_prompt(ocr),
                    "images": [str(frame.path)],
                }
            ],
            think=False,
            options={"num_ctx": _NUM_CTX},
        )
        content = self._response_content(response)
        app_guess, action = self._parse(content)
        return ActivityDescription(
            timestamp=frame.timestamp, action=action, app_guess=app_guess
        )

    def _get_client(self) -> ChatClient:
        if self._client is None:
            import ollama

            self._client = ollama.Client()
        return self._client

    @staticmethod
    def _build_prompt(ocr: OcrText) -> str:
        lines = ocr.normalized_lines()
        ocr_text = "\n".join(lines) if lines else "(テキストなし)"
        return _PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    @staticmethod
    def _response_content(response: Any) -> str:
        if isinstance(response, dict):
            return str(response["message"]["content"])
        return str(response.message.content)

    @staticmethod
    def _parse(content: str) -> tuple[str | None, str]:
        cleaned = _CODE_FENCE_PATTERN.sub("", content.strip()).strip()
        if not cleaned:
            return None, _FALLBACK_ACTION
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return None, cleaned
        app_guess = payload.get("app_guess")
        if isinstance(app_guess, str) and app_guess.lower() in ("null", "none", ""):
            app_guess = None
        action = str(payload.get("action", "")).strip() or _FALLBACK_ACTION
        return app_guess, action
