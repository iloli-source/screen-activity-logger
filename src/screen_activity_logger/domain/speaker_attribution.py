"""映像ベース話者特定（純粋・依存ゼロ、Issue #10）。

会議モードの話者ビュー切替（シーン変化）を「話者交代のタイムスタンプ信号」
として再利用し、OCRが読んだ参加者名ラベル×ASRセグメント時刻の突き合わせで
追加モデルゼロの実名話者特定を行う。

方針: precision優先の保守的設計。帰属できないセグメントは speaker=None
（従来表示にフォールバック）。誤帰属だけを恐れ、未帰属は恐れない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp

# 行全体が漢字氏名（2-5字、姓名区切りの中黒/スペース1個まで許容）
_KANJI_NAME_PATTERN = re.compile(
    r"^[一-鿿]{1,4}[・\s　]?[一-鿿]{1,4}$"
)
# 読み仮名括弧（全半角）: 二村紀花(ニムラノリカ)
_FURIGANA_PATTERN = re.compile(r"[（(][ァ-ヴー]+[）)]$")
# 英大文字イニシャル（2字ちょうどのみ。1字/3字以上は誤検出過多）
_INITIALS_PATTERN = re.compile(r"^[A-Z]{2}$")

# Meet/Zoom UI語・記録ボット名（正規化=大文字化・空白除去後に照合）
_UI_DENYLIST = frozenset(
    {
        "MINOTETAKER",
        "AINOTETAKER",
        "NOTETAKER",
        "YOU",
        "あなた",
        "ミーティング",
        "参加者",
        "全員",
    }
)
# 英字2字のUI略語（イニシャルと衝突するもの）
_INITIALS_DENYLIST = frozenset({"AI", "HD", "CC", "ON", "PC", "TV", "OK", "NG"})

_KANJI_NAME_MIN_LENGTH = 2
_KANJI_NAME_MAX_LENGTH = 5


def extract_name_labels(lines: Iterable[str]) -> tuple[str, ...]:
    """OCR行から参加者名候補を抽出する（行全体マッチのみ、保守的）。"""
    names: list[str] = []
    for line in lines:
        name = _parse_name_line(line.strip())
        if name is not None and name not in names:
            names.append(name)
    return tuple(names)


def _parse_name_line(line: str) -> str | None:
    if not line:
        return None
    normalized_for_deny = re.sub(r"[\s　]", "", line).upper()
    if normalized_for_deny in _UI_DENYLIST:
        return None
    # (b) 読み仮名括弧を剥がす
    stripped = _FURIGANA_PATTERN.sub("", line).strip()
    # (c) 末尾「さん」除去
    if stripped.endswith("さん") and len(stripped) > 2:
        stripped = stripped[:-2]
    # (d) 英大文字イニシャル
    if _INITIALS_PATTERN.match(stripped):
        return None if stripped in _INITIALS_DENYLIST else stripped
    # (a) 漢字氏名
    kanji_only = re.sub(r"[・\s　]", "", stripped)
    if (
        _KANJI_NAME_PATTERN.match(stripped)
        and _KANJI_NAME_MIN_LENGTH <= len(kanji_only) <= _KANJI_NAME_MAX_LENGTH
    ):
        return stripped
    return None


@dataclass(frozen=True)
class SpeakerAttributionConfig:
    """話者帰属のパラメータ（CLIで上書き可能）。"""

    # Meetのビュー切替は発話開始より遅れる: 開始直後の切替を許容する窓
    switch_tolerance_seconds: float = 3.0
    # OCR行数がこれを超えるkeyframeは「画面共有中」とみなし帰属に使わない
    # （共有文書内の人名を参加者と誤認する事故の防衛）
    max_lines_for_attribution: int = 8


@dataclass(frozen=True)
class SpeakerObservation:
    """keyframe1枚から観測した参加者名ラベル。"""

    timestamp: VideoTimestamp
    names: tuple[str, ...]
    ocr_line_count: int = 0


def attribute_speakers(
    segments: Sequence[TranscriptSegment],
    observations: Sequence[SpeakerObservation],
    config: SpeakerAttributionConfig,
) -> tuple[TranscriptSegment, ...]:
    """各セグメントに話者を帰属する（Issue #10の真理値表）。

    有効な観測（セグメント開始時点で最新）のnamesがちょうど1名（話者ビュー）
    なら高信頼で帰属。0名/複数名（グリッド・共有）・観測なし・行数ガード超過は
    None（従来表示）。開始直後 [start, start+tolerance] の切替は切替後を採用。
    """
    ordered = sorted(observations, key=lambda o: o.timestamp)
    result: list[TranscriptSegment] = []
    for segment in segments:
        observation = _observation_for(
            ordered, segment.start.seconds, config.switch_tolerance_seconds
        )
        speaker = _speaker_from(observation, config)
        result.append(
            replace(segment, speaker=speaker) if speaker else segment
        )
    return tuple(result)


def _observation_for(
    ordered: Sequence[SpeakerObservation],
    start_seconds: float,
    tolerance: float,
) -> SpeakerObservation | None:
    """セグメント開始時点で有効な観測。開始直後の切替は切替後を優先する。"""
    current: SpeakerObservation | None = None
    for observation in ordered:
        if observation.timestamp.seconds <= start_seconds:
            current = observation
        elif observation.timestamp.seconds <= start_seconds + tolerance:
            return observation  # 発話開始直後にビューが切り替わったケース
        else:
            break
    return current


def _speaker_from(
    observation: SpeakerObservation | None,
    config: SpeakerAttributionConfig,
) -> str | None:
    if observation is None:
        return None
    if observation.ocr_line_count > config.max_lines_for_attribution:
        return None  # 画面共有ガード
    if len(observation.names) != 1:
        return None  # グリッド/ラベル不検出は帰属しない
    return observation.names[0]


def format_speech_line(segment: TranscriptSegment) -> str:
    """発話行の表示形。話者があれば「話者: テキスト」。"""
    if segment.speaker:
        return f"{segment.speaker}: {segment.text}"
    return segment.text
