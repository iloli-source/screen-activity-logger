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
