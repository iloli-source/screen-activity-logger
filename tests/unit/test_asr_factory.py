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
from screen_activity_logger.infrastructure.whisper_cpp_transcriber import (
    DEFAULT_CPP_ASR_MODEL_PATH,
    WhisperCppTranscriber,
)


class TestResolveBackend:
    @pytest.mark.parametrize(
        ("system", "machine", "cpp_available", "expected"),
        [
            # Apple Silicon: whisper.cpp利用可ならcpp（Issue #22。
            # mlxは長時間入力で品質崩壊のためautoから除外）
            ("Darwin", "arm64", True, "cpp"),
            ("Darwin", "arm64", False, "faster"),  # 未導入時は遅いが正しいfaster
            ("Darwin", "x86_64", True, "faster"),  # Intel Mac（Metal MLX前提なし）
            ("Windows", "AMD64", True, "faster"),
            ("Linux", "x86_64", True, "faster"),
        ],
    )
    def test_auto_resolves_by_platform(
        self, system: str, machine: str, cpp_available: bool, expected: str
    ) -> None:
        resolved = resolve_backend(
            "auto", system=system, machine=machine, cpp_available=cpp_available
        )
        assert resolved == expected

    def test_explicit_backend_passes_through(self) -> None:
        # 明示指定はプラットフォームに関係なくそのまま（MacでfasterのWz検証用）
        assert resolve_backend("faster", system="Darwin", machine="arm64") == "faster"
        assert resolve_backend("mlx", system="Windows", machine="AMD64") == "mlx"
        assert resolve_backend("cpp", system="Linux", machine="x86_64") == "cpp"


class TestDefaultModelFor:
    def test_backend_specific_defaults(self) -> None:
        assert default_model_for("mlx") == DEFAULT_ASR_MODEL
        assert default_model_for("faster") == DEFAULT_FASTER_ASR_MODEL
        assert default_model_for("cpp") == str(DEFAULT_CPP_ASR_MODEL_PATH)

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

    def test_cpp_passes_when_binary_and_model_exist(
        self, monkeypatch, tmp_path
    ) -> None:
        model = tmp_path / "model.bin"
        model.write_bytes(b"fake")
        monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/x")
        ensure_backend_available("cpp", cpp_model_path=model)  # 例外が出ないこと

    def test_cpp_missing_binary_raises_with_brew_hint(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(ValueError) as excinfo:
            ensure_backend_available("cpp", cpp_model_path=tmp_path / "m.bin")
        message = str(excinfo.value)
        assert "brew install whisper-cpp" in message
        assert "--no-asr" in message

    def test_cpp_missing_model_raises_with_path(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/x")
        missing = tmp_path / "missing.bin"
        with pytest.raises(ValueError) as excinfo:
            ensure_backend_available("cpp", cpp_model_path=missing)
        assert str(missing) in str(excinfo.value)


class TestCreateTranscriber:
    def test_wraps_in_chunked_transcriber_by_default(self) -> None:
        from screen_activity_logger.infrastructure.chunked_transcriber import (
            ChunkedTranscriber,
        )

        transcriber = create_transcriber("faster", "some/model")

        assert isinstance(transcriber, ChunkedTranscriber)
        assert isinstance(transcriber._inner, FasterWhisperTranscriber)

    def test_chunking_disabled_returns_raw_adapter(self, tmp_path) -> None:
        assert isinstance(
            create_transcriber("mlx", "some/model", chunk_seconds=0),
            MlxWhisperTranscriber,
        )
        assert isinstance(
            create_transcriber("cpp", str(tmp_path / "m.bin"), chunk_seconds=0),
            WhisperCppTranscriber,
        )

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            create_transcriber("unknown", "m")


class TestDefaultAsrWorkers:
    def test_gpu_backends_are_serial(self) -> None:
        from screen_activity_logger.infrastructure.asr_factory import (
            default_asr_workers,
        )

        assert default_asr_workers("cpp", cpu_count=10) == 1
        assert default_asr_workers("mlx", cpu_count=10) == 1

    def test_faster_scales_with_cores_capped_at_4(self) -> None:
        from screen_activity_logger.infrastructure.asr_factory import (
            default_asr_workers,
        )

        assert default_asr_workers("faster", cpu_count=4) == 2
        assert default_asr_workers("faster", cpu_count=16) == 4
        assert default_asr_workers("faster", cpu_count=1) == 1


class TestSilenceAwareTranscriber:
    """4AIレビューR1: バッチ中1本の無音動画が全動画のASRを無効化するバグの回帰。"""

    class _Inner:
        def __init__(self) -> None:
            self.calls: list = []

        def transcribe(self, video_path):
            self.calls.append(video_path)
            return ("seg",)

    def test_transcribes_video_with_audio(self, tmp_path) -> None:
        from screen_activity_logger.infrastructure.asr_factory import (
            SilenceAwareTranscriber,
        )

        inner = self._Inner()
        transcriber = SilenceAwareTranscriber(inner, has_audio=lambda p: True)

        result = transcriber.transcribe(tmp_path / "a.mp4")

        assert result == ("seg",)
        assert len(inner.calls) == 1

    def test_skips_silent_video_without_calling_inner(self, tmp_path) -> None:
        from screen_activity_logger.infrastructure.asr_factory import (
            SilenceAwareTranscriber,
        )

        inner = self._Inner()
        transcriber = SilenceAwareTranscriber(inner, has_audio=lambda p: False)

        result = transcriber.transcribe(tmp_path / "silent.mp4")

        assert result == ()
        assert inner.calls == []  # 無音動画はASR本体を呼ばない（他動画に影響しない）
