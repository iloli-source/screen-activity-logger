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
