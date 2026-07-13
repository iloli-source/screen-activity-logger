"""映像ベース話者特定のユニットテスト（Issue #10 S1-S3: RED）。

名前パターンは実録画で観測した実データを使用。
"""

import pytest

from screen_activity_logger.domain.models import TranscriptSegment, VideoTimestamp
from screen_activity_logger.domain.speaker_attribution import (
    SpeakerAttributionConfig,
    SpeakerObservation,
    attribute_speakers,
    extract_name_labels,
    format_speech_line,
)


class TestExtractNameLabels:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("山中翔太", "山中翔太"),                    # (a) 単独行漢字
            ("二村紀花(ニムラノリカ)", "二村紀花"),        # (b) 読み仮名括弧
            ("二村紀花（ニムラノリカ）", "二村紀花"),      # (b) 全角括弧
            ("秋山さん", "秋山"),                        # (c) さん除去
            ("YK", "YK"),                               # (d) イニシャル
            ("花田恰", "花田恰"),                        # 3字氏名
            ("山中 翔太", "山中 翔太"),                   # スペース区切り
        ],
    )
    def test_extracts_participant_names(self, line: str, expected: str) -> None:
        assert extract_name_labels([line]) == (expected,)

    @pytest.mark.parametrize(
        "line",
        [
            "MINOTETAKER",       # 記録ボット
            "AI NOTETAKER",
            "あなた",             # Meet自分表示
            "AI",                # UI略語（イニシャルと衝突）
            "HD",
            "F",                 # 英字1字は不採用
            "ABC",               # 英字3字は不採用
            "12:34",             # 時刻
            "会議の議事録を作成する予定です",  # 文章行（行全体マッチのみ）
            "店舗別売上実績",      # 6字（氏名上限超）→ 非人名の複合語
        ],
    )
    def test_rejects_noise(self, line: str) -> None:
        assert extract_name_labels([line]) == ()

    def test_deduplicates_and_keeps_order(self) -> None:
        names = extract_name_labels(["秋山隆利", "YK", "秋山隆利", "花田恰"])
        assert names == ("秋山隆利", "YK", "花田恰")


def _segment(start: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        start=VideoTimestamp(seconds=start),
        end=VideoTimestamp(seconds=start + 1.0),
        text=text,
    )


def _obs(seconds: float, *names: str, lines: int = 3) -> SpeakerObservation:
    return SpeakerObservation(
        timestamp=VideoTimestamp(seconds=seconds),
        names=names,
        ocr_line_count=lines,
    )


class TestAttributeSpeakers:
    _CONFIG = SpeakerAttributionConfig()

    def test_single_name_view_attributes_speaker(self) -> None:
        segments = attribute_speakers(
            [_segment(10.0, "私ですかね")],
            [_obs(5.0, "秋山隆利")],
            self._CONFIG,
        )
        assert segments[0].speaker == "秋山隆利"

    def test_observation_persists_until_next(self) -> None:
        segments = attribute_speakers(
            [_segment(10.0, "a"), _segment(40.0, "b")],
            [_obs(5.0, "秋山隆利"), _obs(30.0, "花田恰")],
            self._CONFIG,
        )
        assert segments[0].speaker == "秋山隆利"
        assert segments[1].speaker == "花田恰"

    def test_grid_view_multiple_names_gives_none(self) -> None:
        segments = attribute_speakers(
            [_segment(10.0, "a")],
            [_obs(5.0, "秋山隆利", "花田恰")],
            self._CONFIG,
        )
        assert segments[0].speaker is None

    def test_no_observation_before_start_gives_none(self) -> None:
        segments = attribute_speakers(
            [_segment(1.0, "冒頭発話")],
            [_obs(10.0, "秋山隆利")],
            self._CONFIG,
        )
        assert segments[0].speaker is None

    def test_switch_shortly_after_start_wins(self) -> None:
        """Meetのビュー切替は発話開始より遅れる: 3秒以内の切替後を採用。"""
        segments = attribute_speakers(
            [_segment(10.0, "私ですかね。秋山と申します")],
            [_obs(5.0, "山中翔太"), _obs(12.0, "秋山隆利")],
            self._CONFIG,
        )
        assert segments[0].speaker == "秋山隆利"

    def test_switch_beyond_tolerance_is_ignored(self) -> None:
        segments = attribute_speakers(
            [_segment(10.0, "a")],
            [_obs(5.0, "山中翔太"), _obs(14.0, "秋山隆利")],  # 4秒後>3秒
            self._CONFIG,
        )
        assert segments[0].speaker == "山中翔太"

    def test_screen_share_guard_by_line_count(self) -> None:
        """OCR行数が多い（画面共有）観測は帰属に使わない。"""
        segments = attribute_speakers(
            [_segment(10.0, "a")],
            [_obs(5.0, "藤井伸治", lines=40)],
            self._CONFIG,
        )
        assert segments[0].speaker is None

    def test_unattributed_segment_is_same_object(self) -> None:
        original = _segment(10.0, "a")
        segments = attribute_speakers([original], [], self._CONFIG)
        assert segments[0] is original  # 無帰属は再構築しない


