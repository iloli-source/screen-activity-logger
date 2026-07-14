"""mlx-whisperによるSpeechTranscriberポートの実装（Apple Silicon GPU）。

既定モデルは日本語特化のkotoba-whisper v2（MLX変換版）。
モデルは設定値のため、多言語用whisper-large-v3-turbo等へ差し替え可能。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import TranscriptSegment
from screen_activity_logger.infrastructure.asr_segments import build_segment
from screen_activity_logger.infrastructure.audio_extraction import extract_audio_wav

DEFAULT_ASR_MODEL = "kaiinui/kotoba-whisper-v2.0-mlx"


def segments_from_result(result: Any) -> tuple[TranscriptSegment, ...]:
    """mlx_whisper.transcribe の結果dictをTranscriptSegment列に変換する。

    正規化（クランプ・空スキップ）はバックエンド共通のbuild_segmentに委譲。
    """
    segments = []
    for raw in result.get("segments", ()):
        segment = build_segment(
            start=float(raw["start"]),
            end=float(raw["end"]),
            text=str(raw.get("text", "")),
            no_speech_prob=_optional_float(raw.get("no_speech_prob")),
            avg_logprob=_optional_float(raw.get("avg_logprob")),
        )
        if segment is not None:
            segments.append(segment)
    return tuple(segments)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


class MlxWhisperTranscriber:
    """動画の音声をffmpegで抽出し、mlx-whisperで文字起こしする。"""

    def __init__(self, model: str = DEFAULT_ASR_MODEL) -> None:
        self._model = model

    def transcribe(self, video_path: Path) -> tuple[TranscriptSegment, ...]:
        with tempfile.TemporaryDirectory(prefix="sal-audio-") as tmp:
            wav_path = Path(tmp) / "audio.wav"
            extract_audio_wav(video_path, wav_path)
            result = self._run_whisper(wav_path)
        return segments_from_result(result)

    def _run_whisper(self, wav_path: Path) -> Any:
        import mlx_whisper

        return mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=self._model,
            language="ja",
            condition_on_previous_text=False,  # 幻覚連鎖の抑制（fasterと対称）
        )
