"""実OCR→ScreenContext抽出の統合テスト（Cycle Y6）。

Excel風のタイトルバーを含む合成スクリーンショットから、
実PaddleOCR→parse_screen_contextでファイル名等を抽出できることを確認。
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from screen_activity_logger.domain.models import Frame, VideoTimestamp
from screen_activity_logger.domain.screen_context import parse_screen_context
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer

from support.fonts import find_jp_font

_JP_FONT = find_jp_font()  # マルチプラットフォーム探索（Issue #16）

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(_JP_FONT is None, reason="日本語フォントなし"),
]


@pytest.fixture(scope="module")
def excel_like_screenshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """タイトルバー・シートタブ・表を模したスクリーンショット。"""
    path = tmp_path_factory.mktemp("ctx") / "excel_like.png"
    image = Image.new("RGB", (1024, 640), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(_JP_FONT), size=28)
    body_font = ImageFont.truetype(str(_JP_FONT), size=24)
    # タイトルバー
    draw.rectangle([0, 0, 1024, 48], fill="#217346")
    draw.text((280, 8), "見積書_2026Q2.xlsx - Excel", fill="white", font=title_font)
    # 表っぽい本文
    draw.text((60, 120), "品目            単価        数量", fill="black", font=body_font)
    draw.text((60, 170), "開発支援        1,200,000    1", fill="black", font=body_font)
    # シートタブ
    draw.rectangle([0, 590, 1024, 640], fill="#f3f2f1")
    draw.text((40, 600), "Sheet1", fill="black", font=body_font)
    image.save(path)
    return path


class TestRealOcrToScreenContext:
    def test_extracts_resource_app_and_location(
        self, excel_like_screenshot: Path
    ) -> None:
        frame = Frame(
            timestamp=VideoTimestamp(seconds=1.0),
            path=excel_like_screenshot,
            is_keyframe=True,
        )
        ocr = PaddleOcrRecognizer(tier="small").recognize(frame)
        ctx = parse_screen_context(ocr.lines)

        assert ctx.resource is not None
        assert "見積書" in ctx.resource
        assert ctx.resource.endswith(".xlsx")
        assert ctx.location == "Sheet1"
