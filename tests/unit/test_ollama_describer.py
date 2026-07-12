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

    def test_empty_response_falls_back_to_placeholder_action(self) -> None:
        """実機で発生: VLMが空応答を返してもクラッシュせずログを残す。"""
        client = FakeOllamaClient("")
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.action  # 空でないこと
        assert desc.app_guess is None

    def test_empty_action_in_valid_json_falls_back(self) -> None:
        client = FakeOllamaClient('{"app_guess": "Finder", "action": ""}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.action

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

        prompt = client.calls[-1]["messages"][0]["content"]
        assert "pytest" in prompt
        assert "FAILED test_auth.py" in prompt

    def test_sends_frame_image_and_disables_thinking(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        call = client.calls[-1]
        assert call["model"] == "qwen3-vl:8b"
        assert call["messages"][0]["images"] == ["/tmp/frame.png"]
        assert call["think"] is False

    def test_parses_context_fields_from_json(self) -> None:
        """Y3: resource/location/focusの構造化フィールドをパースする。"""
        client = FakeOllamaClient(
            '{"app_guess": "Excel", "resource": "見積書.xlsx", '
            '"location": "Sheet1", "focus": "D列の合計を確認", '
            '"action": "セルを修正している"}'
        )
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.resource == "見積書.xlsx"
        assert desc.location == "Sheet1"
        assert desc.focus == "D列の合計を確認"

    def test_missing_context_fields_default_to_none(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "作業中"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.resource is None
        assert desc.location is None
        assert desc.focus is None

    def test_prompt_asks_for_context_fields(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        prompt = client.calls[-1]["messages"][0]["content"]
        assert "resource" in prompt
        assert "location" in prompt
        assert "focus" in prompt

    def test_chat_failure_returns_fallback_instead_of_hanging_batch(self) -> None:
        """実バッチで発覚: 応答が来ないと無限待ち→バッチ全体が停止する。

        呼び出し失敗（タイムアウト等）はフォールバックエントリで継続する。
        """

        class FailingClient:
            def chat(self, **kwargs):
                raise TimeoutError("read timeout")

        describer = OllamaSceneDescriber(
            model="qwen3-vl:8b", client=FailingClient()
        )

        desc = describer.describe(_frame(), _ocr())

        assert desc.action  # 空でない（例外を投げずログに残す）
        assert "Timeout" in desc.action or "失敗" in desc.action

    def test_lazy_client_is_created_with_timeout(self, monkeypatch) -> None:
        """既定クライアントにタイムアウトが設定される（無限待ちの根治）。"""
        import ollama as ollama_module

        captured: dict = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr(ollama_module, "Client", FakeClient)
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", timeout_seconds=120.0)

        describer._get_client()

        assert captured.get("timeout") == 120.0

    def test_requests_expanded_context_window(self) -> None:
        """実録画で発覚: 既定num_ctx=4096では視覚トークンが収まらない。"""
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        assert client.calls[-1]["options"]["num_ctx"] >= 8192


class TestOllamaWarmUp:
    """G1: 初回describe直前の遅延ウォームアップ（Issue #14）。

    Ollamaコールドスタート（モデルロード込み）が300秒タイムアウトを超え、
    先頭フレームの説明がフォールバックになる問題への対策。
    """

    def test_first_describe_sends_lightweight_warmup_before_real_call(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        assert len(client.calls) == 2
        warmup = client.calls[0]
        assert warmup["model"] == "qwen3-vl:8b"
        assert "images" not in warmup["messages"][0]  # 画像なしの軽量プロンプト
        # num_ctxが本番と異なるとOllamaがモデルを再ロードして無意味になる
        assert warmup["options"]["num_ctx"] == client.calls[1]["options"]["num_ctx"]

    def test_warmup_happens_only_once(self) -> None:
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())
        describer.describe(_frame(), _ocr())

        assert len(client.calls) == 3  # warmup + describe×2

    def test_warmup_failure_does_not_break_describe(self) -> None:
        """ウォームアップがタイムアウトしてもサーバ側のロードは継続する。"""

        class WarmupFailingClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def chat(self, **kwargs: Any) -> dict[str, Any]:
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    raise TimeoutError("cold start read timeout")
                return {"message": {"content": '{"app_guess": null, "action": "作業中"}'}}

        client = WarmupFailingClient()
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        desc = describer.describe(_frame(), _ocr())

        assert desc.action == "作業中"  # 本番呼び出しは正常応答
        assert len(client.calls) == 2

    def test_warmup_and_describe_request_keep_alive(self) -> None:
        """バッチ中（動画間のOCRフェーズ等）の再アンロードを防ぐ。"""
        client = FakeOllamaClient('{"app_guess": null, "action": "a"}')
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)

        describer.describe(_frame(), _ocr())

        assert client.calls[0]["keep_alive"] == "30m"
        assert client.calls[1]["keep_alive"] == "30m"
