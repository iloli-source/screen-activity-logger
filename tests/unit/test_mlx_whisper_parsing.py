"""MlxWhisperTranscriber の純関数部分のユニットテスト（Cycle R-1: RED）。"""

from screen_activity_logger.infrastructure.ffmpeg_extractor import (
    parse_audio_stream_presence,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    segments_from_result,
)


class TestSegmentsFromResult:
    def test_converts_whisper_segments(self) -> None:
        result = {
            "segments": [
                {"start": 0.0, "end": 2.5, "text": " こんにちは、テストです。"},
                {"start": 3.0, "end": 5.0, "text": " 次の発話。"},
            ]
        }
        segments = segments_from_result(result)
        assert len(segments) == 2
        assert segments[0].start.seconds == 0.0
        assert segments[0].end.seconds == 2.5
        assert segments[0].text == "こんにちは、テストです。"  # 前後空白は除去

    def test_skips_empty_text_segments(self) -> None:
        result = {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "   "},
                {"start": 1.0, "end": 2.0, "text": "有効な発話"},
            ]
        }
        segments = segments_from_result(result)
        assert len(segments) == 1
        assert segments[0].text == "有効な発話"

    def test_empty_result_gives_empty_tuple(self) -> None:
        assert segments_from_result({}) == ()
        assert segments_from_result({"segments": []}) == ()


class TestParseAudioStreamPresence:
    def test_detects_audio_stream(self) -> None:
        assert parse_audio_stream_presence("audio\n") is True

    def test_no_output_means_no_audio(self) -> None:
        assert parse_audio_stream_presence("") is False
        assert parse_audio_stream_presence("   \n") is False
