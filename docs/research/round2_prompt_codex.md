# 調査依頼：Web＋論文ベースで中国・米国のVLMベストプラクティスを網羅調査（2025後半〜2026-07）

あなたは一次情報（公式ブログ・技術レポート・arXiv論文・公式リポジトリ）を最重視するリサーチャーです。Web検索を駆使して、中国と米国のVLM（Vision-Language Model）の最新ベストプラクティスを網羅的に調査してください。arXiv等の論文にアクセスできる場合は論文の情報も網羅的に集めてください。

## 特に知りたいこと
1. **中国発VLM**: Qwen3-VL(Alibaba), MiniCPM-V(OpenBMB/面壁智能), InternVL(上海AI Lab), GLM-4V/GLM-OCR(智譜), DeepSeek-VL/DeepSeek-OCR, Kimi-VL(Moonshot), 各技術レポート/論文の要点（アーキテクチャ、訓練手法、ベンチ結果）
2. **米国発VLM**: Molmo(AI2), Llama Vision(Meta), NVIDIA系(NVLM/Eagle), Apple(FastVLM/MM系), その他オープンモデル。論文・技術レポートの要点
3. **画面/GUI理解の研究動向**: GUI agent系論文(UI-TARS, OS-Atlas, ShowUI, CogAgent, Aguvis, OS-Genesis等)、screen understanding、screencast/screen recording解析の論文。「録画された画面操作の理解・要約」に直接関係する研究があれば最優先で深掘り
4. **動画理解の研究動向**: 長尺動画理解、フレームサンプリング戦略（uniform vs adaptive/keyframe）、token圧縮(visual token reduction)、video captioning/dense video captioningの最新論文
5. **OCRとVLMの関係**: OCR専用モデル(PP-OCRv6, DeepSeek-OCR, GOT-OCR, dots.ocr等)とVLM内蔵OCRの使い分けに関する知見・論文
6. **実務ベストプラクティス**: 量子化(AWQ/GPTQ/GGUF)の精度影響、解像度・visual token数の制御、VRAM 8〜12GBでの現実的な運用に関する一次情報

## 出力形式
- セクション分けし、各項目に出典（URL/arXiv ID）を付ける
- 論文は「タイトル / arXiv ID / 要点2〜3行 / 本用途への示唆」で列挙
- 実在が確認できないものは「未確認」と明記。ハルシネーション禁止
- 最後に「VRAM 8〜12GBで画面録画→日本語作業ログ化」への示唆を5行程度でまとめる
