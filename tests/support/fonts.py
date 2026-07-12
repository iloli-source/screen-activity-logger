"""テスト用の日本語フォント探索（マルチプラットフォーム、Issue #16）。"""

from __future__ import annotations

from pathlib import Path

_CANDIDATES = (
    # macOS
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
    # Windows
    Path("C:/Windows/Fonts/meiryo.ttc"),
    Path("C:/Windows/Fonts/YuGothM.ttc"),
    Path("C:/Windows/Fonts/msgothic.ttc"),
    # Linux (Noto Sans CJK)
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
)


def find_jp_font() -> Path | None:
    """日本語グリフを持つフォントを探す。見つからなければNone（テストはskip）。"""
    for candidate in _CANDIDATES:
        if candidate.exists():
            return candidate
    return None
