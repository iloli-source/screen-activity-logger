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

    def test_clamps_end_before_start(self) -> None:
        """実会議音声で発生: Whisperがend<startのセグメントを返すことがある。

        クラッシュせず、endをstartにクランプして発話を保持する。
        """
        result = {
            "segments": [
                {"start": 5.0, "end": 4.7, "text": "逆転セグメント"},
            ]
        }
        segments = segments_from_result(result)
        assert len(segments) == 1
        assert segments[0].start.seconds == 5.0
        assert segments[0].end.seconds == 5.0
        assert segments[0].text == "逆転セグメント"

    def test_clamps_negative_start_to_zero(self) -> None:
        result = {"segments": [{"start": -0.3, "end": 1.0, "text": "冒頭"}]}
        segments = segments_from_result(result)
        assert segments[0].start.seconds == 0.0

    def test_propagates_confidence_metadata(self) -> None:
        """no_speech_prob / avg_logprob を捨てずに運ぶ（Issue #14）。"""
        result = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": "発話",
                    "no_speech_prob": 0.87,
                    "avg_logprob": -1.23,
                }
            ]
        }
        segments = segments_from_result(result)
        assert segments[0].no_speech_prob == 0.87
        assert segments[0].avg_logprob == -1.23

    def test_missing_metadata_keys_give_none(self) -> None:
        result = {"segments": [{"start": 0.0, "end": 1.0, "text": "発話"}]}
        segments = segments_from_result(result)
        assert segments[0].no_speech_prob is None
        assert segments[0].avg_logprob is None


class TestParseAudioStreamPresence:
    def test_detects_audio_stream(self) -> None:
        assert parse_audio_stream_presence("audio\n") is True

    def test_no_output_means_no_audio(self) -> None:
        assert parse_audio_stream_presence("") is False
        assert parse_audio_stream_presence("   \n") is False
