"""キーフレーム画像の保存と埋め込み（Issue #27: RED）。"""

from pathlib import Path

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    VideoTimestamp,
)
from screen_activity_logger.domain.services import TimelineMerger


class StaticExtractor:
    def __init__(self, frames):
        self._frames = frames

    def extract(self, video_path):
        return self._frames


class EmptyRecognizer:
    def recognize(self, frame):
        return OcrText(timestamp=frame.timestamp, lines=())


class FakeDescriber:
    def describe(self, frame, ocr, speech=()):
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"作業{int(frame.timestamp.seconds)}",
            app_guess="Excel",
        )


def _keyframe(tmp_path: Path, seconds: float) -> Frame:
    png = tmp_path / f"src_{int(seconds)}.png"
    png.write_bytes(f"png-{int(seconds)}".encode())
    return Frame(
        timestamp=VideoTimestamp(seconds=seconds), path=png, is_keyframe=True
    )


def _use_case(frames, export_dir) -> GenerateWorklog:
    return GenerateWorklog(
        frame_extractor=StaticExtractor(frames),
        text_recognizer=EmptyRecognizer(),
        scene_describer=FakeDescriber(),
        merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        frame_export_dir=export_dir,
    )


class TestFrameExport:
    def test_keyframes_are_copied_and_referenced(self, tmp_path) -> None:
        frames = (_keyframe(tmp_path, 5.0), _keyframe(tmp_path, 65.0))
        export_dir = tmp_path / "out" / "frames"

        worklog = _use_case(frames, export_dir).execute(Path("v.mp4"))

        first = worklog.entries[0]
        assert first.frame_image == "frames/frame_000005.png"
        copied = export_dir / "frame_000005.png"
        assert copied.read_bytes() == b"png-5"
        assert worklog.entries[1].frame_image == "frames/frame_000105.png"

    def test_no_export_dir_leaves_none(self, tmp_path) -> None:
        frames = (_keyframe(tmp_path, 5.0),)

        worklog = _use_case(frames, None).execute(Path("v.mp4"))

        assert worklog.entries[0].frame_image is None

    def test_copy_failure_keeps_entry(self, tmp_path, capsys) -> None:
        frame = _keyframe(tmp_path, 5.0)
        frame.path.unlink()  # コピー元消失＝失敗を再現

        worklog = _use_case((frame,), tmp_path / "frames").execute(Path("v.mp4"))

        assert worklog.entries[0].frame_image is None
        assert worklog.entries[0].action == "作業5"  # エントリは保持
        assert "画像保存失敗" in capsys.readouterr().out
