"""worklog.jsonlの読み込み（検索層の入力、Issue #5）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def read_worklog_records(jsonl_path: Path) -> Iterator[dict]:
    """worklog.jsonlをレコード（dict）列として読む。空行はスキップ。

    壊れた行はどのファイルの何行目かを明示して失敗する（静かに欠落させない）。
    """
    for line_number, line in enumerate(
        jsonl_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"worklog.jsonlの解析に失敗: {jsonl_path}:{line_number}: {error}"
            ) from error
