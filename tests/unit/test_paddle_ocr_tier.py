"""PaddleOcrRecognizer のtier切替のユニットテスト（Cycle M-1: RED）。"""

import pytest

from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer


class TestOcrTier:
    def test_tiny_tier_maps_to_tiny_model_names(self) -> None:
        recognizer = PaddleOcrRecognizer(tier="tiny")
        kwargs = recognizer._engine_kwargs()
        assert kwargs["text_detection_model_name"] == "PP-OCRv6_tiny_det"
        assert kwargs["text_recognition_model_name"] == "PP-OCRv6_tiny_rec"

    def test_small_tier_maps_to_small_model_names(self) -> None:
        recognizer = PaddleOcrRecognizer(tier="small")
        kwargs = recognizer._engine_kwargs()
        assert kwargs["text_detection_model_name"] == "PP-OCRv6_small_det"
        assert kwargs["text_recognition_model_name"] == "PP-OCRv6_small_rec"

    def test_medium_tier_uses_default_models(self) -> None:
        """medium＝PaddleOCRの既定モデルのため明示指定しない。"""
        recognizer = PaddleOcrRecognizer(tier="medium")
        kwargs = recognizer._engine_kwargs()
        assert "text_detection_model_name" not in kwargs
        assert "text_recognition_model_name" not in kwargs

    def test_invalid_tier_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            PaddleOcrRecognizer(tier="huge")

    def test_lang_is_always_included(self) -> None:
        recognizer = PaddleOcrRecognizer(tier="tiny")
        assert recognizer._engine_kwargs()["lang"] == "japan"
