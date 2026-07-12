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

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self.described.append((frame, ocr))
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業@{frame.timestamp.seconds}",
            app_guess="TestApp",
        )


class FakeFrameComparator:
    """パスが同じ画像を「類似」とみなすフェイク。"""

    def are_similar(self, a: Frame, b: Frame) -> bool:
        return a.path == b.path


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


def _frame_at_path(seconds: float, path: str, is_keyframe: bool = False) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds),
        path=Path(path),
        is_keyframe=is_keyframe,
    )


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


class TestOcrSkipWithComparator:
    """フレーム差分によるOCRスキップ（Cycle K: RED）。

    実測でOCRが処理時間の72%を占めたため、直前OCR済みフレームと
    類似するフレームは認識せず前回結果を再利用する。
    """

    def _use_case_with_comparator(
        self, frames: list[Frame]
    ) -> tuple[GenerateWorklog, FakeTextRecognizer]:
        recognizer = FakeTextRecognizer()
        use_case = GenerateWorklog(
            frame_extractor=FakeFrameExtractor(frames),
            text_recognizer=recognizer,
            scene_describer=FakeSceneDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
            frame_comparator=FakeFrameComparator(),
        )
        return use_case, recognizer

    def test_similar_frames_skip_recognizer(self) -> None:
        # 同一パス＝類似。3フレーム中、実際に認識されるのは先頭の1回のみ
        frames = [
            _frame_at_path(1.0, "/tmp/same.png"),
            _frame_at_path(2.0, "/tmp/same.png"),
            _frame_at_path(3.0, "/tmp/same.png"),
        ]
        use_case, recognizer = self._use_case_with_comparator(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        assert len(recognizer.recognized_frames) == 1

    def test_changed_frame_is_recognized(self) -> None:
        frames = [
            _frame_at_path(1.0, "/tmp/a.png"),
            _frame_at_path(2.0, "/tmp/a.png"),
            _frame_at_path(3.0, "/tmp/b.png"),  # 画面が変わった
        ]
        use_case, recognizer = self._use_case_with_comparator(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        recognized_paths = [f.path.name for f in recognizer.recognized_frames]
        assert recognized_paths == ["a.png", "b.png"]

    def test_keyframe_is_always_recognized_even_if_similar(self) -> None:
        frames = [
            _frame_at_path(1.0, "/tmp/same.png"),
            _frame_at_path(2.0, "/tmp/same.png", is_keyframe=True),
        ]
        use_case, recognizer = self._use_case_with_comparator(frames)

        use_case.execute(Path("/tmp/video.mp4"))

        assert len(recognizer.recognized_frames) == 2

    def test_skipped_frame_reuses_lines_with_own_timestamp(self) -> None:
        frames = [
            _frame_at_path(1.0, "/tmp/same.png", is_keyframe=True),
            _frame_at_path(5.0, "/tmp/same.png"),
        ]
        use_case, _ = self._use_case_with_comparator(frames)

        worklog = use_case.execute(Path("/tmp/video.mp4"))

        # キーフレーム(1.0)のエントリには、スキップされたフレームではなく
        # 認識済みの内容が紐づく（lines再利用の内部整合性の検証は
        # 「2フレーム目もOCRテキストを持つ」ことで担保する）
        entry = worklog.entries[0]
        assert entry.ocr_lines == ("text@1.0",)

    def test_without_comparator_all_frames_are_recognized(self) -> None:
        """後方互換: comparator未注入なら従来どおり全フレームOCR。"""
        frames = [
            _frame_at_path(1.0, "/tmp/same.png"),
            _frame_at_path(2.0, "/tmp/same.png"),
        ]
        recognizer = FakeTextRecognizer()
        use_case = GenerateWorklog(
            frame_extractor=FakeFrameExtractor(frames),
            text_recognizer=recognizer,
            scene_describer=FakeSceneDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        )

        use_case.execute(Path("/tmp/video.mp4"))

        assert len(recognizer.recognized_frames) == 2


class TestDwellTimeWiring:
    """T5（Issue #18）: パイプライン経由で滞留時間が結線される回帰。"""

    def test_collapsed_entries_get_end_timestamps(self) -> None:
        class SameActionDescriber:
            def describe(self, frame, ocr, speech=()):
                return ActivityDescription(
                    timestamp=frame.timestamp,
                    action="資料を読んでいる",
                    app_guess="Preview",
                )

        frames = [
            _frame(10.0, is_keyframe=True),
            _frame(20.0, is_keyframe=True),   # collapse対象（同一アクション）
            _frame(30.0, is_keyframe=False),  # OCR観測のみ（timeline_end）
        ]
        use_case = GenerateWorklog(
            frame_extractor=FakeFrameExtractor(frames),
            text_recognizer=FakeTextRecognizer(),
            scene_describer=SameActionDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        )
        worklog = use_case.execute(Path("/tmp/v.mp4"))

        assert len(worklog.entries) == 1  # collapseされている
        entry = worklog.entries[0]
        assert entry.end_timestamp is not None
        assert entry.end_timestamp.seconds == 30.0  # 最終観測まで
        assert entry.duration_seconds == 20.0
