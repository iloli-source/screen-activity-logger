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
