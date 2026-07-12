"""infrastructure/writers のユニットテスト（Cycle E: RED）。"""

import json
from pathlib import Path

from screen_activity_logger.domain.models import (
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)
from screen_activity_logger.infrastructure.writers import (
    JsonlWorklogWriter,
    MarkdownWorklogWriter,
)


def _worklog() -> Worklog:
    return Worklog.from_entries(
        [
            WorklogEntry(
                timestamp=VideoTimestamp(seconds=754.0),
                action="テスト失敗箇所をエディタで確認している",
                app_guess="VS Code",
                ocr_lines=("pytest", "FAILED test_auth.py"),
            ),
            WorklogEntry(
                timestamp=VideoTimestamp(seconds=800.0),
                action="ブラウザでドキュメントを読んでいる",
                app_guess=None,
                ocr_lines=(),
            ),
        ]
    )


class TestJsonlWorklogWriter:
    def test_writes_one_json_line_per_entry(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.jsonl"

        JsonlWorklogWriter().write(_worklog(), out)

        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first == {
            "t": "00:12:34",
            "t_end": None,
            "duration_seconds": None,
            "app_guess": "VS Code",
            "resource": None,
            "location": None,
            "focus": None,
            "ocr": ["pytest", "FAILED test_auth.py"],
            "speech": [],
            "action": "テスト失敗箇所をエディタで確認している",
        }

    def test_japanese_is_not_escaped(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.jsonl"

        JsonlWorklogWriter().write(_worklog(), out)

        raw = out.read_text(encoding="utf-8")
        assert "テスト失敗箇所" in raw


class TestMarkdownWorklogWriter:
    def test_writes_header_and_entry_sections(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"

        MarkdownWorklogWriter().write(_worklog(), out)

        text = out.read_text(encoding="utf-8")
        assert text.startswith("# 作業ログ")
        assert "## 00:12:34 — VS Code" in text
        assert "テスト失敗箇所をエディタで確認している" in text
        assert "- `pytest`" in text
        assert "- `FAILED test_auth.py`" in text

    def test_entry_without_app_and_ocr_renders_cleanly(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"

        MarkdownWorklogWriter().write(_worklog(), out)

        text = out.read_text(encoding="utf-8")
        assert "## 00:13:20" in text
        # app_guess が無い場合は「 — None」を出さない
        assert "None" not in text

    def _entry_with(self, resource: str, location: str) -> Worklog:
        return Worklog.from_entries(
            [
                WorklogEntry(
                    timestamp=VideoTimestamp(seconds=10.0),
                    action="作業中",
                    app_guess="Excel",
                    ocr_lines=(),
                    resource=resource,
                    location=location,
                )
            ]
        )

    def test_location_contained_in_resource_is_not_appended(
        self, tmp_path: Path
    ) -> None:
        """R7（Issue #17 S4）: 重複するlocationを見出しに付けない。"""
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(
            self._entry_with("店舗別売上実績 (Sheet2)", "Sheet2"), out
        )
        text = out.read_text(encoding="utf-8")
        assert "店舗別売上実績 (Sheet2)" in text
        assert "（Sheet2）" not in text

    def test_resource_contained_in_location_is_not_appended(
        self, tmp_path: Path
    ) -> None:
        """逆包含（実録画: 店舗売上実績（シート名: 店舗売上実績））もスキップ。"""
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(
            self._entry_with("店舗売上実績", "シート名: 店舗売上実績"), out
        )
        text = out.read_text(encoding="utf-8")
        assert "— 店舗売上実績" in text
        assert "（シート名: 店舗売上実績）" not in text

    def test_distinct_location_is_appended(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(
            self._entry_with("見積書.xlsx", "Sheet1"), out
        )
        assert "見積書.xlsx（Sheet1）" in out.read_text(encoding="utf-8")


class TestDurationFormatting:
    """T4（Issue #18）: 継続時間の日本語整形。"""

    def test_formats(self) -> None:
        from screen_activity_logger.infrastructure.writers import (
            _format_duration_ja,
        )

        assert _format_duration_ja(45) == "45秒"
        assert _format_duration_ja(450) == "7分30秒"
        assert _format_duration_ja(3720) == "1時間2分"
        assert _format_duration_ja(3600) == "1時間"
        assert _format_duration_ja(0) == "0秒"


class TestDwellTimeOutput:
    """T3-T4（Issue #18）: 滞留時間のJSONL・Markdown出力。"""

    def _entry(self) -> WorklogEntry:
        return WorklogEntry(
            timestamp=VideoTimestamp(seconds=300.0),
            action="資料を読んでいる",
            app_guess="Preview",
            ocr_lines=(),
            end_timestamp=VideoTimestamp(seconds=750.0),
        )

    def test_jsonl_includes_end_and_duration(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.jsonl"
        JsonlWorklogWriter().write(Worklog.from_entries([self._entry()]), out)
        record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert record["t_end"] == "00:12:30"
        assert record["duration_seconds"] == 450.0

    def test_markdown_heading_shows_time_range(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(Worklog.from_entries([self._entry()]), out)
        text = out.read_text(encoding="utf-8")
        assert "## 00:05:00〜00:12:30（7分30秒） — Preview" in text

    def test_zero_duration_falls_back_to_plain_heading(
        self, tmp_path: Path
    ) -> None:
        entry = WorklogEntry(
            timestamp=VideoTimestamp(seconds=10.0),
            action="作業",
            app_guess=None,
            ocr_lines=(),
            end_timestamp=VideoTimestamp(seconds=10.0),
        )
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(Worklog.from_entries([entry]), out)
        assert "## 00:00:10\n" in out.read_text(encoding="utf-8")


class TestAppSummaryTable:
    """T6（Issue #18）: アプリ別滞在時間サマリー。"""

    def test_summary_table_is_rendered(self, tmp_path: Path) -> None:
        entries = [
            WorklogEntry(
                timestamp=VideoTimestamp(seconds=0.0),
                action="編集",
                app_guess="Excel",
                ocr_lines=(),
                end_timestamp=VideoTimestamp(seconds=450.0),
            ),
        ]
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(Worklog.from_entries(entries), out)
        text = out.read_text(encoding="utf-8")
        assert "## アプリ別滞在時間" in text
        assert "| Excel | 7分30秒 |" in text

    def test_no_summary_without_durations(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(_worklog(), out)  # end無しエントリのみ
        assert "アプリ別滞在時間" not in out.read_text(encoding="utf-8")
