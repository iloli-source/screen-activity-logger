

class TestBatchRobustness:
    """4AIレビューR2: stem衝突拒否と動画単位の失敗隔離。"""

    def test_duplicate_stems_are_rejected(self, tmp_path) -> None:
        import pytest

        from screen_activity_logger.application.use_cases import (
            BatchGenerateWorklog,
        )

        batch = BatchGenerateWorklog(
            transcriber=None, use_case=None, writers=[]
        )
        a = tmp_path / "a" / "meeting.mp4"
        b = tmp_path / "b" / "meeting.mp4"

        with pytest.raises(ValueError, match="衝突"):
            batch._ensure_unique_stems([a, b])

    def test_one_failing_video_does_not_kill_batch(self, tmp_path, capsys) -> None:
        from screen_activity_logger.application.use_cases import (
            BatchGenerateWorklog,
        )
        from screen_activity_logger.domain.models import Worklog

        class FlakyUseCase:
            def execute(self, video, precomputed_segments=None):
                if "bad" in video.name:
                    raise RuntimeError("boom")
                return Worklog.from_entries([])

        class NullTranscriber:
            def transcribe(self, video_path):
                return ()

        batch = BatchGenerateWorklog(
            transcriber=NullTranscriber(), use_case=FlakyUseCase(), writers=[]
        )
        good = tmp_path / "good.mp4"
        bad = tmp_path / "bad.mp4"

        results = batch.execute([bad, good], output_dir=tmp_path / "out")

        assert [v.name for v, _ in results] == ["good.mp4"]
        assert "処理失敗" in capsys.readouterr().out

    def test_asr_failure_falls_back_to_empty_segments(self, tmp_path, capsys) -> None:
        from screen_activity_logger.application.use_cases import (
            BatchGenerateWorklog,
        )
        from screen_activity_logger.domain.models import Worklog

        class RaisingTranscriber:
            def transcribe(self, video_path):
                raise RuntimeError("asr boom")

        received = {}

        class RecordingUseCase:
            def execute(self, video, precomputed_segments=None):
                received[video.name] = precomputed_segments
                return Worklog.from_entries([])

        batch = BatchGenerateWorklog(
            transcriber=RaisingTranscriber(),
            use_case=RecordingUseCase(),
            writers=[],
        )
        video = tmp_path / "v.mp4"

        results = batch.execute([video], output_dir=tmp_path / "out")

        assert len(results) == 1  # ASR失敗でも画像解析は続行
        assert received["v.mp4"] == ()
        assert "ASR失敗" in capsys.readouterr().out
