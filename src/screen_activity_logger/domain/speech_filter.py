"""ASR幻覚フィルタ（純粋・依存ゼロ、Issue #14）。

kotoba-whisperが無音・雑音区間で幻覚する「!」等のノイズを除去する。
主兵装は記号のみ判定（mlx_whisper内部の確率チェックをすり抜けた実績があるため）、
no_speech_prob/avg_logprob のAND条件は文章型幻覚
（「ご視聴ありがとうございました」等）への第二防衛線。

確率値は30秒デコード窓単位で同一窓の全セグメントが共有するため、
OR条件にすると雑音窓の正常発話を巻き込む。本家Whisperの無音判定と同じ
AND（no_speech_prob > 閾値 かつ avg_logprob < 閾値）で保守的に除去する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from screen_activity_logger.domain.models import TranscriptSegment


@dataclass(frozen=True)
class SpeechFilterConfig:
    """幻覚フィルタのパラメータ（CLIで上書き可能）。既定値はWhisper本家慣例。"""

    no_speech_threshold: float = 0.6
    logprob_threshold: float = -1.0


def has_verbal_content(text: str) -> bool:
    """英数字・かな・漢字を1文字でも含むか（str.isalnumはUnicode対応）。"""
    return any(ch.isalnum() for ch in text)


def is_reliable_segment(
    segment: TranscriptSegment, config: SpeechFilterConfig
) -> bool:
    """セグメントを保持すべきかの真理値表（Issue #14）。"""
    if not has_verbal_content(segment.text):
        return False  # 記号のみ＝幻覚（確率と無関係に除去）
    if segment.no_speech_prob is None or segment.avg_logprob is None:
        return True  # 判断材料なし＝保持（後方互換）
    return not (
        segment.no_speech_prob > config.no_speech_threshold
        and segment.avg_logprob < config.logprob_threshold
    )


def filter_segments(
    segments: Sequence[TranscriptSegment], config: SpeechFilterConfig
) -> tuple[TranscriptSegment, ...]:
    """順序を保持して信頼できるセグメントのみ残す。"""
    return tuple(seg for seg in segments if is_reliable_segment(seg, config))
