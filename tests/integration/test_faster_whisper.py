"""FasterWhisperTranscriber の統合テスト（W7, Issue #16）。

mlx版（test_mlx_whisper.py）と同じアサーションで実文字起こしを検証する。
faster-whisperはMac(CPU)でも動くため、Wz比較検証の布石を兼ねる。
初回はkotoba-whisper-v2.0-fasterのダウンロード（約1.5GB）が走るため slow。
"""

import importlib.util
from pathlib import Path

import pytest
from support.tts import synthesize_speech_video

from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    FasterWhisperTranscriber,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        importlib.util.find_spec("faster_whisper") is None,
        reason="faster-whisper未インストール（uv pip install -e '.[asr-faster]'）",
    ),
]


@pytest.fixture(scope="module")
def speech_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    video = synthesize_speech_video(tmp_path_factory.mktemp("asr-faster"))
    if video is None:
        pytest.skip("TTSが使えない環境")
    return video


class TestFasterWhisperTranscriber:
    def test_transcribes_japanese_speech(self, speech_video: Path) -> None:
        transcriber = FasterWhisperTranscriber()
        segments = transcriber.transcribe(speech_video)

        assert len(segments) >= 1
        all_text = "".join(seg.text for seg in segments)
        # kotoba-whisper v2の日本語認識スモーク（mlx版と同一アサーション）
        assert "作業" in all_text or "テスト" in all_text
        assert all(seg.start.seconds < 6.0 for seg in segments)
