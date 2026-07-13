"""発話要旨付与のユニットテスト（Issue #23 S1: RED）。

フェイクSummarizerでユースケースの配線（対象選定・例外継続）を検証する。
"""

from pathlib import Path

from screen_activity_logger.application.use_cases import (
    MIN_SPEECH_LINES_FOR_SUMMARY,
    GenerateWorklog,
)
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
)
from screen_activity_logger.domain.services import TimelineMerger


class FakeExtractor:
    def extract(self, video_path: Path):
        return (
            Frame(
                timestamp=VideoTimestamp(seconds=0.0),
                path=Path("/tmp/f.png"),
                is_keyframe=True,
            ),
        )


class FakeRecognizer:
    def recognize(self, frame):
        return OcrText(timestamp=frame.timestamp, lines=())


class FakeDescriber:
    def describe(self, frame, ocr, speech=()):
        return ActivityDescription(
            timestamp=frame.timestamp, action="会議中", app_guess="Chrome"
        )


class FakeSummarizer:
    def __init__(self, result: str | None = "要旨です") -> None:
        self.result = result
        self.calls: list[tuple[str, ...]] = []

    def summarize(self, lines: tuple[str, ...]) -> str | None:
        self.calls.append(lines)
        return self.result


class RaisingSummarizer:
    def summarize(self, lines: tuple[str, ...]) -> str | None:
        raise RuntimeError("サーバー停止")


def _segments(*texts: str) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            start=VideoTimestamp(seconds=1.0 + i),
            end=VideoTimestamp(seconds=2.0 + i),
            text=text,
        )
        for i, text in enumerate(texts)
    ]


def _use_case(summarizer) -> GenerateWorklog:
    return GenerateWorklog(
        frame_extractor=FakeExtractor(),
        text_recognizer=FakeRecognizer(),
        scene_describer=FakeDescriber(),
        merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        speech_summarizer=summarizer,
    )


class TestSpeechSummaryAttachment:
    def test_rich_speech_entry_gets_summary(self) -> None:
        summarizer = FakeSummarizer("案件の進捗を報告している")
        use_case = _use_case(summarizer)

        worklog = use_case.execute(
            Path("v.mp4"),
            precomputed_segments=_segments("進捗ですが", "8割です", "来週完了予定"),
        )

        assert worklog.entries[0].summary == "案件の進捗を報告している"
        assert summarizer.calls == [("進捗ですが", "8割です", "来週完了予定")]

    def test_sparse_speech_entry_is_skipped(self) -> None:
        summarizer = FakeSummarizer()
        use_case = _use_case(summarizer)

        worklog = use_case.execute(
            Path("v.mp4"),
            precomputed_segments=_segments("はい", "お願いします"),
        )

        assert len(worklog.entries[0].speech) < MIN_SPEECH_LINES_FOR_SUMMARY
        assert worklog.entries[0].summary is None
        assert summarizer.calls == []

    def test_summarizer_error_keeps_entry(self, capsys) -> None:
        use_case = _use_case(RaisingSummarizer())

        worklog = use_case.execute(
            Path("v.mp4"),
            precomputed_segments=_segments("あ", "い", "う", "え"),
        )

        assert worklog.entries[0].summary is None
        assert worklog.entries[0].action == "会議中"  # エントリ自体は保持
        assert "要旨生成失敗" in capsys.readouterr().out

    def test_no_summarizer_leaves_none(self) -> None:
        use_case = _use_case(None)

        worklog = use_case.execute(
            Path("v.mp4"),
            precomputed_segments=_segments("あ", "い", "う", "え"),
        )

        assert worklog.entries[0].summary is None
