"""vlm_common（プロンプト・応答パース共通部）のユニットテスト（Issue #3 Q1: RED）。"""

from screen_activity_logger.infrastructure.vlm_common import (
    FALLBACK_ACTION,
    parse_fields,
)


class TestParseFields:
    def test_parses_all_fields(self) -> None:
        content = (
            '{"app_guess": "Excel", "resource": "見積書.xlsx",'
            ' "location": "Sheet1", "focus": "C9セル", "action": "編集中"}'
        )

        fields = parse_fields(content)

        assert fields["app_guess"] == "Excel"
        assert fields["resource"] == "見積書.xlsx"
        assert fields["action"] == "編集中"

    def test_null_string_action_falls_back(self) -> None:
        # 実バグ（Issue #3）: VLMが action に文字列"null"を返すと
        # そのままMarkdownに「null」と表示されていた
        content = '{"app_guess": "Chrome", "action": "null"}'

        fields = parse_fields(content)

        assert fields["action"] == FALLBACK_ACTION

    def test_missing_action_falls_back(self) -> None:
        fields = parse_fields('{"app_guess": "Chrome"}')

        assert fields["action"] == FALLBACK_ACTION

    def test_null_json_value_action_falls_back(self) -> None:
        fields = parse_fields('{"app_guess": "Chrome", "action": null}')

        assert fields["action"] == FALLBACK_ACTION

    def test_code_fence_is_stripped(self) -> None:
        content = '```json\n{"app_guess": "Excel", "action": "入力中"}\n```'

        fields = parse_fields(content)

        assert fields["action"] == "入力中"

    def test_non_json_content_becomes_action(self) -> None:
        fields = parse_fields("画面を確認しています")

        assert fields["action"] == "画面を確認しています"
        assert fields["app_guess"] is None


class TestBuildPromptQualityCriteria:
    """Issue #24: プロンプトに品質基準（対象読者・文体）が含まれる。"""

    def test_prompt_defines_reader_and_style(self) -> None:
        from screen_activity_logger.domain.models import OcrText, VideoTimestamp
        from screen_activity_logger.infrastructure.vlm_common import build_prompt

        prompt = build_prompt(
            OcrText(timestamp=VideoTimestamp(seconds=0.0), lines=())
        )

        assert "後から読み返して作業内容を思い出せ" in prompt  # 本人視点の品質基準
        assert "第三者が業務の流れを追える" in prompt  # 第三者視点の品質基準
        assert "常体" in prompt  # 文体統一の指示


class TestMalformedJsonSalvage:
    """Issue #26 E2Eで顕在化: 閉じ括弧欠け等の不正JSONからフィールドを救出する。"""

    def test_unclosed_json_fields_are_salvaged(self) -> None:
        content = (
            '{"app_guess": "Chrome", "resource": "動画ページ",'
            ' "location": null, "focus": "タイトル",'
            ' "action": "動画ページを開いて説明を開始する準備をしている"'
        )  # 閉じ括弧なし

        fields = parse_fields(content)

        assert fields["action"] == "動画ページを開いて説明を開始する準備をしている"
        assert fields["app_guess"] == "Chrome"
        assert fields["resource"] == "動画ページ"

    def test_json_like_without_action_falls_back(self) -> None:
        fields = parse_fields('{"app_guess": "Excel", "resource": "x.xlsx"')

        assert fields["action"] == FALLBACK_ACTION  # 生JSON断片をactionにしない
        assert fields["app_guess"] == "Excel"

    def test_plain_text_still_becomes_action(self) -> None:
        fields = parse_fields("画面を確認しています")

        assert fields["action"] == "画面を確認しています"
