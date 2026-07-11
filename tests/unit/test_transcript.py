"""発話（TranscriptSegment）のドメインテスト（Cycle O: RED）。"""

import dataclasses

import pytest

from screen_activity_logger.domain.models import (
    ActivityDescription,
    TranscriptSegment,
    VideoTimestamp,
    WorklogEntry,
)
from screen_activity_logger.domain.services import TimelineMerger


def _segment(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=end),
        text=text,
    )


def _desc(seconds: float, action: str) -> ActivityDescription:
    return ActivityDescription(
        timestamp=VideoTimestamp(seconds=seconds), action=action, app_guess=None
    )


class TestTranscriptSegment:
    def test_holds_time_range_and_text(self) -> None:
        seg = _segment(1.0, 3.5, "ここのテストが落ちてる原因は")
        assert seg.start.seconds == 1.0
        assert seg.end.seconds == 3.5
        assert seg.text == "ここのテストが落ちてる原因は"

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError):
            _segment(5.0, 3.0, "invalid")

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError):
            _segment(1.0, 2.0, "   ")

    def test_is_immutable(self) -> None:
        seg = _segment(1.0, 2.0, "hello")
        with pytest.raises(dataclasses.FrozenInstanceError):
            seg.text = "changed"  # type: ignore[misc]


class TestWorklogEntrySpeech:
    def test_speech_defaults_to_empty(self) -> None:
        entry = WorklogEntry(
            timestamp=VideoTimestamp(seconds=1.0),
            action="作業中",
            app_guess=None,
            ocr_lines=(),
        )
        assert entry.speech == ()


class TestTimelineMergerSpeechAttachment:
    def _merger(self) -> TimelineMerger:
        return TimelineMerger(ocr_match_tolerance_seconds=1.0)

    def test_speech_within_entry_window_is_attached(self) -> None:
        worklog = self._merger().merge(
            descriptions=[_desc(10.0, "作業A"), _desc(30.0, "作業B")],
            ocr_texts=[],
            transcript_segments=[_segment(12.0, 15.0, "これはAの説明です")],
        )
        assert worklog.entries[0].speech == ("これはAの説明です",)
        assert worklog.entries[1].speech == ()

    def test_speech_before_first_entry_goes_to_first(self) -> None:
        worklog = self._merger().merge(
            descriptions=[_desc(10.0, "作業A")],
            ocr_texts=[],
            transcript_segments=[_segment(2.0, 5.0, "冒頭の挨拶")],
        )
        assert worklog.entries[0].speech == ("冒頭の挨拶",)

    def test_multiple_speeches_keep_time_order(self) -> None:
        worklog = self._merger().merge(
            descriptions=[_desc(10.0, "作業A")],
            ocr_texts=[],
            transcript_segments=[
                _segment(20.0, 22.0, "二つ目"),
                _segment(12.0, 14.0, "一つ目"),
            ],
        )
        assert worklog.entries[0].speech == ("一つ目", "二つ目")

    def test_speech_attaches_to_collapsed_entry_window(self) -> None:
        """重複除去で消えたエントリの時間帯の発話は、生き残ったエントリに載る。"""
        worklog = self._merger().merge(
            descriptions=[
                _desc(10.0, "資料を読んでいる"),
                _desc(20.0, "資料を読んでいる"),  # 重複除去される
                _desc(30.0, "メールを書いている"),
            ],
            ocr_texts=[],
            transcript_segments=[_segment(22.0, 25.0, "この段落が大事")],
        )
        assert worklog.entries[0].speech == ("この段落が大事",)

    def test_no_segments_keeps_existing_behavior(self) -> None:
        worklog = self._merger().merge(
            descriptions=[_desc(10.0, "作業A")],
            ocr_texts=[],
        )
        assert worklog.entries[0].speech == ()
