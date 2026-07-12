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

    def test_end_timestamp_is_next_entry_start(self) -> None:
        """T2（Issue #18）: 窓解釈——エントリの終端は次エントリの開始時刻。"""
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(300.0, "資料を読んでいる"),
                _desc(450.0, "資料を読んでいる"),  # collapse対象
                _desc(750.0, "メールを書いている"),
            ],
            ocr_texts=[_ocr(800.0, "最後の観測")],
        )
        first, second = worklog.entries
        assert first.end_timestamp is not None
        assert first.end_timestamp.seconds == 750.0  # 次エントリの開始
        assert first.duration_seconds == 450.0
        assert second.end_timestamp is not None
        assert second.end_timestamp.seconds == 800.0  # 最終＝OCR最大時刻

    def test_last_entry_end_falls_back_to_own_timestamp(self) -> None:
        """OCR最大時刻がエントリより過去でも end < start にはしない。"""
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[_desc(100.0, "作業")],
            ocr_texts=[_ocr(50.0, "古い観測")],
        )
        entry = worklog.entries[0]
        assert entry.end_timestamp is not None
        assert entry.end_timestamp.seconds == 100.0
        assert entry.duration_seconds == 0.0

    def test_no_ocr_leaves_last_end_none(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(descriptions=[_desc(10.0, "作業")], ocr_texts=[])
        assert worklog.entries[0].end_timestamp is None

    def test_attach_speech_preserves_end_timestamp(self) -> None:
        """#14 F0系の回帰: 発話紐付けの再構築でendが消えない。"""
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        segment = TranscriptSegment(
            start=VideoTimestamp(seconds=11.0),
            end=VideoTimestamp(seconds=12.0),
            text="発話",
        )
        worklog = merger.merge(
            descriptions=[_desc(10.0, "作業A"), _desc(20.0, "作業B")],
            ocr_texts=[],
            transcript_segments=[segment],
        )
        first = worklog.entries[0]
        assert first.speech == ("発話",)
        assert first.end_timestamp is not None
        assert first.end_timestamp.seconds == 20.0

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


class TestAggregateDurationsByApp:
    """T6（Issue #18）: アプリ別滞在時間の集計。"""

    def _entry(self, app, start, end):
        from screen_activity_logger.domain.models import WorklogEntry

        return WorklogEntry(
            timestamp=VideoTimestamp(seconds=start),
            action="作業",
            app_guess=app,
            ocr_lines=(),
            end_timestamp=(
                VideoTimestamp(seconds=end) if end is not None else None
            ),
        )

    def test_aggregates_descending(self) -> None:
        from screen_activity_logger.domain.models import Worklog
        from screen_activity_logger.domain.services import (
            aggregate_durations_by_app,
        )

        worklog = Worklog.from_entries(
            [
                self._entry("Excel", 0.0, 100.0),
                self._entry("Chrome", 100.0, 400.0),
                self._entry("Excel", 400.0, 450.0),
                self._entry(None, 450.0, 500.0),
                self._entry("VS Code", 500.0, None),  # duration不明→除外
            ]
        )
        assert aggregate_durations_by_app(worklog) == (
            ("Chrome", 300.0),
            ("Excel", 150.0),
            ("（不明）", 50.0),
        )

    def test_empty_when_no_durations(self) -> None:
        from screen_activity_logger.domain.models import Worklog
        from screen_activity_logger.domain.services import (
            aggregate_durations_by_app,
        )

        worklog = Worklog.from_entries([self._entry("Excel", 0.0, None)])
        assert aggregate_durations_by_app(worklog) == ()
