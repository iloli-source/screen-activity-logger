"""チャンク分割ASRの統率（Issue #29）。

長時間音声をchunk_spansで割り、チャンク毎にwav抽出→転写→絶対時刻へ変換→
lead-in重複を除去して連結する。並列度はバックエンドの特性に合わせて
呼び出し側（asr_factory）が決める（GPU系=1、CPU系=N）。
"""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Protocol, Sequence

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp
from screen_activity_logger.infrastructure.audio_chunking import (
    DEFAULT_OVERLAP_SECONDS,
    chunk_spans,
    merge_chunked_segments,
)
from screen_activity_logger.infrastructure.audio_extraction import (
    audio_duration_seconds,
    extract_audio_wav_span,
)


# (チャンク開始秒, 終了秒, セグメント列)。転写に失敗したチャンクはNone
_ChunkResult = tuple[float, float, tuple[TranscriptSegment, ...] | None]


class WavTranscriber(Protocol):
    """wavファイル1個を転写できるASRアダプタ。"""

    def transcribe(self, video_path: Path) -> Sequence[TranscriptSegment]: ...

    def transcribe_wav(self, wav_path: Path) -> Sequence[TranscriptSegment]: ...


class ChunkedTranscriber:
    """音声をチャンクに割って転写するSpeechTranscriber実装。"""

    def __init__(
        self,
        inner: WavTranscriber,
        chunk_seconds: float,
        overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
        max_workers: int = 1,
    ) -> None:
        self._inner = inner
        self._chunk_seconds = chunk_seconds
        self._overlap_seconds = overlap_seconds
        self._max_workers = max(1, max_workers)

    def transcribe(self, video_path: Path) -> tuple[TranscriptSegment, ...]:
        duration = audio_duration_seconds(video_path)
        spans = chunk_spans(duration, self._chunk_seconds, self._overlap_seconds)
        if len(spans) == 1:
            # 短い入力は従来経路（余計な再抽出をしない）
            return tuple(self._inner.transcribe(video_path))
        with tempfile.TemporaryDirectory(prefix="sal-chunks-") as tmp:
            wav_paths = []
            for index, (_, _, media_start, media_duration) in enumerate(spans):
                wav = Path(tmp) / f"chunk_{index:03d}.wav"
                extract_audio_wav_span(video_path, wav, media_start, media_duration)
                wav_paths.append(wav)
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                results = list(
                    pool.map(self._transcribe_chunk, spans, wav_paths)
                )
        _report_failed_chunks(results)
        return merge_chunked_segments(
            [(start, end, segments or ()) for start, end, segments in results]
        )

    def _transcribe_chunk(
        self, span: tuple[float, float, float, float], wav_path: Path
    ) -> _ChunkResult:
        """1チャンクを転写する。失敗時のセグメントはNone（発話なしの()と区別）。"""
        chunk_start, chunk_end, media_start, _ = span
        try:
            relative = self._inner.transcribe_wav(wav_path)
        except Exception as error:  # noqa: BLE001 — 1チャンクの失敗で全体を止めない
            print(
                f"チャンク転写失敗（{chunk_start:.0f}s〜、空として続行）:"
                f" {type(error).__name__}: {error}",
                flush=True,
            )
            return (chunk_start, chunk_end, None)
        absolute = tuple(
            replace(
                seg,
                start=VideoTimestamp(seconds=media_start + seg.start.seconds),
                end=VideoTimestamp(seconds=media_start + seg.end.seconds),
            )
            for seg in relative
        )
        return (chunk_start, chunk_end, absolute)


def _report_failed_chunks(results: Sequence[_ChunkResult]) -> None:
    """失敗チャンクの欠落区間をまとめて知らせる（Issue #32）。

    失敗チャンクは空として続行するため、出力だけ見ると「その区間は発話なし」
    と区別できない。件数と区間を最後に1回出し、欠落に気付けるようにする。
    """
    failed = [(start, end) for start, end, segments in results if segments is None]
    if not failed:
        return
    ranges = "、".join(
        f"{VideoTimestamp(seconds=start)}〜{VideoTimestamp(seconds=end)}"
        for start, end in failed
    )
    message = (
        f"警告: ASRは{len(results)}チャンク中{len(failed)}チャンクの転写に失敗しました。"
        f"該当区間の発話はログから欠落します: {ranges}"
    )
    if len(failed) == len(results):
        message += "（発話は1件も取得できていません。ASRの設定・モデルを確認してください）"
    print(message, flush=True)
