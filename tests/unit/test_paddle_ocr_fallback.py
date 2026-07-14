"""OCR失敗のフレーム単位フォールバック（4AIレビューR2: use_case層）。

R1ではアダプタ内で空OcrTextに落としていたが、差分スキップのキャッシュに
失敗結果が載って後続フレームへ伝播するため、use_case層でNone区別に変更。
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


class FlakyRecognizer:
    """1枚目だけ失敗し、以降は成功するOCR。"""

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, frame: Frame) -> OcrText:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("paddle internal error")
        return OcrText(timestamp=frame.timestamp, lines=("回復した文字",))


class AlwaysSimilarComparator:
    def are_similar(self, a: Frame, b: Frame) -> bool:
        return True


class FakeDescriber:
    def describe(self, frame, ocr, speech=()):
        return ActivityDescription(
            timestamp=frame.timestamp, action="作業", app_guess=None
        )


class StaticExtractor:
    def __init__(self, frames):
        self._frames = frames

    def extract(self, video_path):
        return self._frames


def _frames(tmp_path: Path, count: int) -> tuple[Frame, ...]:
    frames = []
    for i in range(count):
        png = tmp_path / f"f{i}.png"
        png.write_bytes(b"fake")
        frames.append(
            Frame(
                timestamp=VideoTimestamp(seconds=float(i)),
                path=png,
                is_keyframe=(i == 0),
            )
        )
    return tuple(frames)


class TestOcrFailureIsolation:
    def test_failure_does_not_poison_skip_cache(self, tmp_path, capsys) -> None:
        """先頭フレームのOCR失敗が類似フレーム列へ空OCRとして伝播しない。"""
        recognizer = FlakyRecognizer()
        use_case = GenerateWorklog(
            frame_extractor=StaticExtractor(_frames(tmp_path, 3)),
            text_recognizer=recognizer,
            scene_describer=FakeDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
            frame_comparator=AlwaysSimilarComparator(),
        )

        frames = use_case.frame_extractor.extract(Path("v.mp4"))
        ocr_by_frame = use_case._recognize_frames(frames)

        # 失敗がキャッシュに載っていれば2枚目以降は再OCRされず空のまま。
        # 非汚染なら2枚目で再OCRが走り、3枚目のスキップ再利用も回復後の値になる
        assert recognizer.calls == 2  # 1枚目失敗→2枚目再OCR→3枚目はスキップ
        assert "OCR失敗" in capsys.readouterr().out
        assert ocr_by_frame[frames[0].timestamp].lines == ()
        assert ocr_by_frame[frames[1].timestamp].lines == ("回復した文字",)
        assert ocr_by_frame[frames[2].timestamp].lines == ("回復した文字",)
