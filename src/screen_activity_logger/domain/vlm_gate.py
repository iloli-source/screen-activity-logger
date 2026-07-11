"""VLM実行ゲート（純粋・依存ゼロ）。

3者協議（Issue #13）で採択:
「前回VLMを呼んだ時から画面上の文字が意味的に変わったか」を
トークン集合Jaccardで判定する主ゲート。時間はmin_gap/max_gapの安全弁のみ。
話者ビュー切替（文字不変）はスキップし、画面共有開始・操作ステップ
（文字が変わる）は発火する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# 除去する行: 2文字以下（OCRノイズ）・数字/時刻のみ（時計・参加者数）
_MIN_LINE_LENGTH = 3
_DIGIT_LIKE = set("0123456789:./- ")


@dataclass(frozen=True)
class VlmGateConfig:
    """VLMゲートのパラメータ（CLIで上書き可能）。"""

    jaccard_skip_threshold: float = 0.85
    min_gap_seconds: float = 10.0
    max_gap_seconds: float = 120.0
    min_token_union: int = 3


def normalize_ocr_tokens(lines: Iterable[str]) -> frozenset[str]:
    """OCR行をノイズ除去し、空白分割のトークン集合にする。

    行分割のゆれ（PaddleOCRの非決定性）とMeet UIノイズ
    （時計・参加者数・記号断片）への耐性を持たせる。
    """
    tokens: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if len(stripped) < _MIN_LINE_LENGTH:
            continue
        if set(stripped) <= _DIGIT_LIKE:
            continue
        tokens.update(stripped.split())
    return frozenset(tokens)


def token_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """トークン集合のJaccard類似度。両方空は1.0（完全一致扱い）。"""
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union)


def should_describe(
    now_seconds: float,
    tokens: frozenset[str],
    last_vlm_seconds: float | None,
    last_vlm_tokens: frozenset[str] | None,
    config: VlmGateConfig,
) -> bool:
    """このキーフレームでVLMを呼ぶべきかの真理値表（Issue #13）。"""
    if last_vlm_seconds is None or last_vlm_tokens is None:
        return True  # 初回は必ず
    elapsed = now_seconds - last_vlm_seconds
    if elapsed >= config.max_gap_seconds:
        return True  # 安全弁: 完全無記録を防ぐ強制VLM
    if elapsed < config.min_gap_seconds:
        return False  # debounce
    if bool(tokens) != bool(last_vlm_tokens):
        return True  # 文字の出現/消滅＝画面共有の開始/終了
    if len(tokens | last_vlm_tokens) < config.min_token_union:
        return False  # 低情報: Jaccard無効、時間ガードに委ねる
    return token_jaccard(tokens, last_vlm_tokens) < config.jaccard_skip_threshold
