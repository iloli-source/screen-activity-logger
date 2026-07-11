"""ドメインサービス。

TimelineMerger: OCR結果・VLM説明・発話を時系列で統合しWorklogを構築する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from screen_activity_logger.domain.models import (
    ActivityDescription,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)


@dataclass(frozen=True)
class TimelineMerger:
    """OCRテキスト・発話をタイムスタンプで突合し、重複を除去する。

    発話は重複除去後のエントリ時間窓 [t_i, t_{i+1}) に segment.start が
    入るものを紐付ける（先頭エントリより前の発話は先頭に載せる）。
    """

    ocr_match_tolerance_seconds: float

    def merge(
        self,
        descriptions: Iterable[ActivityDescription],
        ocr_texts: Iterable[OcrText],
        transcript_segments: Iterable[TranscriptSegment] = (),
    ) -> Worklog:
        ocr_list = list(ocr_texts)
        ordered = sorted(descriptions, key=lambda d: d.timestamp)
        entries = [
            WorklogEntry(
                timestamp=desc.timestamp,
                action=desc.action,
                app_guess=desc.app_guess,
                ocr_lines=self._nearest_ocr_lines(desc.timestamp, ocr_list),
                resource=desc.resource,
                location=desc.location,
                focus=desc.focus,
            )
            for desc in ordered
        ]
        collapsed = self._collapse_consecutive(entries)
        with_speech = self._attach_speech(collapsed, list(transcript_segments))
        return Worklog.from_entries(with_speech)

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
        # 同じ操作でもリソース（ファイル等）が変われば別エントリとして残す
        collapsed: list[WorklogEntry] = []
        for entry in entries:
            if collapsed and (collapsed[-1].action, collapsed[-1].resource) == (
                entry.action,
                entry.resource,
            ):
                continue
            collapsed.append(entry)
        return tuple(collapsed)

    @staticmethod
    def _attach_speech(
        entries: Sequence[WorklogEntry],
        segments: Sequence[TranscriptSegment],
    ) -> tuple[WorklogEntry, ...]:
        if not entries or not segments:
            return tuple(entries)
        ordered_segments = sorted(segments, key=lambda s: s.start)
        result: list[WorklogEntry] = []
        for index, entry in enumerate(entries):
            window_end = (
                entries[index + 1].timestamp.seconds
                if index + 1 < len(entries)
                else float("inf")
            )
            # 先頭エントリは窓の開始を0秒に広げ、冒頭の発話も拾う
            window_start = 0.0 if index == 0 else entry.timestamp.seconds
            speech = tuple(
                seg.text
                for seg in ordered_segments
                if window_start <= seg.start.seconds < window_end
            )
            result.append(
                WorklogEntry(
                    timestamp=entry.timestamp,
                    action=entry.action,
                    app_guess=entry.app_guess,
                    ocr_lines=entry.ocr_lines,
                    speech=speech,
                )
            )
        return tuple(result)
