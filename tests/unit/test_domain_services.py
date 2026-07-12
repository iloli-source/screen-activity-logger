"""domain/services TimelineMerger のユニットテスト（Cycle C: RED）。"""

from screen_activity_logger.domain.models import (
    ActivityDescription,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
)
from screen_activity_logger.domain.services import TimelineMerger


def _desc(seconds: float, action: str, app: str | None = None) -> ActivityDescription:
    return ActivityDescription(
        timestamp=VideoTimestamp(seconds=seconds), action=action, app_guess=app
    )


def _ocr(seconds: float, *lines: str) -> OcrText:
    return OcrText(timestamp=VideoTimestamp(seconds=seconds), lines=lines)


class TestTimelineMerger:
    def test_merges_description_with_ocr_at_same_timestamp(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[_desc(10.0, "エディタでコードを編集", "VS Code")],
            ocr_texts=[_ocr(10.0, "def main():", "pytest")],
        )
        entry = worklog.entries[0]
        assert entry.action == "エディタでコードを編集"
        assert entry.app_guess == "VS Code"
        assert entry.ocr_lines == ("def main():", "pytest")

    def test_attaches_nearest_ocr_within_tolerance(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[_desc(10.0, "作業A")],
            ocr_texts=[_ocr(9.4, "far"), _ocr(9.8, "near")],
        )
        assert worklog.entries[0].ocr_lines == ("near",)

    def test_no_ocr_within_tolerance_gives_empty_lines(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[_desc(10.0, "作業A")],
            ocr_texts=[_ocr(5.0, "too far")],
        )
        assert worklog.entries[0].ocr_lines == ()

    def test_collapses_consecutive_entries_with_same_action(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(10.0, "資料を読んでいる"),
                _desc(20.0, "資料を読んでいる"),
                _desc(30.0, "メールを書いている"),
            ],
            ocr_texts=[],
        )
        actions = [e.action for e in worklog.entries]
        assert actions == ["資料を読んでいる", "メールを書いている"]
        # 重複除去時は最初のタイムスタンプを保持する
        assert worklog.entries[0].timestamp.seconds == 10.0

    def test_same_action_reappearing_later_is_kept(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(10.0, "資料を読んでいる"),
                _desc(20.0, "メールを書いている"),
                _desc(30.0, "資料を読んでいる"),
            ],
            ocr_texts=[],
        )
        assert [e.action for e in worklog.entries] == [
            "資料を読んでいる",
            "メールを書いている",
            "資料を読んでいる",
        ]

    def test_result_is_sorted_by_timestamp(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[_desc(30.0, "作業C"), _desc(10.0, "作業A")],
            ocr_texts=[],
        )
        assert [e.timestamp.seconds for e in worklog.entries] == [10.0, 30.0]

    def test_attach_speech_preserves_context_fields(self) -> None:
        """発話紐付けで resource/location/focus が消えない（👁行消失バグの回帰）。"""
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        description = ActivityDescription(
            timestamp=VideoTimestamp(seconds=10.0),
            action="コードレビュー",
            app_guess="GitHub",
            resource="pull/123",
            location="Files changed",
            focus="diff表示",
        )
        segment = TranscriptSegment(
            start=VideoTimestamp(seconds=11.0),
            end=VideoTimestamp(seconds=12.0),
            text="ここを直しました",
        )
        worklog = merger.merge(
            descriptions=[description],
            ocr_texts=[],
            transcript_segments=[segment],
        )
        entry = worklog.entries[0]
        assert entry.speech == ("ここを直しました",)
        assert entry.resource == "pull/123"
        assert entry.location == "Files changed"
        assert entry.focus == "diff表示"
