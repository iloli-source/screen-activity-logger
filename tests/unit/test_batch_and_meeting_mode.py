"""会議モード・precomputed_segments・バッチ2フェーズのテスト（Cycle T-V: RED）。"""

from pathlib import Path

from screen_activity_logger.application.use_cases import (
    BatchGenerateWorklog,
    GenerateWorklog,
)
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
    Worklog,
)
from screen_activity_logger.domain.services import TimelineMerger


def _frame(seconds: float, is_keyframe: bool) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds),
        path=Path(f"/tmp/f_{int(seconds*10):06d}.png"),
        is_keyframe=is_keyframe,
    )


def _segment(start: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=start + 1.0),
        text=text,
    )


class FakeExtractor:
    def __init__(self, frames: list[Frame]) -> None:
        self._frames = frames

    def extract(self, video_path: Path) -> list[Frame]:
        return self._frames


class FakeRecognizer:
    def __init__(self, call_log: list[str] | None = None) -> None:
        self.recognized: list[Frame] = []
        self._call_log = call_log

    def recognize(self, frame: Frame) -> OcrText:
        self.recognized.append(frame)
        if self._call_log is not None:
            self._call_log.append("ocr")
        return OcrText(timestamp=frame.timestamp, lines=("text",))


class FakeDescriber:
    def __init__(self, call_log: list[str] | None = None) -> None:
        self._call_log = call_log

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        if self._call_log is not None:
            self._call_log.append("describe")
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業@{frame.timestamp.seconds}",
            app_guess=None,
        )


class FakeTranscriber:
    def __init__(
        self,
        segments_by_video: dict[str, list[TranscriptSegment]],
        call_log: list[str] | None = None,
    ) -> None:
        self._by_video = segments_by_video
        self.calls: list[Path] = []
        self._call_log = call_log

    def transcribe(self, video_path: Path) -> list[TranscriptSegment]:
        self.calls.append(video_path)
        if self._call_log is not None:
            self._call_log.append(f"transcribe:{video_path.stem}")
        return self._by_video.get(video_path.stem, [])


def _use_case(
    frames: list[Frame],
    ocr_keyframes_only: bool = False,
    transcriber: FakeTranscriber | None = None,
) -> tuple[GenerateWorklog, FakeRecognizer]:
    recognizer = FakeRecognizer()
    use_case = GenerateWorklog(
        frame_extractor=FakeExtractor(frames),
        text_recognizer=recognizer,
        scene_describer=FakeDescriber(),
        merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        ocr_keyframes_only=ocr_keyframes_only,
        speech_transcriber=transcriber,
    )
    return use_case, recognizer


class TestMeetingModeOcrPolicy:
    """Cycle T: 会議モード（OCRをキーフレームのみに限定）。"""

    def test_only_keyframes_are_recognized(self) -> None:
        frames = [_frame(1.0, False), _frame(2.0, True), _frame(3.0, False)]
        use_case, recognizer = _use_case(frames, ocr_keyframes_only=True)

        use_case.execute(Path("/tmp/v.mp4"))

        assert [f.timestamp.seconds for f in recognizer.recognized] == [2.0]

    def test_non_keyframes_get_empty_ocr(self) -> None:
        frames = [_frame(1.0, False), _frame(2.0, True)]
        use_case, _ = _use_case(frames, ocr_keyframes_only=True)

        worklog = use_case.execute(Path("/tmp/v.mp4"))

        # キーフレームのエントリにはOCRが付く（非キーフレームは対象外）
        assert worklog.entries[0].ocr_lines == ("text",)

    def test_default_is_backward_compatible(self) -> None:
        frames = [_frame(1.0, False), _frame(2.0, True)]
        use_case, recognizer = _use_case(frames, ocr_keyframes_only=False)

        use_case.execute(Path("/tmp/v.mp4"))

        assert len(recognizer.recognized) == 2


class TestPrecomputedSegments:
    """Cycle U: 2フェーズの部品 — 事前計算済み発話の注入。"""

    def test_precomputed_segments_skip_transcriber(self) -> None:
        transcriber = FakeTranscriber({"v": [_segment(1.0, "should not be used")]})
        use_case, _ = _use_case([_frame(1.0, True)], transcriber=transcriber)

        worklog = use_case.execute(
            Path("/tmp/v.mp4"),
            precomputed_segments=[_segment(1.5, "事前計算の発話")],
        )

        assert transcriber.calls == []
        assert worklog.entries[0].speech == ("事前計算の発話",)

    def test_none_uses_transcriber_as_before(self) -> None:
        transcriber = FakeTranscriber({"v": [_segment(1.5, "通常経路の発話")]})
        use_case, _ = _use_case([_frame(1.0, True)], transcriber=transcriber)

        worklog = use_case.execute(Path("/tmp/v.mp4"))

        assert len(transcriber.calls) == 1
        assert worklog.entries[0].speech == ("通常経路の発話",)


class VaryingOcrRecognizer:
    """フレームパスに応じて異なるOCRを返すフェイク。"""

    def __init__(self, texts_by_stem: dict[str, tuple[str, ...]]) -> None:
        self._by_stem = texts_by_stem

    def recognize(self, frame: Frame) -> OcrText:
        return OcrText(
            timestamp=frame.timestamp,
            lines=self._by_stem.get(frame.path.stem, ()),
        )


