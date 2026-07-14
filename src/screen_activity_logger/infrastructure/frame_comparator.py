"""PILによるフレーム類似判定アダプタ。

グレースケール縮小画像の平均絶対差で「ほぼ同一画面か」を判定する。
numpyに依存せず、標準的なPIL操作のみで実装する。
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops

from screen_activity_logger.domain.models import Frame

_COMPARE_SIZE = (64, 64)


@dataclass(frozen=True)
class PilFrameComparator:
    """FrameComparatorポートの実装。

    threshold: 正規化した平均絶対差（0.0〜1.0）の閾値。
    これ未満なら「類似（＝OCRスキップ可）」とみなす。
    カーソル点滅などの微小変化を吸収しつつ、ウィンドウ切替は検出できる
    水準として既定0.02とする。
    """

    threshold: float = 0.02

    def are_similar(self, a: Frame, b: Frame) -> bool:
        try:
            return self._are_similar(a, b)
        except Exception as error:  # noqa: BLE001 — 比較失敗は安全側（再OCR）へ
            print(
                f"フレーム比較失敗（再OCRします）: {type(error).__name__}",
                flush=True,
            )
            return False

    def _are_similar(self, a: Frame, b: Frame) -> bool:
        return self._mean_abs_diff(a, b) < self.threshold

    @staticmethod
    def _mean_abs_diff(a: Frame, b: Frame) -> float:
        with Image.open(a.path) as image_a, Image.open(b.path) as image_b:
            gray_a = image_a.convert("L").resize(_COMPARE_SIZE)
            gray_b = image_b.convert("L").resize(_COMPARE_SIZE)
            diff = ImageChops.difference(gray_a, gray_b)
            histogram = diff.histogram()
        total_pixels = _COMPARE_SIZE[0] * _COMPARE_SIZE[1]
        weighted_sum = sum(value * count for value, count in enumerate(histogram))
        return weighted_sum / (total_pixels * 255)
