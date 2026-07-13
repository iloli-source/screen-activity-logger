"""numpyブルートフォースのベクトル索引（Issue #5）。

正規化済み内積（=コサイン類似度）の全件走査。1万エントリ×256次元で
数ms・約10MBのため、この規模ではANN（faiss等）は不要（ポートで抽象化
してあるため、スケール時にfaissアダプタへ差し替え可能）。

永続化形式（index_dir/）:
  vectors.npz     — float32 (N, D)、L2正規化済み
  documents.jsonl — 1行=1文書（text＋表示用メタデータ）
  manifest.json   — {model, dimension, count}（クエリ時のモデル不一致検出）
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from screen_activity_logger.domain.search import SearchDocument, SearchHit


class NumpyVectorIndex:
    """VectorSearchIndexポートのnumpy実装。numpyは遅延import。"""

    def __init__(self) -> None:
        self._documents: tuple[SearchDocument, ...] = ()
        self._vectors: Any = None  # np.ndarray (N, D) 正規化済み
        self._model_name: str | None = None

    def build(
        self,
        documents: Sequence[SearchDocument],
        vectors: Sequence[Sequence[float]],
        model_name: str,
    ) -> None:
        import numpy as np

        self._documents = tuple(documents)
        matrix = np.asarray(vectors, dtype=np.float32)
        self._vectors = _normalize_rows(np, matrix)
        self._model_name = model_name

    def save(self, index_dir: Path) -> None:
        import numpy as np

        index_dir.mkdir(parents=True, exist_ok=True)
        np.savez(index_dir / "vectors.npz", vectors=self._vectors)
        documents_lines = "\n".join(
            json.dumps(asdict(doc), ensure_ascii=False) for doc in self._documents
        )
        (index_dir / "documents.jsonl").write_text(
            documents_lines + "\n", encoding="utf-8"
        )
        manifest = {
            "model": self._model_name,
            "dimension": int(self._vectors.shape[1]),
            "count": len(self._documents),
        }
        (index_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

    def load(self, index_dir: Path, expected_model: str | None = None) -> None:
        import numpy as np

        manifest = json.loads(
            (index_dir / "manifest.json").read_text(encoding="utf-8")
        )
        if expected_model is not None and manifest["model"] != expected_model:
            raise ValueError(
                f"索引のモデル不一致: 索引={manifest['model']} / "
                f"指定={expected_model}。sal-search index で再作成してください"
            )
        self._model_name = manifest["model"]
        self._vectors = np.load(index_dir / "vectors.npz")["vectors"]
        self._documents = tuple(
            SearchDocument(**json.loads(line))
            for line in (index_dir / "documents.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )

    @property
    def model_name(self) -> str | None:
        return self._model_name

    def search(
        self, query_vector: Sequence[float], k: int
    ) -> tuple[SearchHit, ...]:
        import numpy as np

        if self._vectors is None or len(self._documents) == 0:
            return ()
        query = np.asarray(query_vector, dtype=np.float32)
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        scores = self._vectors @ query
        order = np.argsort(-scores)[:k]
        return tuple(
            SearchHit(document=self._documents[i], score=float(scores[i]))
            for i in order
        )


def _normalize_rows(np: Any, matrix: Any) -> Any:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms
