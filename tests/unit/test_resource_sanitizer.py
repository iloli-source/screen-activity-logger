"""resource昇格時の浄化のユニットテスト（Issue #17 R1: RED）。

テストケースの文字列は実録画検証（Excel/Chromeチュートリアル・実会議クリップ）で
観測した実データをそのまま使う。
"""

import pytest

from screen_activity_logger.domain.resource_sanitizer import (
    clean_vlm_resource,
    sanitize_url,
    strip_location_suffix,
)

# Chromeチュートリアル実データ（200字超・OCR文字化け混じり）
_GARBAGE_SEARCH_URL = (
    "google.com/search?q=天気予报+東京8toq=天気予短%E3%80%80秉京"
    "&aqs=chrome..69i57j0i4i51219.2982j1j7&sourceid=chrome8ie=UTF-8"
)


class TestSanitizeUrl:
    def test_strips_query_string(self) -> None:
        assert sanitize_url(_GARBAGE_SEARCH_URL) == "google.com/search"

    def test_clean_url_with_path_is_unchanged(self) -> None:
        url = "weather.yahoo.co.jp/weather/jp/13/4410.html"
        assert sanitize_url(url) == url

    def test_https_url_is_unchanged(self) -> None:
        assert sanitize_url("https://example.com/pricing") == (
            "https://example.com/pricing"
        )

    def test_strips_fragment(self) -> None:
        assert sanitize_url("example.com/docs#section-3") == "example.com/docs"

    def test_truncates_long_path_with_ellipsis(self) -> None:
        url = "example.com/" + "a" * 100
        result = sanitize_url(url)
        assert len(result) == 60
        assert result.endswith("…")
        assert result.startswith("example.com/")

    def test_trims_trailing_punctuation(self) -> None:
        assert sanitize_url("example.com/page.") == "example.com/page"


class TestCleanVlmResource:
    """R4（Issue #17 S3）: VLM由来resourceの品質ゲート。実録画の実文字列を使用。"""

    @pytest.mark.parametrize(
        "value",
        [
            'Web page titled "Ureya hasde"',  # 英語ボイラープレート（幻覚シグナル）
            "A web page",
            "Screenshot of desktop",
            "Untitled document",
            "Browser tab",
            "IRW",   # 低情報断片（OCRゴミの復唱）
            "EZEO",
        ],
    )
    def test_rejects_hallucination_patterns(self, value: str) -> None:
        assert clean_vlm_resource(value) is None

    @pytest.mark.parametrize(
        "value",
        [
            "Zoom Meeting",          # 正当な英語リソース名
            "料金ページ",             # 日本語は無条件で通す
            "a.py",                  # 短くても区切り記号（.）があれば通す
            "tl;dv MINOTETAKER",     # 実録画で正しく抽出できていた値
            "店舗別売上実績.xlsx",
            "Yahoo! JAPAN 天気・災害ページ（URL：weather.yahoo.co.jp/…）",
        ],
    )
    def test_keeps_legitimate_resources(self, value: str) -> None:
        assert clean_vlm_resource(value) == value

    def test_none_passes_through(self) -> None:
        assert clean_vlm_resource(None) is None


class TestStripLocationSuffix:
    """R6（Issue #17 S4）: resource末尾の括弧付きlocation重複を剥がす。"""

    def test_strips_half_width_paren_suffix(self) -> None:
        # 実録画: 見出しが「店舗別売上実績 (Sheet1)（Sheet1）」になっていた
        assert (
            strip_location_suffix("店舗別売上実績 (Sheet1)", "Sheet1")
            == "店舗別売上実績"
        )

    def test_strips_full_width_paren_suffix(self) -> None:
        assert (
            strip_location_suffix("店舗別売上実績（Sheet1）", "Sheet1")
            == "店舗別売上実績"
        )

    def test_non_matching_suffix_is_unchanged(self) -> None:
        assert (
            strip_location_suffix("見積書.xlsx", "Sheet1") == "見積書.xlsx"
        )

    def test_location_in_middle_is_unchanged(self) -> None:
        assert (
            strip_location_suffix("Sheet1のまとめ資料.xlsx", "Sheet1")
            == "Sheet1のまとめ資料.xlsx"
        )

    def test_none_location_is_unchanged(self) -> None:
        assert strip_location_suffix("見積書.xlsx", None) == "見積書.xlsx"
