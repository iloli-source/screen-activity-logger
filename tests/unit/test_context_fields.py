"""コンテキストフィールドのモデル・merger伝搬テスト（Cycle Y2: RED）。"""

from screen_activity_logger.domain.models import (
    ActivityDescription,
    VideoTimestamp,
    WorklogEntry,
)
from screen_activity_logger.domain.services import TimelineMerger


def _desc(
    seconds: float,
    action: str,
    resource: str | None = None,
    location: str | None = None,
    focus: str | None = None,
) -> ActivityDescription:
    return ActivityDescription(
        timestamp=VideoTimestamp(seconds=seconds),
        action=action,
        app_guess=None,
        resource=resource,
        location=location,
        focus=focus,
    )


class TestContextFieldDefaults:
    def test_description_fields_default_to_none(self) -> None:
        desc = ActivityDescription(
            timestamp=VideoTimestamp(seconds=1.0), action="作業", app_guess=None
        )
        assert desc.resource is None
        assert desc.location is None
        assert desc.focus is None

    def test_entry_fields_default_to_none(self) -> None:
        entry = WorklogEntry(
            timestamp=VideoTimestamp(seconds=1.0),
            action="作業",
            app_guess=None,
            ocr_lines=(),
        )
        assert entry.resource is None
        assert entry.location is None
        assert entry.focus is None


class TestEnrichDescription:
    """Y4: OCR由来の事実がVLM推測を上書きし、OCRが沈黙ならVLM値を採用。"""

    def test_ocr_facts_override_vlm_guess(self) -> None:
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(
            1.0, "編集している", resource="たぶんreport.xlsx", location=None
        )
        enriched = enrich_description(
            vlm_desc, ocr_lines=("見積書_2026Q2.xlsx - Excel", "Sheet1")
        )
        assert enriched.resource == "見積書_2026Q2.xlsx"  # OCRの事実が勝つ
        assert enriched.location == "Sheet1"
        assert enriched.app_guess == "Excel"  # タイトルバー由来
        assert enriched.action == "編集している"  # actionは変えない

    def test_vlm_values_used_when_ocr_silent(self) -> None:
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(
            1.0, "閲覧している", resource="料金ページ", focus="価格表"
        )
        enriched = enrich_description(vlm_desc, ocr_lines=("ただの本文",))
        assert enriched.resource == "料金ページ"
        assert enriched.focus == "価格表"


class TestMergerPropagatesContext:
    def test_fields_flow_into_worklog_entry(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(
                    1.0,
                    "セルを修正している",
                    resource="見積書.xlsx",
                    location="Sheet1",
                    focus="D列の合計",
                )
            ],
            ocr_texts=[],
        )
        entry = worklog.entries[0]
        assert entry.resource == "見積書.xlsx"
        assert entry.location == "Sheet1"
        assert entry.focus == "D列の合計"

    def test_same_action_different_resource_is_kept(self) -> None:
        """同じ操作でもファイルが変われば別エントリ（collapse キー拡張）。"""
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(1.0, "資料を確認している", resource="A社提案.pptx"),
                _desc(2.0, "資料を確認している", resource="B社提案.pptx"),
            ],
            ocr_texts=[],
        )
        assert len(worklog.entries) == 2

    def test_same_action_same_resource_is_collapsed(self) -> None:
        merger = TimelineMerger(ocr_match_tolerance_seconds=1.0)
        worklog = merger.merge(
            descriptions=[
                _desc(1.0, "資料を確認している", resource="A社提案.pptx"),
                _desc(2.0, "資料を確認している", resource="A社提案.pptx"),
            ],
            ocr_texts=[],
        )
        assert len(worklog.entries) == 1
