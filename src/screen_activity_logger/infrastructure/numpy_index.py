"""numpyブルートフォースのベクトル索引（Issue #5）。

正規化済み内積（=コサイン類似度）の全件走査。1万エントリ×256次元で
数ms・約10MBのため、この規模ではANN（faiss等）は不要（ポートで抽象化
してあるため、スケール時にfaissアダプタへ差し替え可能）。

永続化形式（index_dir/）:
  vectors-<世代>.npz     — float32 (N, D)、L2正規化済み
  documents-<世代>.jsonl — 1行=1文書（text＋表示用メタデータ）
  manifest.json          — {model, dimension, count, generation, files}

保存は世代単位（Issue #32）。データ2ファイルを世代つきの新しい名前で書き、
最後にmanifest.jsonを原子的に差し替える（ここがコミット点）。manifestは
自分の世代のファイル名とSHA-256を持つので、保存途中で止まっても・保存中に
読まれても、loadは「揃った1世代」を返すか破損として報告するかのどちらかに
なる。旧形式（vectors.npz / documents.jsonl 固定名、filesなし）も読める。
モデルの検討記録は formal/IndexSave.tla。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from screen_activity_logger.domain.search import SearchDocument, SearchHit
from screen_activity_logger.infrastructure.atomic_write import atomic_write_text

MANIFEST_NAME = "manifest.json"
_LEGACY_FILES = {"vectors": "vectors.npz", "documents": "documents.jsonl"}
_DATA_FILE_PATTERNS = ("vectors*.npz", "documents*.jsonl")
_REBUILD_HINT = "sal-search index で再作成してください"


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
        generation = uuid.uuid4().hex
        names = {
            "vectors": f"vectors-{generation}.npz",
            "documents": f"documents-{generation}.jsonl",
        }
        try:
            buffer = io.BytesIO()
            np.savez(buffer, vectors=self._vectors)
            files = {
                "vectors": _write_data_file(
                    index_dir / names["vectors"], buffer.getvalue()
                )
            }
            documents_lines = "\n".join(
                json.dumps(asdict(doc), ensure_ascii=False)
                for doc in self._documents
            )
            files["documents"] = _write_data_file(
                index_dir / names["documents"],
                (documents_lines + "\n").encode("utf-8"),
            )
            manifest = {
                "model": self._model_name,
                "dimension": int(self._vectors.shape[1]),
                "count": len(self._documents),
                "generation": generation,
                "files": files,
            }
            # コミット点: ここより前で止まれば旧世代が、後なら新世代が読まれる
            atomic_write_text(
                index_dir / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False)
            )
        except BaseException:
            _remove_files(index_dir / name for name in names.values())
            raise
        _remove_stale_data_files(index_dir, keep=set(names.values()))

    def load(self, index_dir: Path, expected_model: str | None = None) -> None:
        import numpy as np

        manifest = json.loads(
            (index_dir / MANIFEST_NAME).read_text(encoding="utf-8")
        )
        if expected_model is not None and manifest["model"] != expected_model:
            raise ValueError(
                f"索引のモデル不一致: 索引={manifest['model']} / "
                f"指定={expected_model}。{_REBUILD_HINT}"
            )
        files = manifest.get("files")
        vectors_bytes = _read_data_file(index_dir, files, "vectors")
        documents_bytes = _read_data_file(index_dir, files, "documents")
        vectors = np.load(io.BytesIO(vectors_bytes))["vectors"]
        documents = tuple(
            SearchDocument(**json.loads(line))
            for line in documents_bytes.decode("utf-8").splitlines()
            if line.strip()
        )
        if len(vectors) != len(documents):
            raise ValueError(
                f"索引が壊れています: vectors {len(vectors)}行 vs "
                f"documents {len(documents)}件。{_REBUILD_HINT}"
            )
        self._model_name = manifest["model"]
        self._vectors = vectors
        self._documents = documents

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


def _write_data_file(path: Path, data: bytes) -> dict[str, Any]:
    """世代つきの新規ファイルを書き、manifestに載せる照合情報を返す。

    manifestが指すまで誰にも読まれない名前のため、直接書いてよい。
    """
    with open(path, "xb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    return {
        "name": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def _read_data_file(
    index_dir: Path, files: dict[str, Any] | None, kind: str
) -> bytes:
    """manifestが指すデータファイルを読み、同じ世代のものか照合する。"""
    if files is None:
        # 旧形式: 固定名・照合情報なし（件数照合はload側）
        return (index_dir / _LEGACY_FILES[kind]).read_bytes()
    try:
        name, expected_sha256 = files[kind]["name"], files[kind]["sha256"]
    except (KeyError, TypeError):
        raise ValueError(
            f"索引が壊れています: manifestに{kind}の情報がありません。{_REBUILD_HINT}"
        ) from None
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError(
            f"索引が壊れています: manifestのファイル名が不正です（{name}）。"
            f"{_REBUILD_HINT}"
        )
    try:
        data = (index_dir / name).read_bytes()
    except FileNotFoundError:
        raise ValueError(
            f"索引が壊れています: {name} がありません（索引の更新中に読んだ場合は"
            f"再実行してください）。{_REBUILD_HINT}"
        ) from None
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError(
            f"索引が壊れています: {name} の内容がmanifestと一致しません。"
            f"{_REBUILD_HINT}"
        )
    return data


def _remove_stale_data_files(index_dir: Path, keep: set[str]) -> None:
    """現世代以外のデータファイル（旧世代・旧形式・中断した保存の残骸）を消す。"""
    _remove_files(
        path
        for pattern in _DATA_FILE_PATTERNS
        for path in index_dir.glob(pattern)
        if path.name not in keep
    )


def _remove_files(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Windowsでは読み込み中のファイルを消せない。索引の正しさには
            # 影響しないため次回の保存に任せる
            pass
