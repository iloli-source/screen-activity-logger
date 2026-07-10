"""Worklogの出力アダプタ（JSONL / Markdown）。"""

from __future__ import annotations

import json
from pathlib import Path

from screen_activity_logger.domain.models import Worklog, WorklogEntry


class JsonlWorklogWriter:
    """1エントリ=1行のJSONとして書き出す。"""

    def write(self, worklog: Worklog, output_path: Path) -> None:
        lines = (self._to_json(entry) for entry in worklog.entries)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _to_json(entry: WorklogEntry) -> str:
        payload = {
            "t": str(entry.timestamp),
            "app_guess": entry.app_guess,
            "ocr": list(entry.ocr_lines),
            "action": entry.action,
        }
        return json.dumps(payload, ensure_ascii=False)


class MarkdownWorklogWriter:
    """人が読む用のMarkdownとして書き出す。"""

    def write(self, worklog: Worklog, output_path: Path) -> None:
        sections = [self._to_section(entry) for entry in worklog.entries]
        text = "# 作業ログ\n\n" + "\n".join(sections)
        output_path.write_text(text, encoding="utf-8")

    @staticmethod
    def _to_section(entry: WorklogEntry) -> str:
        heading = f"## {entry.timestamp}"
        if entry.app_guess:
            heading += f" — {entry.app_guess}"
        body = [heading, "", entry.action]
        if entry.ocr_lines:
            body.append("")
            body.extend(f"- `{line}`" for line in entry.ocr_lines)
        body.append("")
        return "\n".join(body)
