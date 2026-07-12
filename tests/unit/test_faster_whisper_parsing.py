"""faster-whisperセグメント変換のユニットテスト（W3: RED）。

faster-whisperのSegmentは属性アクセス（start/end/text/no_speech_prob/
avg_logprob）のためSimpleNamespaceで偽装する。実ライブラリ不要。
"""

from types import SimpleNamespace

from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    segments_from_faster_segments,
)


def _raw(
    start: float = 0.0,
    end: float = 1.0,
    text: str = "発話",
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        start=start, end=end, text=text,
        no_speech_prob=no_speech_prob, avg_logprob=avg_logprob,
    )


class TestSegmentsFromFasterSegments:
    def test_converts_segments(self) -> None:
        segments = segments_from_faster_segments(
            [_raw(0.0, 2.5, " こんにちは、テストです。"), _raw(3.0, 5.0, " 次の発話。")]
        )
        assert len(segments) == 2
        assert segments[0].start.seconds == 0.0
        assert segments[0].end.seconds == 2.5
        assert segments[0].text == "こんにちは、テストです。"

    def test_skips_empty_text_segments(self) -> None:
        segments = segments_from_faster_segments(
            [_raw(text="   "), _raw(text="有効な発話")]
        )
        assert len(segments) == 1
        assert segments[0].text == "有効な発話"

    def test_empty_input_gives_empty_tuple(self) -> None:
        assert segments_from_faster_segments([]) == ()

    def test_clamps_end_before_start(self) -> None:
        segments = segments_from_faster_segments([_raw(5.0, 4.7, "逆転")])
        assert segments[0].start.seconds == 5.0
        assert segments[0].end.seconds == 5.0

    def test_clamps_negative_start_to_zero(self) -> None:
        segments = segments_from_faster_segments([_raw(-0.3, 1.0, "冒頭")])
        assert segments[0].start.seconds == 0.0

    def test_propagates_confidence_metadata(self) -> None:
        segments = segments_from_faster_segments(
            [_raw(no_speech_prob=0.87, avg_logprob=-1.23)]
        )
        assert segments[0].no_speech_prob == 0.87
        assert segments[0].avg_logprob == -1.23

    def test_missing_metadata_gives_none(self) -> None:
        segments = segments_from_faster_segments([_raw()])
        assert segments[0].no_speech_prob is None
        assert segments[0].avg_logprob is None

    def test_consumes_generator_input(self) -> None:
        """transcribe()は遅延ジェネレータを返すため、消費できること。"""
        generator = (_raw(float(i), float(i) + 1.0, f"発話{i}") for i in range(3))
        segments = segments_from_faster_segments(generator)
        assert [s.text for s in segments] == ["発話0", "発話1", "発話2"]


class FakeWhisperModel:
    """faster_whisper.WhisperModel の記録用フェイク。"""

    constructed: list[dict] = []
    transcribe_calls: list[dict] = []

    def __init__(self, model: str, **kwargs) -> None:
        FakeWhisperModel.constructed.append({"model": model, **kwargs})

    def transcribe(self, audio: str, **kwargs):
        FakeWhisperModel.transcribe_calls.append({"audio": audio, **kwargs})
        info = SimpleNamespace(language="ja")
        return iter([_raw(0.0, 1.0, "テスト発話")]), info


class TestFasterWhisperTranscriberWiring:
    """fakeモジュール注入によりfaster-whisper未導入環境でも配線を検証（W4）。"""

    def _install_fake(self, monkeypatch) -> None:
        import sys
        import types

        FakeWhisperModel.constructed = []
        FakeWhisperModel.transcribe_calls = []
        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    def _transcriber(self, monkeypatch, tmp_path):
        from pathlib import Path

        from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
            FasterWhisperTranscriber,
        )

        self._install_fake(monkeypatch)
        transcriber = FasterWhisperTranscriber()
        # ffmpeg実行を回避（wavファイルだけ用意する）
        monkeypatch.setattr(
            "screen_activity_logger.infrastructure.faster_whisper_transcriber"
            ".extract_audio_wav",
            lambda video, wav: Path(wav).write_bytes(b""),
        )
        return transcriber

    def test_passes_kotoba_recommended_options(self, monkeypatch, tmp_path) -> None:
        from pathlib import Path

        transcriber = self._transcriber(monkeypatch, tmp_path)
        segments = transcriber.transcribe(Path("/tmp/v.mp4"))

        assert [s.text for s in segments] == ["テスト発話"]
        call = FakeWhisperModel.transcribe_calls[0]
        assert call["language"] == "ja"
        assert call["chunk_length"] == 15
        assert call["condition_on_previous_text"] is False
        assert call["vad_filter"] is False

    def test_model_is_loaded_once_across_transcribes(
        self, monkeypatch, tmp_path
    ) -> None:
        from pathlib import Path

        transcriber = self._transcriber(monkeypatch, tmp_path)
        transcriber.transcribe(Path("/tmp/a.mp4"))
        transcriber.transcribe(Path("/tmp/b.mp4"))

        assert len(FakeWhisperModel.constructed) == 1  # バッチでロード1回
        assert FakeWhisperModel.constructed[0]["device"] == "auto"
        assert FakeWhisperModel.constructed[0]["compute_type"] == "auto"
