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


def build_use_case(
    fps: float,
    scene_threshold: float,
    model: str,
    ocr_tolerance_seconds: float,
    workdir: Path,
) -> GenerateWorklog:
    """設定値から全アダプタを組み立てたユースケースを返す。"""
    return GenerateWorklog(
        frame_extractor=FfmpegFrameExtractor(
            fps=fps, scene_threshold=scene_threshold, workdir=workdir
        ),
        text_recognizer=PaddleOcrRecognizer(),
        scene_describer=OllamaSceneDescriber(model=model),
        merger=TimelineMerger(ocr_match_tolerance_seconds=ocr_tolerance_seconds),
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
