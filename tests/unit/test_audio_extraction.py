"""ASR共通の音声抽出コマンド構築のユニットテスト（W1: RED）。"""

from pathlib import Path

from screen_activity_logger.infrastructure.audio_extraction import (
    ffmpeg_wav_command,
)


class TestFfmpegWavCommand:
    def test_builds_16khz_mono_wav_command(self) -> None:
        command = ffmpeg_wav_command(Path("/videos/rec.mp4"), Path("/tmp/a.wav"))
        assert command[0] == "ffmpeg"
        assert "-y" in command
        assert str(Path("/videos/rec.mp4")) in command
        assert command[-1] == str(Path("/tmp/a.wav"))
        # ASR前提: 映像なし・モノラル・16kHz
        assert "-vn" in command
        ac_index = command.index("-ac")
        assert command[ac_index + 1] == "1"
        ar_index = command.index("-ar")
        assert command[ar_index + 1] == "16000"

    def test_input_precedes_output(self) -> None:
        command = ffmpeg_wav_command(Path("in.mp4"), Path("out.wav"))
        assert command.index(str(Path("in.mp4"))) < command.index(str(Path("out.wav")))
