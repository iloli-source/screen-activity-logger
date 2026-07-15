"""チャンク分割ASRの純関数（Issue #29 P1: RED）。

設計: chunk_spansが (チャンク開始, media読み出し開始, media長) を返し、
転写側は media_start を加算した絶対時刻のセグメントを作る。
merge_chunked_segments は絶対時刻セグメントを受け取り、
start < チャンク開始 のもの（lead-inオーバーラップの重複）を破棄して連結する。
"""

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp
from screen_activity_logger.infrastructure.audio_chunking import (
    chunk_spans,
    merge_chunked_segments,
)


def _seg(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=end),
        text=text,
    )


class TestChunkSpans:
    def test_short_audio_is_single_span(self) -> None:
        spans = chunk_spans(600.0, chunk_seconds=1800.0, overlap_seconds=10.0)

        assert spans == ((0.0, 0.0, 600.0),)

    def test_long_audio_gets_leadin_overlap(self) -> None:
        # 3900秒を1800秒チャンクで3分割。先頭以外はlead-in 10秒つきで読む
        spans = chunk_spans(3900.0, chunk_seconds=1800.0, overlap_seconds=10.0)

        assert spans == (
            (0.0, 0.0, 1800.0),
            (1800.0, 1790.0, 1810.0),
            (3600.0, 3590.0, 310.0),  # 残り300秒＋lead-in 10秒
        )

    def test_zero_chunk_seconds_disables_chunking(self) -> None:
        spans = chunk_spans(7200.0, chunk_seconds=0.0, overlap_seconds=10.0)

        assert spans == ((0.0, 0.0, 7200.0),)

    def test_exact_multiple_has_no_empty_tail(self) -> None:
        spans = chunk_spans(3600.0, chunk_seconds=1800.0, overlap_seconds=10.0)

        assert len(spans) == 2
        assert spans[-1] == (1800.0, 1790.0, 1810.0)


class TestMergeChunkedSegments:
    def test_concatenates_in_time_order(self) -> None:
        merged = merge_chunked_segments([
            (0.0, (_seg(5.0, 8.0, "前半"),)),
            (1800.0, (_seg(1802.0, 1804.0, "後半"),)),
        ])

        assert [s.text for s in merged] == ["前半", "後半"]
        assert merged[1].start.seconds == 1802.0

    def test_leadin_duplicates_are_dropped(self) -> None:
        # 第2チャンクのlead-in領域（start < 1800）は前チャンク帰属として破棄
        merged = merge_chunked_segments([
            (0.0, (_seg(1795.0, 1799.0, "前チャンク側"),)),
            (1800.0, (
                _seg(1796.0, 1799.5, "lead-in重複"),
                _seg(1801.0, 1805.0, "本体"),
            )),
        ])

        assert [s.text for s in merged] == ["前チャンク側", "本体"]

    def test_first_chunk_keeps_everything(self) -> None:
        merged = merge_chunked_segments([
            (0.0, (_seg(0.0, 2.0, "冒頭"),)),
        ])

        assert [s.text for s in merged] == ["冒頭"]
