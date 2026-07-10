"""application/use_cases GenerateWorklog のユニットテスト（Cycle D: RED）。

外部技術はすべてフェイクポートで差し替える（クリーンアーキテクチャの検証）。
"""

from pathlib import Path

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    VideoTimestamp,
)
from screen_activity_logger.domain.services import TimelineMerger


def _frame(seconds: float, is_keyframe: bool) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds),
        path=Path(f"/tmp/f_{int(seconds):06d}.png"),
        is_keyframe=is_keyframe,
    )


class FakeFrameExtractor:
    def __init__(self, frames: list[Frame]) -> None:
        self._frames = frames

    def extract(self, video_path: Path) -> list[Frame]:
        return self._frames


class FakeTextRecognizer:
    def __init__(self) -> None:
        self.recognized_frames: list[Frame] = []

    def recognize(self, frame: Frame) -> OcrText:
        self.recognized_frames.append(frame)
        return OcrText(
            timestamp=frame.timestamp,
            lines=(f"text@{frame.timestamp.seconds}",),
        )


class FakeSceneDescriber:
    def __init__(self) -> None:
        self.described: list[tuple[Frame, OcrText]] = []

    def describe(self, frame: Frame, ocr: OcrText) -> ActivityDescription:
        self.described.append((frame, ocr))
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業@{frame.timestamp.seconds}",
            app_guess="TestApp",
        )


def _use_case(
    frames: list[Frame],
) -> tuple[GenerateWorklog, FakeTextRecognizer, FakeSceneDescriber]:
    recognizer = FakeTextRecognizer()
    describer = FakeSceneDescriber()
    use_case = GenerateWorklog(
        frame_extractor=FakeFrameExtractor(frames),
        text_recognizer=recognizer,
        scene_describer=describer,
        merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
    )
    return use_case, recognizer, describer


class TestGenerateWorklog:
    def test_ocr_is_applied_to_all_frames(self) -> None:
        frames = [_frame(1.0, False), _frame(2.0, True), _frame(3.0, False)]
        use_case, recognizer, _ = _use_case(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        assert len(recognizer.recognized_frames) == 3

    def test_vlm_describes_only_keyframes(self) -> None:
        frames = [_frame(1.0, False), _frame(2.0, True), _frame(3.0, True)]
        use_case, _, describer = _use_case(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        described_seconds = [f.timestamp.seconds for f, _ in describer.described]
        assert described_seconds == [2.0, 3.0]

    def test_describer_receives_ocr_context_of_same_frame(self) -> None:
        frames = [_frame(2.0, True)]
        use_case, _, describer = _use_case(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        _, ocr = describer.described[0]
        assert ocr.lines == ("text@2.0",)

    def test_returns_merged_worklog_with_ocr_lines(self) -> None:
        frames = [_frame(2.0, True)]
        use_case, _, _ = _use_case(frames)

        worklog = use_case.execute(Path("/tmp/video.mp4"))

        entry = worklog.entries[0]
        assert entry.action == "作業@2.0"
        assert entry.ocr_lines == ("text@2.0",)

    def test_empty_frames_give_empty_worklog(self) -> None:
        use_case, _, _ = _use_case([])

        worklog = use_case.execute(Path("/tmp/video.mp4"))

        assert worklog.entries == ()
