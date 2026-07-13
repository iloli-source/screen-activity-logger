"""映像ベース話者特定の実データ検証（Issue #10 S7、VLM不要）。

会議クリップを ffmpeg + PaddleOCR(keyframesのみ) + mlx whisper で処理して
話者帰属を実行し、Circleback公式トランスクリプト（話者名付き、
/tmp/sal-circleback/transcripts/<clip>.json）と照合する。

整列は時刻ベース（初回検証でクリップ＝会議冒頭からの切り出しと判明。
公式はかな分かち書き・SALは漢字のためテキスト類似は機能しない）。
SALセグメント開始時刻に最も近い公式セグメント（±5秒以内）と照合し、
話者比較は姓（先頭2字）の一致＋空白正規化。

使い方:
    python scripts/validate_speaker_attribution.py <clip.mp4> <transcript.json>
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from screen_activity_logger.domain.models import (
    TranscriptSegment,
    VideoTimestamp,
)
from screen_activity_logger.domain.speech_filter import (
    SpeechFilterConfig,
    filter_segments,
)
from screen_activity_logger.domain.speaker_attribution import (
    SpeakerAttributionConfig,
    SpeakerObservation,
    attribute_speakers,
    extract_name_labels,
)
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    MlxWhisperTranscriber,
)
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer

_MAX_TIME_GAP_SECONDS = 5.0


def _normalize(text: str) -> str:
    return "".join(text.split())


def _speakers_match(attributed: str, official: str) -> bool:
    a = _normalize(attributed)
    o = _normalize(official).split("（")[0]  # 読み仮名括弧を除去
    if a in o or o in a:
        return True
    return a[:2] == o[:2]  # 姓一致（OCR誤読「花田恰」vs公式「花田怜」を救う）


def _compute_or_load(clip_path: Path):
    """OCR観測とASRセグメントを計算（キャッシュがあれば再利用）。"""
    cache = Path(f"/tmp/sal-issue10-cache-{clip_path.stem}.json")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        observations = [
            SpeakerObservation(
                timestamp=VideoTimestamp(seconds=o["t"]),
                names=tuple(o["names"]),
                ocr_line_count=o["lines"],
            )
            for o in data["observations"]
        ]
        segments = [
            TranscriptSegment(
                start=VideoTimestamp(seconds=s["start"]),
                end=VideoTimestamp(seconds=s["end"]),
                text=s["text"],
            )
            for s in data["segments"]
        ]
        return observations, segments
    observations, segments = _compute(clip_path)
    cache.write_text(json.dumps({
        "observations": [
            {"t": o.timestamp.seconds, "names": list(o.names), "lines": o.ocr_line_count}
            for o in observations
        ],
        "segments": [
            {"start": s.start.seconds, "end": s.end.seconds, "text": s.text}
            for s in segments
        ],
    }, ensure_ascii=False), encoding="utf-8")
    return observations, segments


def _compute(clip_path: Path):
    with tempfile.TemporaryDirectory(prefix="sal-verify-") as tmp:
        frames = FfmpegFrameExtractor(
            fps=0.5, scene_threshold=0.08, workdir=Path(tmp)
        ).extract(clip_path)
        recognizer = PaddleOcrRecognizer(tier="small")
        observations = []
        for frame in frames:
            if not frame.is_keyframe:
                continue
            lines = recognizer.recognize(frame).normalized_lines()
            observations.append(
                SpeakerObservation(
                    timestamp=frame.timestamp,
                    names=extract_name_labels(lines),
                    ocr_line_count=len(lines),
                )
            )
        segments = MlxWhisperTranscriber().transcribe(clip_path)
    return observations, list(segments)


def main(clip_path: Path, transcript_path: Path) -> int:
    official = json.loads(transcript_path.read_text(encoding="utf-8"))["transcript"]
    observations, segments = _compute_or_load(clip_path)
    # 実パイプラインと同じ前処理: 幻覚フィルタを帰属の前に適用（Issue #14）
    segments = list(filter_segments(segments, SpeechFilterConfig()))

    attributed = attribute_speakers(
        segments, observations, SpeakerAttributionConfig()
    )

    total = len(attributed)
    with_speaker = [seg for seg in attributed if seg.speaker]
    matched = 0
    mismatches: list[str] = []
    unaligned = 0
    ordered_official = sorted(official, key=lambda e: e["timestamp"])
    for segment in with_speaker:
        best_official = None
        for index, entry in enumerate(ordered_official):
            next_ts = (
                ordered_official[index + 1]["timestamp"]
                if index + 1 < len(ordered_official)
                else float("inf")
            )
            if entry["timestamp"] - 2.0 <= segment.start.seconds < next_ts:
                best_official = entry  # 区間被覆（開始2秒の食い込み許容）
        if best_official is None:
            unaligned += 1
            continue
        if _speakers_match(segment.speaker, best_official["speaker"]):
            matched += 1
        else:
            mismatches.append(
                f"  [{segment.start}] 帰属={segment.speaker} / "
                f"公式={best_official['speaker']} / 「{segment.text[:30]}」"
            )

    evaluable = len(with_speaker) - unaligned
    precision = matched / evaluable if evaluable else 0.0
    print(f"クリップ: {clip_path.name}")
    print(f"  セグメント: {total} / 帰属: {len(with_speaker)}"
          f"（カバレッジ {len(with_speaker)/total:.0%}）")
    print(f"  整列可能: {evaluable} / 話者一致: {matched}"
          f" / precision: {precision:.0%}")
    if mismatches:
        print("  不一致:")
        print("\n".join(mismatches))
    if unaligned:
        print(f"  整列不能: {unaligned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
