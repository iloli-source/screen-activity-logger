# Issue #4 OCR比較実測: PP-OCRv6 vs GLM-OCR vs DeepSeek-OCR（日本語UI文字、2026-07-13）

環境: M4 Air 24GB。ベンチ: 日本語UIフレーム5枚（Excelリボン×2・Chrome検索結果・
Chrome新規タブ・会議タイル、640×360の低解像度＝小フォントの厳しめ条件）。
正解: 目視キュレーションしたキー文字列46個（メニュー名・ボタン・小フォント優先）。
指標: NFKC正規化＋空白除去後の部分一致recall。採点: /tmp/sal-issue4-ocr/score_ocr.py

## 結果

| エンジン | recall | 秒/枚（中央値付近） | CPU可否 | 備考 |
|---|---|---|---|---|
| PP-OCRv6 tiny | 30.4% | 0.2〜1.2s | ✅ | 会議タイルは4/4。UI小フォントは大幅取りこぼし |
| **PP-OCRv6 small（現行既定）** | **58.7%** | 0.4〜4.0s | ✅ | バランス最良 |
| PP-OCRv6 medium | 65.2% | 1.6〜10.2s | ✅ | +6.5pt / 約2.6倍遅 |
| GLM-OCR-4bit (mlx-vlm) | 28.3% | 1.1〜7.0s | ❌ Mac専用 | **密なUI画面で反復ループ退化＋幻覚読み**（下記） |
| DeepSeek-OCR-4bit | 実行不可 | — | ❌ | mlx-vlm 0.6.4 processor未対応、vllm-mlxも `deepseekocr not supported` |
| Sarashina2.2-OCR | 未実施 | — | — | MLX版なし・縦書き文書特化＝UI用途とズレ（計画時に対象外と判断） |

## GLM-OCR-4bitの退化の実例

Excelリボン画面（1216字出力のうちキー文字列0/12）:
「標準\n表示\nヘブ\n対象行数を指定します」の無限反復。Chrome検索結果でも
「東京都の天気手術」「ダブの目ではじめのわけは」等の幻覚読み＋反復。
4bit量子化＋greedyデコードの典型的退化で、PP-OCRv6論文（arXiv:2606.13108）の
「VLMはOCRで幻覚・位置誤差」主張をそのまま再現した。repetition penalty調整は
時間ボックス外（そもそも幻覚読みはpenaltyでは直らない）。

## 判断

- **既定は PP-OCRv6 small 維持**。CPU動作（Windows両対応）・統合済み・recall最良バランス
- **medium は精度優先時の選択肢**（+6.5ptと引き換えに約2.6倍遅。既存の tier 指定で切替可能、コード変更不要）
- VLM系OCRは採用基準（recall +10pt以上 かつ 3s/枚以内）に**遠く未達**（-30pt）。不採用
- 再訪条件: (a) DeepSeek-OCRのMLXスタック対応 or deepseek-ocr.rs（Rust製OpenAI互換サーバ）の安定版、
  (b) GLM-OCRのbf16/8bitでの退化解消の報告。ただし現行構成はOCR/VLM二層分離
  （OCRで正確な文字、VLMで文脈理解）であり、この分離の根拠が本実測でさらに強化された

## 評価軸4点の消化

| 軸 | 消化 |
|---|---|
| 日本語UI精度 | recall実測（上表） |
| 速度 | 秒/枚実測（上表） |
| VRAM | PP-OCRv6はCPUのみ（VRAM 0）。GLM-OCR-4bitは約1.5GB（unified memory） |
| CPU動作可否 | PP-OCRv6のみ✅（クロスプラットフォーム方針に合致） |
