"""手順書Markdown出力（Issue #26: RED）。"""

from pathlib import Path

from screen_activity_logger.domain.models import (
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)
from screen_activity_logger.infrastructure.manual_writer import (
    ManualMarkdownWriter,
    step_title,
)


def _entry(seconds: float, action: str, **kwargs) -> WorklogEntry:
    return WorklogEntry(
        timestamp=VideoTimestamp(seconds=seconds),
        action=action,
        app_guess=kwargs.pop("app_guess", "Excel"),
        ocr_lines=kwargs.pop("ocr_lines", ()),
        **kwargs,
    )


class TestStepTitle:
    def test_first_sentence_is_used(self) -> None:
        action = "セルC9に合計値を入力している。数式バーにSUM関数が表示されている。"

        assert step_title(action) == "セルC9に合計値を入力している"

    def test_long_sentence_is_truncated(self) -> None:
        action = "あ" * 60

        title = step_title(action)

        assert len(title) == 40
        assert title.endswith("…")

    def test_short_action_passes_through(self) -> None:
        assert step_title("保存する") == "保存する"


class TestManualMarkdownWriter:
    def test_writes_step_structure(self, tmp_path: Path) -> None:
        worklog = Worklog.from_entries([
            _entry(5.0, "ファイルを開いている。メニューから選択。"),
            _entry(65.0, "数式を入力している", focus="数式バー",
                   frame_image="frames/frame_000105.png",
                   ocr_lines=("=SUM(D4:D7)",)),
        ])
        path = tmp_path / "manual.md"

        ManualMarkdownWriter(source_name="excel_tutorial").write(worklog, path)

        text = path.read_text(encoding="utf-8")
        assert text.startswith("# excel_tutorial 手順書")
        assert "## Step 1: ファイルを開いている" in text
        assert "## Step 2: 数式を入力している" in text
        assert "![00:01:05](frames/frame_000105.png)" in text
        assert "👁 数式バー" in text
        assert "対象: Excel" in text
        assert "- `=SUM(D4:D7)`" not in text  # 生OCRは手順書では省略（jsonlに常在）

    def test_speech_is_omitted_from_manual(self, tmp_path: Path) -> None:
        # 手順書は操作の再現が目的。発話はworklog.jsonlに残る
        worklog = Worklog.from_entries([
            _entry(5.0, "保存している", speech=("はいでは保存します",)),
        ])
        path = tmp_path / "manual.md"

        ManualMarkdownWriter(source_name="v").write(worklog, path)

        assert "はいでは保存します" not in path.read_text(encoding="utf-8")
