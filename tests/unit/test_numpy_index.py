"""numpy索引のユニットテスト（Issue #5 P4: RED）。

numpyはsentence-transformersの依存として[search]で入るが、CI（未導入環境）
では本テストをスキップする（遅延import設計の検証を兼ねる）。
"""

import importlib.util
import json
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


def _build(model_name: str, doc_ids: tuple[str, str], vectors) -> NumpyVectorIndex:
    index = NumpyVectorIndex()
    index.build(
        [_doc(doc_id, doc_id) for doc_id in doc_ids],
        vectors=vectors,
        model_name=model_name,
    )
    return index


def _old_generation() -> NumpyVectorIndex:
    return _build("model-old", ("old-a", "old-b"), [(1.0, 0.0), (0.0, 1.0)])


def _new_generation() -> NumpyVectorIndex:
    """旧世代と件数・次元が同じで、ベクトルの並びだけ逆（件数照合では区別不能）。"""
    return _build("model-new", ("new-a", "new-b"), [(0.0, 1.0), (1.0, 0.0)])


def _top_hit(index_dir: Path) -> tuple[str | None, str]:
    """(モデル名, クエリ(1,0)の最上位doc_id)。世代の取り違えを検出する指紋。"""
    loaded = NumpyVectorIndex()
    loaded.load(index_dir)
    return loaded.model_name, loaded.search((1.0, 0.0), k=1)[0].document.doc_id


OLD_FINGERPRINT = ("model-old", "old-a")
NEW_FINGERPRINT = ("model-new", "new-b")


class SimulatedCrash(Exception):
    """保存途中でのプロセス停止の代役。"""


def _hook_json_dumps(monkeypatch, wants, action) -> None:
    """save内のjson.dumpsのうちwants(obj)が真の最初の1回でactionを実行する。

    saveは「ベクトル書き込み → 文書の直列化 → manifestの直列化」の順に進むため、
    直列化の瞬間が各ファイルの書き込み境界になる（決定的な割り込み点）。
    """
    from screen_activity_logger.infrastructure import numpy_index

    real_dumps = json.dumps
    fired = []

    def hooked(obj, *args, **kwargs):
        if not fired and wants(obj):
            fired.append(True)
            action()
        return real_dumps(obj, *args, **kwargs)

    monkeypatch.setattr(numpy_index.json, "dumps", hooked)


def _is_document(obj) -> bool:
    return isinstance(obj, dict) and "doc_id" in obj


def _is_manifest(obj) -> bool:
    return isinstance(obj, dict) and "model" in obj


def _raise_crash() -> None:
    raise SimulatedCrash


