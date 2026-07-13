"""作業ログ意味検索のドメインモデル（純粋・依存ゼロ、Issue #5）。

worklog.jsonlの1レコードを「検索文書」（埋め込み対象のラベル付きテキスト＋
表示用メタデータ）に変換する。埋め込みモデルへの依存はここには置かない。
"""

from __future__ import annotations

from dataclasses import dataclass

# OCRは誤認識ノイズを含むため短めに制限（埋め込みの汚染抑制）
_MAX_SPEECH_CHARS = 400
_MAX_OCR_CHARS = 200


@dataclass(frozen=True)
class SearchDocument:
    """検索対象の1文書（worklogエントリ1件に対応）。"""

    doc_id: str
    text: str  # 埋め込み対象のラベル付きテキスト
    source: str  # 動画（出力ディレクトリ）名
    t: str
    t_end: str | None
    duration_seconds: float | None
    app_guess: str | None
    action: str


@dataclass(frozen=True)
class SearchHit:
    """検索結果1件。"""

    document: SearchDocument
    score: float


def build_search_document(record: dict, source: str, doc_id: str) -> SearchDocument:
    """worklog.jsonlの1レコードから検索文書を構築する。

    ラベル付きセクション形式（None/空フィールドは行ごと省略）。
    Issue #18以前の旧形式（t_end/duration_seconds欠損）にも耐える。
    """
    lines: list[str] = []
    action = record.get("action") or ""
    if action:
        lines.append(f"作業: {action}")
    if record.get("app_guess"):
        lines.append(f"アプリ: {record['app_guess']}")
    if record.get("resource"):
        location = record.get("location")
        suffix = f"（{location}）" if location else ""
        lines.append(f"対象: {record['resource']}{suffix}")
    if record.get("focus"):
        lines.append(f"注視: {record['focus']}")
    speech = "。".join(record.get("speech") or ())
    if speech:
        lines.append(f"発話: {speech[:_MAX_SPEECH_CHARS]}")
    ocr = " / ".join(record.get("ocr") or ())
    if ocr:
        lines.append(f"画面: {ocr[:_MAX_OCR_CHARS]}")
    return SearchDocument(
        doc_id=doc_id,
        text="\n".join(lines),
        source=source,
        t=record.get("t") or "00:00:00",
        t_end=record.get("t_end"),
        duration_seconds=record.get("duration_seconds"),
        app_guess=record.get("app_guess"),
        action=action,
    )
