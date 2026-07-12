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

    def test_vlm_hallucination_fragment_is_rejected(self) -> None:
        """R5（Issue #17 S3）: OCR沈黙時のVLM幻覚断片は昇格させない。"""
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(1.0, "会議中", resource="IRW")
        enriched = enrich_description(vlm_desc, ocr_lines=("IRW",))
        assert enriched.resource is None

    def test_vlm_boilerplate_is_rejected(self) -> None:
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(
            1.0, "閲覧中", resource='Web page titled "Ureya hasde"'
        )
        enriched = enrich_description(vlm_desc, ocr_lines=("Ureya", "hasde"))
        assert enriched.resource is None

    def test_vlm_title_with_url_wins_when_ocr_url_confirms_domain(self) -> None:
        """R3（Issue #17）: OCRのURLがVLMのタイトル+URL併記を裏付ける場合はVLM値を優先。

        実録画の理想形（Issue #12）を保護する回帰テスト。
        """
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(
            1.0,
            "天気を確認している",
            resource=(
                "Yahoo! JAPAN 天気・災害ページ"
                "（URL：weather.yahoo.co.jp/weather/jp/4410.html）"
            ),
        )
        enriched = enrich_description(
            vlm_desc,
            ocr_lines=("weather.yahoo.co.jp/weather/jp/13/4410.html", "Yahoo!"),
        )
        assert enriched.resource == vlm_desc.resource  # 豊かな方を採る

    def test_ocr_url_wins_when_vlm_lacks_domain(self) -> None:
        from screen_activity_logger.domain.screen_context import enrich_description

        vlm_desc = _desc(1.0, "閲覧している", resource="4410.html")
        enriched = enrich_description(
            vlm_desc,
            ocr_lines=("weather.yahoo.co.jp/weather/jp/13/4410.html",),
        )
        assert enriched.resource == "weather.yahoo.co.jp/weather/jp/13/4410.html"


class TestContextInWriters:
    """Y5: 見出し・👁行・JSONLキーの出力。"""

    def _entry(self) -> WorklogEntry:
        return WorklogEntry(
            timestamp=VideoTimestamp(seconds=312.0),
            action="単価セルを修正している",
            app_guess="Excel",
            ocr_lines=("見積書_2026Q2.xlsx - Excel",),
            resource="見積書_2026Q2.xlsx",
            location="Sheet1",
            focus="D列の単価合計を確認しながら",
        )

    def test_markdown_heading_includes_context(self, tmp_path) -> None:
        from pathlib import Path

        from screen_activity_logger.domain.models import Worklog
        from screen_activity_logger.infrastructure.writers import (
            MarkdownWorklogWriter,
        )

        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(Worklog.from_entries([self._entry()]), out)
        text = out.read_text(encoding="utf-8")
        assert "## 00:05:12 — Excel — 見積書_2026Q2.xlsx（Sheet1）" in text
        assert "👁 D列の単価合計を確認しながら" in text

    def test_markdown_omits_missing_parts(self, tmp_path) -> None:
        from screen_activity_logger.domain.models import Worklog
        from screen_activity_logger.infrastructure.writers import (
            MarkdownWorklogWriter,
        )

        entry = WorklogEntry(
            timestamp=VideoTimestamp(seconds=10.0),
            action="作業中",
            app_guess=None,
            ocr_lines=(),
        )
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(Worklog.from_entries([entry]), out)
        text = out.read_text(encoding="utf-8")
        assert "## 00:00:10\n" in text
        assert "👁" not in text
        assert "None" not in text

    def test_jsonl_includes_context_keys(self, tmp_path) -> None:
        import json

        from screen_activity_logger.domain.models import Worklog
        from screen_activity_logger.infrastructure.writers import (
            JsonlWorklogWriter,
        )

        out = tmp_path / "worklog.jsonl"
        JsonlWorklogWriter().write(Worklog.from_entries([self._entry()]), out)
        record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert record["resource"] == "見積書_2026Q2.xlsx"
        assert record["location"] == "Sheet1"
        assert record["focus"] == "D列の単価合計を確認しながら"


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
