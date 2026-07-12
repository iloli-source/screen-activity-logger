"""mlx-whisperによるSpeechTranscriberポートの実装（Apple Silicon GPU）。

既定モデルは日本語特化のkotoba-whisper v2（MLX変換版）。
モデルは設定値のため、多言語用whisper-large-v3-turbo等へ差し替え可能。
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp

DEFAULT_ASR_MODEL = "kaiinui/kotoba-whisper-v2.0-mlx"


def segments_from_result(result: Any) -> tuple[TranscriptSegment, ...]:
    """mlx_whisper.transcribe の結果dictをTranscriptSegment列に変換する。

    実会議音声ではWhisperが end < start や負のstartを返すことがあるため、
    ドメインの不変条件を満たすようクランプする（発話テキストは保持）。
    """
    segments = []
    for raw in result.get("segments", ()):
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        start = max(0.0, float(raw["start"]))
        end = max(start, float(raw["end"]))
        segments.append(
            TranscriptSegment(
                start=VideoTimestamp(seconds=start),
                end=VideoTimestamp(seconds=end),
                text=text,
                no_speech_prob=_optional_float(raw.get("no_speech_prob")),
                avg_logprob=_optional_float(raw.get("avg_logprob")),
            )
        )
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
            self._extract_audio(video_path, wav_path)
            result = self._run_whisper(wav_path)
        return segments_from_result(result)

    @staticmethod
    def _extract_audio(video_path: Path, wav_path: Path) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "16000",
                str(wav_path),
            ],
            check=True,
            capture_output=True,
        )

    def _run_whisper(self, wav_path: Path) -> Any:
        import mlx_whisper

        return mlx_whisper.transcribe(
            str(wav_path), path_or_hf_repo=self._model, language="ja"
        )
