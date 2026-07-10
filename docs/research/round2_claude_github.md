# 第2回調査：Claude担当 GitHub再検索（2026-07-11）

`gh search repos` / `gh api` による直接調査。スター数・日付は調査時点の実測値。

## 同一用途の先行例（空白地帯の確認）

| リポジトリ | ⭐ | 要点 |
|-----------|----|------|
| PBLIZZ/Screen-Recording-OCR | 0 | 画面録画→時系列テキスト抽出・重複除去・timestamp付き。**まさに同一用途だが Gemini 3.5 Flash（クラウド）依存**。完全ローカル版は空白地帯 |
| xanthiawang/mindscope | 0 | macOS向けAIデジタルメモリ（画面録画+OCR検索+会議文字起こし） |
| snapotter-hq/SnapOtter | 1,947 | セルフホスト型ファイル処理基盤（画像/動画/音声のOCR・transcribe） |

## 2026H1のOCR特化トレンド（スター実測）

| リポジトリ | ⭐ | 作成/更新 | 要点 |
|-----------|----|----------|------|
| deepseek-ai/DeepSeek-OCR | 23,548 | 2026-01更新 | Contexts Optical Compression（視覚トークン圧縮） |
| **baidu/Unlimited-OCR** | **13,915** | **2026-06-18作成** | 「One-shot Long-horizon Parsing」。**3週間で13.9k星＝2026H1最大の新星** |
| zai-org/GLM-OCR | 7,139 | 2026-02作成 | 智譜のOCR特化（0.9B） |
| StarTrail-org/PixelRAG | 6,422 | 2026-05作成 | 「pixel-native search」＝スクショを直接検索する潮流 |
| deepseek-ai/DeepSeek-OCR-2 | 3,119 | 2026-02更新 | Visual Causal Flow |
| TimmyOVO/deepseek-ocr.rs | 2,164 | 2026-02更新 | **Rust製・Python不要**のOCR/VLMエンジン（DeepSeek-OCR-1/2, PaddleOCR-VL, DotsOCR対応、OpenAI互換サーバ） |

## 画面理解・GUI agent（米国・中国）

| リポジトリ | ⭐ | 要点 |
|-----------|----|------|
| alibaba/page-agent | 25,775 | JSページ内GUIエージェント |
| microsoft/OmniParser | 25,030 | 純視覚の画面パース（米国発の画面理解代表）。フレーム構造化の前処理に流用可 |
| X-PLUG/MobileAgent | 8,926 | Mobile GUI agentファミリー |
| stepfun-ai/gelab-zero | 2,223 | STEP-GUI |
| showlab/computer_use_ootb | 1,952 | Windows/macOS向けGUI agent |
| Tongyi-MAI/MAI-UI | 1,823 | 2B〜235BのGUI foundationファミリー |
| OpenBMB/AgentCPM-GUI | 1,391 | オンデバイスGUI agent（Android） |
| showlab/Awesome-GUI-Agent | 1,198 | 論文・リソースまとめ |

## 活用層（embedding/検索）の新顔

| リポジトリ | ⭐ | 要点 |
|-----------|----|------|
| QwenLM/Qwen3-VL-Embedding | 1,322 | **マルチモーダル埋め込み**。スクショを直接ベクトル検索できる。活用層でRuri v3（テキスト）と併用候補 |
| ssrajadh/sentrysearch | 小 | Qwen3-VLで動画の意味検索（参考実装） |

## 示唆

1. 「画面録画→ローカル作業ログ」の成熟OSSは第2回調査でも**未発見**。クラウド依存の先行例（PBLIZZ）が出始めており、ローカル版の空白は今が狙い目
2. OCR特化の再ブームは本物（3週間で14k星）。PaddleOCR本命は維持しつつ、GLM-OCR / DeepSeek-OCR系の比較検証をバックログに
3. OmniParser（画面の構造化）とQwen3-VL-Embedding（スクショ直接検索）はパイプラインの前後を強化する部品として注目
