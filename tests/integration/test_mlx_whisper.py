"""MlxWhisperTranscriber の統合テスト（Cycle R-2: RED）。

macの`say`で合成した日本語音声入り動画を実際に文字起こしする。
初回はkotoba-whisper-v2.0-mlxモデルのダウンロードが走るため slow。
"""

import subprocess
from pathlib import Path

import pytest

from screen_activity_logger.infrastructure.ffmpeg_extractor import has_audio_stream
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    MlxWhisperTranscriber,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def speech_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """「作業ログのテストを実行しています」と喋る5秒動画。"""
    base = tmp_path_factory.mktemp("asr")
    aiff = base / "speech.aiff"
    subprocess.run(
        ["say", "-v", "Kyoko", "-o", str(aiff), "作業ログのテストを実行しています"],
        check=True,
        capture_output=True,
    )
    video = base / "speech.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=gray:size=320x240:duration=5:rate=10",
            "-i", str(aiff),
            "-c:a", "aac", "-shortest", "-pix_fmt", "yuv420p", str(video),
        ],
        check=True,
        capture_output=True,
    )
    return video


class TestHasAudioStream:
    def test_detects_audio_in_speech_video(self, speech_video: Path) -> None:
        assert has_audio_stream(speech_video) is True

    def test_no_audio_in_silent_video(
        self, tmp_path: Path
    ) -> None:
        silent = tmp_path / "silent.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=red:size=320x240:duration=2:rate=10",
                "-pix_fmt", "yuv420p", str(silent),
            ],
            check=True,
            capture_output=True,
        )
        assert has_audio_stream(silent) is False


class TestMlxWhisperTranscriber:
    def test_transcribes_japanese_speech(self, speech_video: Path) -> None:
        transcriber = MlxWhisperTranscriber()
        segments = transcriber.transcribe(speech_video)

        assert len(segments) >= 1
        all_text = "".join(seg.text for seg in segments)
        # kotoba-whisper v2の日本語認識スモーク（表記ゆれ許容）
        assert "作業" in all_text or "テスト" in all_text
        # タイムスタンプが動画範囲内
        assert all(seg.start.seconds < 6.0 for seg in segments)
