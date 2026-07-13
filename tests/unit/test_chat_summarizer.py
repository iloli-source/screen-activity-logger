"""発話要旨アダプタのユニットテスト（Issue #23 S3: RED）。"""

from screen_activity_logger.infrastructure.chat_summarizer import (
    SUMMARY_PROMPT,
    OllamaChatSummarizer,
    OpenAIChatSummarizer,
)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None: ...

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


class TestOpenAIChatSummarizer:
    def test_sends_prompt_with_lines(self, monkeypatch) -> None:
        calls: list[dict] = []

        def fake_post(url, json=None, timeout=None):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse("  案件の進捗を報告している  ")

        monkeypatch.setattr("httpx.post", fake_post)
        summarizer = OpenAIChatSummarizer(
            model="m", base_url="http://localhost:8991/v1", timeout_seconds=60.0
        )

        result = summarizer.summarize(("進捗ですが", "8割です", "来週完了"))

        (call,) = calls
        assert call["url"] == "http://localhost:8991/v1/chat/completions"
        content = call["json"]["messages"][0]["content"]
        assert SUMMARY_PROMPT in content
        assert "進捗ですが" in content
        assert call["json"]["temperature"] == 0
        assert result == "案件の進捗を報告している"

    def test_empty_response_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResponse("  "))

        assert OpenAIChatSummarizer(model="m").summarize(("あ",)) is None


class TestOllamaChatSummarizer:
    def test_uses_ollama_chat(self, monkeypatch) -> None:
        import sys
        import types

        calls: list[dict] = []

        def fake_chat(model, messages, options=None):
            calls.append({"model": model, "messages": messages})
            return {"message": {"content": "要旨文"}}

        fake_module = types.SimpleNamespace(chat=fake_chat)
        monkeypatch.setitem(sys.modules, "ollama", fake_module)

        result = OllamaChatSummarizer(model="qwen3-vl:8b").summarize(
            ("発話1", "発話2", "発話3")
        )

        (call,) = calls
        assert call["model"] == "qwen3-vl:8b"
        assert SUMMARY_PROMPT in call["messages"][0]["content"]
        assert result == "要旨文"
