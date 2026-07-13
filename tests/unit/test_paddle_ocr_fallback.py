"""PaddleOCR失敗時のフォールバック（4AIレビューR1: RED）。

1フレームのOCR例外がパイプライン全体を停止させない（VLMと同方針）。
"""

from pathlib import Path

from screen_activity_logger.domain.models import Frame, VideoTimestamp
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer


class _RaisingEngine:
    def predict(self, path: str):
        raise RuntimeError("paddle internal error")


def _frame(tmp_path: Path) -> Frame:
    png = tmp_path / "f.png"
    png.write_bytes(b"fake")
    return Frame(timestamp=VideoTimestamp(seconds=5.0), path=png, is_keyframe=True)


class TestOcrFallback:
    def test_engine_error_returns_empty_ocr(self, tmp_path, capsys) -> None:
        recognizer = PaddleOcrRecognizer(tier="small")
        recognizer._engine = _RaisingEngine()  # 遅延初期化をフェイクで差し替え

        ocr = recognizer.recognize(_frame(tmp_path))

        assert ocr.lines == ()
        assert ocr.timestamp.seconds == 5.0
        assert "OCR失敗" in capsys.readouterr().out