class CountingDescriber:
    def __init__(self) -> None:
        self.called_at: list[float] = []

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self.called_at.append(frame.timestamp.seconds)
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業@{frame.timestamp.seconds}",
            app_guess=None,
        )


def _kf(seconds: float, stem: str) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds),
        path=Path(f"/tmp/{stem}.png"),
        is_keyframe=True,
    )


class TestVlmGateInUseCase:
    """Cycle Z2: VLMゲートのユースケース統合。"""

    _MEETING_UI = ("参加者リスト", "ミュート解除", "チャット表示", "画面を共有")
    _SHARED_DOC = ("四半期売上報告", "前年比較グラフ", "アクションアイテム一覧")

    def _run(self, frames, ocr_map, gate):
        from screen_activity_logger.domain.vlm_gate import VlmGateConfig

        describer = CountingDescriber()
        use_case = GenerateWorklog(
            frame_extractor=FakeExtractor(frames),
            text_recognizer=VaryingOcrRecognizer(ocr_map),
            scene_describer=describer,
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
            vlm_gate=VlmGateConfig() if gate else None,
        )
        use_case.execute(Path("/tmp/v.mp4"))
        return describer

    def test_speaker_switches_with_same_text_call_vlm_once(self) -> None:
        """話者切替の連続（文字不変）→ VLMは初回の1回だけ。"""
        frames = [_kf(0.0, "a"), _kf(20.0, "b"), _kf(40.0, "c")]
        ocr_map = {s: self._MEETING_UI for s in ("a", "b", "c")}
        describer = self._run(frames, ocr_map, gate=True)
        assert describer.called_at == [0.0]

    def test_screen_share_start_fires_vlm(self) -> None:
        """画面共有開始（文字が大きく変化）→ 発火。"""
        frames = [_kf(0.0, "a"), _kf(30.0, "share")]
        ocr_map = {"a": self._MEETING_UI, "share": self._SHARED_DOC}
        describer = self._run(frames, ocr_map, gate=True)
        assert describer.called_at == [0.0, 30.0]

    def test_max_gap_forces_vlm_even_if_same(self) -> None:
        frames = [_kf(0.0, "a"), _kf(130.0, "b")]
        ocr_map = {"a": self._MEETING_UI, "b": self._MEETING_UI}
        describer = self._run(frames, ocr_map, gate=True)
        assert describer.called_at == [0.0, 130.0]

    def test_gate_none_describes_all_keyframes(self) -> None:
        """後方互換: ゲート未注入なら全キーフレームでVLM（現行動作）。"""
        frames = [_kf(0.0, "a"), _kf(20.0, "b")]
        ocr_map = {"a": self._MEETING_UI, "b": self._MEETING_UI}
        describer = self._run(frames, ocr_map, gate=False)
        assert describer.called_at == [0.0, 20.0]


class RecordingWriter:
    def __init__(self) -> None:
        self.written: list[tuple[Worklog, Path]] = []

    def write(self, worklog: Worklog, output_path: Path) -> None:
        self.written.append((worklog, output_path))


class TestBatchGenerateWorklog:
    """Cycle V: 2フェーズバッチ — 全ASR（Phase A）→ 各動画のOCR/VLM（Phase B）。"""

    def _batch(self, call_log: list[str]) -> tuple[BatchGenerateWorklog, RecordingWriter]:
        frames = [_frame(1.0, True)]
        transcriber = FakeTranscriber(
            {
                "v1": [_segment(1.2, "動画1の発話")],
                "v2": [_segment(1.2, "動画2の発話")],
            },
            call_log=call_log,
        )
        use_case = GenerateWorklog(
            frame_extractor=FakeExtractor(frames),
            text_recognizer=FakeRecognizer(call_log=call_log),
            scene_describer=FakeDescriber(call_log=call_log),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        )
        writer = RecordingWriter()
        batch = BatchGenerateWorklog(
            transcriber=transcriber,
            use_case=use_case,
            writers=[(writer, "worklog.md")],
        )
        return batch, writer

    def test_all_transcriptions_happen_before_any_describe(self) -> None:
        call_log: list[str] = []
        batch, _ = self._batch(call_log)

        batch.execute(
            [Path("/tmp/v1.mp4"), Path("/tmp/v2.mp4")], output_dir=Path("/tmp/out")
        )

        transcribe_indices = [
            i for i, c in enumerate(call_log) if c.startswith("transcribe")
        ]
        describe_indices = [i for i, c in enumerate(call_log) if c == "describe"]
        assert max(transcribe_indices) < min(describe_indices)

    def test_each_video_gets_its_own_segments(self) -> None:
        call_log: list[str] = []
        batch, writer = self._batch(call_log)

        batch.execute(
            [Path("/tmp/v1.mp4"), Path("/tmp/v2.mp4")], output_dir=Path("/tmp/out")
        )

        speeches = [w.entries[0].speech for w, _ in writer.written]
        assert ("動画1の発話",) in speeches
        assert ("動画2の発話",) in speeches

    def test_outputs_go_to_per_video_subdirs(self) -> None:
        call_log: list[str] = []
        batch, writer = self._batch(call_log)

        batch.execute(
            [Path("/tmp/v1.mp4"), Path("/tmp/v2.mp4")], output_dir=Path("/tmp/out")
        )

        dirs = sorted({p.parent.name for _, p in writer.written})
        assert dirs == ["v1", "v2"]
