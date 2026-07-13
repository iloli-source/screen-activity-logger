"""ユースケース: 作業ログの索引作成と意味検索（Issue #5）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence

from screen_activity_logger.application.ports import (
    TextEmbedder,
    VectorSearchIndex,
)
from screen_activity_logger.domain.search import (
    SearchDocument,
    SearchHit,
    build_search_document,
)


@dataclass(frozen=True)
class IndexWorklogs:
    """worklog.jsonl群から検索索引を構築して保存する。"""

    embedder: TextEmbedder
    index: VectorSearchIndex
    read_records: Callable[[Path], Iterator[dict]]
    model_name: str

    def execute(self, jsonl_paths: Sequence[Path], index_dir: Path) -> int:
        documents: list[SearchDocument] = []
        for path in jsonl_paths:
            source = path.parent.name or path.stem
            for position, record in enumerate(self.read_records(path)):
                documents.append(
                    build_search_document(
                        record, source=source, doc_id=f"{source}:{position}"
                    )
                )
        vectors = self.embedder.embed_documents([doc.text for doc in documents])
        self.index.build(documents, vectors, model_name=self.model_name)
        self.index.save(index_dir)
        return len(documents)


@dataclass(frozen=True)
class SearchWorklogs:
    """保存済み索引に対する意味検索。

    model_name: クエリ埋め込みに使うモデル。索引manifestと不一致なら
    load側が明示エラーにする（無言の無意味スコアを防ぐ、4AIレビューR1）。
    """

    embedder: TextEmbedder
    index: VectorSearchIndex
    model_name: str | None = None

    def execute(self, query: str, index_dir: Path, k: int = 5) -> tuple[SearchHit, ...]:
        self.index.load(index_dir, expected_model=self.model_name)
        query_vector = self.embedder.embed_query(query)
        return self.index.search(query_vector, k=k)
