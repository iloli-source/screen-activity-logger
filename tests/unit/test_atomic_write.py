"""原子的書き込みヘルパーと出力ライターの回帰テスト（Issue #32）。

書き込み途中で止まっても、既存の出力が切り詰められた状態で残らないこと。
"""

from pathlib import Path

import pytest

from screen_activity_logger.domain.models import (
    VideoTimestamp,
    Worklog,
    WorklogEntry,
)
from screen_activity_logger.infrastructure import atomic_write
from screen_activity_logger.infrastructure.atomic_write import (
    atomic_write_bytes,
    atomic_write_text,
)
from screen_activity_logger.infrastructure.manual_writer import ManualMarkdownWriter
from screen_activity_logger.infrastructure.writers import (
    JsonlWorklogWriter,
    MarkdownWorklogWriter,
)


def _worklog() -> Worklog:
    return Worklog.from_entries(
        [
            WorklogEntry(
                timestamp=VideoTimestamp(seconds=1.0),
                action="エディタでコードを確認している",
                app_guess="VS Code",
                ocr_lines=(),
            )
        ]
    )


def _fail(*args, **kwargs):
    raise OSError("simulated crash")


class TestAtomicWrite:
    def test_writes_text(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"

        atomic_write_text(target, "日本語\n")

        assert target.read_text(encoding="utf-8") == "日本語\n"
        assert [path.name for path in tmp_path.iterdir()] == ["out.txt"]

    def test_writes_bytes(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"

        atomic_write_bytes(target, b"\x00\x01")

        assert target.read_bytes() == b"\x00\x01"

    def test_replaces_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("previous", encoding="utf-8")

        atomic_write_text(target, "next")

        assert target.read_text(encoding="utf-8") == "next"

    @pytest.mark.parametrize("step", ["fsync", "replace"])
    def test_failure_keeps_previous_content_and_no_temp_file(
        self, tmp_path: Path, monkeypatch, step: str
    ) -> None:
        target = tmp_path / "out.txt"
        target.write_text("previous", encoding="utf-8")
        monkeypatch.setattr(atomic_write.os, step, _fail)

        with pytest.raises(OSError):
            atomic_write_text(target, "next")

        assert target.read_text(encoding="utf-8") == "previous"
        assert [path.name for path in tmp_path.iterdir()] == ["out.txt"]


class TestWritersAreAtomic:
    """各ライターは完成したファイルだけを出力先に置く（途中状態を見せない）。"""

    @pytest.mark.parametrize(
        "writer",
        [
            JsonlWorklogWriter(),
            MarkdownWorklogWriter(),
            ManualMarkdownWriter(source_name="demo"),
        ],
        ids=["jsonl", "markdown", "manual"],
    )
    def test_interrupted_write_keeps_previous_output(
        self, tmp_path: Path, monkeypatch, writer
    ) -> None:
        output = tmp_path / "worklog.out"
        output.write_text("previous run", encoding="utf-8")
        monkeypatch.setattr(atomic_write.os, "replace", _fail)

        with pytest.raises(OSError):
            writer.write(_worklog(), output)

        assert output.read_text(encoding="utf-8") == "previous run"
        assert [path.name for path in tmp_path.iterdir()] == ["worklog.out"]
