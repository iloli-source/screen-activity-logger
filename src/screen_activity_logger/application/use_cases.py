"""ユースケース: 動画から作業ログを生成する。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from screen_activity_logger.application.ports import (
    FrameComparator,
    FrameExtractor,
    SceneDescriber,
    TextRecognizer,
)
from screen_activity_logger.domain.models import Frame, OcrText, Worklog
from screen_activity_logger.domain.services import TimelineMerger


@dataclass(frozen=True)
class GenerateWorklog:
    """間引きポリシー:
    - VLMはキーフレームのみ疎適用
    - OCRは原則全フレーム。ただしframe_comparator注入時は、直前OCR済み
      フレームと類似するフレームの認識をスキップし前回結果を再利用する
      （実測: 静止画面ではOCRが処理時間の72%を占めたため）
    - 先頭フレームとキーフレームは常にOCRする
    """

    frame_extractor: FrameExtractor
    text_recognizer: TextRecognizer
    scene_describer: SceneDescriber
    merger: TimelineMerger
    frame_comparator: FrameComparator | None = None

    def execute(self, video_path: Path) -> Worklog:
        frames = self.frame_extractor.extract(video_path)
        ocr_by_frame = self._recognize_with_skip(frames)
        descriptions = [
            self.scene_describer.describe(frame, ocr_by_frame[frame.timestamp])
            for frame in frames
            if frame.is_keyframe
        ]
        return self.merger.merge(
            descriptions=descriptions, ocr_texts=ocr_by_frame.values()
        )

    def _recognize_with_skip(self, frames) -> dict:
        ocr_by_frame = {}
        last_recognized: Frame | None = None
        last_lines: tuple[str, ...] = ()
        for frame in frames:
            if self._should_recognize(frame, last_recognized):
                ocr = self.text_recognizer.recognize(frame)
                last_recognized = frame
                last_lines = ocr.lines
            else:
                ocr = OcrText(timestamp=frame.timestamp, lines=last_lines)
            ocr_by_frame[frame.timestamp] = ocr
        return ocr_by_frame

    def _should_recognize(self, frame: Frame, last: Frame | None) -> bool:
        if last is None or frame.is_keyframe or self.frame_comparator is None:
            return True
        return not self.frame_comparator.are_similar(last, frame)
