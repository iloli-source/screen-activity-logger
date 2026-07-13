"""Ruri v3（cl-nagoya/ruri-v3-*）によるTextEmbedderポートの実装（Issue #5）。

日本語特化の軽量埋め込みモデル（30m=37M・256次元、Apache-2.0）。CPUで動作。
Ruri v3のプレフィックス規約（1+3方式、encode前に手動連結）:
  検索クエリ側「検索クエリ: 」／検索文書側「検索文書: 」
この規約はRuri固有仕様のため本アダプタに閉じる（ポートは汎用のまま）。
"""

from __future__ import annotations

from typing import Any, Sequence

DEFAULT_EMBEDDING_MODEL = "cl-nagoya/ruri-v3-30m"

_QUERY_PREFIX = "検索クエリ: "
_DOCUMENT_PREFIX = "検索文書: "


class RuriEmbedder:
    """sentence-transformers経由のRuri v3。モデルは遅延ロード＆キャッシュ。"""

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self._model_name = model
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(
        self, texts: Sequence[str]
    ) -> tuple[tuple[float, ...], ...]:
        prefixed = [f"{_DOCUMENT_PREFIX}{text}" for text in texts]
        vectors = self._encode(prefixed)
        return tuple(tuple(float(v) for v in row) for row in vectors)

    def embed_query(self, text: str) -> tuple[float, ...]:
        vectors = self._encode([f"{_QUERY_PREFIX}{text}"])
        return tuple(float(v) for v in vectors[0])

    def _encode(self, texts: list[str]) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # 遅延import

            self._model = SentenceTransformer(self._model_name, device="cpu")
        return self._model.encode(texts, normalize_embeddings=True)
