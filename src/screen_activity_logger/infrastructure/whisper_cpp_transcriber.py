"""whisper.cpp（Metal GPU）によるSpeechTranscriberポートの実装（Issue #22）。

長時間実測（2時間合成入力）でmlx-whisperは内容崩壊＋40倍超の減速、
faster-whisper(CPU)は実時間の1.3〜1.9倍しか出ないことが確定したため追加。
whisper.cppは同一kotoba重み（q5_0）で「fasterの品質×mlxの速度」を両取りする
（10分音声39s・内容線形）。whisper-cliバイナリをsubprocessで呼び、
-oj のJSON出力（offsetsはミリ秒）を共通正規化build_segmentへ流す。
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any

from screen_activity_logger.domain.models import TranscriptSegment
from screen_activity_logger.infrastructure.asr_segments import build_segment
from screen_activity_logger.infrastructure.audio_extraction import extract_audio_wav
from screen_activity_logger.infrastructure.subprocess_runner import run_captured

DEFAULT_CPP_BINARY = "whisper-cli"
DEFAULT_CPP_ASR_MODEL_PATH = (
    Path.home() / ".cache" / "screen-activity-logger"
    / "kotoba-whisper-v2.0-q5_0.bin"
)

_MS_PER_SECOND = 1000.0

# 3時間音声≒15分（実測15倍速）に余裕を持たせた上限（ハング防止、4AIレビューR1）
WHISPER_CLI_TIMEOUT_SECONDS = 7200.0


def segments_from_cpp_json(payload: dict) -> tuple[TranscriptSegment, ...]:
    """whisper-cli -oj のJSONをTranscriptSegment列に変換する。

    mlx版segments_from_result / faster版segments_from_faster_segmentsと対。
    no_speech_probはwhisper.cppのJSONに存在しないためNone。avg_logprobは
    -ojf のトークン確率pから算出し、幻覚フィルタの第二防衛線を生かす
    （4AIレビューR1: 旧実装は両方Noneでフィルタが素通しだった）。
    """
    segments = []
    for raw in payload.get("transcription", ()):
        offsets = raw.get("offsets", {})
        segment = build_segment(
            start=float(offsets.get("from", 0)) / _MS_PER_SECOND,
            end=float(offsets.get("to", 0)) / _MS_PER_SECOND,
            text=str(raw.get("text", "")),
            no_speech_prob=None,
            avg_logprob=_avg_logprob_from_tokens(raw.get("tokens", ())),
        )
        if segment is not None:
            segments.append(segment)
    return tuple(segments)


def _avg_logprob_from_tokens(tokens) -> float | None:
    """トークン確率の対数平均（[_BEG_]等の特殊トークンは除外）。"""
    probs = [
        float(tok["p"])
        for tok in tokens
        if tok.get("p") is not None
        and float(tok["p"]) > 0  # log定義域ガード（4AIレビューR2）
        and not str(tok.get("text", "")).startswith("[_")
    ]
    if not probs:
        return None
    return sum(math.log(p) for p in probs) / len(probs)


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
        run_captured(
            [
                self._binary,
                "-m", str(self._model_path),
                "-f", str(wav_path),
                "-l", "ja",
                "-ojf",  # full JSON（トークン確率つき）
                "-of", str(output_prefix),
            ],
            timeout_seconds=WHISPER_CLI_TIMEOUT_SECONDS,
        )
        json_path = output_prefix.with_suffix(".json")
        return json.loads(json_path.read_text(encoding="utf-8"))
