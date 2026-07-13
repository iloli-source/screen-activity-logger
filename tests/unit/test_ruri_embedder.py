"""Ruri埋め込みアダプタのユニットテスト（Issue #5 P5: RED）。

sys.modulesへのfake sentence_transformers注入で、プレフィックス規約と
モデル名の伝搬・遅延ロードを検証（実ライブラリ不要）。
"""

import sys
import types

from screen_activity_logger.infrastructure.ruri_embedder import RuriEmbedder


class FakeSentenceTransformer:
    constructed: list[dict] = []

    def __init__(self, model_name, device=None):
        FakeSentenceTransformer.constructed.append(
            {"model": model_name, "device": device}
        )
        self.encode_calls: list = []

    def encode(self, texts, normalize_embeddings=False):
        self.encode_calls.append(
            {"texts": list(texts), "normalize": normalize_embeddings}
        )
        return [[float(len(t)), 0.0] for t in texts]


def _install_fake(monkeypatch) -> None:
    FakeSentenceTransformer.constructed = []
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


class TestRuriEmbedder:
    def test_documents_get_document_prefix(self, monkeypatch) -> None:
        _install_fake(monkeypatch)
        embedder = RuriEmbedder()

        vectors = embedder.embed_documents(["作業: Excelで集計"])

        model = FakeSentenceTransformer.constructed[0]
        assert model["model"] == "cl-nagoya/ruri-v3-30m"
        assert model["device"] == "cpu"
        instance_calls = embedder._model.encode_calls
        assert instance_calls[0]["texts"] == ["検索文書: 作業: Excelで集計"]
        assert instance_calls[0]["normalize"] is True
        assert len(vectors) == 1

    def test_query_gets_query_prefix(self, monkeypatch) -> None:
        _install_fake(monkeypatch)
        embedder = RuriEmbedder(model="cl-nagoya/ruri-v3-130m")

        embedder.embed_query("Excelで集計していたのは？")

        assert FakeSentenceTransformer.constructed[0]["model"] == (
            "cl-nagoya/ruri-v3-130m"
        )
        assert embedder._model.encode_calls[0]["texts"] == [
            "検索クエリ: Excelで集計していたのは？"
        ]

    def test_model_loads_once(self, monkeypatch) -> None:
        _install_fake(monkeypatch)
        embedder = RuriEmbedder()

        embedder.embed_documents(["a"])
        embedder.embed_query("b")

        assert len(FakeSentenceTransformer.constructed) == 1  # 遅延ロード1回
