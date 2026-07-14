"""Worklogの出力アダプタ（JSONL / Markdown）。"""

from __future__ import annotations

import json
from pathlib import Path

from screen_activity_logger.domain.models import Worklog, WorklogEntry
from screen_activity_logger.domain.services import aggregate_durations_by_app

# 全角括弧・空白を正規化して包含判定する（Issue #17 S4の表示ガード）
_NORMALIZE_TABLE = str.maketrans({"（": "(", "）": ")", "　": " "})


def _format_duration_ja(seconds: float) -> str:
    """継続時間の日本語整形（45秒/7分30秒/1時間2分。ゼロ単位は省略）。"""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}時間")
    if minutes:
        parts.append(f"{minutes}分")
    if secs or not parts:
        parts.append(f"{secs}秒")
    return "".join(parts)


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
            "t_end": (
                str(entry.end_timestamp)
                if entry.end_timestamp is not None
                else None
            ),
            "duration_seconds": entry.duration_seconds,
            "app_guess": entry.app_guess,
            "resource": entry.resource,
            "location": entry.location,
            "focus": entry.focus,
            "ocr": list(entry.ocr_lines),
            "speech": list(entry.speech),
            "summary": entry.summary,
            "action": entry.action,
        }
        return json.dumps(payload, ensure_ascii=False)


class MarkdownWorklogWriter:
    """人が読む用のMarkdownとして書き出す。"""

    def write(self, worklog: Worklog, output_path: Path) -> None:
        sections = [self._to_section(entry) for entry in worklog.entries]
        text = "# 作業ログ\n\n" + "\n".join(sections)
        summary = self._app_summary(worklog)
        if summary:
            text += summary
        output_path.write_text(text, encoding="utf-8")

    @staticmethod
    def _app_summary(worklog: Worklog) -> str:
        """アプリ別滞在時間のサマリーテーブル（duration皆無なら空、Issue #18）。"""
        totals = aggregate_durations_by_app(worklog)
        if not totals:
            return ""
        lines = ["## アプリ別滞在時間", "", "| アプリ | 滞在時間 |", "|---|---|"]
        lines.extend(
            f"| {app} | {_format_duration_ja(seconds)} |" for app, seconds in totals
        )
        return "\n" + "\n".join(lines) + "\n"

    @staticmethod
    def _to_section(entry: WorklogEntry) -> str:
        duration = entry.duration_seconds
        # duration 0は「観測が過去のみ」の丸め（Issue #18）で、0秒表示はノイズの
        # ため見出しに終端を出さない（4AIレビューR2の指摘は意図的設計として棄却）
        if entry.end_timestamp is not None and duration:
            heading = (
                f"## {entry.timestamp}〜{entry.end_timestamp}"
                f"（{_format_duration_ja(duration)}）"
            )
        else:
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
        if entry.summary:
            body.append(f"🧭 {entry.summary}")
            body.append("")
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
