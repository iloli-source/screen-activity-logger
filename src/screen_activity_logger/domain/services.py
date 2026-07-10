"""ドメインサービス。

TimelineMerger: OCR結果とVLM説明を時系列で統合しWorklogを構築する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from screen_activity_logger.domain.models import (
    ActivityDescription,
    OcrText,
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)


@dataclass(frozen=True)
class TimelineMerger:
    """OCRテキストとVLM説明をタイムスタンプで突合し、重複を除去する。"""

    ocr_match_tolerance_seconds: float

    def merge(
        self,
        descriptions: Iterable[ActivityDescription],
        ocr_texts: Iterable[OcrText],
    ) -> Worklog:
        ocr_list = list(ocr_texts)
        ordered = sorted(descriptions, key=lambda d: d.timestamp)
        entries = [
            WorklogEntry(
                timestamp=desc.timestamp,
                action=desc.action,
                app_guess=desc.app_guess,
                ocr_lines=self._nearest_ocr_lines(desc.timestamp, ocr_list),
            )
            for desc in ordered
        ]
        return Worklog.from_entries(self._collapse_consecutive(entries))

    def _nearest_ocr_lines(
        self, timestamp: VideoTimestamp, ocr_texts: Sequence[OcrText]
    ) -> tuple[str, ...]:
        candidates = [
            ocr
            for ocr in ocr_texts
            if abs(ocr.timestamp.seconds - timestamp.seconds)
            <= self.ocr_match_tolerance_seconds
        ]
        if not candidates:
            return ()
        nearest = min(
            candidates, key=lambda ocr: abs(ocr.timestamp.seconds - timestamp.seconds)
        )
        return nearest.normalized_lines()

    @staticmethod
    def _collapse_consecutive(
        entries: Sequence[WorklogEntry],
    ) -> tuple[WorklogEntry, ...]:
        collapsed: list[WorklogEntry] = []
        for entry in entries:
            if collapsed and collapsed[-1].action == entry.action:
                continue
            collapsed.append(entry)
        return tuple(collapsed)