class TestFormatSpeechLine:
    def test_with_speaker(self) -> None:
        segment = TranscriptSegment(
            start=VideoTimestamp(seconds=0.0),
            end=VideoTimestamp(seconds=1.0),
            text="私ですかね",
            speaker="秋山隆利",
        )
        assert format_speech_line(segment) == "秋山隆利: 私ですかね"

    def test_without_speaker_is_plain_text(self) -> None:
        assert format_speech_line(_segment(0.0, "はい")) == "はい"

    def test_speaker_defaults_to_none(self) -> None:
        assert _segment(0.0, "はい").speaker is None  # S3後方互換


class TestPipelineWiring:
    """S4-S5（Issue #10）: パイプライン結線と表示。"""

    def _run(self, speaker_attribution):
        from pathlib import Path

        from screen_activity_logger.application.use_cases import GenerateWorklog
        from screen_activity_logger.domain.models import (
            ActivityDescription,
            Frame,
            OcrText,
        )
        from screen_activity_logger.domain.services import TimelineMerger

        frames = [
            Frame(
                timestamp=VideoTimestamp(seconds=5.0),
                path=Path("/tmp/f1.png"),
                is_keyframe=True,
            ),
        ]

        class NameLabelRecognizer:
            def recognize(self, frame):
                return OcrText(
                    timestamp=frame.timestamp, lines=("秋山隆利", "12:34")
                )

        class NullDescriber:
            def describe(self, frame, ocr, speech=()):
                return ActivityDescription(
                    timestamp=frame.timestamp, action="会議中", app_guess=None
                )

        class FixedTranscriber:
            def transcribe(self, video_path):
                return [
                    TranscriptSegment(
                        start=VideoTimestamp(seconds=10.0),
                        end=VideoTimestamp(seconds=12.0),
                        text="私ですかね",
                    )
                ]

        use_case = GenerateWorklog(
            frame_extractor=type(
                "E", (), {"extract": lambda self, p: frames}
            )(),
            text_recognizer=NameLabelRecognizer(),
            scene_describer=NullDescriber(),
            merger=TimelineMerger(ocr_match_tolerance_seconds=1.0),
            speech_transcriber=FixedTranscriber(),
            speaker_attribution=speaker_attribution,
        )
        return use_case.execute(Path("/tmp/v.mp4"))

    def test_meeting_pipeline_attributes_and_formats(self) -> None:
        worklog = self._run(SpeakerAttributionConfig())
        assert worklog.entries[0].speech == ("秋山隆利: 私ですかね",)

    def test_disabled_attribution_keeps_plain_speech(self) -> None:
        worklog = self._run(None)
        assert worklog.entries[0].speech == ("私ですかね",)
