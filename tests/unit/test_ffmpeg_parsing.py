"""ffmpeg showinfo出力パースのユニットテスト（Cycle F-1: RED）。"""

from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    parse_scene_timestamps,
)


class TestParseSceneTimestamps:
    def test_extracts_pts_time_values(self) -> None:
        stderr = (
            "[Parsed_showinfo_1 @ 0x600] n:   0 pts:  90000 pts_time:3.0     "
            "duration_time:0.033 fmt:yuv420p\n"
            "[Parsed_showinfo_1 @ 0x600] n:   1 pts: 150000 pts_time:5.02    "
            "duration_time:0.033 fmt:yuv420p\n"
        )
        assert parse_scene_timestamps(stderr) == (3.0, 5.02)

    def test_returns_empty_for_no_matches(self) -> None:
        assert parse_scene_timestamps("no scene changes here") == ()

    def test_ignores_unrelated_lines(self) -> None:
        stderr = (
            "frame=  100 fps=50 q=-0.0 size=N/A time=00:00:04.00\n"
            "[Parsed_showinfo_1 @ 0x1] n: 0 pts: 1 pts_time:1.5 fmt:x\n"
        )
        assert parse_scene_timestamps(stderr) == (1.5,)
