"""faster-whisper（CTranslate2）によるSpeechTranscriberポートの実装。

Windows/Linux/Intel Mac向けのASRバックエンド（Issue #16）。既定モデルは
kotoba-whisper v2.0の公式CTranslate2変換版。mlx版と同じく
ffmpegでwav抽出 → 認識 → 共通正規化（asr_segments.build_segment）の流れ。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Iterable

from screen_activity_logger.domain.models import TranscriptSegment
from screen_activity_logger.infrastructure.asr_segments import build_segment
from screen_activity_logger.infrastructure.audio_extraction import extract_audio_wav

DEFAULT_FASTER_ASR_MODEL = "kotoba-tech/kotoba-whisper-v2.0-faster"


def segments_from_faster_segments(
    raw_segments: Iterable[Any],
) -> tuple[TranscriptSegment, ...]:
    """faster-whisperのSegment列をTranscriptSegment列に変換する。

    mlx版segments_from_resultと対。transcribe()は遅延ジェネレータを返す
    ため、ここで完全に消費する（消費しないと推論が走らない）。
    """
    segments = []
    for raw in raw_segments:
        segment = build_segment(
            start=float(raw.start),
            end=float(raw.end),
            text=str(raw.text),
            no_speech_prob=_optional_float(getattr(raw, "no_speech_prob", None)),
            avg_logprob=_optional_float(getattr(raw, "avg_logprob", None)),
        )
        if segment is not None:
            segments.append(segment)
    return tuple(segments)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


class FasterWhisperTranscriber:
    """動画音声をffmpegで抽出し、faster-whisperで文字起こしする。

    WhisperModelは初回ロード後インスタンス内にキャッシュする
    （バッチのPhase A直列実行で「モデルロード1回」を維持、Issue #7と同方針）。
    device/compute_type="auto"はCTranslate2がCUDA有無を自動判別し、
    CUDA未導入のWindowsでもCPU(int8)にフォールバックする。
    """

    def __init__(
        self,
        model: str = DEFAULT_FASTER_ASR_MODEL,
        device: str = "auto",
        compute_type: str = "auto",
        num_workers: int = 1,
    ) -> None:
        self._model = model
        self._device = device
        self._compute_type = compute_type
        self._num_workers = max(1, num_workers)  # 並列transcribe用（Issue #29）
        self._loaded_model: Any = None

    def transcribe(self, video_path: Path) -> tuple[TranscriptSegment, ...]:
        with tempfile.TemporaryDirectory(prefix="sal-audio-") as tmp:
            wav_path = Path(tmp) / "audio.wav"
            extract_audio_wav(video_path, wav_path)
            raw_segments = self._run_whisper(wav_path)
            # 一時ディレクトリ内で消費し切る（遅延ジェネレータ対策）
            return segments_from_faster_segments(raw_segments)

    def transcribe_wav(self, wav_path: Path) -> tuple[TranscriptSegment, ...]:
        """wav1個の転写（チャンク分割ASR用、Issue #29）。

        CTranslate2モデルはスレッドセーフで、num_workers>1なら複数スレッド
        からの同時transcribeを実並列で処理する（モデルは1つを共有）。
        """
        return segments_from_faster_segments(self._run_whisper(wav_path))

    def _run_whisper(self, wav_path: Path) -> Any:
        if self._loaded_model is None:
            from faster_whisper import WhisperModel  # 遅延import（mlx版と同方針）

            self._loaded_model = WhisperModel(
                self._model,
                device=self._device,
                compute_type=self._compute_type,
                # チャンク並列時に複数スレッドからのtranscribeを実並列で
                # 処理する（CTranslate2のinter_threads。モデルは1つを共有）
                num_workers=self._num_workers,
            )
        raw_segments, _info = self._loaded_model.transcribe(
            str(wav_path),
            language="ja",
            chunk_length=15,  # kotoba公式推奨
            condition_on_previous_text=False,  # kotoba公式推奨＋幻覚連鎖の抑制
            vad_filter=False,  # mlxと挙動を揃え、幻覚対策はdomainフィルタに一元化
        )
        return raw_segments
