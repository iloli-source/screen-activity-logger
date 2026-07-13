"""検索文書のドメインモデルのユニットテスト（Issue #5 P1: RED）。"""

from screen_activity_logger.domain.search import build_search_document


def _record(**overrides) -> dict:
    base = {
        "t": "00:01:46",
        "t_end": "00:03:21",
        "duration_seconds": 95.0,
        "app_guess": "Excel",
        "resource": "店舗別売上実績.xlsx",
        "location": "Sheet1",
        "focus": "C8セルの合計を確認",
        "ocr": ["店舗別売上実績", "=SUM(C4:C7)"],
        "speech": ["合計を出します", "サム関数を使います"],
        "action": "SUM関数で集計している",
    }
    base.update(overrides)
    return base


class TestBuildSearchDocument:
    def test_builds_labeled_sections(self) -> None:
        doc = build_search_document(_record(), source="02", doc_id="02:0")
        assert "作業: SUM関数で集計している" in doc.text
        assert "アプリ: Excel" in doc.text
        assert "対象: 店舗別売上実績.xlsx（Sheet1）" in doc.text
        assert "注視: C8セルの合計を確認" in doc.text
        assert "発話: 合計を出します。サム関数を使います" in doc.text
        assert "画面: 店舗別売上実績 / =SUM(C4:C7)" in doc.text

    def test_keeps_display_metadata(self) -> None:
        doc = build_search_document(_record(), source="02", doc_id="02:0")
        assert doc.source == "02"
        assert doc.t == "00:01:46"
        assert doc.t_end == "00:03:21"
        assert doc.duration_seconds == 95.0
        assert doc.action == "SUM関数で集計している"

    def test_none_fields_omit_lines(self) -> None:
        doc = build_search_document(
            _record(app_guess=None, resource=None, focus=None, ocr=[], speech=[]),
            source="02",
            doc_id="02:0",
        )
        assert "アプリ:" not in doc.text
        assert "対象:" not in doc.text
        assert "注視:" not in doc.text
        assert "発話:" not in doc.text
        assert "画面:" not in doc.text
        assert doc.text == "作業: SUM関数で集計している"

    def test_legacy_record_without_dwell_fields(self) -> None:
        """Issue #18以前の旧形式（t_end/duration_seconds欠損）に耐える。"""
        record = _record()
        del record["t_end"]
        del record["duration_seconds"]
        doc = build_search_document(record, source="00", doc_id="00:1")
        assert doc.t_end is None
        assert doc.duration_seconds is None

    def test_truncates_noisy_ocr(self) -> None:
        doc = build_search_document(
            _record(ocr=["あ" * 500]), source="02", doc_id="02:0"
        )
        screen_line = next(
            line for line in doc.text.splitlines() if line.startswith("画面:")
        )
        assert len(screen_line) <= 200 + len("画面: ")

    def test_truncates_long_speech(self) -> None:
        doc = build_search_document(
            _record(speech=["長い発話です" * 200]), source="02", doc_id="02:0"
        )
        speech_line = next(
            line for line in doc.text.splitlines() if line.startswith("発話:")
        )
        assert len(speech_line) <= 400 + len("発話: ")
