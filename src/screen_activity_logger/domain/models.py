"""ドメインモデル（値オブジェクト・集約）。

クリーンアーキテクチャのdomain層。外部ライブラリへの依存を持たない。
全モデルはイミュータブル（frozen dataclass）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, order=True)
class VideoTimestamp:
    """動画先頭からの経過秒を表す値オブジェクト。"""

    seconds: float

    def __post_init__(self) -> None:
        if self.seconds < 0:
            raise ValueError(f"seconds must be >= 0, got {self.seconds}")

    def __str__(self) -> str:
        total = int(self.seconds)
        hours, rest = divmod(total, 3600)
        minutes, secs = divmod(rest, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True)
class Frame:
    """抽出されたフレーム1枚。"""

    timestamp: VideoTimestamp
    path: Path
    is_keyframe: bool


@dataclass(frozen=True)
class OcrText:
    """あるタイムスタンプのフレームから抽出されたテキスト群。"""

    timestamp: VideoTimestamp
    lines: tuple[str, ...]

    def normalized_lines(self) -> tuple[str, ...]:
        """空白除去し、空行を除いた行を返す。"""
        stripped = (line.strip() for line in self.lines)
        return tuple(line for line in stripped if line)


@dataclass(frozen=True)
class ActivityDescription:
    """VLMによる「この画面で何をしているか」の説明。

    resource: 開いているファイル名・URL・文書名（一次情報からの抽出 or VLM推測）
    location: リソース内の位置（シート・スライド・ページ・見出し等）
    focus: どこを見て判断しているか（VLM推測。視線情報ではない）
    """

    timestamp: VideoTimestamp
    action: str
    app_guess: str | None
    resource: str | None = None
    location: str | None = None
    focus: str | None = None

    def __post_init__(self) -> None:
        if not self.action.strip():
            raise ValueError("action must not be empty")


@dataclass(frozen=True)
class TranscriptSegment:
    """音声認識による発話1区間。"""

    start: VideoTimestamp
    end: VideoTimestamp
    text: str

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        if not self.text.strip():
            raise ValueError("text must not be empty")


@dataclass(frozen=True)
class WorklogEntry:
    """作業ログの1エントリ（OCR・VLM説明・発話の統合結果）。"""

    timestamp: VideoTimestamp
    action: str
    app_guess: str | None
    ocr_lines: tuple[str, ...]
    speech: tuple[str, ...] = ()
    resource: str | None = None
    location: str | None = None
    focus: str | None = None


@dataclass(frozen=True)
class Worklog:
    """作業ログ全体を表す集約ルート。エントリは常に時系列順。"""

    entries: tuple[WorklogEntry, ...] = field(default_factory=tuple)

    @classmethod
    def from_entries(cls, entries: Iterable[WorklogEntry]) -> Worklog:
        ordered = tuple(sorted(entries, key=lambda e: e.timestamp))
        return cls(entries=ordered)
