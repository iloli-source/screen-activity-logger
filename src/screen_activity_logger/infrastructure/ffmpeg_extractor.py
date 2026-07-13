"""ffmpegによるフレーム抽出アダプタ。

- 均等サンプリング（fps指定）で全フレームを抽出し、
- シーン変化検出（select=gt(scene,th)）で得たタイムスタンプに
  最も近いフレームをキーフレームとしてマークする。
- 先頭フレームは常にキーフレーム（ベースライン）。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from screen_activity_logger.domain.models import Frame, VideoTimestamp

_PTS_TIME_PATTERN = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


def parse_scene_timestamps(ffmpeg_stderr: str) -> tuple[float, ...]:
    """showinfoフィルタのstderr出力からpts_time（秒）を抽出する。"""
    return tuple(float(m) for m in _PTS_TIME_PATTERN.findall(ffmpeg_stderr))


def parse_audio_stream_presence(ffprobe_output: str) -> bool:
    """ffprobe（codec_type出力）の結果から音声トラックの有無を判定する。"""
    return bool(ffprobe_output.strip())


def has_audio_stream(video_path: Path) -> bool:
    """動画に音声トラックがあるかをffprobeで判定する。"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_audio_stream_presence(result.stdout)


@dataclass(frozen=True)
class FfmpegFrameExtractor:
    """ffmpeg CLIを用いたFrameExtractorポートの実装。

    max_long_edge: フレームの長辺上限（px）。高解像度画面録画の視覚トークンが
    VLMのコンテキストを超過しないよう縮小する（調査推奨値: 896〜1024）。
    """

    fps: float
    scene_threshold: float
    workdir: Path
    max_long_edge: int = 1024

    def __post_init__(self) -> None:
        # fps<=0はタイムスタンプ計算のゼロ除算になる（4AIレビューR1）
        if self.fps <= 0:
            raise ValueError(f"fpsは正の値が必要です: {self.fps}")

    def extract(self, video_path: Path) -> tuple[Frame, ...]:
        frame_paths = self._sample_uniform_frames(video_path)
        scene_seconds = self._detect_scene_changes(video_path)
        return self._build_frames(frame_paths, scene_seconds)

    def _sample_uniform_frames(self, video_path: Path) -> tuple[Path, ...]:
        self.workdir.mkdir(parents=True, exist_ok=True)
        # バッチ処理はworkdirを全動画で共有するため、前動画の残渣PNGを
        # globで拾って汚染しないよう抽出前に必ず掃除する（4AIレビューR1）
        for stale in self.workdir.glob("frame_*.png"):
            stale.unlink()
        pattern = self.workdir / "frame_%06d.png"
        # scale: 長辺がmax_long_edgeを超える場合のみ縮小（拡大はしない）。-2は偶数丸め
        scale = f"scale='min({self.max_long_edge},iw)':-2"
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vf", f"fps={self.fps},{scale}",
                str(pattern),
            ],
            check=True,
            capture_output=True,
        )
        return tuple(sorted(self.workdir.glob("frame_*.png")))

    def _detect_scene_changes(self, video_path: Path) -> tuple[float, ...]:
        result = subprocess.run(
            [
                "ffmpeg", "-i", str(video_path),
                "-vf", f"select='gt(scene,{self.scene_threshold})',showinfo",
                "-fps_mode", "vfr",
                "-f", "null", "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return parse_scene_timestamps(result.stderr)

    def _build_frames(
        self, frame_paths: tuple[Path, ...], scene_seconds: tuple[float, ...]
    ) -> tuple[Frame, ...]:
        if not frame_paths:
            # 破損動画等でフレーム0枚のとき空min()で落ちない（4AIレビューR1）
            return ()
        timestamps = [index / self.fps for index in range(len(frame_paths))]
        keyframe_indices = {0} | {
            self._nearest_index(timestamps, scene_at) for scene_at in scene_seconds
        }
        return tuple(
            Frame(
                timestamp=VideoTimestamp(seconds=seconds),
                path=path,
                is_keyframe=index in keyframe_indices,
            )
            for index, (seconds, path) in enumerate(zip(timestamps, frame_paths))
        )

    @staticmethod
    def _nearest_index(timestamps: list[float], target: float) -> int:
        return min(
            range(len(timestamps)), key=lambda i: abs(timestamps[i] - target)
        )
