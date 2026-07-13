"""VLMバックエンド共通部（プロンプト・応答パース・リトライ判定、Issue #21）。

Ollama / OpenAI互換（vllm-mlx）の両アダプタで、プロンプトと出力解釈の仕様を
共有し、バックエンド間の挙動差を構造的に排除する（asr_segmentsと同じ発想）。
"""

from __future__ import annotations

import json
import re

from screen_activity_logger.domain.models import OcrText

PROMPT_TEMPLATE = """あなたはPC作業の記録係です。このスクリーンショットについて日本語で記録します:
1) app_guess: 使用中のアプリ（Excel/PowerPoint/Chrome/VS Code等）
2) resource: 開いているファイル名・ページタイトル・文書名。タイトルバーやタブに明確に読み取れる場合のみ。読み取れない・確信がない場合はnull。画面の説明文（"Web page titled..."等）や意味不明な文字断片は書かない
3) location: リソース内の位置（シート名・スライド番号・ページ番号・見出し・URLパス等）
4) focus: ユーザーが画面のどこを見て何を判断していそうか（カーソル位置・選択状態・強調から推測）
5) action: 今している操作の説明（1〜2文）

参考: この画面からOCRで抽出されたテキスト:
{ocr_text}

参考: この時間帯にユーザーが話していた内容（音声認識）:
{speech_text}

次のJSONのみを出力してください（説明文・コードフェンス不要。不明な項目はnull）:
{{"app_guess": "...", "resource": "...", "location": "...", "focus": "...", "action": "..."}}"""

_CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\n|\n?```$")

FALLBACK_ACTION = "（この画面の説明を生成できませんでした）"

# VLM呼び出しのタイムアウト（秒）。実測: 応答が宙に浮くとsock_recvで
# 無限待ちになりバッチ全体が停止するため必須（実会議10本バッチで発覚）
DEFAULT_TIMEOUT_SECONDS = 300.0

# タイムアウト時のリトライ上限（Issue #15。ハング・一時的負荷の救済）
MAX_ATTEMPTS = 2

# 推論時間テレメトリのSLOW警告閾値
SLOW_CALL_THRESHOLD_SECONDS = 60.0


def build_prompt(ocr: OcrText, speech: tuple[str, ...] = ()) -> str:
    lines = ocr.normalized_lines()
    ocr_text = "\n".join(lines) if lines else "(テキストなし)"
    speech_text = "\n".join(speech) if speech else "(発話なし)"
    return PROMPT_TEMPLATE.format(ocr_text=ocr_text, speech_text=speech_text)


def parse_fields(content: str) -> dict[str, str | None]:
    """VLM応答テキストを構造化フィールドに解釈する（コードフェンス耐性）。"""
    empty: dict[str, str | None] = {
        "app_guess": None,
        "resource": None,
        "location": None,
        "focus": None,
    }
    cleaned = _CODE_FENCE_PATTERN.sub("", content.strip()).strip()
    if not cleaned:
        return {**empty, "action": FALLBACK_ACTION}
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return {**empty, "action": cleaned}
    fields: dict[str, str | None] = {
        key: normalize_json_value(payload.get(key)) for key in empty
    }
    # actionも空値表現（null/"null"/"none"）を正規化する（Issue #3の実バグ:
    # 文字列"null"が素通りしてMarkdownに「null」と表示されていた）
    fields["action"] = (
        normalize_json_value(payload.get("action")) or FALLBACK_ACTION
    )
    return fields


def normalize_json_value(value: object) -> str | None:
    """JSONの空値表現（null/"null"/"none"/空文字）をNoneに正規化する。"""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in ("null", "none"):
        return None
    return stripped


def is_retryable(error: BaseException) -> bool:
    """タイムアウト系例外か（Issue #15のリトライ対象判定）。

    httpxを直接importせず例外MROのクラス名で判定する。
    """
    return any(
        cls.__name__ in ("TimeoutException", "TimeoutError")
        for cls in type(error).__mro__
    )
