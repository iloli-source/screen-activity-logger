"""CLIエントリポイント。アダプタのDI組み立てと実行を担う。"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.domain.services import TimelineMerger
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
)
from screen_activity_logger.infrastructure.frame_comparator import (
    PilFrameComparator,
)
from screen_activity_logger.infrastructure.ollama_describer import (
    OllamaSceneDescriber,
)
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer
from screen_activity_logger.infrastructure.writers import (
    JsonlWorklogWriter,
    MarkdownWorklogWriter,
)

DEFAULT_MODEL = "qwen3-vl:8b"
DEFAULT_FPS = 0.5
DEFAULT_SCENE_THRESHOLD = 0.08
DEFAULT_OCR_TOLERANCE_SECONDS = 2.0
DEFAULT_OCR_TIER = "small"
DEFAULT_DIFF_THRESHOLD = 0.02


def build_use_case(
    fps: float,
    scene_threshold: float,
    model: str,
    ocr_tolerance_seconds: float,
    workdir: Path,
    ocr_tier: str = DEFAULT_OCR_TIER,
    diff_threshold: float = DEFAULT_DIFF_THRESHOLD,
) -> GenerateWorklog:
    """設定値から全アダプタを組み立てたユースケースを返す。"""
    return GenerateWorklog(
        frame_extractor=FfmpegFrameExtractor(
            fps=fps, scene_threshold=scene_threshold, workdir=workdir
        ),
        text_recognizer=PaddleOcrRecognizer(tier=ocr_tier),
        scene_describer=OllamaSceneDescriber(model=model),
        merger=TimelineMerger(ocr_match_tolerance_seconds=ocr_tolerance_seconds),
        frame_comparator=PilFrameComparator(threshold=diff_threshold),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screen-activity-logger",
        description="画面録画動画をローカルでOCR+VLM解析し、日本語の作業ログを生成する",
    )
    parser.add_argument("video", type=Path, help="入力動画（mp4等）")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("."),
        help="worklog.md / worklog.jsonl の出力先（既定: カレント）",
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument(
        "--scene-threshold", type=float, default=DEFAULT_SCENE_THRESHOLD
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--ocr-tolerance", type=float, default=DEFAULT_OCR_TOLERANCE_SECONDS
    )
    parser.add_argument(
        "--ocr-tier", choices=["tiny", "small", "medium"], default=DEFAULT_OCR_TIER,
        help="OCRモデルの規模（tiny=最速/medium=最高精度、既定: small）",
    )
    parser.add_argument(
        "--diff-threshold", type=float, default=DEFAULT_DIFF_THRESHOLD,
        help="OCRスキップの画面差分閾値（0.0〜1.0、既定: 0.02）",
    )
    args = parser.parse_args(argv)

    if not args.video.exists():
        parser.error(f"動画が見つかりません: {args.video}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sal-frames-") as tmp:
        use_case = build_use_case(
            fps=args.fps,
            scene_threshold=args.scene_threshold,
            model=args.model,
            ocr_tolerance_seconds=args.ocr_tolerance,
            workdir=Path(tmp),
            ocr_tier=args.ocr_tier,
            diff_threshold=args.diff_threshold,
        )
        worklog = use_case.execute(args.video)

    md_path = args.output_dir / "worklog.md"
    jsonl_path = args.output_dir / "worklog.jsonl"
    MarkdownWorklogWriter().write(worklog, md_path)
    JsonlWorklogWriter().write(worklog, jsonl_path)

    print(f"エントリ数: {len(worklog.entries)}")
    print(f"出力: {md_path}")
    print(f"出力: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
