"""アプリケーション層のポート定義（Protocol）。

インフラ層のアダプタはこれらのProtocolを満たすことで差し替え可能になる。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    Worklog,
)


class FrameExtractor(Protocol):
    """動画からフレーム列を抽出する。"""

    def extract(self, video_path: Path) -> Sequence[Frame]: ...


class TextRecognizer(Protocol):
    """フレーム画像から文字を抽出する（OCR層）。"""

    def recognize(self, frame: Frame) -> OcrText: ...


class SceneDescriber(Protocol):
    """フレーム画像から「何をしているか」を説明する（VLM層）。"""

    def describe(self, frame: Frame, ocr: OcrText) -> ActivityDescription: ...


class WorklogWriter(Protocol):
    """Worklogを永続化する（JSONL/Markdown等）。"""

    def write(self, worklog: Worklog, output_path: Path) -> None: ...
