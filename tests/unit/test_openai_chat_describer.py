"""OpenAI互換SceneDescriberのユニットテスト（Issue #21 M2: RED）。

httpx.postをmonkeypatchで差し替え、実サーバー不要で配線を検証する。
"""

import base64
import json
from pathlib import Path

from screen_activity_logger.domain.models import Frame, OcrText, VideoTimestamp
from screen_activity_logger.infrastructure.openai_chat_describer import (
    OpenAIChatSceneDescriber,
)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None: ...

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _frame(tmp_path: Path) -> Frame:
    png = tmp_path / "frame.png"
    png.write_bytes(b"\x89PNG-fake")
    return Frame(
        timestamp=VideoTimestamp(seconds=12.0), path=png, is_keyframe=True
    )


def _ocr(*lines: str) -> OcrText:
    return OcrText(timestamp=VideoTimestamp(seconds=12.0), lines=lines)


def _install_fake_post(monkeypatch, handler):
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return handler(len(calls))

    monkeypatch.setattr("httpx.post", fake_post)
    return calls


class TestOpenAIChatSceneDescriber:
    _OK = '{"app_guess": "Excel", "resource": "見積書.xlsx", "location": null, "focus": null, "action": "編集中"}'

    def test_sends_base64_image_and_prompt(self, monkeypatch, tmp_path) -> None:
        calls = _install_fake_post(
            monkeypatch, lambda n: FakeResponse(self._OK)
        )
        describer = OpenAIChatSceneDescriber(
            base_url="http://localhost:8991/v1", timeout_seconds=123.0
        )

        desc = describer.describe(_frame(tmp_path), _ocr("見積書.xlsx - Excel"))

        call = calls[1]  # calls[0]はウォームアップ（Issue #28）
        assert call["url"] == "http://localhost:8991/v1/chat/completions"
        assert call["timeout"] == 123.0
        payload = call["json"]
        assert payload["temperature"] == 0
        parts = payload["messages"][0]["content"]
        assert "見積書.xlsx - Excel" in parts[0]["text"]  # Ollamaと同一プロンプト
        assert "PC作業の記録係" in parts[0]["text"]
        expected_b64 = base64.b64encode(b"\x89PNG-fake").decode()
        assert parts[1]["image_url"]["url"].endswith(expected_b64)
        assert desc.app_guess == "Excel"
        assert desc.resource == "見積書.xlsx"
        assert desc.action == "編集中"

    def test_timeout_then_success_is_rescued(self, monkeypatch, tmp_path) -> None:
        def handler(call_number: int):
            if call_number == 2:  # 1はウォームアップ（Issue #28）
                raise TimeoutError("read timeout")
            return FakeResponse(self._OK)

        calls = _install_fake_post(monkeypatch, handler)
        describer = OpenAIChatSceneDescriber()

        desc = describer.describe(_frame(tmp_path), _ocr())

        assert len(calls) == 3  # ウォームアップ＋リトライ1回
        assert desc.action == "編集中"

    def test_non_retryable_error_falls_back(self, monkeypatch, tmp_path) -> None:
        def handler(call_number: int):
            raise ValueError("bad request")

        calls = _install_fake_post(monkeypatch, handler)
        describer = OpenAIChatSceneDescriber()

        desc = describer.describe(_frame(tmp_path), _ocr())

        assert len(calls) == 2  # ウォームアップ失敗＋本処理即フォールバック
        assert "失敗" in desc.action

    def test_telemetry_line_is_emitted(self, monkeypatch, tmp_path, capsys) -> None:
        _install_fake_post(monkeypatch, lambda n: FakeResponse(self._OK))
        OpenAIChatSceneDescriber().describe(_frame(tmp_path), _ocr())
        assert "VLM推論 t=00:00:12 attempt=1" in capsys.readouterr().out


class TestWarmupAndEmptyRetry:
    """Issue #28: 初回ウォームアップと空応答リトライ。"""

    _OK = '{"app_guess": "Excel", "resource": null, "location": null, "focus": null, "action": "編集中"}'

    def test_first_describe_sends_warmup_request(self, monkeypatch, tmp_path) -> None:
        calls = _install_fake_post(monkeypatch, lambda n: FakeResponse(self._OK))
        describer = OpenAIChatSceneDescriber()

        describer.describe(_frame(tmp_path), _ocr())
        describer.describe(_frame(tmp_path), _ocr())

        # 1回目describeの前にウォームアップ1回 → 合計3リクエスト
        assert len(calls) == 3
        warmup_payload = calls[0]["json"]
        assert warmup_payload["max_tokens"] <= 8  # 軽量リクエスト
        assert isinstance(warmup_payload["messages"][0]["content"], str)  # 画像なし

    def test_warmup_failure_does_not_block_describe(
        self, monkeypatch, tmp_path
    ) -> None:
        def handler(call_number: int):
            if call_number == 1:
                raise ConnectionError("cold")
            return FakeResponse(self._OK)

        _install_fake_post(monkeypatch, handler)
        describer = OpenAIChatSceneDescriber()

        desc = describer.describe(_frame(tmp_path), _ocr())

        assert desc.action == "編集中"

    def test_empty_content_is_retried(self, monkeypatch, tmp_path) -> None:
        def handler(call_number: int):
            if call_number <= 2:  # warmup + 1回目describe
                return FakeResponse("")
            return FakeResponse(self._OK)

        calls = _install_fake_post(monkeypatch, handler)
        describer = OpenAIChatSceneDescriber()

        desc = describer.describe(_frame(tmp_path), _ocr())

        assert len(calls) == 3  # warmup→空→リトライ成功
        assert desc.action == "編集中"
