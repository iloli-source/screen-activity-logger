"""numpy索引のユニットテスト（Issue #5 P4: RED）。

numpyはsentence-transformersの依存として[search]で入るが、CI（未導入環境）
では本テストをスキップする（遅延import設計の検証を兼ねる）。
"""

import importlib.util
from pathlib import Path

import pytest

from screen_activity_logger.domain.search import SearchDocument
from screen_activity_logger.infrastructure.numpy_index import NumpyVectorIndex

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None, reason="numpy未インストール"
)


def _doc(doc_id: str, text: str) -> SearchDocument:
    return SearchDocument(
        doc_id=doc_id, text=text, source="v", t="00:00:00",
        t_end=None, duration_seconds=None, app_guess=None, action=text,
    )


class TestNumpyVectorIndex:
    def test_cosine_top_k(self) -> None:
        index = NumpyVectorIndex()
        index.build(
            [_doc("a", "A"), _doc("b", "B"), _doc("c", "C")],
            vectors=[(1.0, 0.0), (0.0, 1.0), (0.7, 0.7)],
            model_name="m",
        )
        hits = index.search((1.0, 0.1), k=2)
        assert [h.document.doc_id for h in hits] == ["a", "c"]
        assert hits[0].score > hits[1].score

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        index = NumpyVectorIndex()
        index.build(
            [_doc("a", "文書A")], vectors=[(0.6, 0.8)], model_name="ruri-test"
        )
        index.save(tmp_path / "idx")

        loaded = NumpyVectorIndex()
        loaded.load(tmp_path / "idx")
        assert loaded.model_name == "ruri-test"
        hits = loaded.search((0.6, 0.8), k=1)
        assert hits[0].document.doc_id == "a"
        assert hits[0].score == pytest.approx(1.0, abs=1e-5)

    def test_model_mismatch_raises(self, tmp_path: Path) -> None:
        index = NumpyVectorIndex()
        index.build([_doc("a", "A")], vectors=[(1.0,)], model_name="model-x")
        index.save(tmp_path / "idx")

        loaded = NumpyVectorIndex()
        with pytest.raises(ValueError) as excinfo:
            loaded.load(tmp_path / "idx", expected_model="model-y")
        assert "モデル不一致" in str(excinfo.value)

    def test_empty_index_returns_no_hits(self) -> None:
        assert NumpyVectorIndex().search((1.0,), k=3) == ()
