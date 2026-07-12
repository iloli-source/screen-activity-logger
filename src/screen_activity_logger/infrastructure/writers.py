"""Worklogの出力アダプタ（JSONL / Markdown）。"""

from __future__ import annotations

import json
from pathlib import Path

from screen_activity_logger.domain.models import Worklog, WorklogEntry

# 全角括弧・空白を正規化して包含判定する（Issue #17 S4の表示ガード）
_NORMALIZE_TABLE = str.maketrans({"（": "(", "）": ")", "　": " "})


def _is_redundant_location(resource: str, location: str) -> bool:
    """locationがresourceと重複情報なら見出しへの付与をスキップする。

    JSONLの両フィールドは無加工のため、誤スキップの損失はMarkdown表示のみ。
    """
    norm_resource = resource.translate(_NORMALIZE_TABLE).strip()
    norm_location = location.translate(_NORMALIZE_TABLE).strip()
    return norm_location in norm_resource or norm_resource in norm_location


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
            "resource": entry.resource,
            "location": entry.location,
            "focus": entry.focus,
            "ocr": list(entry.ocr_lines),
            "speech": list(entry.speech),
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
        if entry.resource:
            heading += f" — {entry.resource}"
            if entry.location and not _is_redundant_location(
                entry.resource, entry.location
            ):
                heading += f"（{entry.location}）"
        body = [heading, ""]
        if entry.speech:
            body.extend(f"🗣️ {line}" for line in entry.speech)
            body.append("")
        if entry.focus:
            body.append(f"👁 {entry.focus}")
        body.append(entry.action)
        if entry.ocr_lines:
            body.append("")
            body.extend(f"- `{line}`" for line in entry.ocr_lines)
        body.append("")
        return "\n".join(body)
