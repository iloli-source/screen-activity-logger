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
    if segment.no_speech_prob is not None and segment.avg_logprob is not None:
        # 両シグナルあり（mlx/faster）: 本家Whisper慣例のAND条件
        return not (
            segment.no_speech_prob > config.no_speech_threshold
            and segment.avg_logprob < config.logprob_threshold
        )
    if segment.avg_logprob is not None:
        # logprobのみ（whisper.cpp）: 単独でも極端な低信頼は除去
        # （平均トークン確率 e^-1≈37% 未満は実発話でまず出ない、4AIレビューR1）
        return segment.avg_logprob >= config.logprob_threshold
    return True  # 判断材料なし＝保持（後方互換）


def filter_segments(
    segments: Sequence[TranscriptSegment], config: SpeechFilterConfig
) -> tuple[TranscriptSegment, ...]:
    """順序を保持して信頼できるセグメントのみ残す。"""
    return tuple(seg for seg in segments if is_reliable_segment(seg, config))


def collapse_repeated_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    """連続する同一発話行を1行に圧縮する（Issue #3）。

    ASRは相槌や言い直しで同一テキストを連続出力しやすく、そのまま列挙すると
    可読性を下げる。間に別発話を挟む反復は会話の流れとして意味を持つため
    保持する（全体dedupはしない）。
    """
    collapsed: list[str] = []
    for line in lines:
        if not collapsed or collapsed[-1] != line:
            collapsed.append(line)
    return tuple(collapsed)
