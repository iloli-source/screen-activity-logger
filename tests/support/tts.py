"""テスト用の日本語TTS音声つき動画合成（マルチプラットフォーム、Issue #16）。

macOSは`say`、WindowsはPowerShellのSpeechSynthesizerを使う。
どちらも使えない環境（Linux CI等）はNoneを返し、呼び出し側でskipする。
sine波では発話内容の検証（「作業/テスト を含む」）ができないため不採用。
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

SPEECH_TEXT = "作業ログのテストを実行しています"


def synthesize_speech_video(base_dir: Path) -> Path | None:
    """SPEECH_TEXTを喋る5秒動画を合成する。TTSが使えなければNone。"""
    audio = _synthesize_audio(base_dir)
    if audio is None:
        return None
    video = base_dir / "speech.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=gray:size=320x240:duration=5:rate=10",
            "-i", str(audio),
            "-c:a", "aac", "-shortest", "-pix_fmt", "yuv420p", str(video),
        ],
        check=True,
        capture_output=True,
    )
    return video


def _synthesize_audio(base_dir: Path) -> Path | None:
    if shutil.which("say"):  # macOS
        aiff = base_dir / "speech.aiff"
        subprocess.run(
            ["say", "-v", "Kyoko", "-o", str(aiff), SPEECH_TEXT],
            check=True,
            capture_output=True,
        )
        return aiff
    if platform.system() == "Windows":
        wav = base_dir / "speech.wav"
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{wav}'); "
            f"$s.Speak('{SPEECH_TEXT}'); $s.Dispose()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=True,
            capture_output=True,
        )
        return wav
    return None
