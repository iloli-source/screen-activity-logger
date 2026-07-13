"""whisper.cpp（Metal GPU）によるSpeechTranscriberポートの実装（Issue #22）。

長時間実測（2時間合成入力）でmlx-whisperは内容崩壊＋40倍超の減速、
faster-whisper(CPU)は実時間の1.3〜1.9倍しか出ないことが確定したため追加。
whisper.cppは同一kotoba重み（q5_0）で「fasterの品質×mlxの速度」を両取りする
（10分音声39s・内容線形）。whisper-cliバイナリをsubprocessで呼び、
-oj のJSON出力（offsetsはミリ秒）を共通正規化build_segmentへ流す。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import TranscriptSegment
from screen_activity_logger.infrastructure.asr_segments import build_segment
from screen_activity_logger.infrastructure.audio_extraction import extract_audio_wav

DEFAULT_CPP_BINARY = "whisper-cli"
DEFAULT_CPP_ASR_MODEL_PATH = (
    Path.home() / ".cache" / "screen-activity-logger"
    / "kotoba-whisper-v2.0-q5_0.bin"
)

_MS_PER_SECOND = 1000.0


def segments_from_cpp_json(payload: dict) -> tuple[TranscriptSegment, ...]:
    """whisper-cli -oj のJSONをTranscriptSegment列に変換する。

    mlx版segments_from_result / faster版segments_from_faster_segmentsと対。
    -oj出力にno_speech_prob/avg_logprobはないためNone（speech_filterは
    None値をフィルタ対象にしない）。
    """
    segments = []
    for raw in payload.get("transcription", ()):
        offsets = raw.get("offsets", {})
        segment = build_segment(
            start=float(offsets.get("from", 0)) / _MS_PER_SECOND,
            end=float(offsets.get("to", 0)) / _MS_PER_SECOND,
            text=str(raw.get("text", "")),
            no_speech_prob=None,
            avg_logprob=None,
        )
        if segment is not None:
            segments.append(segment)
    return tuple(segments)


class WhisperCppTranscriber:
    """動画音声をffmpegで抽出し、whisper-cli（whisper.cpp）で文字起こしする。"""

    def __init__(
        self,
        model_path: Path | str = DEFAULT_CPP_ASR_MODEL_PATH,
        binary: str = DEFAULT_CPP_BINARY,
    ) -> None:
        self._model_path = Path(model_path)
        self._binary = binary

    def transcribe(self, video_path: Path) -> tuple[TranscriptSegment, ...]:
        with tempfile.TemporaryDirectory(prefix="sal-audio-") as tmp:
            wav_path = Path(tmp) / "audio.wav"
            extract_audio_wav(video_path, wav_path)
            payload = self._run_whisper_cli(wav_path, Path(tmp) / "out")
        return segments_from_cpp_json(payload)

    def _run_whisper_cli(self, wav_path: Path, output_prefix: Path) -> Any:
        subprocess.run(
            [
                self._binary,
                "-m", str(self._model_path),
                "-f", str(wav_path),
                "-l", "ja",
                "-oj",
                "-of", str(output_prefix),
            ],
            check=True,
            capture_output=True,
        )
        json_path = output_prefix.with_suffix(".json")
        return json.loads(json_path.read_text(encoding="utf-8"))
