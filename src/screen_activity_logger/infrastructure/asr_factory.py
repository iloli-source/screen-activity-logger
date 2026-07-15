"""ASRバックエンドの解決とアダプタ生成（プラットフォーム対応、Issue #16/#22）。

cli.pyはカバレッジ除外のため、選択ロジックはここに置いてテスト対象にする。
アダプタ本体は遅延importのため、create_transcriberはバックエンド
ライブラリをimportしない。可用性チェックはensure_backend_availableに分離し、
CLIのmain()冒頭でのみ呼ぶ（重い処理が走る前に親切なエラーで止める）。

Issue #22（2時間実測）: mlx-whisperは長時間入力で内容崩壊＋40倍超の減速を
起こすためautoから除外。Apple Siliconの本線はwhisper.cpp（Metal、
品質×速度両立）、未導入時はfaster-whisper（遅いが正しい）に落とす。
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
from pathlib import Path

import os

from screen_activity_logger.application.ports import SpeechTranscriber
from screen_activity_logger.domain.models import TranscriptSegment
from screen_activity_logger.infrastructure.audio_chunking import (
    DEFAULT_CHUNK_SECONDS,
)
from screen_activity_logger.infrastructure.chunked_transcriber import (
    ChunkedTranscriber,
)
from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    DEFAULT_FASTER_ASR_MODEL,
    FasterWhisperTranscriber,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    DEFAULT_ASR_MODEL,
    MlxWhisperTranscriber,
)
from screen_activity_logger.infrastructure.whisper_cpp_transcriber import (
    DEFAULT_CPP_ASR_MODEL_PATH,
    DEFAULT_CPP_BINARY,
    WhisperCppTranscriber,
)

ASR_BACKENDS = ("auto", "cpp", "faster", "mlx")

_DEFAULT_MODELS = {
    "mlx": DEFAULT_ASR_MODEL,
    "faster": DEFAULT_FASTER_ASR_MODEL,
    "cpp": str(DEFAULT_CPP_ASR_MODEL_PATH),
}

_BACKEND_MODULES = {"mlx": "mlx_whisper", "faster": "faster_whisper"}

_INSTALL_HINTS = {
    "mlx": 'uv pip install -e ".[asr-mlx]"',
    "faster": 'uv pip install -e ".[asr-faster]"',
}


def is_cpp_available(model_path: Path | None = None) -> bool:
    """whisper.cppが使えるか（バイナリ＋モデルファイルの両方）。"""
    resolved_model = DEFAULT_CPP_ASR_MODEL_PATH if model_path is None else model_path
    return (
        shutil.which(DEFAULT_CPP_BINARY) is not None
        and Path(resolved_model).exists()
    )


def resolve_backend(
    backend: str,
    system: str | None = None,
    machine: str | None = None,
    cpp_available: bool | None = None,
) -> str:
    """auto → Apple Siliconはcpp（利用可能時）/faster、それ以外はfaster。

    明示指定はそのまま。mlxは長時間入力で品質崩壊（Issue #22）のため
    autoの解決先から除外し、明示オプトインのみとする。
    """
    if backend != "auto":
        return backend
    resolved_system = platform.system() if system is None else system
    resolved_machine = platform.machine() if machine is None else machine
    if resolved_system == "Darwin" and resolved_machine == "arm64":
        resolved_cpp = (
            is_cpp_available() if cpp_available is None else cpp_available
        )
        return "cpp" if resolved_cpp else "faster"
    return "faster"


def default_model_for(backend: str) -> str:
    """バックエンド毎の既定ASRモデル（同一kotoba-whisper v2.0の変換版）。"""
    if backend not in _DEFAULT_MODELS:
        raise ValueError(f"未知のASRバックエンド: {backend}")
    return _DEFAULT_MODELS[backend]


def ensure_backend_available(
    backend: str, cpp_model_path: Path | None = None
) -> None:
    """バックエンドの導入チェック。未導入なら導入コマンド付きで失敗。"""
    if backend == "cpp":
        _ensure_cpp_available(cpp_model_path)
        return
    module_name = _BACKEND_MODULES.get(backend)
    if module_name is None:
        raise ValueError(f"未知のASRバックエンド: {backend}")
    if importlib.util.find_spec(module_name) is None:
        raise ValueError(
            f"ASRバックエンド '{backend}'（{module_name}）が未インストールです。"
            f" {_INSTALL_HINTS[backend]} で導入するか、"
            "--no-asr で音声認識を無効化してください"
        )


def _ensure_cpp_available(model_path: Path | None) -> None:
    resolved_model = DEFAULT_CPP_ASR_MODEL_PATH if model_path is None else model_path
    if shutil.which(DEFAULT_CPP_BINARY) is None:
        raise ValueError(
            f"whisper.cppバイナリ（{DEFAULT_CPP_BINARY}）が見つかりません。"
            " brew install whisper-cpp で導入するか、"
            "--asr-backend faster か --no-asr を指定してください"
        )
    if not Path(resolved_model).exists():
        raise ValueError(
            f"whisper.cpp用モデルがありません: {resolved_model}。"
            " README「ASRセットアップ」の手順でGGUFモデルを配置するか、"
            "--asr-model <パス> で指定してください（回避: --asr-backend faster）"
        )


def default_asr_workers(backend: str, cpu_count: int | None = None) -> int:
    """チャンク並列度の既定値（Issue #29）。

    GPU系（cpp/mlx）は1固定: 同一GPUの時分割は効果が薄く、ファンレス機の
    熱制限リスク（#22実測）だけが乗る。CPU系（faster）はコアが余るため並列。
    """
    if backend != "faster":
        return 1
    cores = cpu_count if cpu_count is not None else (os.cpu_count() or 2)
    return max(1, min(4, cores // 2))


def create_transcriber(
    backend: str,
    model: str,
    chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
    max_workers: int | None = None,
) -> SpeechTranscriber:
    """解決済みバックエンドからアダプタを生成する（import自体は遅延のまま）。

    chunk_seconds > 0 ならChunkedTranscriberで包む（長時間の頑健性＋
    fasterのCPU並列）。0で従来どおりの一括転写。
    """
    workers = (
        default_asr_workers(backend) if max_workers is None else max(1, max_workers)
    )
    if backend == "mlx":
        inner: SpeechTranscriber = MlxWhisperTranscriber(model=model)
    elif backend == "faster":
        inner = FasterWhisperTranscriber(model=model, num_workers=workers)
    elif backend == "cpp":
        inner = WhisperCppTranscriber(model_path=model)
    else:
        raise ValueError(f"未知のASRバックエンド: {backend}")
    if chunk_seconds <= 0:
        return inner
    return ChunkedTranscriber(
        inner, chunk_seconds=chunk_seconds, max_workers=workers
    )


class SilenceAwareTranscriber:
    """動画単位で音声トラック有無を判定し、無音動画だけASRをスキップする。

    4AIレビューR1: 旧実装はバッチ中1本でも無音があると全動画のASRを
    無効化していた（cli.pyのall()判定）。判定関数は注入可能（テスト用）。
    """

    def __init__(self, inner: SpeechTranscriber, has_audio=None) -> None:
        if has_audio is None:
            from screen_activity_logger.infrastructure.ffmpeg_extractor import (
                has_audio_stream,
            )

            has_audio = has_audio_stream
        self._inner = inner
        self._has_audio = has_audio

    def transcribe(self, video_path: Path) -> tuple[TranscriptSegment, ...]:
        if not self._has_audio(video_path):
            print(f"音声トラックなし → ASRスキップ: {video_path.name}", flush=True)
            return ()
        return tuple(self._inner.transcribe(video_path))
