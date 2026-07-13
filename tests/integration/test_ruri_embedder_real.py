"""Ruri v3実モデルの統合テスト（Issue #5 P6、slow）。

初回はruri-v3-30m（約150MB）のダウンロードが走る。CPUのみで動作すること
自体が検証項目（GPU不要の活用層という設計前提の確認）。
"""

import importlib.util

import pytest

from screen_activity_logger.infrastructure.ruri_embedder import RuriEmbedder

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        importlib.util.find_spec("sentence_transformers") is None,
        reason="sentence-transformers未インストール（uv pip install -e '.[search]'）",
    ),
]


class TestRuriEmbedderReal:
    def test_dimension_is_256(self) -> None:
        embedder = RuriEmbedder()
        vector = embedder.embed_query("テスト")
        assert len(vector) == 256

    def test_semantic_similarity_ranks_correctly(self) -> None:
        embedder = RuriEmbedder()
        documents = [
            "作業: Excelで売上を集計している\nアプリ: Excel",
            "作業: ビデオ会議で自己紹介している\nアプリ: Zoom",
        ]
        doc_vectors = embedder.embed_documents(documents)
        query = embedder.embed_query("Excelで集計していたのは？")

        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        excel_score = dot(query, doc_vectors[0])
        meeting_score = dot(query, doc_vectors[1])
        assert excel_score > meeting_score
