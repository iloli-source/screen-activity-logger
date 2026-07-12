"""ASRバックエンド共通のセグメント正規化のユニットテスト（W2: RED）。"""

from screen_activity_logger.infrastructure.asr_segments import build_segment


class TestBuildSegment:
    def test_builds_segment_with_metadata(self) -> None:
        segment = build_segment(
            start=1.0, end=2.5, text=" こんにちは ",
            no_speech_prob=0.3, avg_logprob=-0.5,
        )
        assert segment is not None
        assert segment.start.seconds == 1.0
        assert segment.end.seconds == 2.5
        assert segment.text == "こんにちは"  # 前後空白は除去
        assert segment.no_speech_prob == 0.3
        assert segment.avg_logprob == -0.5

    def test_empty_text_returns_none(self) -> None:
        assert build_segment(0.0, 1.0, "   ", None, None) is None

    def test_clamps_negative_start_to_zero(self) -> None:
        segment = build_segment(-0.3, 1.0, "冒頭", None, None)
        assert segment is not None
        assert segment.start.seconds == 0.0

    def test_clamps_end_before_start(self) -> None:
        """実会議音声で発生: Whisperがend<startを返す（f9898beで発覚）。"""
        segment = build_segment(5.0, 4.7, "逆転", None, None)
        assert segment is not None
        assert segment.start.seconds == 5.0
        assert segment.end.seconds == 5.0

    def test_missing_metadata_stays_none(self) -> None:
        segment = build_segment(0.0, 1.0, "発話", None, None)
        assert segment is not None
        assert segment.no_speech_prob is None
        assert segment.avg_logprob is None
