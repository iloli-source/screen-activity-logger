"""OllamaSceneDescriber のユニットテスト（Cycle H-1: RED）。

Ollamaクライアントはフェイクを注入し、プロンプト構築と応答パースを検証する。
"""

from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import Frame, OcrText, VideoTimestamp
from screen_activity_logger.infrastructure.ollama_describer import (
    OllamaSceneDescriber,
)


class FakeOllamaClient:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"message": {"content": self._content}}


def _frame() -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=12.0),
        path=Path("/tmp/frame.png"),
        is_keyframe=True,
    )


def _ocr(*lines: str) -> OcrText:
    return OcrText(timestamp=VideoTimestamp(seconds=12.0), lines=lines)


class TestOllamaSceneDescriber:
    def test_parses_json_response_into_description(self) -> None:
        client = FakeOllamaClient(
            '{"app_guess": "VS Code", "action": "コードを編集している"}'
        )
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr("def main():"))

        assert desc.app_guess == "VS Code"
        assert desc.action == "コードを編集している"
        assert desc.timestamp.seconds == 12.0

    def test_strips_markdown_code_fences(self) -> None:
        client = FakeOllamaClient(
            '```json\n{"app_guess": null, "action": "資料を読んでいる"}\n```'
        )
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.app_guess is None
        assert desc.action == "資料を読んでいる"

    def test_falls_back_to_raw_text_on_invalid_json(self) -> None:
        client = FakeOllamaClient("ブラウザで検索している様子です")
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.action == "ブラウザで検索している様子です"
        assert desc.app_guess is None

    def test_prompt_includes_ocr_lines(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr("pytest", "FAILED test_auth.py"))

        prompt = client.calls[0]["messages"][0]["content"]
        assert "pytest" in prompt
        assert "FAILED test_auth.py" in prompt

    def test_sends_frame_image_and_disables_thinking(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        call = client.calls[0]
        assert call["model"] == "qwen3-vl:8b"
        assert call["messages"][0]["images"] == ["/tmp/frame.png"]
        assert call["think"] is False
