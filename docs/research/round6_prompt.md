# 調査依頼: OCRとVLMの高速化ベストプラクティス（2026-07時点）

ローカル完結の「画面録画→作業ログ」パイプライン（M4 Air 24GB、PaddleOCR PP-OCRv6 + Qwen3-VL 8B）の高速化のため、最新動向を網羅的に調査してほしい。**英語圏と中国語圏の両方を必ずカバー**すること。

## 調査項目
1. **VLM推論の高速化**（Apple Silicon中心、CUDAの知見も可）
   - MLX系ランタイム（vllm-mlx, mlx-vlm等）の最新状況・実測報告
   - vision token圧縮/削減（トークン数がボトルネック）: FastVLM, ShowUI系, token pruning
   - 量子化（4bit/8bit）の速度と品質のトレードオフ実測
   - vision embedding cache・KVキャッシュ再利用・speculative decoding for VLM
2. **OCRの高速化**
   - PaddleOCR PP-OCRv6の高速化設定（ONNX/バッチ/解像度）
   - GPU/ANE活用のOCR（Apple Vision framework, LiveText API等のmacネイティブ）
   - 中国発の新世代OCR（GLM-OCR, DeepSeek-OCR, GOT-OCR等）の速度面の評判
3. **パイプライン設計の高速化パターン**: フレーム間引き・キャッシュ・並列化の実践報告

## 出力形式
- 各知見に出典（URL・投稿・論文番号）を必ず付ける
- 「M4 Air 24GBで今すぐ効くもの」と「ハード更新が必要なもの」を区別
- 中国語ソースは日本語で要約

特にXの投稿（英語・中国語両方）を検索して、実務者の実測報告・ベストプラクティスを集めてください。中国語圏のMLX/OCR/VLM高速化の議論も必ず検索すること。
