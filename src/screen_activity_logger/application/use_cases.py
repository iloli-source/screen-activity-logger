"""ユースケース: 動画から作業ログを生成する。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from screen_activity_logger.application.ports import (
    FrameExtractor,
    SceneDescriber,
    TextRecognizer,
)
from screen_activity_logger.domain.models import Worklog
from screen_activity_logger.domain.services import TimelineMerger


@dataclass(frozen=True)
class GenerateWorklog:
    """間引きポリシー: OCRは全フレームに密適用、VLMはキーフレームのみ疎適用。"""

    frame_extractor: FrameExtractor
    text_recognizer: TextRecognizer
    scene_describer: SceneDescriber
    merger: TimelineMerger

    def execute(self, video_path: Path) -> Worklog:
        frames = self.frame_extractor.extract(video_path)

        ocr_by_frame = {
            frame.timestamp: self.text_recognizer.recognize(frame)
            for frame in frames
        }
        descriptions = [
            self.scene_describer.describe(frame, ocr_by_frame[frame.timestamp])
            for frame in frames
            if frame.is_keyframe
        ]
        return self.merger.merge(
            descriptions=descriptions, ocr_texts=ocr_by_frame.values()
        )
