"""PilFrameComparator のユニットテスト（Cycle L: RED）。"""

from pathlib import Path

from PIL import Image, ImageDraw

from screen_activity_logger.domain.models import Frame, VideoTimestamp
from screen_activity_logger.infrastructure.frame_comparator import (
    PilFrameComparator,
)


def _frame(path: Path) -> Frame:
    return Frame(
        timestamp=VideoTimestamp(seconds=0.0), path=path, is_keyframe=False
    )


def _save_screen(path: Path, text_y: int = 100, extra: str = "") -> None:
    """擬似的な画面: 白背景に黒い矩形（ウィンドウ）とテキスト風の線。"""
    image = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([50, 50, 590, 350], outline="black", width=3)
    draw.text((70, text_y), f"some window content {extra}", fill="black")
    image.save(path)


class TestPilFrameComparator:
    def test_identical_images_are_similar(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _save_screen(a)
        _save_screen(b)

        assert PilFrameComparator().are_similar(_frame(a), _frame(b)) is True

    def test_cursor_blink_level_change_is_similar(self, tmp_path: Path) -> None:
        """数ピクセルの微小差（カーソル点滅相当）は類似とみなす。"""
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _save_screen(a)
        _save_screen(b, extra="|")  # わずかな文字追加

        assert PilFrameComparator().are_similar(_frame(a), _frame(b)) is True

    def test_largely_different_screens_are_not_similar(
        self, tmp_path: Path
    ) -> None:
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _save_screen(a)
        # 全面が異なる画面（背景色から違う）
        image = Image.new("RGB", (640, 400), "navy")
        image.save(b)

        assert PilFrameComparator().are_similar(_frame(a), _frame(b)) is False

    def test_different_sizes_are_compared_safely(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _save_screen(a)
        Image.new("RGB", (320, 200), "white").save(b)

        # 例外を出さずbool判定できること
        result = PilFrameComparator().are_similar(_frame(a), _frame(b))
        assert isinstance(result, bool)

    def test_threshold_is_configurable(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _save_screen(a, text_y=100)
        _save_screen(b, text_y=180)  # 中程度の変化

        strict = PilFrameComparator(threshold=0.001)
        loose = PilFrameComparator(threshold=0.5)
        assert strict.are_similar(_frame(a), _frame(b)) is False
        assert loose.are_similar(_frame(a), _frame(b)) is True