class TestCrashConsistentSave:
    """保存途中の停止・保存中の読み込みでも世代が混ざらないこと（Issue #32）。

    formal/IndexSave.tla の LoadedIndexIsConsistent /
    CommittedGenerationIsComplete に対応する回帰テスト。
    """

    @pytest.mark.parametrize("boundary", [_is_document, _is_manifest])
    def test_crash_during_save_keeps_previous_generation(
        self, tmp_path: Path, monkeypatch, boundary
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        _hook_json_dumps(monkeypatch, boundary, _raise_crash)

        with pytest.raises(SimulatedCrash):
            _new_generation().save(index_dir)

        assert _top_hit(index_dir) == OLD_FINGERPRINT

    @pytest.mark.parametrize("boundary", [_is_document, _is_manifest])
    def test_load_during_save_sees_single_generation(
        self, tmp_path: Path, monkeypatch, boundary
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        seen: list[tuple[str | None, str]] = []
        _hook_json_dumps(
            monkeypatch, boundary, lambda: seen.append(_top_hit(index_dir))
        )

        _new_generation().save(index_dir)

        assert seen == [OLD_FINGERPRINT]
        assert _top_hit(index_dir) == NEW_FINGERPRINT

    def test_save_removes_previous_generation_files(self, tmp_path: Path) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        _new_generation().save(index_dir)

        assert len(list(index_dir.glob("vectors*.npz"))) == 1
        assert len(list(index_dir.glob("documents*.jsonl"))) == 1
        assert len(list(index_dir.iterdir())) == 3

    def test_failed_save_leaves_no_orphan_files(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        before = sorted(path.name for path in index_dir.iterdir())
        _hook_json_dumps(monkeypatch, _is_manifest, _raise_crash)

        with pytest.raises(SimulatedCrash):
            _new_generation().save(index_dir)

        assert sorted(path.name for path in index_dir.iterdir()) == before

    def test_swapped_data_file_is_reported_as_corruption(
        self, tmp_path: Path
    ) -> None:
        """件数・次元が同じ別世代のファイルが紛れ込んでも検出する。"""
        index_dir, other_dir = tmp_path / "idx", tmp_path / "other"
        _old_generation().save(index_dir)
        _new_generation().save(other_dir)
        (vectors_path,) = index_dir.glob("vectors*.npz")
        (other_vectors,) = other_dir.glob("vectors*.npz")
        vectors_path.write_bytes(other_vectors.read_bytes())

        with pytest.raises(ValueError) as excinfo:
            NumpyVectorIndex().load(index_dir)
        assert "壊れています" in str(excinfo.value)

    def test_missing_data_file_is_reported_as_corruption(
        self, tmp_path: Path
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        (documents_path,) = index_dir.glob("documents*.jsonl")
        documents_path.unlink()

        with pytest.raises(ValueError) as excinfo:
            NumpyVectorIndex().load(index_dir)
        assert "壊れています" in str(excinfo.value)

    def test_manifest_file_name_cannot_escape_index_dir(
        self, tmp_path: Path
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        manifest_path = index_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["vectors"]["name"] = "../outside.npz"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(ValueError) as excinfo:
            NumpyVectorIndex().load(index_dir)
        assert "壊れています" in str(excinfo.value)

    def test_manifest_without_file_entry_is_reported_as_corruption(
        self, tmp_path: Path
    ) -> None:
        index_dir = tmp_path / "idx"
        _old_generation().save(index_dir)
        manifest_path = index_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["files"]["documents"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(ValueError) as excinfo:
            NumpyVectorIndex().load(index_dir)
        assert "壊れています" in str(excinfo.value)


class TestLegacyIndexCompatibility:
    """世代名・チェックサムを持たない旧形式の索引も読めること（Issue #32）。"""

    def _write_legacy(self, index_dir: Path) -> None:
        import numpy as np

        index_dir.mkdir(parents=True)
        np.savez(
            index_dir / "vectors.npz",
            vectors=np.asarray([(1.0, 0.0), (0.0, 1.0)], dtype=np.float32),
        )
        lines = [
            json.dumps(
                {
                    "doc_id": doc_id, "text": doc_id, "source": "v",
                    "t": "00:00:00", "t_end": None, "duration_seconds": None,
                    "app_guess": None, "action": doc_id,
                },
                ensure_ascii=False,
            )
            for doc_id in ("old-a", "old-b")
        ]
        (index_dir / "documents.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        (index_dir / "manifest.json").write_text(
            json.dumps({"model": "model-old", "dimension": 2, "count": 2}),
            encoding="utf-8",
        )

    def test_legacy_index_loads(self, tmp_path: Path) -> None:
        index_dir = tmp_path / "idx"
        self._write_legacy(index_dir)

        assert _top_hit(index_dir) == OLD_FINGERPRINT

    def test_legacy_count_mismatch_still_raises(self, tmp_path: Path) -> None:
        index_dir = tmp_path / "idx"
        self._write_legacy(index_dir)
        with (index_dir / "documents.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps({
                "doc_id": "extra", "text": "x", "source": "v", "t": "00:00:00",
                "t_end": None, "duration_seconds": None, "app_guess": None,
                "action": "x",
            }) + "\n")

        with pytest.raises(ValueError) as excinfo:
            NumpyVectorIndex().load(index_dir)
        assert "壊れています" in str(excinfo.value)

    def test_crash_while_upgrading_legacy_index_keeps_it_loadable(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        index_dir = tmp_path / "idx"
        self._write_legacy(index_dir)
        _hook_json_dumps(monkeypatch, _is_document, _raise_crash)

        with pytest.raises(SimulatedCrash):
            _new_generation().save(index_dir)

        assert _top_hit(index_dir) == OLD_FINGERPRINT

    def test_save_over_legacy_index_replaces_it(self, tmp_path: Path) -> None:
        index_dir = tmp_path / "idx"
        self._write_legacy(index_dir)

        _new_generation().save(index_dir)

        assert _top_hit(index_dir) == NEW_FINGERPRINT
        assert not (index_dir / "vectors.npz").exists()
        assert not (index_dir / "documents.jsonl").exists()
