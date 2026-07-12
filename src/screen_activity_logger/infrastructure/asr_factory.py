"""ASRバックエンドの解決とアダプタ生成（プラットフォーム対応、Issue #16）。

cli.pyはカバレッジ除外のため、選択ロジックはここに置いてテスト対象にする。
アダプタ本体は遅延importのため、create_transcriberはバックエンド
ライブラリをimportしない。可用性チェックはensure_backend_availableに分離し、
CLIのmain()冒頭でのみ呼ぶ（重い処理が走る前に親切なエラーで止める）。
"""

from __future__ import annotations

import importlib.util
import platform

from screen_activity_logger.application.ports import SpeechTranscriber
from screen_activity_logger.infrastructure.faster_whisper_transcriber import (
    DEFAULT_FASTER_ASR_MODEL,
    FasterWhisperTranscriber,
)
from screen_activity_logger.infrastructure.mlx_whisper_transcriber import (
    DEFAULT_ASR_MODEL,
    MlxWhisperTranscriber,
)

ASR_BACKENDS = ("auto", "mlx", "faster")

_DEFAULT_MODELS = {
    "mlx": DEFAULT_ASR_MODEL,
    "faster": DEFAULT_FASTER_ASR_MODEL,
}

_BACKEND_MODULES = {"mlx": "mlx_whisper", "faster": "faster_whisper"}

_INSTALL_HINTS = {
    "mlx": 'uv pip install -e ".[asr-mlx]"',
    "faster": 'uv pip install -e ".[asr-faster]"',
}


def resolve_backend(
    backend: str,
    system: str | None = None,
    machine: str | None = None,
) -> str:
    """auto → Darwin+arm64ならmlx、それ以外はfaster。明示指定はそのまま。"""
    if backend != "auto":
        return backend
    resolved_system = platform.system() if system is None else system
    resolved_machine = platform.machine() if machine is None else machine
    if resolved_system == "Darwin" and resolved_machine == "arm64":
        return "mlx"
    return "faster"


def default_model_for(backend: str) -> str:
    """バックエンド毎の既定ASRモデル（同一kotoba-whisper v2.0の変換版）。"""
    if backend not in _DEFAULT_MODELS:
        raise ValueError(f"未知のASRバックエンド: {backend}")
    return _DEFAULT_MODELS[backend]


def ensure_backend_available(backend: str) -> None:
    """バックエンドライブラリの導入チェック。未導入なら導入コマンド付きで失敗。"""
    module_name = _BACKEND_MODULES.get(backend)
    if module_name is None:
        raise ValueError(f"未知のASRバックエンド: {backend}")
    if importlib.util.find_spec(module_name) is None:
        raise ValueError(
            f"ASRバックエンド '{backend}'（{module_name}）が未インストールです。"
            f" {_INSTALL_HINTS[backend]} で導入するか、"
            "--no-asr で音声認識を無効化してください"
        )


def create_transcriber(backend: str, model: str) -> SpeechTranscriber:
    """解決済みバックエンドからアダプタを生成する（import自体は遅延のまま）。"""
    if backend == "mlx":
        return MlxWhisperTranscriber(model=model)
    if backend == "faster":
        return FasterWhisperTranscriber(model=model)
    raise ValueError(f"未知のASRバックエンド: {backend}")
