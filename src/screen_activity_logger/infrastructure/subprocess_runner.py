"""外部プロセス実行の共通ヘルパー（4AIレビューR2）。

check=True + capture_output=True の組はエラー理由（stderr）がtracebackに
埋もれて運用不能なため、失敗時にstderr末尾を含む例外へ変換する。
"""

from __future__ import annotations

import subprocess

_STDERR_TAIL_CHARS = 600


def run_captured(
    command: list[str], timeout_seconds: float, text: bool = False
) -> subprocess.CompletedProcess:
    """capture付き実行。失敗時はstderr末尾を含むRuntimeErrorにする。"""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=text,
            timeout=timeout_seconds,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        tail = (stderr or "").strip()[-_STDERR_TAIL_CHARS:]
        raise RuntimeError(
            f"{command[0]} が失敗しました（exit {error.returncode}）: {tail}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{command[0]} が{timeout_seconds:.0f}秒以内に完了しませんでした"
        ) from error
