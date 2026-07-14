"""ffmpegによる16kHzモノラルwav抽出（ASRバックエンド共通の前処理）。

faster-whisperは動画を直接デコードできるが、あえてwav抽出を挟むことで
mlx/faster両バックエンドに「同一の音声入力」を与え、結果差の変数を減らす。
ffmpegのPATH解決・エラー挙動も両者で完全に揃う（Windows対応 Issue #16）。
"""

from __future__ import annotations

from pathlib import Path

from screen_activity_logger.infrastructure.subprocess_runner import run_captured

# 3時間級入力の実測（2時間で数分）から十分な余裕を持たせた上限。
# 無制限だとffmpegハングでバッチ全体が永久停止する（4AIレビューR1）
FFMPEG_TIMEOUT_SECONDS = 1800.0


def ffmpeg_wav_command(video_path: Path, wav_path: Path) -> list[str]:
    """16kHzモノラルwav抽出コマンドを構築する（純粋関数）。"""
    return [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(wav_path),
    ]


def extract_audio_wav(video_path: Path, wav_path: Path) -> None:
    run_captured(
        ffmpeg_wav_command(video_path, wav_path),
        timeout_seconds=FFMPEG_TIMEOUT_SECONDS,
    )
