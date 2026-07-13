"""アプリケーション層のポート定義（Protocol）。

インフラ層のアダプタはこれらのProtocolを満たすことで差し替え可能になる。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
    TranscriptSegment,
    Worklog,
)
from screen_activity_logger.domain.search import SearchDocument, SearchHit


class FrameExtractor(Protocol):
    """動画からフレーム列を抽出する。"""

    def extract(self, video_path: Path) -> Sequence[Frame]: ...


class TextRecognizer(Protocol):
    """フレーム画像から文字を抽出する（OCR層）。"""

    def recognize(self, frame: Frame) -> OcrText: ...


class FrameComparator(Protocol):
    """2フレームがほぼ同一画面かを判定する（OCRスキップ用）。"""

    def are_similar(self, a: Frame, b: Frame) -> bool: ...


class SceneDescriber(Protocol):
    """フレーム画像から「何をしているか」を説明する（VLM層）。

    speech: フレーム近傍の発話テキスト（ASR層からのカンニングペーパー）。
    """

    def describe(
        self, frame: Frame, ocr: OcrText, speech: tuple[str, ...] = ()
    ) -> ActivityDescription: ...


class SpeechTranscriber(Protocol):
    """動画の音声を文字起こしする（ASR層）。"""

    def transcribe(self, video_path: Path) -> Sequence[TranscriptSegment]: ...


class SpeechSummarizer(Protocol):
    """エントリの発話断片列から日本語1文の要旨を生成する（Issue #23）。"""

    def summarize(self, lines: tuple[str, ...]) -> str | None: ...


class WorklogWriter(Protocol):
    """Worklogを永続化する（JSONL/Markdown等）。"""

    def write(self, worklog: Worklog, output_path: Path) -> None: ...


class TextEmbedder(Protocol):
    """テキストをベクトル化する（検索層、Issue #5）。

    クエリ/文書のプレフィックス規約はアダプタの責務（Ruri固有仕様）。
    """

    def embed_documents(
        self, texts: Sequence[str]
    ) -> tuple[tuple[float, ...], ...]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...


class VectorSearchIndex(Protocol):
    """ベクトル索引の構築・永続化・検索（検索層、Issue #5）。"""

    def build(
        self,
        documents: Sequence[SearchDocument],
        vectors: Sequence[Sequence[float]],
        model_name: str,
    ) -> None: ...

    def save(self, index_dir: Path) -> None: ...

    def load(self, index_dir: Path) -> None: ...

    def search(
        self, query_vector: Sequence[float], k: int
    ) -> tuple[SearchHit, ...]: ...
