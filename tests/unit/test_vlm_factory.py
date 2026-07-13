"""VLMファクトリのユニットテスト（Issue #21 M3: RED）。"""

import pytest

from screen_activity_logger.infrastructure.ollama_describer import (
    OllamaSceneDescriber,
)
from screen_activity_logger.infrastructure.openai_chat_describer import (
    DEFAULT_VLLM_MODEL,
    OpenAIChatSceneDescriber,
)
from screen_activity_logger.infrastructure.vlm_factory import (
    create_describer,
    ensure_backend_available,
)


class TestCreateDescriber:
    def test_creates_ollama(self) -> None:
        describer = create_describer("ollama", "qwen3-vl:8b", timeout_seconds=450.0)
        assert isinstance(describer, OllamaSceneDescriber)
        assert describer._timeout_seconds == 450.0

    def test_creates_vllm_mlx(self) -> None:
        describer = create_describer(
            "vllm-mlx", "mlx-community/Custom-Model",
            base_url="http://localhost:9000/v1",
        )
        assert isinstance(describer, OpenAIChatSceneDescriber)
        assert describer._model == "mlx-community/Custom-Model"
        assert describer._base_url == "http://localhost:9000/v1"

    def test_ollama_tag_model_is_translated_for_vllm(self) -> None:
        """qwen3-vl:8b（Ollamaタグ形式）はMLX既定モデルに読み替える。"""
        describer = create_describer("vllm-mlx", "qwen3-vl:8b")
        assert describer._model == DEFAULT_VLLM_MODEL

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            create_describer("unknown", "m")


class TestEnsureBackendAvailable:
    def test_ollama_is_never_checked(self) -> None:
        ensure_backend_available("ollama")  # 例外なし（httpx呼び出しもなし）

    def test_unreachable_vllm_raises_with_hint(self, monkeypatch) -> None:
        def fail_get(url, timeout=None):
            raise ConnectionError("refused")

        monkeypatch.setattr("httpx.get", fail_get)
        with pytest.raises(ValueError) as excinfo:
            ensure_backend_available("vllm-mlx")
        message = str(excinfo.value)
        assert "vllm-mlx serve" in message  # 起動コマンドの提示
        assert "pip install vllm-mlx" in message

    def test_reachable_vllm_passes(self, monkeypatch) -> None:
        class OkResponse:
            def raise_for_status(self): ...

        monkeypatch.setattr("httpx.get", lambda url, timeout=None: OkResponse())
        ensure_backend_available("vllm-mlx")


class TestCreateSummarizer:
    def test_ollama_backend(self) -> None:
        from screen_activity_logger.infrastructure.chat_summarizer import (
            OllamaChatSummarizer,
        )
        from screen_activity_logger.infrastructure.vlm_factory import (
            create_summarizer,
        )

        summarizer = create_summarizer("ollama", "qwen3-vl:8b")

        assert isinstance(summarizer, OllamaChatSummarizer)

    def test_vllm_backend_translates_ollama_model_name(self) -> None:
        from screen_activity_logger.infrastructure.chat_summarizer import (
            OpenAIChatSummarizer,
        )
        from screen_activity_logger.infrastructure.openai_chat_describer import (
            DEFAULT_VLLM_MODEL,
        )
        from screen_activity_logger.infrastructure.vlm_factory import (
            create_summarizer,
        )

        summarizer = create_summarizer("vllm-mlx", "qwen3-vl:8b")

        assert isinstance(summarizer, OpenAIChatSummarizer)
        assert summarizer._model == DEFAULT_VLLM_MODEL

    def test_unknown_backend_raises(self) -> None:
        import pytest

        from screen_activity_logger.infrastructure.vlm_factory import (
            create_summarizer,
        )

        with pytest.raises(ValueError):
            create_summarizer("unknown", "m")
