"""ASRバックエンド解決とファクトリのユニットテスト（W5: RED）。"""

import pytest

from screen_activity_logger.infrastructure.asr_factory import (
    create_transcriber,
    default_model_for,
    ensure_backend_available,
    resolve_backend,
)
from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    DEFAULT_FASTER_ASR_MODEL,
    FasterWhisperTranscriber,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    DEFAULT_ASR_MODEL,
    MlxWhisperTranscriber,
)


class TestResolveBackend:
    @pytest.mark.parametrize(
        ("system", "machine", "expected"),
        [
            ("Darwin", "arm64", "mlx"),      # Apple Silicon
            ("Darwin", "x86_64", "faster"),  # Intel Mac（MLX不可）
            ("Windows", "AMD64", "faster"),
            ("Linux", "x86_64", "faster"),
        ],
    )
    def test_auto_resolves_by_platform(
        self, system: str, machine: str, expected: str
    ) -> None:
        assert resolve_backend("auto", system=system, machine=machine) == expected

    def test_explicit_backend_passes_through(self) -> None:
        # 明示指定はプラットフォームに関係なくそのまま（MacでfasterのWz検証用）
        assert resolve_backend("faster", system="Darwin", machine="arm64") == "faster"
        assert resolve_backend("mlx", system="Windows", machine="AMD64") == "mlx"


class TestDefaultModelFor:
    def test_backend_specific_defaults(self) -> None:
        assert default_model_for("mlx") == DEFAULT_ASR_MODEL
        assert default_model_for("faster") == DEFAULT_FASTER_ASR_MODEL

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            default_model_for("unknown")


class TestEnsureBackendAvailable:
    def test_available_backend_passes(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "importlib.util.find_spec", lambda name: object()
        )
        ensure_backend_available("faster")  # 例外が出ないこと

    def test_missing_backend_raises_with_install_hint(self, monkeypatch) -> None:
        monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
        with pytest.raises(ValueError) as excinfo:
            ensure_backend_available("faster")
        message = str(excinfo.value)
        assert "asr-faster" in message  # 導入コマンドの提示
        assert "--no-asr" in message   # 回避手段の提示


class TestCreateTranscriber:
    def test_creates_mlx_transcriber(self) -> None:
        transcriber = create_transcriber("mlx", "some/model")
        assert isinstance(transcriber, MlxWhisperTranscriber)

    def test_creates_faster_transcriber(self) -> None:
        transcriber = create_transcriber("faster", "some/model")
        assert isinstance(transcriber, FasterWhisperTranscriber)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            create_transcriber("unknown", "m")
