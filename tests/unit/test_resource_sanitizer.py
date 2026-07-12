"""resource昇格時の浄化のユニットテスト（Issue #17 R1: RED）。

テストケースの文字列は実録画検証（Excel/Chromeチュートリアル・実会議クリップ）で
観測した実データをそのまま使う。
"""

from screen_activity_logger.domain.resource_sanitizer import sanitize_url

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
