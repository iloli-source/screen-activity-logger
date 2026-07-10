"""PaddleOCRによるTextRecognizerポートの実装（CPU動作）。"""

from __future__ import annotations

from typing import Any

from screen_activity_logger.domain.models import Frame, OcrText


class PaddleOcrRecognizer:
    """PaddleOCR（日本語モデル）でフレーム画像から文字を抽出する。

    エンジン生成が重いため遅延初期化し、インスタンスで再利用する。
    """

    def __init__(self, lang: str = "japan") -> None:
        self._lang = lang
        self._engine: Any | None = None

    def recognize(self, frame: Frame) -> OcrText:
        result = self._get_engine().predict(str(frame.path))
        lines = self._extract_texts(result)
        return OcrText(timestamp=frame.timestamp, lines=lines)

    def _get_engine(self) -> Any:
        if self._engine is None:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(
                lang=self._lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._engine

    @staticmethod
    def _extract_texts(result: Any) -> tuple[str, ...]:
        if not result:
            return ()
        return tuple(str(text) for text in result[0].get("rec_texts", ()))
