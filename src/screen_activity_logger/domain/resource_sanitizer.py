"""resource昇格時の浄化（純粋・依存ゼロ、Issue #17）。

見出し（resource/location）への昇格値のみを浄化する。
一次情報（生OCR行・JSONLのocrキー）は無加工で保持する（Issue #12の不変条件）。
"""

from __future__ import annotations

import re

# 見出しに表示するURLの上限（超過は…付き切り詰め。ドメインは常に残る）
_MAX_URL_DISPLAY_LENGTH = 60

# VLMが対象名を読めず説明文で埋めたシグナル（実録画: Web page titled "Ureya hasde"）
_VLM_BOILERPLATE_PATTERN = re.compile(
    r"^(?:a |the )?(?:web ?page|screenshot|untitled|unknown|browser (?:tab|window))\b",
    re.IGNORECASE,
)

# 低情報断片の判定: 区切り記号があれば正当な短い名前（a.py等）とみなす
_SEPARATOR_CHARS = set("./:")
_MAX_FRAGMENT_LENGTH = 4


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


def clean_vlm_resource(value: str | None) -> str | None:
    """VLM由来resourceの品質ゲート（Issue #17 S3）。棄却はNone。

    (a) 英語ボイラープレート: VLMが対象名を読めず説明文で埋めたシグナル。
        中身もOCRゴミの復唱である実データを確認済みのため丸ごと棄却。
    (b) 低情報断片: 4文字以下・ASCII英数のみ・区切り記号なし（IRW/EZEO型）。
        短いファイル名は拡張子のドットを持ち、日本語は無条件で通るため
        正当な値は落とさない。
    """
    if value is None:
        return None
    if _VLM_BOILERPLATE_PATTERN.match(value):
        return None
    is_short_ascii_alnum = (
        len(value) <= _MAX_FRAGMENT_LENGTH
        and value.isascii()
        and value.isalnum()
        and not (set(value) & _SEPARATOR_CHARS)
    )
    if is_short_ascii_alnum:
        return None
    return value
