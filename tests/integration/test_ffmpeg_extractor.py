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


@pytest.fixture(scope="module")
def high_res_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Retina画面録画を模した高解像度（2560x1600）の合成動画。"""
    video = tmp_path_factory.mktemp("video") / "highres.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=gray:size=2560x1600:duration=2:rate=10",
        "-pix_fmt", "yuv420p", str(video),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return video


class TestFrameDownscaling:
    """実録画で発覚: フル解像度フレームは視覚トークンがVLMコンテキストを超過する。

    調査済み推奨値（長辺896〜1024px）に基づき、抽出時に縮小する。
    """

    def test_frames_are_downscaled_to_max_long_edge(
        self, high_res_video: Path, tmp_path: Path
    ) -> None:
        from PIL import Image

        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path, max_long_edge=1024
        )
        frames = extractor.extract(high_res_video)
        widths = [Image.open(f.path).size[0] for f in frames]
        assert all(w <= 1024 for w in widths)

    def test_small_video_is_not_upscaled(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        from PIL import Image

        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path, max_long_edge=1024
        )
        frames = extractor.extract(scene_change_video)
        # 元動画は320x240なので拡大されないこと
        assert Image.open(frames[0].path).size[0] == 320


class TestStaleFrameCleanup:
    """4AIレビューR1: バッチで前動画のフレーム残渣が次動画を汚染するバグの回帰。"""

    def test_previous_extraction_residue_is_removed(
        self, scene_change_video: Path, tmp_path: Path
    ) -> None:
        stale = tmp_path / "frame_000099.png"
        stale.write_bytes(b"stale-from-previous-video")
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )

        frames = extractor.extract(scene_change_video)

        assert not stale.exists()
        assert all(f.path.read_bytes() != b"stale-from-previous-video" for f in frames)
        assert 5 <= len(frames) <= 7  # 残渣が数に混入しない


class TestInputValidation:
    """4AIレビューR1: fps=0でZeroDivisionError、フレーム0枚で空min()の回帰。"""

    def test_zero_fps_is_rejected_at_construction(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="fps"):
            FfmpegFrameExtractor(fps=0.0, scene_threshold=0.1, workdir=tmp_path)

    def test_negative_fps_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="fps"):
            FfmpegFrameExtractor(fps=-1.0, scene_threshold=0.1, workdir=tmp_path)

    def test_empty_frames_returns_empty_without_crash(self, tmp_path: Path) -> None:
        extractor = FfmpegFrameExtractor(
            fps=1.0, scene_threshold=0.1, workdir=tmp_path
        )
        # フレーム0枚＋シーン検出ありでも空min()で落ちない
        frames = extractor._build_frames((), (1.0, 2.0))
        assert frames == ()
