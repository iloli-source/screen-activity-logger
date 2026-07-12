"""resource昇格時の浄化（純粋・依存ゼロ、Issue #17）。

見出し（resource/location）への昇格値のみを浄化する。
一次情報（生OCR行・JSONLのocrキー）は無加工で保持する（Issue #12の不変条件）。
"""

from __future__ import annotations

# 見出しに表示するURLの上限（超過は…付き切り詰め。ドメインは常に残る）
_MAX_URL_DISPLAY_LENGTH = 60


def url_domain(url: str) -> str | None:
    """URLからドメイン部分を取り出す（スキーム除去→最初の/まで）。"""
    core = url.split("://", 1)[-1]
    domain = core.split("/", 1)[0]
    return domain if "." in domain else None


def sanitize_url(url: str) -> str:
    """URLからクエリ・フラグメントを除去し、表示長を制限する。

    クエリ文字列はOCR文字化けの主戦場であり、除去が浄化と
    プライバシー低減（検索語の見出し露出防止）を兼ねる。
    """
    core = url.split("?", 1)[0].split("#", 1)[0].rstrip(".,;:")
    if len(core) <= _MAX_URL_DISPLAY_LENGTH:
        return core
    return core[: _MAX_URL_DISPLAY_LENGTH - 1] + "…"
