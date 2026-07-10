"""FfmpegFrameExtractor の統合テスト（Cycle F-2: RED）。

赤3秒→青3秒の合成動画を生成し、フレーム抽出とシーン変化検出を検証する。
"""

import subprocess
from pathlib import Path

import pytest

from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def scene_change_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """t=3.0でシーンが切り替わる6秒の合成動画。"""
    video = tmp_path_factory.mktemp("video") / "scenes.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:size=320x240:duration=3:rate=10",
        "-f", "lavfi", "-i", "color=c=blue:size=320x240:duration=3:rate=10",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
        "-pix_fmt", "yuv420p", str(video),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return video


class TestFfmpegFrameExtractor:
    def test_extracts_frames_at_configured_fps(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )
        frames = extractor.extract(scene_change_video)
        # 6秒 × 1fps → 約6フレーム（±1許容）
        assert 5 <= len(frames) <= 7

    def test_frame_files_exist_and_timestamps_increase(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )
        frames = extractor.extract(scene_change_video)
        assert all(f.path.exists() for f in frames)
        seconds = [f.timestamp.seconds for f in frames]
        assert seconds == sorted(seconds)

    def test_first_frame_is_always_keyframe(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )
        frames = extractor.extract(scene_change_video)
        assert frames[0].is_keyframe is True

    def test_scene_change_marks_nearby_frame_as_keyframe(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )
        frames = extractor.extract(scene_change_video)
        # t=3.0のシーン変化の近傍（±1秒）にキーフレームがあること
        keyframe_seconds = [
            f.timestamp.seconds for f in frames if f.is_keyframe
        ]
        assert any(abs(s - 3.0) <= 1.0 for s in keyframe_seconds)
