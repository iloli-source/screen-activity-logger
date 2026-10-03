"""ファイルの原子的な書き込み（Issue #32）。

出力先を直接上書きすると、書き込み途中でプロセスが止まったときに
切り詰められたファイルが残る（JSONLは行単位のため、途中までの出力は
「短いが正常なログ」と区別できない）。同じディレクトリの一時ファイルへ
書き切ってから os.replace で差し替え、読み手には旧内容か新内容の
どちらか一方だけを見せる。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Path.write_text の原子版（改行変換の挙動は write_text と同じ）。"""
    temp_path = _temp_path(path)
    try:
        with open(temp_path, "x", encoding=encoding) as file:
            file.write(text)
            _sync(file)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Path.write_bytes の原子版。"""
    temp_path = _temp_path(path)
    try:
        with open(temp_path, "xb") as file:
            file.write(data)
            _sync(file)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _temp_path(path: Path) -> Path:
    # os.replace が原子的なのは同一ファイルシステム内のみ → 出力先と同じ場所に作る
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def _sync(file) -> None:
    """差し替え前に内容をディスクへ落とす（電源断で空ファイルに差し替わらない）。"""
    file.flush()
    os.fsync(file.fileno())
