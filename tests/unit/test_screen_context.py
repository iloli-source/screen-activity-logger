"""domain/screen_context のユニットテスト（Cycle Y1: RED）。

OCR行（一次情報）からアプリ・リソース・位置の「事実」を抽出する。
"""

from screen_activity_logger.domain.screen_context import (
    ScreenContext,
    parse_screen_context,
)


class TestFileNameExtraction:
    def test_excel_title_bar(self) -> None:
        ctx = parse_screen_context(
            ("見積書_2026Q2.xlsx - Excel", "ホーム", "挿入")
        )
        assert ctx.resource == "見積書_2026Q2.xlsx"
        assert ctx.app == "Excel"

    def test_powerpoint_title_bar(self) -> None:
        ctx = parse_screen_context(("提案資料.pptx - PowerPoint",))
        assert ctx.resource == "提案資料.pptx"
        assert ctx.app == "PowerPoint"

    def test_filename_without_app_suffix(self) -> None:
        ctx = parse_screen_context(("report_final.pdf", "その他の行"))
        assert ctx.resource == "report_final.pdf"
        assert ctx.app is None

    def test_source_code_filename(self) -> None:
        ctx = parse_screen_context(("use_cases.py", "def execute"))
        assert ctx.resource == "use_cases.py"


class TestUrlExtraction:
    def test_https_url(self) -> None:
        ctx = parse_screen_context(
            ("料金プラン | サービスA", "https://example.com/pricing")
        )
        assert ctx.resource == "https://example.com/pricing"

    def test_url_takes_priority_over_nothing(self) -> None:
        ctx = parse_screen_context(("github.com/sivachi/screen-activity-logger",))
        assert ctx.resource == "github.com/sivachi/screen-activity-logger"


class TestLocationExtraction:
    def test_slide_position(self) -> None:
        ctx = parse_screen_context(("提案資料.pptx - PowerPoint", "スライド 3/12"))
        assert ctx.location == "スライド 3/12"

    def test_japanese_page_position(self) -> None:
        ctx = parse_screen_context(("5/20ページ",))
        assert ctx.location == "5/20ページ"

    def test_english_page_position(self) -> None:
        ctx = parse_screen_context(("Page 5 of 20",))
        assert ctx.location == "Page 5 of 20"

    def test_sheet_name(self) -> None:
        ctx = parse_screen_context(("見積書.xlsx - Excel", "Sheet1", "明細"))
        assert ctx.location == "Sheet1"


class TestNoMatch:
    def test_no_context_gives_all_none(self) -> None:
        ctx = parse_screen_context(("こんにちは", "ただのテキスト"))
        assert ctx == ScreenContext(app=None, resource=None, location=None)

    def test_empty_lines(self) -> None:
        ctx = parse_screen_context(())
        assert ctx.resource is None

    def test_input_is_not_mutated(self) -> None:
        lines = ("見積書.xlsx - Excel", "スライド 1/2")
        parse_screen_context(lines)
        assert lines == ("見積書.xlsx - Excel", "スライド 1/2")
