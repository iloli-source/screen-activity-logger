"""チャンク分割ASRの計算部（Issue #29）。

長時間音声をチャンクに割り、境界の発話切断をlead-inオーバーラップで防ぎ、
重複を帰属規則（start < チャンク開始 → 前チャンク帰属）で除去する。
純関数のみ（I/OはChunkedTranscriber側）。
"""

from __future__ import annotations

from typing import Sequence

from screen_activity_logger.domain.models import TranscriptSegment

# チャンク境界で発話が切れないよう前方に重ねて読む秒数の既定値
DEFAULT_OVERLAP_SECONDS = 10.0

# チャンク長の既定値（暫定30分。Issue #29 P4の実測で確定させる）
DEFAULT_CHUNK_SECONDS = 1800.0

ChunkSpan = tuple[float, float, float]  # (チャンク開始, media読み出し開始, media長)


def chunk_spans(
    duration_seconds: float,
    chunk_seconds: float,
    overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
) -> tuple[ChunkSpan, ...]:
    """音声全長をチャンク区間に割る。

    chunk_seconds <= 0 は無効化（全体を1スパンで返す）。
    先頭以外のチャンクは lead-in（overlap秒前から）つきでmediaを読む。
    """
    if chunk_seconds <= 0 or duration_seconds <= chunk_seconds:
        return ((0.0, 0.0, duration_seconds),)
    spans: list[ChunkSpan] = []
    start = 0.0
    while start < duration_seconds:
        media_start = max(0.0, start - overlap_seconds) if start > 0 else 0.0
        end = min(start + chunk_seconds, duration_seconds)
        spans.append((start, media_start, end - media_start))
        start = end
    return tuple(spans)


def merge_chunked_segments(
    chunked: Sequence[tuple[float, Sequence[TranscriptSegment]]],
) -> tuple[TranscriptSegment, ...]:
    """チャンク毎の絶対時刻セグメントを連結する。

    lead-in領域（start < チャンク開始）のセグメントは前チャンクで
    転写済みの重複として破棄する（帰属規則）。
    """
    merged: list[TranscriptSegment] = []
    for chunk_start, segments in chunked:
        for segment in segments:
            if segment.start.seconds < chunk_start:
                continue  # lead-in重複＝前チャンク帰属
            merged.append(segment)
    return tuple(merged)
