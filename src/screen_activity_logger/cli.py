"""CLIエントリポイント。アダプタのDI組み立てと実行を担う。"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from screen_activity_logger.application.use_cases import (
    BatchGenerateWorklog,
    GenerateWorklog,
)
from screen_activity_logger.domain.services import TimelineMerger
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
    has_audio_stream,
)
from screen_activity_logger.infrastructure.frame_comparator import (
    PilFrameComparator,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    DEFAULT_ASR_MODEL,
    MlxWhisperTranscriber,
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
    asr_model: str | None = None,
    ocr_keyframes_only: bool = False,
) -> GenerateWorklog:
    """設定値から全アダプタを組み立てたユースケースを返す。

    asr_model: Noneなら音声認識を無効化する。
    ocr_keyframes_only: 会議モード（OCRをキーフレームに限定）。
    """
    return GenerateWorklog(
        frame_extractor=FfmpegFrameExtractor(
            fps=fps, scene_threshold=scene_threshold, workdir=workdir
        ),
        text_recognizer=PaddleOcrRecognizer(tier=ocr_tier),
        scene_describer=OllamaSceneDescriber(model=model),
        merger=TimelineMerger(ocr_match_tolerance_seconds=ocr_tolerance_seconds),
        frame_comparator=PilFrameComparator(threshold=diff_threshold),
        speech_transcriber=(
            MlxWhisperTranscriber(model=asr_model) if asr_model else None
        ),
        ocr_keyframes_only=ocr_keyframes_only,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screen-activity-logger",
        description="画面録画動画をローカルでOCR+VLM解析し、日本語の作業ログを生成する",
    )
    parser.add_argument(
        "videos", type=Path, nargs="+", metavar="video",
        help="入力動画（複数指定でバッチ2フェーズ処理: 全動画ASR→各動画OCR/VLM）",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("."),
        help="出力先（単一動画: 直下 / 複数動画: <動画名>/ サブディレクトリ）",
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
    parser.add_argument(
        "--asr-model", default=DEFAULT_ASR_MODEL,
        help=f"音声認識モデル（MLX形式のHFリポジトリ、既定: {DEFAULT_ASR_MODEL}）",
    )
    parser.add_argument(
        "--no-asr", action="store_true", help="音声認識を無効化する"
    )
    parser.add_argument(
        "--mode", choices=["screencast", "meeting"], default="screencast",
        help="meeting: OCRをキーフレームのみに限定（会議動画向け、既定: screencast）",
    )
    args = parser.parse_args(argv)

    for video in args.videos:
        if not video.exists():
            parser.error(f"動画が見つかりません: {video}")

    asr_model: str | None = None if args.no_asr else args.asr_model
    if asr_model and not all(has_audio_stream(v) for v in args.videos):
        print("音声トラックのない動画あり → 音声認識をスキップします")
        asr_model = None

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
            asr_model=asr_model,
            ocr_keyframes_only=(args.mode == "meeting"),
        )
        if len(args.videos) == 1:
            _run_single(use_case, args.videos[0], args.output_dir)
        else:
            _run_batch(use_case, args.videos, args.output_dir, asr_model)
    return 0


def _run_single(
    use_case: GenerateWorklog, video: Path, output_dir: Path
) -> None:
    worklog = use_case.execute(video)
    md_path = output_dir / "worklog.md"
    jsonl_path = output_dir / "worklog.jsonl"
    MarkdownWorklogWriter().write(worklog, md_path)
    JsonlWorklogWriter().write(worklog, jsonl_path)
    print(f"エントリ数: {len(worklog.entries)}")
    print(f"出力: {md_path}")
    print(f"出力: {jsonl_path}")


def _run_batch(
    use_case: GenerateWorklog,
    videos: list[Path],
    output_dir: Path,
    asr_model: str | None,
) -> None:
    if asr_model is None:
        # ASRなしでも2フェーズ構造は維持（Phase Aが空になるだけ）
        transcriber = _NullTranscriber()
    else:
        transcriber = MlxWhisperTranscriber(model=asr_model)
    batch = BatchGenerateWorklog(
        transcriber=transcriber,
        use_case=use_case,
        writers=[
            (MarkdownWorklogWriter(), "worklog.md"),
            (JsonlWorklogWriter(), "worklog.jsonl"),
        ],
    )
    results = batch.execute(videos, output_dir=output_dir)
    for video, worklog in results:
        print(f"{video.stem}: エントリ{len(worklog.entries)}件 → {output_dir / video.stem}/")


class _NullTranscriber:
    """ASR無効時の空実装。"""

    def transcribe(self, video_path: Path) -> tuple:
        return ()


if __name__ == "__main__":
    raise SystemExit(main())
