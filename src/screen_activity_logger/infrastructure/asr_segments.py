"""ASRバックエンド共通のセグメント正規化（純粋・依存ゼロ）。

mlx/faster両アダプタで正規化仕様（クランプ・空スキップ・メタデータ伝搬）を
共有し、バックエンド間の挙動差を構造的に排除する（Windows対応 Issue #16）。
"""

from __future__ import annotations

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp


def build_segment(
    start: float,
    end: float,
    text: str,
    no_speech_prob: float | None,
    avg_logprob: float | None,
) -> TranscriptSegment | None:
    """クランプ・空textスキップを適用してTranscriptSegmentを作る。

    実会議音声でWhisperが end < start / 負のstart を返す事象への防御
    （f9898beで発覚・修正済みの仕様）を単一箇所に集約する。
    Noneを返したら呼び出し側はスキップする。
    """
    stripped = text.strip()
    if not stripped:
        return None
    clamped_start = max(0.0, float(start))
    clamped_end = max(clamped_start, float(end))
    return TranscriptSegment(
        start=VideoTimestamp(seconds=clamped_start),
        end=VideoTimestamp(seconds=clamped_end),
        text=stripped,
        no_speech_prob=no_speech_prob,
        avg_logprob=avg_logprob,
    )
