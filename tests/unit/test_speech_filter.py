"""domain/speech_filter のユニットテスト（Issue #14 F1: RED）。

真理値表:
  記号のみ（verbal contentなし）                → 除去（主兵装）
  no_speech_prob / avg_logprob いずれかNone     → 保持（判断材料なし）
  no_speech > threshold AND logprob < threshold → 除去（Whisper本家と同じAND）
  それ以外                                      → 保持
"""

import pytest

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp
from screen_activity_logger.domain.speech_filter import (
    SpeechFilterConfig,
    filter_segments,
    has_verbal_content,
    is_reliable_segment,
)


def _segment(
    text: str,
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
    start: float = 0.0,
) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=start + 1.0),
        text=text,
        no_speech_prob=no_speech_prob,
        avg_logprob=avg_logprob,
    )


class TestHasVerbalContent:
    @pytest.mark.parametrize("text", ["!", "。", "!!!", "…？", "、、、"])
    def test_symbol_only_is_not_verbal(self, text: str) -> None:
        assert has_verbal_content(text) is False

    @pytest.mark.parametrize("text", ["はい", "OK", "123", "あ!", "漢字です。"])
    def test_alnum_content_is_verbal(self, text: str) -> None:
        assert has_verbal_content(text) is True


class TestIsReliableSegment:
    def test_symbol_only_is_rejected_regardless_of_probs(self) -> None:
        # 確率が優秀でも記号のみは除去（mlx内部チェックをすり抜けた「!」対策）
        segment = _segment("!", no_speech_prob=0.01, avg_logprob=-0.1)
        assert is_reliable_segment(segment, SpeechFilterConfig()) is False

    def test_missing_metadata_is_kept(self) -> None:
        # 判断材料なし＝保持（後方互換: 旧経路のセグメントを巻き込まない）
        config = SpeechFilterConfig()
        assert is_reliable_segment(_segment("はい"), config) is True
        assert is_reliable_segment(_segment("はい", no_speech_prob=0.9), config) is True
        assert is_reliable_segment(_segment("はい", avg_logprob=-1.5), config) is True

    def test_high_no_speech_and_low_logprob_is_rejected(self) -> None:
        segment = _segment("ご視聴ありがとうございました", 0.9, -1.5)
        assert is_reliable_segment(segment, SpeechFilterConfig()) is False

    def test_high_no_speech_but_good_logprob_is_kept(self) -> None:
        # AND条件: 片側だけでは除去しない（30秒窓共有の正常発話を守る）
        segment = _segment("はい", 0.9, -0.3)
        assert is_reliable_segment(segment, SpeechFilterConfig()) is True

    def test_low_no_speech_and_low_logprob_is_kept(self) -> None:
        segment = _segment("はい", 0.3, -1.5)
        assert is_reliable_segment(segment, SpeechFilterConfig()) is True

    def test_exact_thresholds_are_kept(self) -> None:
        # 境界値: ちょうど閾値は保持（本家Whisperの > / < と同じ開区間）
        segment = _segment("はい", 0.6, -1.0)
        assert is_reliable_segment(segment, SpeechFilterConfig()) is True

    def test_custom_thresholds(self) -> None:
        config = SpeechFilterConfig(no_speech_threshold=0.3, logprob_threshold=-0.5)
        assert is_reliable_segment(_segment("はい", 0.4, -0.6), config) is False


class TestFilterSegments:
    def test_keeps_order_and_drops_unreliable(self) -> None:
        config = SpeechFilterConfig()
        segments = (
            _segment("最初の発話", start=0.0),
            _segment("!", 0.98, -1.4, start=5.0),
            _segment("次の発話", 0.1, -0.2, start=10.0),
        )
        result = filter_segments(segments, config)
        assert [s.text for s in result] == ["最初の発話", "次の発話"]

    def test_all_rejected_gives_empty_tuple(self) -> None:
        segments = (_segment("!", start=0.0), _segment("。", start=1.0))
        assert filter_segments(segments, SpeechFilterConfig()) == ()

    def test_empty_input_gives_empty_tuple(self) -> None:
        assert filter_segments((), SpeechFilterConfig()) == ()


class TestCollapseRepeatedLines:
    def test_collapses_consecutive_duplicates(self) -> None:
        # 実バグ（Issue #3）: 「アドメット」×2「はい」×3がそのまま列挙されていた
        from screen_activity_logger.domain.speech_filter import (
            collapse_repeated_lines,
        )

        lines = ("アドメット", "アドメット", "はい", "はい", "はい", "了解です")

        collapsed = collapse_repeated_lines(lines)

        assert collapsed == ("アドメット", "はい", "了解です")

    def test_keeps_non_consecutive_duplicates(self) -> None:
        from screen_activity_logger.domain.speech_filter import (
            collapse_repeated_lines,
        )

        # 間に別発話を挟む反復は会話として意味があるため保持する
        lines = ("はい", "お願いします", "はい")

        assert collapse_repeated_lines(lines) == lines

    def test_empty_input(self) -> None:
        from screen_activity_logger.domain.speech_filter import (
            collapse_repeated_lines,
        )

        assert collapse_repeated_lines(()) == ()
