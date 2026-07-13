"""VLMバックエンドの解決とアダプタ生成（Issue #21、asr_factoryと同型）。"""

from __future__ import annotations

from screen_activity_logger.application.ports import (
    SceneDescriber,
    SpeechSummarizer,
)
from screen_activity_logger.infrastructure.chat_summarizer import (
    OllamaChatSummarizer,
    OpenAIChatSummarizer,
)
from screen_activity_logger.infrastructure.ollama_describer import (
    OllamaSceneDescriber,
)
from screen_activity_logger.infrastructure.openai_chat_describer import (
    DEFAULT_VLLM_MODEL,
    DEFAULT_VLLM_URL,
    OpenAIChatSceneDescriber,
)
from screen_activity_logger.infrastructure.vlm_common import (
    DEFAULT_TIMEOUT_SECONDS,
)

VLM_BACKENDS = ("ollama", "vllm-mlx")


def create_describer(
    backend: str,
    model: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    base_url: str = DEFAULT_VLLM_URL,
) -> SceneDescriber:
    """解決済みバックエンドからSceneDescriberを生成する。

    vllm-mlx時はmodelがOllama形式（qwen3-vl:8b）ならMLX既定モデルに読み替える
    （タグ形式はOllama固有のため）。
    """
    if backend == "ollama":
        return OllamaSceneDescriber(model=model, timeout_seconds=timeout_seconds)
    if backend == "vllm-mlx":
        resolved_model = DEFAULT_VLLM_MODEL if ":" in model else model
        return OpenAIChatSceneDescriber(
            model=resolved_model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"未知のVLMバックエンド: {backend}")


def ensure_backend_available(backend: str, base_url: str = DEFAULT_VLLM_URL) -> None:
    """vllm-mlxサーバーの到達性チェック（重い処理の前に親切なエラーで止める）。"""
    if backend != "vllm-mlx":
        return  # ollamaは従来どおりチェックなし（describe時のフォールバックに委ねる）
    import httpx

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/models", timeout=5.0)
        response.raise_for_status()
    except Exception as error:  # noqa: BLE001
        raise ValueError(
            f"vllm-mlxサーバーに接続できません（{base_url}）: {type(error).__name__}。"
            " 起動例: vllm-mlx serve"
            f" {DEFAULT_VLLM_MODEL} --port 8991"
            "（導入: pip install vllm-mlx。README参照）"
        ) from error


def create_summarizer(
    backend: str,
    model: str,
    base_url: str = DEFAULT_VLLM_URL,
) -> SpeechSummarizer:
    """VLMと同一バックエンド・モデルで発話要旨アダプタを生成する（Issue #23）。

    モデル名の読み替え規則はcreate_describerと同一（挙動差の排除）。
    """
    if backend == "ollama":
        return OllamaChatSummarizer(model=model)
    if backend == "vllm-mlx":
        resolved_model = DEFAULT_VLLM_MODEL if ":" in model else model
        return OpenAIChatSummarizer(model=resolved_model, base_url=base_url)
    raise ValueError(f"未知のVLMバックエンド: {backend}")
