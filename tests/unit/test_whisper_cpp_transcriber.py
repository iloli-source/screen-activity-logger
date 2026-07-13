"""whisper.cppアダプタのユニットテスト（Issue #22 C1: RED）。

whisper-cli -oj のJSON（offsetsはミリ秒）をTranscriptSegmentへ変換する
純関数と、subprocess呼び出しの配線を検証する。
"""

import json
from pathlib import Path

from screen_activity_logger.infrastructure.whisper_cpp_transcriber import (
    WhisperCppTranscriber,
    segments_from_cpp_json,
)


def _payload(*segments: dict) -> dict:
    return {"transcription": list(segments)}


class TestSegmentsFromCppJson:
    def test_converts_millisecond_offsets_to_seconds(self) -> None:
        payload = _payload(
            {"offsets": {"from": 0, "to": 2720}, "text": "あと倉田さんの"},
            {"offsets": {"from": 2720, "to": 5000}, "text": "画面ですね"},
        )

        segments = segments_from_cpp_json(payload)

        assert len(segments) == 2
        assert segments[0].start.seconds == 0.0
        assert segments[0].end.seconds == 2.72
        assert segments[0].text == "あと倉田さんの"
        assert segments[1].start.seconds == 2.72

    def test_skips_empty_text_segments(self) -> None:
        payload = _payload(
            {"offsets": {"from": 0, "to": 1000}, "text": "  "},
            {"offsets": {"from": 1000, "to": 2000}, "text": "有効な発話"},
        )

        segments = segments_from_cpp_json(payload)

        assert len(segments) == 1
        assert segments[0].text == "有効な発話"

    def test_avg_logprob_computed_from_token_probs(self) -> None:
        # -ojf のトークン確率から算出（幻覚フィルタの防衛線を生かす、4AIレビューR1）
        import math

        payload = _payload({
            "offsets": {"from": 0, "to": 500},
            "text": "発話",
            "tokens": [
                {"text": "[_BEG_]", "p": 0.8},  # 特殊トークンは除外
                {"text": "発", "p": 0.9},
                {"text": "話", "p": 0.6},
            ],
        })

        (segment,) = segments_from_cpp_json(payload)

        expected = (math.log(0.9) + math.log(0.6)) / 2
        assert segment.avg_logprob is not None
        assert abs(segment.avg_logprob - expected) < 1e-9
        assert segment.no_speech_prob is None  # cppでは取得不能のままNone

    def test_probs_are_none_without_tokens(self) -> None:
        payload = _payload({"offsets": {"from": 0, "to": 500}, "text": "発話"})

        (segment,) = segments_from_cpp_json(payload)

        assert segment.no_speech_prob is None
        assert segment.avg_logprob is None

    def test_empty_transcription(self) -> None:
        assert segments_from_cpp_json({"transcription": []}) == ()
        assert segments_from_cpp_json({}) == ()


class TestWhisperCppTranscriber:
    def test_runs_cli_and_parses_json(self, monkeypatch, tmp_path) -> None:
        video = tmp_path / "input.mp4"
        video.write_bytes(b"fake")
        model = tmp_path / "model.bin"
        model.write_bytes(b"fake-model")
        calls: list[list[str]] = []

        def fake_extract(video_path: Path, wav_path: Path) -> None:
            Path(wav_path).write_bytes(b"RIFF-fake")

        def fake_run(cmd, check, capture_output, timeout=None):
            calls.append([str(part) for part in cmd])
            out_prefix = cmd[cmd.index("-of") + 1]
            Path(f"{out_prefix}.json").write_text(
                json.dumps(_payload(
                    {"offsets": {"from": 1000, "to": 3500}, "text": "こんにちは"}
                )),
                encoding="utf-8",
            )

        monkeypatch.setattr(
            "screen_activity_logger.infrastructure.whisper_cpp_transcriber"
            ".extract_audio_wav",
            fake_extract,
        )
        monkeypatch.setattr("subprocess.run", fake_run)

        transcriber = WhisperCppTranscriber(model_path=model)
        segments = transcriber.transcribe(video)

        (cmd,) = calls
        assert cmd[0] == "whisper-cli"
        assert cmd[cmd.index("-m") + 1] == str(model)
        assert cmd[cmd.index("-l") + 1] == "ja"
        assert "-ojf" in cmd
        assert len(segments) == 1
        assert segments[0].start.seconds == 1.0
        assert segments[0].end.seconds == 3.5
        assert segments[0].text == "こんにちは"
