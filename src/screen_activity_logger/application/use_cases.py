"""ユースケース: 動画から作業ログを生成する。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from screen_activity_logger.application.ports import (
    FrameComparator,
    FrameExtractor,
    SceneDescriber,
    SpeechTranscriber,
    TextRecognizer,
    WorklogWriter,
)
from screen_activity_logger.domain.models import (
    Frame,
    OcrText,
    TranscriptSegment,
    Worklog,
)
from screen_activity_logger.domain.services import TimelineMerger

# キーフレームのVLM説明に添える発話の時間窓（前後秒）
SPEECH_CONTEXT_WINDOW_SECONDS = 15.0


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
        ocr_by_frame = self._recognize_frames(frames)
        descriptions = [
            self.scene_describer.describe(
                frame,
                ocr_by_frame[frame.timestamp],
                speech=self._speech_near(frame, segments),
            )
            for frame in frames
            if frame.is_keyframe
        ]
        return self.merger.merge(
            descriptions=descriptions,
            ocr_texts=ocr_by_frame.values(),
            transcript_segments=segments,
        )

    def _transcribe(self, video_path: Path) -> Sequence[TranscriptSegment]:
        if self.speech_transcriber is None:
            return ()
        return self.speech_transcriber.transcribe(video_path)

    @staticmethod
    def _speech_near(
        frame: Frame, segments: Sequence[TranscriptSegment]
    ) -> tuple[str, ...]:
        center = frame.timestamp.seconds
        return tuple(
            seg.text
            for seg in sorted(segments, key=lambda s: s.start)
            if abs(seg.start.seconds - center) <= SPEECH_CONTEXT_WINDOW_SECONDS
        )

    def _recognize_frames(self, frames: Sequence[Frame]) -> dict:
        if self.ocr_keyframes_only:
            return self._recognize_keyframes_only(frames)
        return self._recognize_with_skip(frames)

    def _recognize_keyframes_only(self, frames: Sequence[Frame]) -> dict:
        return {
            frame.timestamp: (
                self.text_recognizer.recognize(frame)
                if frame.is_keyframe
                else OcrText(timestamp=frame.timestamp, lines=())
            )
            for frame in frames
        }

    def _recognize_with_skip(self, frames: Sequence[Frame]) -> dict:
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
