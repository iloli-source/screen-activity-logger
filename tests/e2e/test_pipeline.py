"""パイプラインのe2eテスト（Cycle I-2）。

文字入りの2シーン合成動画を、実ffmpeg＋実PaddleOCR＋FakeDescriberで
end-to-end処理し、worklog.md / worklog.jsonl の構造を検証する。
VLM（Ollama）のみフェイク（実VLMはCycle Jの実機統合で検証）。
"""

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from screen_activity_logger.application.use_cases import GenerateWorklog
from screen_activity_logger.cli import DEFAULT_SCENE_THRESHOLD
from screen_activity_logger.domain.models import (
    ActivityDescription,
    Frame,
    OcrText,
)
from screen_activity_logger.domain.services import TimelineMerger
from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    FfmpegFrameExtractor,
)
from screen_activity_logger.infrastructure.paddle_ocr import PaddleOcrRecognizer
from screen_activity_logger.infrastructure.writers import (
    JsonlWorklogWriter,
    MarkdownWorklogWriter,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_JP_FONT = Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc")


class FakeDescriber:
    """VLMの代替。キーフレームごとに固定の説明を返す。"""

    def describe(self, frame: Frame, ocr: OcrText) -> ActivityDescription:
        return ActivityDescription(
            timestamp=frame.timestamp,
            action=f"画面{int(frame.timestamp.seconds)}秒時点の作業",
            app_guess="TestApp",
        )


@pytest.fixture(scope="module")
def text_scene_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """「EDITOR STEP」→「BROWSER STEP」の2シーン（各3秒）の合成動画。"""
    base = tmp_path_factory.mktemp("e2e")
    font = ImageFont.truetype(str(_JP_FONT), size=64)
    images = []
    for name, text, bg in [
        ("scene1.png", "EDITOR STEP 111", "lightgray"),
        ("scene2.png", "BROWSER STEP 222", "lightblue"),
    ]:
        path = base / name
        image = Image.new("RGB", (960, 480), bg)
        ImageDraw.Draw(image).text((60, 200), text, fill="black", font=font)
        image.save(path)
        images.append(path)

    video = base / "screen.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", "3", "-i", str(images[0]),
        "-loop", "1", "-t", "3", "-i", str(images[1]),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,fps=10",
        "-pix_fmt", "yuv420p", str(video),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return video


class TestPipelineEndToEnd:
    def test_video_becomes_structured_worklog(
        self, text_scene_video: Path, tmp_path: Path
    ) -> None:
        use_case = GenerateWorklog(
            frame_extractor=FfmpegFrameExtractor(
                fps=1.0,
                scene_threshold=DEFAULT_SCENE_THRESHOLD,
                workdir=tmp_path / "frames",
            ),
            text_recognizer=PaddleOcrRecognizer(),
            scene_describer=FakeDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
        )

        worklog = use_case.execute(text_scene_video)

        # シーンが2つ→キーフレーム由来のエントリが2件以上
        assert len(worklog.entries) >= 2
        all_ocr = " ".join(
            line for entry in worklog.entries for line in entry.ocr_lines
        )
        assert "EDITOR" in all_ocr
        assert "BROWSER" in all_ocr

        md_path = tmp_path / "worklog.md"
        jsonl_path = tmp_path / "worklog.jsonl"
        MarkdownWorklogWriter().write(worklog, md_path)
        JsonlWorklogWriter().write(worklog, jsonl_path)

        md = md_path.read_text(encoding="utf-8")
        assert md.startswith("# 作業ログ")
        assert "TestApp" in md

        first = json.loads(
            jsonl_path.read_text(encoding="utf-8").splitlines()[0]
        )
        assert set(first.keys()) == {"t", "app_guess", "ocr", "action"}
