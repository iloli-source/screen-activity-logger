"""手順書Markdown出力アダプタ（Issue #26）。

時系列の作業ログを「Step 1→2→3」の手順書構造に再構成する。
追加のAI呼び出しはしない（既存エントリの機械的再構成のみ）。
発話・要旨は省略する——手順書は操作の再現が目的で、一次情報は
worklog.jsonl に常に残るため情報は失われない。
"""

from __future__ import annotations

from pathlib import Path

from screen_activity_logger.domain.models import Worklog, WorklogEntry

_TITLE_MAX_CHARS = 40
_SENTENCE_SEPARATOR = "。"


def step_title(action: str) -> str:
    """actionの第1文をステップ見出しにする（40字超は丸める）。"""
    first_sentence = action.split(_SENTENCE_SEPARATOR)[0].strip()
    if len(first_sentence) <= _TITLE_MAX_CHARS:
        return first_sentence
    return first_sentence[: _TITLE_MAX_CHARS - 1] + "…"


def _format_target(entry: WorklogEntry) -> str | None:
    """操作対象（アプリ・ファイル・位置）の1行表記。"""
    parts = [p for p in (entry.app_guess, entry.resource) if p]
    if not parts:
        return None
    line = "対象: " + " — ".join(parts)
    if entry.location:
        line += f"（{entry.location}）"
    return line


class ManualMarkdownWriter:
    """Worklogをステップ構造の手順書Markdownとして書き出す。"""

    def __init__(self, source_name: str) -> None:
        self._source_name = source_name

    def write(self, worklog: Worklog, output_path: Path) -> None:
        sections = [
            self._to_step(number, entry)
            for number, entry in enumerate(worklog.entries, start=1)
        ]
        text = f"# {self._source_name} 手順書\n\n" + "\n".join(sections)
        output_path.write_text(text, encoding="utf-8")

    @staticmethod
    def _to_step(number: int, entry: WorklogEntry) -> str:
        title = step_title(entry.action)
        body = [f"## Step {number}: {title}", ""]
        if entry.frame_image:
            body.append(f"![{entry.timestamp}]({entry.frame_image})")
            body.append("")
        target = _format_target(entry)
        if target:
            body.append(target)
        if entry.focus:
            body.append(f"👁 {entry.focus}")
        # 見出しと同一のactionは重複掲載しない（1文のactionが大半）
        if entry.action.rstrip("。") != title.rstrip("…"):
            body.append(entry.action)
        # 生OCRは手順書では省略（ノイズ行が多い。一次情報はworklog.jsonlに常在）
        body.append("")
        return "\n".join(body)
