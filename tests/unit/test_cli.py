"""cli の組み立て（DI）のユニットテスト（Cycle I-1: RED）。"""

from pathlib import Path

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.cli import build_use_case
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
)
from screen_activity_logger.infrastructure.ollama_describer import (
    OllamaSceneDescriber,
)
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer


class TestBuildUseCase:
    def test_wires_all_adapters_with_config(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )

        assert isinstance(use_case, GenerateWorklog)
        assert isinstance(use_case.frame_extractor, FfmpegFrameExtractor)
        assert use_case.frame_extractor.fps == 0.5
        assert use_case.frame_extractor.scene_threshold == 0.08
        assert isinstance(use_case.text_recognizer, PaddleOcrRecognizer)
        assert isinstance(use_case.scene_describer, OllamaSceneDescriber)
        assert use_case.merger.ocr_match_tolerance_seconds == 2.0

    def test_wires_speech_transcriber_when_asr_model_given(
        self, tmp_path: Path
    ) -> None:
        """Cycle S: ASRモデル指定時はMlxWhisperTranscriberが配線される。"""
        from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
            MlxWhisperTranscriber,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            asr_model="kaiinui/kotoba-whisper-v2.0-mlx",
        )
        assert isinstance(use_case.speech_transcriber, MlxWhisperTranscriber)

    def test_asr_disabled_when_model_is_none(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            asr_model=None,
        )
        assert use_case.speech_transcriber is None

    def test_meeting_mode_enables_vlm_gate(self, tmp_path: Path) -> None:
        """Z3: --mode meetingでVLMゲートが既定値で有効化される。"""
        from screen_activity_logger.domain.vlm_gate import VlmGateConfig

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            vlm_gate=VlmGateConfig(jaccard_skip_threshold=0.9),
        )
        assert use_case.vlm_gate is not None
        assert use_case.vlm_gate.jaccard_skip_threshold == 0.9

    def test_default_has_no_vlm_gate(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert use_case.vlm_gate is None

    def test_meeting_mode_wires_ocr_keyframes_only(self, tmp_path: Path) -> None:
        """Cycle W: --mode meeting はOCRをキーフレームのみに限定する。"""
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            ocr_keyframes_only=True,
        )
        assert use_case.ocr_keyframes_only is True

    def test_default_mode_keeps_full_ocr(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert use_case.ocr_keyframes_only is False

    def test_wires_faster_backend(self, tmp_path: Path) -> None:
        """W6: asr_backend=fasterでFasterWhisperTranscriberが配線される（#16）。"""
        from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
            FasterWhisperTranscriber,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            asr_model="kotoba-tech/kotoba-whisper-v2.0-faster",
            asr_backend="faster",
        )
        assert isinstance(use_case.speech_transcriber, FasterWhisperTranscriber)

    def test_default_backend_is_mlx(self, tmp_path: Path) -> None:
        """後方互換: asr_backend未指定は従来どおりmlx配線。"""
        from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
            MlxWhisperTranscriber,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            asr_model="kaiinui/kotoba-whisper-v2.0-mlx",
        )
        assert isinstance(use_case.speech_transcriber, MlxWhisperTranscriber)

    def test_wires_vlm_timeout(self, tmp_path: Path) -> None:
        """H7（Issue #15）: --vlm-timeoutがdescriberに配線される。"""
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            vlm_timeout_seconds=450.0,
        )
        assert use_case.scene_describer._timeout_seconds == 450.0

    def test_default_vlm_timeout_is_300(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert use_case.scene_describer._timeout_seconds == 300.0

    def test_wires_speech_filter(self, tmp_path: Path) -> None:
        """F4: ASR幻覚フィルタが配線される（Issue #14）。"""
        from screen_activity_logger.domain.speech_filter import SpeechFilterConfig

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            speech_filter=SpeechFilterConfig(no_speech_threshold=0.7),
        )
        assert use_case.speech_filter is not None
        assert use_case.speech_filter.no_speech_threshold == 0.7

    def test_default_has_no_speech_filter(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert use_case.speech_filter is None

    def test_wires_frame_comparator_and_ocr_tier(self, tmp_path: Path) -> None:
        """Cycle M: 差分スキップとOCR tierがCLIから設定できる。"""
        from screen_activity_logger.infrastructure.frame_comparator import (
            PilFrameComparator,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            ocr_tier="tiny",
            diff_threshold=0.05,
        )

        assert isinstance(use_case.frame_comparator, PilFrameComparator)
        assert use_case.frame_comparator.threshold == 0.05
        kwargs = use_case.text_recognizer._engine_kwargs()
        assert kwargs["text_detection_model_name"] == "PP-OCRv6_tiny_det"


class TestSpeakerAttributionWiring:
    """S6（Issue #10）: 話者特定のCLI配線。"""

    def test_wires_speaker_attribution(self, tmp_path: Path) -> None:
        from screen_activity_logger.domain.speaker_attribution import (
            SpeakerAttributionConfig,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            speaker_attribution=SpeakerAttributionConfig(
                switch_tolerance_seconds=5.0
            ),
        )
        assert use_case.speaker_attribution is not None
        assert use_case.speaker_attribution.switch_tolerance_seconds == 5.0

    def test_default_has_no_speaker_attribution(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert use_case.speaker_attribution is None


class TestVlmBackendWiring:
    """M4（Issue #21）: VLMバックエンドのCLI配線。"""

    def test_wires_vllm_mlx_backend(self, tmp_path: Path) -> None:
        from screen_activity_logger.infrastructure.openai_chat_describer import (
            OpenAIChatSceneDescriber,
        )

        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
            vlm_backend="vllm-mlx",
            vlm_url="http://localhost:9000/v1",
        )
        assert isinstance(use_case.scene_describer, OpenAIChatSceneDescriber)
        assert use_case.scene_describer._base_url == "http://localhost:9000/v1"

    def test_default_backend_is_ollama(self, tmp_path: Path) -> None:
        use_case = build_use_case(
            fps=0.5,
            scene_threshold=0.08,
            model="qwen3-vl:8b",
            ocr_tolerance_seconds=2.0,
            workdir=tmp_path,
        )
        assert isinstance(use_case.scene_describer, OllamaSceneDescriber)
