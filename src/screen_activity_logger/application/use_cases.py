"""ユースケース: 動画から作業ログを生成する。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from screen_activity_logger.application.ports import (
    FrameComparator,
    FrameExtractor,
    SceneDescriber,
    SpeechSummarizer,
    SpeechTranscriber,
    TextRecognizer,
    WorklogWriter,
)
from screen_activity_logger.domain.models import (
    Frame,
    OcrText,
    TranscriptSegment,
    VideoTimestamp,
    Worklog,
)
from screen_activity_logger.domain.screen_context import enrich_description
from screen_activity_logger.domain.services import TimelineMerger
from screen_activity_logger.domain.speaker_attribution import (
    SpeakerAttributionConfig,
    SpeakerObservation,
    attribute_speakers,
    extract_name_labels,
)
from screen_activity_logger.domain.speech_filter import (
    SpeechFilterConfig,
    filter_segments,
)
from screen_activity_logger.domain.vlm_gate import (
    VlmGateConfig,
    normalize_ocr_tokens,
    should_describe,
)

# キーフレームのVLM説明に添える発話の時間窓（前後秒）
SPEECH_CONTEXT_WINDOW_SECONDS = 15.0

# 発話要旨の対象とする最小発話行数（相槌だけのエントリは要約しない、Issue #23）
MIN_SPEECH_LINES_FOR_SUMMARY = 3


@dataclass(frozen=True)
class GenerateWorklog:
    """間引きポリシー:
    - VLMはキーフレームのみ疎適用
    - OCRは原則全フレーム。ただしframe_comparator注入時は、直前OCR済み
      フレームと類似するフレームの認識をスキップし前回結果を再利用する
      （実測: 静止画面ではOCRが処理時間の72%を占めたため）
    - ocr_keyframes_only=True（会議モード）ではOCRをキーフレームに限定する
      （会議動画は顔の動きで差分スキップが効かず、文字は画面共有時のみのため）
    - 先頭フレームとキーフレームは常にOCRする
    - speech_transcriber注入時は音声を文字起こしし、エントリへの紐付けと
      VLMプロンプトへの同梱（キーフレーム前後15秒）を行う
    """

    frame_extractor: FrameExtractor
    text_recognizer: TextRecognizer
    scene_describer: SceneDescriber
    merger: TimelineMerger
    frame_comparator: FrameComparator | None = None
    speech_transcriber: SpeechTranscriber | None = None
    ocr_keyframes_only: bool = False
    vlm_gate: VlmGateConfig | None = None
    speech_filter: SpeechFilterConfig | None = None
    speaker_attribution: SpeakerAttributionConfig | None = None
    speech_summarizer: SpeechSummarizer | None = None

    def execute(
        self,
        video_path: Path,
        precomputed_segments: Sequence[TranscriptSegment] | None = None,
    ) -> Worklog:
        """precomputed_segments指定時はtranscriberを呼ばずそれを使う（2フェーズ用）。"""
        frames = self.frame_extractor.extract(video_path)
        segments = (
            precomputed_segments
            if precomputed_segments is not None
            else self._transcribe(video_path)
        )
        # 単発・バッチ両経路のチョークポイントで幻覚フィルタを適用（Issue #14）
        if self.speech_filter is not None:
            segments = filter_segments(segments, self.speech_filter)
        # 発話はここで1回だけソートする（キーフレーム毎の再ソート排除、4AIレビューR1）
        sorted_segments = sorted(segments, key=lambda s: s.start)
        ocr_by_frame = self._recognize_frames(frames)
        if self.speaker_attribution is not None:
            sorted_segments = attribute_speakers(
                sorted_segments,
                self._speaker_observations(frames, ocr_by_frame),
                self.speaker_attribution,
            )
        descriptions = [
            enrich_description(
                self.scene_describer.describe(
                    frame,
                    ocr_by_frame[frame.timestamp],
                    speech=self._speech_near(frame, sorted_segments),
                ),
                ocr_lines=ocr_by_frame[frame.timestamp].lines,
            )
            for frame in self._frames_to_describe(frames, ocr_by_frame)
        ]
        worklog = self.merger.merge(
            descriptions=descriptions,
            ocr_texts=ocr_by_frame.values(),
            transcript_segments=sorted_segments,
        )
        return self._attach_summaries(worklog)

    def _attach_summaries(self, worklog: Worklog) -> Worklog:
        """発話リッチなエントリに1文要旨を付与する（Issue #23、オプトイン）。

        要旨は補助情報のため、生成失敗はエントリを損なわず警告のみで継続する
        （VLM失敗時のフォールバックと同方針）。
        """
        if self.speech_summarizer is None:
            return worklog
        entries = []
        for entry in worklog.entries:
            summary = None
            if len(entry.speech) >= MIN_SPEECH_LINES_FOR_SUMMARY:
                try:
                    summary = self.speech_summarizer.summarize(entry.speech)
                except Exception as error:  # noqa: BLE001 — バッチ継続を優先
                    print(
                        f"要旨生成失敗 t={entry.timestamp}:"
                        f" {type(error).__name__}: {error}",
                        flush=True,
                    )
            entries.append(
                replace(entry, summary=summary) if summary else entry
            )
        return Worklog.from_entries(entries)

    @staticmethod
    def _speaker_observations(
        frames: Sequence[Frame],
        ocr_by_frame: dict[VideoTimestamp, OcrText],
    ) -> tuple[SpeakerObservation, ...]:
        """keyframeのOCRから話者観測列を構築する（Issue #10）。

        シーン変化＝keyframeが話者ビュー切替の信号。名前ラベル抽出は
        domainの純粋関数に委譲する。
        """
        observations = []
        for frame in frames:
            if not frame.is_keyframe:
                continue
            ocr = ocr_by_frame[frame.timestamp]
            lines = ocr.normalized_lines()
            observations.append(
                SpeakerObservation(
                    timestamp=frame.timestamp,
                    names=extract_name_labels(lines),
                    ocr_line_count=len(lines),
                )
            )
        return tuple(observations)

    def _frames_to_describe(
        self, frames: Sequence[Frame], ocr_by_frame: dict
    ) -> list[Frame]:
        """VLMを呼ぶキーフレームを選ぶ。

        vlm_gate注入時: 「最後にVLMを呼んだフレーム」のOCRトークン集合との
        Jaccard類似度で間引く（Issue #13、is_keyframeは変更しない）。
        未注入時: 全キーフレーム（従来動作）。
        """
        keyframes = [f for f in frames if f.is_keyframe]
        if self.vlm_gate is None:
            return keyframes
        selected: list[Frame] = []
        last_seconds: float | None = None
        last_tokens: frozenset[str] | None = None
        for frame in keyframes:
            tokens = normalize_ocr_tokens(ocr_by_frame[frame.timestamp].lines)
            if should_describe(
                now_seconds=frame.timestamp.seconds,
                tokens=tokens,
                last_vlm_seconds=last_seconds,
                last_vlm_tokens=last_tokens,
                config=self.vlm_gate,
            ):
                selected.append(frame)
                last_seconds = frame.timestamp.seconds
                last_tokens = tokens
        return selected

    def _transcribe(self, video_path: Path) -> Sequence[TranscriptSegment]:
        if self.speech_transcriber is None:
            return ()
        return self.speech_transcriber.transcribe(video_path)

    @staticmethod
    def _speech_near(
        frame: Frame, segments: Sequence[TranscriptSegment]
    ) -> tuple[str, ...]:
        """フレーム前後の発話（VLMコンテキスト用）。segmentsはソート済み前提。

        窓との区間重複で判定する（開始点のみの判定では、窓直前に始まる
        長い発話・窓末尾に掛かる発話が落ちる、4AIレビューR1）。
        """
        window_start = frame.timestamp.seconds - SPEECH_CONTEXT_WINDOW_SECONDS
        window_end = frame.timestamp.seconds + SPEECH_CONTEXT_WINDOW_SECONDS
        return tuple(
            seg.text
            for seg in segments
            if seg.start.seconds <= window_end and seg.end.seconds >= window_start
        )

    def _recognize_frames(
        self, frames: Sequence[Frame]
    ) -> dict[VideoTimestamp, OcrText]:
        if self.ocr_keyframes_only:
            return self._recognize_keyframes_only(frames)
        return self._recognize_with_skip(frames)

    def _recognize_keyframes_only(
        self, frames: Sequence[Frame]
    ) -> dict[VideoTimestamp, OcrText]:
        return {
            frame.timestamp: (
                self.text_recognizer.recognize(frame)
                if frame.is_keyframe
                else OcrText(timestamp=frame.timestamp, lines=())
            )
            for frame in frames
        }

    def _recognize_with_skip(
        self, frames: Sequence[Frame]
    ) -> dict[VideoTimestamp, OcrText]:
        ocr_by_frame = {}
        last_recognized: Frame | None = None
        last_lines: tuple[str, ...] = ()
        for frame in frames:
            if self._should_recognize(frame, last_recognized):
                ocr = self.text_recognizer.recognize(frame)
                last_recognized = frame
                last_lines = ocr.lines
            else:
                ocr = OcrText(timestamp=frame.timestamp, lines=last_lines)
            ocr_by_frame[frame.timestamp] = ocr
        return ocr_by_frame

    def _should_recognize(self, frame: Frame, last: Frame | None) -> bool:
        if last is None or frame.is_keyframe or self.frame_comparator is None:
            return True
        return not self.frame_comparator.are_similar(last, frame)


@dataclass(frozen=True)
class BatchGenerateWorklog:
    """複数動画の2フェーズ処理。

    Phase A: 全動画のASRを直列実行（プロセス内モデルキャッシュにより1回ロード）
    Phase B: 各動画のフレーム抽出→OCR→VLM→統合→出力

    実測背景: N並列×各自モデルロードは24GBユニファイドメモリで破綻するため、
    重いモデルのロードを1回に集約する（Issue #7）。
    """

    transcriber: SpeechTranscriber
    use_case: GenerateWorklog
    writers: Sequence[tuple[WorklogWriter, str]]  # (writer, 出力ファイル名)

    def execute(
        self, video_paths: Sequence[Path], output_dir: Path
    ) -> list[tuple[Path, Worklog]]:
        # Phase A: 全動画のASR
        segments_by_video = {
            video: tuple(self.transcriber.transcribe(video))
            for video in video_paths
        }
        # Phase B: 各動画の画像解析と出力
        results: list[tuple[Path, Worklog]] = []
        for video in video_paths:
            worklog = self.use_case.execute(
                video, precomputed_segments=segments_by_video[video]
            )
            video_out = output_dir / video.stem
            video_out.mkdir(parents=True, exist_ok=True)
            for writer, filename in self.writers:
                writer.write(worklog, video_out / filename)
            results.append((video, worklog))
        return results
