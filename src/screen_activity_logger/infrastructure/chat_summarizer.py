"""発話断片の1文要旨アダプタ（Issue #23、VLMバックエンドのモデル使い回し）。

Issue #3 Q4実測: Qwen3-VL系へのテキストのみ入力で品質10/10・約2s/エントリ。
VLMと同一サーバー・同一モデルを使うため追加メモリはゼロ。要旨は補助情報のため
リトライはせず、失敗はユースケース側で握って継続する。
"""

from __future__ import annotations

# Q4検証済みの文言（誤認識前提・捏造禁止・40字・要約文のみ）を変えないこと
SUMMARY_PROMPT = (
    "以下はオンライン会議の音声認識テキストの断片です（誤認識を含む）。"
    "この時間帯に何が話されていたかを、日本語1文（40字以内）で要約してください。"
    "推測で固有名詞を補わないこと。要約文のみを出力:"
)

_MAX_TOKENS = 100
DEFAULT_SUMMARY_TIMEOUT_SECONDS = 60.0


def build_summary_prompt(lines: tuple[str, ...]) -> str:
    return SUMMARY_PROMPT + "\n\n" + "\n".join(lines)


def _normalize(content: str) -> str | None:
    stripped = content.strip()
    return stripped or None


class OpenAIChatSummarizer:
    """OpenAI互換API（vllm-mlx等）で発話要旨を生成する。"""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8991/v1",
        timeout_seconds: float = DEFAULT_SUMMARY_TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def summarize(self, lines: tuple[str, ...]) -> str | None:
        import httpx  # 遅延import（既存依存）

        response = httpx.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "user", "content": build_summary_prompt(lines)}
                ],
                "temperature": 0,
                "max_tokens": _MAX_TOKENS,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        content = str(response.json()["choices"][0]["message"]["content"])
        return _normalize(content)


class OllamaChatSummarizer:
    """Ollamaのchat APIで発話要旨を生成する（VLMと同一モデルにテキストのみ入力）。"""

    def __init__(
        self,
        model: str,
        timeout_seconds: float = DEFAULT_SUMMARY_TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._timeout_seconds = timeout_seconds

    def summarize(self, lines: tuple[str, ...]) -> str | None:
        import ollama  # 遅延import（既存流儀）

        # 無限待ちで--speech-summaryがバッチを止めないようclientにtimeout
        # を設定する（OpenAI側と対称、4AIレビューR1）
        client = ollama.Client(timeout=self._timeout_seconds)
        response = client.chat(
            model=self._model,
            messages=[{"role": "user", "content": build_summary_prompt(lines)}],
            options={"temperature": 0, "num_predict": _MAX_TOKENS},
        )
        return _normalize(str(response["message"]["content"]))
