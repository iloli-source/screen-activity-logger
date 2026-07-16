"""チャンク分割ASRの計算部（Issue #29）。

長時間音声をチャンクに割り、境界の発話切断を両側オーバーラップで防ぎ、
重複を帰属規則（chunk_start <= start < chunk_end のみ採用）で除去する。
純関数のみ（I/OはChunkedTranscriber側）。

E2E実測（2026-07-17）: lead-inのみの旧実装は境界をまたぐ発話が
前チャンクで尻切れ・次チャンクで破棄され、境界毎に約80〜160字欠落した。
lead-out（後方オーバーラップ）を追加し、またぐ発話は前チャンクが
完全版を転写する設計に修正。
"""

from __future__ import annotations

from typing import Sequence

from screen_activity_logger.domain.models import TranscriptSegment

# チャンク境界で発話が切れないよう両側に重ねて読む秒数の既定値。
# 実測（2h実会議）: 10秒では境界lapに10〜15%の欠落が残り、30秒で
# 旧（非分割）比103%まで回復（境界をまたぐ長い発話も完全転写）
DEFAULT_OVERLAP_SECONDS = 30.0

# チャンク長の既定値（30分。実測で速度は10〜60分で同等のため、
# 頑健性（再開単位・有界メモリ）と境界数のバランスで選定。Issue #29 P4）
DEFAULT_CHUNK_SECONDS = 1800.0

# (チャンク開始, チャンク終了, media読み出し開始, media長)
ChunkSpan = tuple[float, float, float, float]


def chunk_spans(
    duration_seconds: float,
    chunk_seconds: float,
    overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
) -> tuple[ChunkSpan, ...]:
    """音声全長をチャンク区間に割る。

    chunk_seconds <= 0 は無効化（全体を1スパンで返す）。
    mediaは前後overlap秒を重ねて読む（先頭はlead-inなし、末尾はlead-outなし）。
    """
    if chunk_seconds <= 0 or duration_seconds <= chunk_seconds:
        return ((0.0, duration_seconds, 0.0, duration_seconds),)
    spans: list[ChunkSpan] = []
    start = 0.0
    while start < duration_seconds:
        end = min(start + chunk_seconds, duration_seconds)
        media_start = max(0.0, start - overlap_seconds) if start > 0 else 0.0
        media_end = min(duration_seconds, end + overlap_seconds)
        spans.append((start, end, media_start, media_end - media_start))
        start = end
    return tuple(spans)


def merge_chunked_segments(
    chunked: Sequence[tuple[float, float, Sequence[TranscriptSegment]]],
) -> tuple[TranscriptSegment, ...]:
    """チャンク毎の絶対時刻セグメントを連結する。

    帰属規則: chunk_start <= start < chunk_end のセグメントのみ採用。
    lead-in領域（start < chunk_start）は前チャンクが完全版を持ち、
    lead-out領域（start >= chunk_end）は次チャンクが本体として持つ。
    """
    merged: list[TranscriptSegment] = []
    for chunk_start, chunk_end, segments in chunked:
        for segment in segments:
            if not chunk_start <= segment.start.seconds < chunk_end:
                continue
            merged.append(segment)
    return tuple(merged)
