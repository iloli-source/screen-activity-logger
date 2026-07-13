"""検索層のユースケース・読み込みのユニットテスト（Issue #5 P2-P3: RED）。"""

import json
from pathlib import Path

import pytest

from screen_activity_logger.application.search_use_cases import (
    IndexWorklogs,
    SearchWorklogs,
)
from screen_activity_logger.domain.search import SearchDocument, SearchHit
from screen_activity_logger.infrastructure.worklog_reader import (
    read_worklog_records,
)


class TestReadWorklogRecords:
    def test_reads_records_and_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "worklog.jsonl"
        path.write_text(
            '{"t": "00:00:00", "action": "a"}\n\n{"t": "00:00:10", "action": "b"}\n',
            encoding="utf-8",
        )
        records = list(read_worklog_records(path))
        assert [r["action"] for r in records] == ["a", "b"]

    def test_broken_line_raises_with_location(self, tmp_path: Path) -> None:
        path = tmp_path / "worklog.jsonl"
        path.write_text('{"t": "00:00:00"}\n{broken\n', encoding="utf-8")
        with pytest.raises(ValueError) as excinfo:
            list(read_worklog_records(path))
        assert ":2" in str(excinfo.value)  # 何行目かを明示


class FakeEmbedder:
    """テキスト長を1次元ベクトルにする決定的フェイク。"""

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return tuple((float(len(t)),) for t in texts)

    def embed_query(self, text):
        self.query_calls.append(text)
        return (float(len(text)),)


class InMemoryIndex:
    def __init__(self) -> None:
        self.saved_dir: Path | None = None
        self.loaded_dir: Path | None = None
        self._documents: list[SearchDocument] = []
        self._vectors: list = []
        self.model_name: str | None = None

    def build(self, documents, vectors, model_name):
        self._documents = list(documents)
        self._vectors = list(vectors)
        self.model_name = model_name

    def save(self, index_dir: Path) -> None:
        self.saved_dir = index_dir

    def load(self, index_dir: Path, expected_model: str | None = None) -> None:
        self.loaded_expected_model = expected_model
        self.loaded_dir = index_dir

    def search(self, query_vector, k):
        # ベクトル距離（1次元の絶対差）の近い順
        scored = [
            SearchHit(document=doc, score=-abs(vec[0] - query_vector[0]))
            for doc, vec in zip(self._documents, self._vectors)
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])


def _write_jsonl(path: Path, actions: list[str]) -> None:
    lines = [
        json.dumps({"t": f"00:00:0{i}", "action": action}, ensure_ascii=False)
        for i, action in enumerate(actions)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestIndexWorklogs:
    def test_indexes_all_records_from_multiple_files(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "видео_a"
        dir_a.mkdir()
        dir_b = tmp_path / "video_b"
        dir_b.mkdir()
        _write_jsonl(dir_a / "worklog.jsonl", ["会議で自己紹介", "資料を説明"])
        _write_jsonl(dir_b / "worklog.jsonl", ["Excelで集計"])

        embedder = FakeEmbedder()
        index = InMemoryIndex()
        use_case = IndexWorklogs(
            embedder=embedder,
            index=index,
            read_records=read_worklog_records,
            model_name="fake-model",
        )
        count = use_case.execute(
            [dir_a / "worklog.jsonl", dir_b / "worklog.jsonl"],
            index_dir=tmp_path / "index",
        )

        assert count == 3
        assert len(embedder.document_calls[0]) == 3
        assert index.model_name == "fake-model"
        assert index.saved_dir == tmp_path / "index"
        # sourceは親ディレクトリ名、doc_idは連番
        assert index._documents[0].source == "видео_a"
        assert index._documents[2].doc_id == "video_b:0"


class TestSearchWorklogs:
    def test_returns_top_k_by_score(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        index = InMemoryIndex()
        docs = [
            SearchDocument(
                doc_id=f"v:{i}", text=t, source="v", t="00:00:00",
                t_end=None, duration_seconds=None, app_guess=None, action=t,
            )
            for i, t in enumerate(["短い", "ちょっと長いテキスト", "中くらい文"])
        ]
        index.build(docs, [(3.0,), (10.0,), (6.0,)], model_name="fake")

        use_case = SearchWorklogs(embedder=embedder, index=index)
        hits = use_case.execute("与えるク", index_dir=tmp_path, k=2)  # len=4

        assert index.loaded_dir == tmp_path
        assert len(hits) == 2
        assert hits[0].document.doc_id == "v:0"  # |3-4|=1 が最も近い


class TestSearchCliBuilders:
    """P7（Issue #5）: sal-searchのDI組み立て検証。"""

    def test_index_use_case_wiring(self) -> None:
        from screen_activity_logger.infrastructure.numpy_index import (
            NumpyVectorIndex,
        )
        from screen_activity_logger.infrastructure.ruri_embedder import (
            RuriEmbedder,
        )
        from screen_activity_logger.search_cli import build_index_use_case

        use_case = build_index_use_case(model="cl-nagoya/ruri-v3-130m")
        assert isinstance(use_case.embedder, RuriEmbedder)
        assert use_case.embedder.model_name == "cl-nagoya/ruri-v3-130m"
        assert isinstance(use_case.index, NumpyVectorIndex)
        assert use_case.model_name == "cl-nagoya/ruri-v3-130m"

    def test_format_hit_shows_range_and_action(self) -> None:
        from screen_activity_logger.search_cli import format_hit

        doc = SearchDocument(
            doc_id="02:1", text="", source="02", t="00:01:46",
            t_end="00:03:21", duration_seconds=95.0,
            app_guess="Excel", action="SUM関数で集計している",
        )
        line = format_hit(1, SearchHit(document=doc, score=0.724))
        assert "[0.724]" in line
        assert "00:01:46〜00:03:21" in line
        assert "Excel" in line
        assert "SUM関数で集計している" in line


class TestSearchWorklogsModelGuard:
    """4AIレビューR1: 索引モデルとクエリ埋め込みモデルの不一致を検出する。"""

    def test_load_receives_expected_model(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        index = InMemoryIndex()
        index.build([], [], model_name="model-a")

        use_case = SearchWorklogs(
            embedder=embedder, index=index, model_name="model-a"
        )
        use_case.execute("query", index_dir=tmp_path, k=1)

        assert index.loaded_expected_model == "model-a"
