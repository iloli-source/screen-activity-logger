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


class TestChunkedTranscriber:
    """I/O部（Issue #29 P2）: チャンク転写の統率。ffmpeg/ffprobeはフェイク。"""

    def _make(self, monkeypatch, duration, max_workers=2):
        from screen_activity_logger.infrastructure import chunked_transcriber as ct

        extracted: list[tuple[float, float]] = []
        monkeypatch.setattr(ct, "audio_duration_seconds", lambda video: duration)

        def fake_extract_span(video, wav, start, dur):
            extracted.append((start, dur))
            wav.write_bytes(b"wav")

        monkeypatch.setattr(ct, "extract_audio_wav_span", fake_extract_span)

        class FakeInner:
            def __init__(self):
                self.wav_calls = 0

            def transcribe_wav(self, wav_path):
                self.wav_calls += 1
                # 各チャンク相対時刻のセグメントを返す
                return (_seg(1.0, 2.0, f"c{self.wav_calls}"),)

            def transcribe(self, video_path):
                return (_seg(0.5, 1.0, "single"),)

        inner = FakeInner()
        transcriber = ct.ChunkedTranscriber(
            inner, chunk_seconds=1800.0, overlap_seconds=10.0,
            max_workers=max_workers,
        )
        return transcriber, inner, extracted

    def test_short_video_delegates_to_inner(self, monkeypatch, tmp_path) -> None:
        transcriber, inner, extracted = self._make(monkeypatch, duration=600.0)

        segments = transcriber.transcribe(tmp_path / "v.mp4")

        assert [s.text for s in segments] == ["single"]
        assert extracted == []  # チャンク抽出なし＝従来経路

    def test_long_video_is_chunked_and_offsets_applied(
        self, monkeypatch, tmp_path
    ) -> None:
        transcriber, inner, extracted = self._make(monkeypatch, duration=3900.0)

        segments = transcriber.transcribe(tmp_path / "v.mp4")

        assert inner.wav_calls == 3
        assert [(s, d) for s, d in extracted] == [
            (0.0, 1800.0), (1790.0, 1810.0), (3590.0, 310.0),
        ]
        # 相対1.0秒 → media_start加算で絶対時刻に（チャンク2は1791.0、3は3591.0）。
        # lead-in帰属規則: 1791.0 < 1800.0 と 3591.0 < 3600.0 は破棄される
        assert [s.start.seconds for s in segments] == [1.0]

    def test_chunk_failure_falls_back_to_empty_chunk(
        self, monkeypatch, tmp_path, capsys
    ) -> None:
        from screen_activity_logger.infrastructure import chunked_transcriber as ct

        monkeypatch.setattr(ct, "audio_duration_seconds", lambda video: 3900.0)

        def fake_extract_span(video, wav, start, dur):
            wav.write_bytes(b"wav")

        monkeypatch.setattr(ct, "extract_audio_wav_span", fake_extract_span)

        class FlakyInner:
            def __init__(self):
                self.calls = 0

            def transcribe_wav(self, wav_path):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("chunk boom")
                return (_seg(20.0, 21.0, f"c{self.calls}"),)

        transcriber = ct.ChunkedTranscriber(
            FlakyInner(), chunk_seconds=1800.0, overlap_seconds=10.0, max_workers=1
        )

        segments = transcriber.transcribe(tmp_path / "v.mp4")

        # 失敗チャンクは空として続行（他チャンクの結果は生きる）
        assert len(segments) == 2
        assert "チャンク転写失敗" in capsys.readouterr().out
