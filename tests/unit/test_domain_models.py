"""domain/models のユニットテスト（Cycle B: RED）。"""

import dataclasses
from pathlib import Path

import pytest

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)


class TestVideoTimestamp:
    def test_formats_seconds_as_hh_mm_ss(self) -> None:
        ts = VideoTimestamp(seconds=754.2)
        assert str(ts) == "00:12:34"

    def test_formats_hour_boundary(self) -> None:
        ts = VideoTimestamp(seconds=3661.0)
        assert str(ts) == "01:01:01"

    def test_rejects_negative_seconds(self) -> None:
        with pytest.raises(ValueError):
            VideoTimestamp(seconds=-1.0)

    def test_is_immutable(self) -> None:
        ts = VideoTimestamp(seconds=10.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ts.seconds = 20.0  # type: ignore[misc]

    def test_orders_by_seconds(self) -> None:
        assert VideoTimestamp(seconds=5.0) < VideoTimestamp(seconds=10.0)


class TestFrame:
    def test_holds_timestamp_path_and_keyframe_flag(self) -> None:
        frame = Frame(
            timestamp=VideoTimestamp(seconds=1.0),
            path=Path("/tmp/f_000001.png"),
            is_keyframe=True,
        )
        assert frame.is_keyframe is True
        assert frame.path.name == "f_000001.png"


class TestOcrText:
    def test_holds_text_lines_for_a_timestamp(self) -> None:
        ocr = OcrText(
            timestamp=VideoTimestamp(seconds=2.0),
            lines=("pytest", "FAILED test_auth.py"),
        )
        assert ocr.lines == ("pytest", "FAILED test_auth.py")

    def test_normalized_lines_strips_whitespace_and_drops_empties(self) -> None:
        ocr = OcrText(
            timestamp=VideoTimestamp(seconds=2.0),
            lines=("  pytest  ", "", "   "),
        )
        assert ocr.normalized_lines() == ("pytest",)


class TestActivityDescription:
    def test_rejects_empty_action(self) -> None:
        with pytest.raises(ValueError):
            ActivityDescription(
                timestamp=VideoTimestamp(seconds=3.0),
                action="",
                app_guess=None,
            )

    def test_holds_action_and_optional_app_guess(self) -> None:
        desc = ActivityDescription(
            timestamp=VideoTimestamp(seconds=3.0),
            action="テスト失敗箇所をエディタで確認している",
            app_guess="VS Code",
        )
        assert desc.app_guess == "VS Code"


class TestWorklog:
    def _entry(self, seconds: float, action: str = "作業中") -> WorklogEntry:
        return WorklogEntry(
            timestamp=VideoTimestamp(seconds=seconds),
            action=action,
            app_guess=None,
            ocr_lines=(),
        )

    def test_sorts_entries_by_timestamp(self) -> None:
        log = Worklog.from_entries(
            [self._entry(30.0), self._entry(10.0), self._entry(20.0)]
        )
        assert [e.timestamp.seconds for e in log.entries] == [10.0, 20.0, 30.0]

    def test_is_immutable_aggregate(self) -> None:
        log = Worklog.from_entries([self._entry(1.0)])
        with pytest.raises(dataclasses.FrozenInstanceError):
            log.entries = ()  # type: ignore[misc]
