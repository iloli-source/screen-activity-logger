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
from screen_activity_logger.domain.speaker_attribution import (
    SpeakerAttributionConfig,
)
from screen_activity_logger.domain.speech_filter import SpeechFilterConfig
from screen_activity_logger.domain.vlm_gate import VlmGateConfig
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
    has_audio_stream,
)
from screen_activity_logger.infrastructure.frame_comparator import (
    PilFrameComparator,
)
from screen_activity_logger.infrastructure.asr_factory import (
    create_transcriber,
    default_model_for,
    ensure_backend_available,
    resolve_backend,
)
from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    DEFAULT_FASTER_ASR_MODEL,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    DEFAULT_ASR_MODEL,
)
from screen_activity_logger.infrastructure.ollama_describer import (
    DEFAULT_TIMEOUT_SECONDS,
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
    vlm_gate: VlmGateConfig | None = None,
    speech_filter: SpeechFilterConfig | None = None,
    asr_backend: str = "mlx",
    vlm_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    speaker_attribution: SpeakerAttributionConfig | None = None,
) -> GenerateWorklog:
    """設定値から全アダプタを組み立てたユースケースを返す。

    asr_model: Noneなら音声認識を無効化する。
    ocr_keyframes_only: 会議モード（OCRをキーフレームに限定）。
    vlm_gate: VLM間引きゲート（Noneで無効＝screencast既定）。
    speech_filter: ASR幻覚フィルタ（Noneで無効。CLI経由では既定ON）。
    asr_backend: 解決済みバックエンド（mlx/faster。既定mlx＝後方互換）。
    """
    return GenerateWorklog(
        frame_extractor=FfmpegFrameExtractor(
            fps=fps, scene_threshold=scene_threshold, workdir=workdir
        ),
        text_recognizer=PaddleOcrRecognizer(tier=ocr_tier),
        scene_describer=OllamaSceneDescriber(
            model=model, timeout_seconds=vlm_timeout_seconds
        ),
        merger=TimelineMerger(ocr_match_tolerance_seconds=ocr_tolerance_seconds),
        frame_comparator=PilFrameComparator(threshold=diff_threshold),
        speech_transcriber=(
            create_transcriber(asr_backend, asr_model) if asr_model else None
        ),
        ocr_keyframes_only=ocr_keyframes_only,
        vlm_gate=vlm_gate,
        speech_filter=speech_filter,
        speaker_attribution=speaker_attribution,
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
        "--asr-backend", choices=["auto", "mlx", "faster"], default="auto",
        help="ASRバックエンド（auto: Apple Silicon→mlx / それ以外→faster、既定: auto）",
    )
    parser.add_argument(
        "--asr-model", default=None,
        help="音声認識モデル（未指定時はバックエンド既定: "
        f"mlx={DEFAULT_ASR_MODEL} / faster={DEFAULT_FASTER_ASR_MODEL}）",
    )
    parser.add_argument(
        "--no-asr", action="store_true", help="音声認識を無効化する"
    )
    parser.add_argument(
        "--mode", choices=["screencast", "meeting"], default="screencast",
        help="meeting: OCRをキーフレーム限定＋VLMゲート有効（会議動画向け、既定: screencast）",
    )
    parser.add_argument(
        "--vlm-skip-threshold", type=float, default=0.85,
        help="VLMスキップのJaccard閾値（meetingモード時のみ有効、既定: 0.85）",
    )
    parser.add_argument(
        "--vlm-min-gap", type=float, default=10.0,
        help="VLM呼び出しの最小間隔秒（debounce、既定: 10）",
    )
    parser.add_argument(
        "--vlm-max-gap", type=float, default=120.0,
        help="VLM強制実行の最大間隔秒（安全弁、既定: 120）",
    )
    parser.add_argument(
        "--vlm-timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
        help="VLM呼び出しの試行毎タイムアウト秒（タイムアウト時は1回リトライ、既定: 300）",
    )
    parser.add_argument(
        "--speaker-attribution", action="store_true",
        help="映像ベース話者特定を有効化する（実験的。話者ビュー追従の録画のみ有効、"
        "ギャラリー/固定タイル録画では誤帰属リスクあり。meetingモード専用）",
    )
    parser.add_argument(
        "--speaker-switch-tolerance", type=float, default=3.0,
        help="話者ビュー切替と発話開始のズレ許容秒（既定: 3.0）",
    )
    parser.add_argument(
        "--asr-no-speech-prob", type=float, default=0.6,
        help="幻覚フィルタ: no_speech_probがこれを超えると除去候補（既定: 0.6）",
    )
    parser.add_argument(
        "--asr-avg-logprob", type=float, default=-1.0,
        help="幻覚フィルタ: avg_logprobがこれ未満なら除去候補（既定: -1.0）",
    )
    parser.add_argument(
        "--no-asr-filter", action="store_true",
        help="ASR幻覚フィルタを無効化する（デバッグ用）",
    )
    args = parser.parse_args(argv)

    for video in args.videos:
        if not video.exists():
            parser.error(f"動画が見つかりません: {video}")

    asr_backend = resolve_backend(args.asr_backend)
    if not args.no_asr:
        try:
            ensure_backend_available(asr_backend)
        except ValueError as exc:
            parser.error(str(exc))
    asr_model: str | None = (
        None if args.no_asr else (args.asr_model or default_model_for(asr_backend))
    )
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
            asr_backend=asr_backend,
            vlm_timeout_seconds=args.vlm_timeout,
            ocr_keyframes_only=(args.mode == "meeting"),
            # 実測（Issue #10）でボット録画はタイル固定が多く前提が崩れるため
            # 既定OFFのオプトイン（話者ビュー追従録画でのみ有効な実験的機能）
            speaker_attribution=(
                SpeakerAttributionConfig(
                    switch_tolerance_seconds=args.speaker_switch_tolerance
                )
                if args.mode == "meeting" and args.speaker_attribution
                else None
            ),
            vlm_gate=(
                VlmGateConfig(
                    jaccard_skip_threshold=args.vlm_skip_threshold,
                    min_gap_seconds=args.vlm_min_gap,
                    max_gap_seconds=args.vlm_max_gap,
                )
                if args.mode == "meeting"
                else None
            ),
            # 幻覚は両モードで起きるため既定ON（screencastのナレーションでも発生）
            speech_filter=(
                None
                if args.no_asr_filter
                else SpeechFilterConfig(
                    no_speech_threshold=args.asr_no_speech_prob,
                    logprob_threshold=args.asr_avg_logprob,
                )
            ),
        )
        if len(args.videos) == 1:
            _run_single(use_case, args.videos[0], args.output_dir)
        else:
            _run_batch(
                use_case, args.videos, args.output_dir, asr_model, asr_backend
            )
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
    asr_backend: str = "mlx",
) -> None:
    if asr_model is None:
        # ASRなしでも2フェーズ構造は維持（Phase Aが空になるだけ）
        transcriber = _NullTranscriber()
    else:
        transcriber = create_transcriber(asr_backend, asr_model)
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
