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
