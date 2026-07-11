"""domain/vlm_gate のユニットテスト（Cycle Z1: RED）。

3者協議（Issue #13）で採択した設計:
主ゲート＝トークン集合Jaccard、時間はmin_gap/max_gapの安全弁のみ。
"""

from screen_activity_logger.domain.vlm_gate import (
    VlmGateConfig,
    normalize_ocr_tokens,
    should_describe,
    token_jaccard,
)

CONFIG = VlmGateConfig()  # 既定: threshold=0.85, min_gap=10, max_gap=120, min_union=3


class TestNormalizeOcrTokens:
    def test_tokenizes_lines_by_whitespace(self) -> None:
        tokens = normalize_ocr_tokens(("見積書 作成中", "Excel シート"))
        assert tokens == frozenset({"見積書", "作成中", "Excel", "シート"})

    def test_drops_short_lines(self) -> None:
        """2文字以下の行（OCRノイズ: □・田・Q等）を除去する。"""
        tokens = normalize_ocr_tokens(("□", "田", "OK", "有効なテキスト"))
        assert tokens == frozenset({"有効なテキスト"})

    def test_drops_digit_only_lines(self) -> None:
        """数字のみの行（時計・参加者数・ページ番号ゆれ）を除去する。"""
        tokens = normalize_ocr_tokens(("1234", "12:34", "会議メモ"))
        assert tokens == frozenset({"会議メモ"})

    def test_strips_whitespace(self) -> None:
        tokens = normalize_ocr_tokens(("  余白あり  ",))
        assert tokens == frozenset({"余白あり"})

    def test_empty_input(self) -> None:
        assert normalize_ocr_tokens(()) == frozenset()


class TestTokenJaccard:
    def test_identical_sets_are_one(self) -> None:
        s = frozenset({"a", "b", "c"})
        assert token_jaccard(s, s) == 1.0

    def test_disjoint_sets_are_zero(self) -> None:
        assert token_jaccard(frozenset({"a"}), frozenset({"b"})) == 0.0

    def test_partial_overlap(self) -> None:
        a = frozenset({"a", "b", "c", "d"})
        b = frozenset({"a", "b", "c", "x"})
        assert token_jaccard(a, b) == 0.6  # 3/5

    def test_both_empty_is_one(self) -> None:
        assert token_jaccard(frozenset(), frozenset()) == 1.0


class TestShouldDescribe:
    """真理値表の7分岐（Issue #13）。"""

    def test_first_keyframe_always_fires(self) -> None:
        assert (
            should_describe(
                now_seconds=0.0,
                tokens=frozenset({"any", "tokens", "here"}),
                last_vlm_seconds=None,
                last_vlm_tokens=None,
                config=CONFIG,
            )
            is True
        )

    def test_max_gap_forces_vlm(self) -> None:
        same = frozenset({"完全に", "同じ", "画面"})
        assert (
            should_describe(
                now_seconds=125.0,
                tokens=same,
                last_vlm_seconds=0.0,
                last_vlm_tokens=same,
                config=CONFIG,
            )
            is True
        )

    def test_min_gap_debounces(self) -> None:
        different = frozenset({"全く", "違う", "内容"})
        assert (
            should_describe(
                now_seconds=5.0,
                tokens=different,
                last_vlm_seconds=0.0,
                last_vlm_tokens=frozenset({"元の", "画面", "文字"}),
                config=CONFIG,
            )
            is False
        )

    def test_one_side_empty_fires(self) -> None:
        """画面共有の開始/終了（文字の出現/消滅）は必ず拾う。"""
        assert (
            should_describe(
                now_seconds=30.0,
                tokens=frozenset({"共有された", "資料の", "文字"}),
                last_vlm_seconds=0.0,
                last_vlm_tokens=frozenset(),
                config=CONFIG,
            )
            is True
        )

    def test_low_information_defers_to_time_guard(self) -> None:
        """両方低情報（顔だけの会議画面）はJaccard無効→スキップ（max_gapが拾う）。"""
        assert (
            should_describe(
                now_seconds=30.0,
                tokens=frozenset({"ab"}),
                last_vlm_seconds=0.0,
                last_vlm_tokens=frozenset({"cd"}),
                config=CONFIG,
            )
            is False
        )

    def test_high_similarity_skips(self) -> None:
        """話者切替: 文字がほぼ同じならスキップ。"""
        base = frozenset({f"token{i}" for i in range(20)})
        nearly_same = frozenset(list(base)[:19] | {"新規1"})
        assert (
            should_describe(
                now_seconds=30.0,
                tokens=frozenset(nearly_same),
                last_vlm_seconds=0.0,
                last_vlm_tokens=base,
                config=CONFIG,
            )
            is False
        )

    def test_low_similarity_fires(self) -> None:
        """画面共有開始・アプリ切替: 文字が大きく変わったら発火。"""
        assert (
            should_describe(
                now_seconds=30.0,
                tokens=frozenset({"スライド", "提案資料", "アジェンダ", "背景"}),
                last_vlm_seconds=0.0,
                last_vlm_tokens=frozenset({"参加者", "ミュート", "チャット", "退出"}),
                config=CONFIG,
            )
            is True
        )
