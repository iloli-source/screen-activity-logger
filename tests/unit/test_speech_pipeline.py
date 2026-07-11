"""発話のユースケース統合・出力・プロンプトのテスト（Cycle P-Q: RED）。"""

import json
from pathlib import Path

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)
from screen_activity_logger.domain.services import TimelineMerger
from screen_activity_logger.infrastructure.writers import (
    JsonlWorklogWriter,
    MarkdownWorklogWriter,
)


def _frame(seconds: float, is_keyframe: bool = True) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds),
        path=Path(f"/tmp/f_{int(seconds):06d}.png"),
        is_keyframe=is_keyframe,
    )


def _segment(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=end),
        text=text,
    )


class FakeExtractor:
    def __init__(self, frames: list[Frame]) -> None:
        self._frames = frames

    def extract(self, video_path: Path) -> list[Frame]:
        return self._frames


class FakeRecognizer:
    def recognize(self, frame: Frame) -> OcrText:
        return OcrText(timestamp=frame.timestamp, lines=())


class SpeechCapturingDescriber:
    def __init__(self) -> None:
        self.received_speech: list[tuple[str, ...]] = []

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription:
        self.received_speech.append(speech)
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業@{frame.timestamp.seconds}",
            app_guess=None,
        )


class FakeTranscriber:
    def __init__(self, segments: list[TranscriptSegment]) -> None:
        self._segments = segments
        self.called_with: list[Path] = []

    def transcribe(self, video_path: Path) -> list[TranscriptSegment]:
        self.called_with.append(video_path)
        return self._segments


class TestGenerateWorklogWithSpeech:
    def _build(
        self,
        frames: list[Frame],
        segments: list[TranscriptSegment] | None,
    ) -> tuple[GenerateWorklog, SpeechCapturingDescriber]:
        describer = SpeechCapturingDescriber()
        use_case = GenerateWorklog(
            frame_extractor=FakeExtractor(frames),
            text_recognizer=FakeRecognizer(),
            scene_describer=describer,
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
            speech_transcriber=(
                FakeTranscriber(segments) if segments is not None else None
            ),
        )
        return use_case, describer

    def test_speech_appears_in_worklog_entries(self) -> None:
        use_case, _ = self._build(
            frames=[_frame(10.0)],
            segments=[_segment(11.0, 13.0, "この画面の説明をしています")],
        )
        worklog = use_case.execute(Path("/tmp/v.mp4"))
        assert worklog.entries[0].speech == ("この画面の説明をしています",)

    def test_describer_receives_speech_near_keyframe(self) -> None:
        use_case, describer = self._build(
            frames=[_frame(10.0)],
            segments=[
                _segment(5.0, 8.0, "直前の発話"),
                _segment(100.0, 103.0, "遠い発話"),
            ],
        )
        use_case.execute(Path("/tmp/v.mp4"))
        assert describer.received_speech[0] == ("直前の発話",)

    def test_without_transcriber_speech_is_empty(self) -> None:
        use_case, describer = self._build(frames=[_frame(10.0)], segments=None)
        worklog = use_case.execute(Path("/tmp/v.mp4"))
        assert worklog.entries[0].speech == ()
        assert describer.received_speech[0] == ()


class TestSpeechInWriters:
    def _worklog(self) -> Worklog:
        return Worklog.from_entries(
            [
                WorklogEntry(
                    timestamp=VideoTimestamp(seconds=10.0),
                    action="レビューをしている",
                    app_guess="Cursor",
                    ocr_lines=("diff",),
                    speech=("ここの実装が気になりますね", "直しておきます"),
                ),
                WorklogEntry(
                    timestamp=VideoTimestamp(seconds=20.0),
                    action="無言の作業",
                    app_guess=None,
                    ocr_lines=(),
                ),
            ]
        )

    def test_markdown_renders_speech_lines(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(self._worklog(), out)
        text = out.read_text(encoding="utf-8")
        assert "🗣️ ここの実装が気になりますね" in text
        assert "🗣️ 直しておきます" in text

    def test_markdown_omits_speech_when_absent(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.md"
        MarkdownWorklogWriter().write(self._worklog(), out)
        # 2番目のエントリ（無言）のセクションに🗣️が無いこと
        section = out.read_text(encoding="utf-8").split("## 00:00:20")[1]
        assert "🗣️" not in section

    def test_jsonl_includes_speech_key(self, tmp_path: Path) -> None:
        out = tmp_path / "worklog.jsonl"
        JsonlWorklogWriter().write(self._worklog(), out)
        first = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert first["speech"] == ["ここの実装が気になりますね", "直しておきます"]


class TestSpeechInVlmPrompt:
    def test_prompt_includes_speech_context(self) -> None:
        from screen_activity_logger.infrastructure.ollama_describer import (
            OllamaSceneDescriber,
        )

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def chat(self, **kwargs):
                self.calls.append(kwargs)
                return {"message": {"content": '{"app_guess": null, "action": "a"}'}}

        client = FakeClient()
        describer = OllamaSceneDescriber(model="qwen3-vl:8b", client=client)
        describer.describe(
            _frame(1.0),
            OcrText(timestamp=VideoTimestamp(seconds=1.0), lines=()),
            speech=("このバグの原因を説明します",),
        )
        prompt = client.calls[0]["messages"][0]["content"]
        assert "このバグの原因を説明します" in prompt
