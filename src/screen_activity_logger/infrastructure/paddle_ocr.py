"""PaddleOCRによるTextRecognizerポートの実装（CPU動作）。"""

from __future__ import annotations

from typing import Any

from screen_activity_logger.domain.models import Frame, OcrText

# PP-OCRv6のモデルティア。tiny/smallは軽量・高速（論文公称: M4でtinyは6.1倍速）。
# medium はPaddleOCRの既定モデルのため明示指定しない。
_TIER_MODEL_NAMES = {
    "tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
    "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "medium": None,
}


class PaddleOcrRecognizer:
    """PaddleOCR（日本語モデル）でフレーム画像から文字を抽出する。

    エンジン生成が重いため遅延初期化し、インスタンスで再利用する。
    tier: "tiny" | "small" | "medium"（速度と精度のトレードオフ）。
    """

    def __init__(self, lang: str = "japan", tier: str = "medium") -> None:
        if tier not in _TIER_MODEL_NAMES:
            raise ValueError(
                f"tier must be one of {sorted(_TIER_MODEL_NAMES)}, got {tier!r}"
            )
        self._lang = lang
        self._tier = tier
        self._engine: Any | None = None

    def recognize(self, frame: Frame) -> OcrText:
        # 例外はuse_case層でフレーム単位に処理する（差分スキップの
        # キャッシュ汚染を防ぐため、失敗と「文字なし」を区別する必要がある。
        # 4AIレビューR2でR1のアダプタ内フォールバックを移動）
        result = self._get_engine().predict(str(frame.path))
        lines = self._extract_texts(result)
        return OcrText(timestamp=frame.timestamp, lines=lines)

    def _engine_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "lang": self._lang,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        model_names = _TIER_MODEL_NAMES[self._tier]
        if model_names is not None:
            det_name, rec_name = model_names
            kwargs["text_detection_model_name"] = det_name
            kwargs["text_recognition_model_name"] = rec_name
        return kwargs

    def _get_engine(self) -> Any:
        if self._engine is None:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(**self._engine_kwargs())
        return self._engine

    @staticmethod
    def _extract_texts(result: Any) -> tuple[str, ...]:
        if not result:
            return ()
        return tuple(str(text) for text in result[0].get("rec_texts", ()))
