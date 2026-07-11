"""PaddleOcrRecognizer の統合テスト（Cycle G: RED）。

PILで文字を描画した画像を生成し、実OCRで読めることを検証する。
初回はモデルダウンロードが走るため slow マーカー付き。
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from screen_activity_logger.domain.models import Frame, VideoTimestamp
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_JP_FONT = Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc")


def _make_text_image(path: Path, text: str, font: ImageFont.FreeTypeFont) -> None:
    image = Image.new("RGB", (960, 240), "white")
    ImageDraw.Draw(image).text((40, 80), text, fill="black", font=font)
    image.save(path)


def _frame(path: Path) -> Frame:
    return Frame(timestamp=VideoTimestamp(seconds=1.0), path=path, is_keyframe=True)


@pytest.fixture(scope="module")
def recognizer() -> PaddleOcrRecognizer:
    return PaddleOcrRecognizer()


class TestPaddleOcrRecognizer:
    def test_recognizes_ascii_text(
        self, recognizer: PaddleOcrRecognizer, tmp_path: Path
    ) -> None:
        image_path = tmp_path / "ascii.png"
        font = ImageFont.truetype(str(_JP_FONT), size=56)
        _make_text_image(image_path, "Hello World 12345", font)

        ocr = recognizer.recognize(_frame(image_path))

        joined = " ".join(ocr.lines)
        assert "Hello" in joined
        assert "12345" in joined

    @pytest.mark.skipif(not _JP_FONT.exists(), reason="日本語フォントなし")
    def test_recognizes_japanese_text(
        self, recognizer: PaddleOcrRecognizer, tmp_path: Path
    ) -> None:
        image_path = tmp_path / "japanese.png"
        font = ImageFont.truetype(str(_JP_FONT), size=56)
        _make_text_image(image_path, "作業ログを生成する", font)

        ocr = recognizer.recognize(_frame(image_path))

        assert any("作業" in line for line in ocr.lines)

    def test_result_carries_frame_timestamp(
        self, recognizer: PaddleOcrRecognizer, tmp_path: Path
    ) -> None:
        image_path = tmp_path / "ts.png"
        font = ImageFont.truetype(str(_JP_FONT), size=56)
        _make_text_image(image_path, "timestamp", font)

        ocr = recognizer.recognize(_frame(image_path))

        assert ocr.timestamp.seconds == 1.0


class TestOcrTierIntegration:
    """small tier（CLI既定）が日本語を読めることのスモーク（Cycle M）。"""

    @pytest.mark.skipif(not _JP_FONT.exists(), reason="日本語フォントなし")
    def test_small_tier_reads_japanese(self, tmp_path: Path) -> None:
        image_path = tmp_path / "jp_small.png"
        font = ImageFont.truetype(str(_JP_FONT), size=56)
        _make_text_image(image_path, "作業ログを生成する", font)

        ocr = PaddleOcrRecognizer(tier="small").recognize(_frame(image_path))

        assert any("作業" in line for line in ocr.lines)
