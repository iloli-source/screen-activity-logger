調査依頼として読み取り中心で進めます。英語圏・中国語圏のWebとXを並行して当たり、M4 Air向けに効く知見を整理します。# 調査報告: OCR・VLM 高速化ベストプラクティス（2026-07時点）

対象: **M4 Air 24GB / ローカル完結「画面録画→作業ログ」**（PaddleOCR PP-OCRv6 + Qwen3-VL 8B 想定）  
前提: VLM が支配項（5分録画で約15分前後の実績）であり、**「フレーム数 × (vision prefill + decode)」** が壁。

---

## 0. 結論サマリ（先に読む）

| 優先 | 施策 | 期待効果 | 区分 |
|------|------|----------|------|
| **S** | フレーム間引き（シーン変化・滞留検出）+ OCRハッシュでVLMスキップ | 壁時間を **2–10×** 削減しうる | **今すぐ** |
| **S** | Ollama → **mlx-vlm**（4bit）へ切替 | decode/prefill とも **+15–30%〜2×** 級の報告多数 | **今すぐ** |
| **A** | **vision feature / image prefix cache**（同一・類似フレーム再利用） | 同一画面マルチターンで **7–28×**（論文・実装） | **今すぐ** |
| **A** | OCR: **PP-OCRv6 tiny + ONNX** または **Apple Vision** に切替 | OCR段を **数百ms→数十ms** 級へ | **今すぐ** |
| **B** | 入力解像度を落とす（UI作業ログは 720–1080p で十分なことが多い） | vision token 削減 = TTFT 直撃 | **今すぐ** |
| **B** | 出力 max_tokens を短く（構造化1–3行） | decode 時間比例削減 | **今すぐ** |
| **C** | speculative decoding（DFlash/MTP） | **1.5–2×** 級だが VLM+短出力では効果薄め | 試す価値あり |
| **D** | Qwen3-VL 8B → 2B/4B 二段 or OCR専用VLM | 品質トレードオフ | 設計変更 |
| **—** | M4 Max/Ultra・大メモリ | 帯域・同時実行が伸びる | **ハード更新** |

---

## 1. VLM推論の高速化（Apple Silicon中心）

### 1.1 MLX系ランタイムの最新状況

#### **mlx-vlm**（本命のVLMランタイム）

- リポジトリ: [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm)  
- 2026時点で **Qwen3-VL / DeepSeek-OCR / GLM-OCR / PaddleOCR-VL / Unlimited-OCR** 等をネイティブ対応。
- 実務で重要な機能（READMEより）:
  - **Vision Feature Caching**（同一画像のvision encoderスキップ、多ターンで **prompt TPS 11×+**）
  - **Automatic Prefix Caching (APC)**（共有プレフィックスのKV再利用）
  - **Speculative decoding**（DFlash / EAGLE-3 / MTP）
  - **KV cache quant**（uniform 8-bit / TurboQuant 3.5-bit）
  - Continuous batching 付き FastAPI サーバ

**実測・実務者報告:**

| 報告 | 内容 | 出典 |
|------|------|------|
| mlx-vlm 作者 | 正常時 **~30 tok/s decode / ~300 tok/s prefill** 目安 | [X @Prince_Canuma](https://x.com/Prince_Canuma/status/2069336447325290942) |
| Core AI上 Qwen3-VL 2B | iPhone 17 Pro **33 tok/s**、M4 Max **188 tok/s**、vision encode **~60ms** | [X @JackdeS11](https://x.com/JackdeS11/status/2065052688589660433) |
| Ollama vs MLX | 同じ量子化でも **MLXの方が速いが精度差が出る** との比較動画 | [YouTube: Qwen3-VL Accuracy Ollama vs MLX](https://www.youtube.com/watch?v=s6DktZsGXTk) |
| 長時間連続推論 | Qwen3-VL-4B on MLX が **~60生成後に腐る**（Metal state）→ **プロセス分割で解消** | [X @sudonur](https://x.com/sudonur/status/2070784014055571681) |
| M4 mini 32GB | `qwen3-vl:4b` で集中/スマホ/離席程度は実用 | [X @UmeboshiCenter](https://x.com/UmeboshiCenter/status/2073592004328788035) |

**screen-activity-logger への示唆:**  
現状 `ollama pull qwen3-vl:8b` 前提なら、**MLX 4bit へ逃がすだけで支配項が改善**しやすい。ただし長時間バッチでは **チャンクごとにプロセス再起動** を設計に入れるのが実務知見。

#### **vllm-mlx**（サービング＋ビジョンキャッシュ）

論文: *Native LLM and MLLM Inference at Scale on Apple Silicon*（[arXiv:2601.19139](https://arxiv.org/html/2601.19139v2)）  
実装: [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx)

**M4 Max 実測（論文）:**

| 項目 | 数値 |
|------|------|
| テキスト最大 | 最大 **525 tok/s**（Qwen3-0.6B） |
| vs llama.cpp | **+21–87%** スループット |
| Qwen3-VL-8B 同一画像マルチターン | **21.7s → 0.78s（28×）**（content-hash による vision+KV cache） |
| 動画 32フレーム cache | **最大 24.7×** |
| Qwen3-VL-4B | **143 tok/s** 到達報告 |
| vision embedding cache のみ | **7.8×**、KV のみ **1.2×**、合算 **19×**（Turn2） |

**中国語圏の受け止め（要約）:**  
Reddit/CSDN系では「**単流は mlx-lm と大差なく、効くのは連続バッチとキャッシュ**」という整理が主流。単一録画を順次処理するパイプラインでは **vision prefix cache の価値が本体**。

**M4 Air 24GB 注意:** 論文計測は **M4 Max 128GB**。Air ではピーク帯域・同時バッチが落ちるが、**「同一/類似フレームのvision再計算回避」はメモリ帯域に依存せず効く**。

#### **Ollama MLX / その他**

- Ollama の MLX バックエンド統合後、prefill/decode 改善の記事多数（例: [Medium: Ollama 0.19 MLX](https://medium.com/@tentenco/ollama-0-19-ships-mlx-backend-for-apple-silicon-local-ai-inference-gets-a-real-speed-bump-878b4928f680)）。
- ただし VLM では **「Ollama便利だが mlx-vlm 直の方が速い/機能が厚い」** という実務層の声が優勢。

---

### 1.2 Vision token 圧縮・削減（最大のボトルネック）

画面録画では **高解像度UI × 多数フレーム** で visual tokens が爆発する。

#### **FastVLM（Apple, CVPR 2025）**

- 論文: [arXiv:2412.13303](https://arxiv.org/html/2412.13303v2)  
- 解説: [Apple ML Research: FastVLM](https://machinelearning.apple.com/research/fast-vision-language-models)  
- コード: [apple/ml-fastvlm](https://github.com/apple/ml-fastvlm)

**要点:**
- FastViTHD が **少ないが質の高い visual tokens** を出す（例: 336解像度で ViT-L/14 比 **16× トークン削減** 級）。
- 高解像度比較で **TTFT 最大 85× 改善**、vision encoder **3.4× 小型** 等の主張。
- **既存 Qwen3-VL に後付けは不可**（encoder 再設計モデル）。「別モデルへ乗り換え」選択肢。

#### **ShowUI（CVPR 2025）— UI画面に特化**

- 論文: [arXiv:2411.17465](https://arxiv.org/html/2411.17465v1)  
- コード: [showlab/ShowUI](https://github.com/showlab/ShowUI)

**要点（作業ログ向き）:**
- UI は **空白・単色領域が多い** → RGB 連結グラフで冗長パッチを特定。
- **視覚トークン 33% 削減、1.4× 高速**。
- 画面録画→操作理解に思想が直結。Qwen3-VL 本体への移植は研究実装が必要だが、**「単色背景パッチを落としてから VLM」** は今すぐ真似できる。

#### **その他 token pruning**

- **SCOPE**（NeurIPS 2025）: saliency + coverage で visual token 選択。  
  [NeurIPS poster](https://neurips.cc/virtual/2025/poster/116033)
- 実務者の警告: post-hoc pruning は LLM 負荷を減らすが **vision encoder 自体がボトルネックになる** ケースあり（[X @jji_hwannn](https://x.com/jji_hwannn/status/2056761615815504112)）。
- UI では **OCRでテキスト化→短トークンJSON** に落とす「vision token 裁定」がコスト削減として語られる（[X @bickov](https://x.com/bickov/status/2061375510861471825)）— ただしコード画面では OCR 誤読リスク。

**DeepSeek-OCR 系の圧縮思想（参考）:**  
10× 圧縮で 97% 精度（論文主張）だが、実ページ検証では **密な新聞で主張値を大きく下回る** 報告（[X @witcheer](https://x.com/witcheer/status/2072592890962854123): 12.6× で 28% 等）。

---

### 1.3 量子化（4bit / 8bit）速度と品質

| 設定 | 速度 | メモリ | 品質メモ | 出典 |
|------|------|--------|----------|------|
| **MLX 4bit** | 帯域律速で decode が伸びやすい。8bit より速いことが多い | 8B VLM を 24GB に収める現実解 | 一般に「十分」だが Ollama と同精度とは限らない | [willitrunai MLX guide](https://willitrunai.com/blog/qwen-3-5-mlx-apple-silicon-guide), [YouTube Ollama vs MLX](https://www.youtube.com/watch?v=s6DktZsGXTk) |
| **8bit** | 遅い／同程度 | 余裕があるマシン向け | 構造化抽出で差が出る報告あり | 同上 |
| **3bit 以下** | 速いが品質崩壊リスク | さらに軽い | Qwen3.6 系で **3bit が coding 全シード失敗** の実測 | [X @filicroval](https://x.com/filicroval/status/2076343654986203423) |
| **KV 8bit** | gen tok/s ほぼ変わらず（50.3→52.6） | KV **1.33× 圧縮** | 速度レバーというより **メモリレバー** | [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm) |
| **TurboQuant 3.5bit KV** | gen が落ちる例（50→25）もある | KV **1.7×〜**、長コンテキストで有利 | 512k+ では帯域削減で逆転しうる | 同上 / [arXiv:2504.19874](https://arxiv.org/abs/2504.19874) |
| **4bit KV** | ほぼ速度不変（28.8 vs 29.2） | メモリ削減 | 「速度ではなくメモリレバー」 | [X @danpacary](https://x.com/danpacary/status/2074912689915330690) |

**M4 Air 24GB 推奨:**  
- 本体重み: **4bit 固定**  
- 作業ログは短コンテキスト → **KV quant は優先度低**  
- 品質検証: 自前の画面スクショ数枚で Ollama 8bit と比較してから切替

---

### 1.4 Vision embedding cache / KV 再利用 / Speculative decoding

#### Vision embedding cache（**録画パイプラインで最重要**）

| 実装 | 効果 | 出典 |
|------|------|------|
| mlx-vlm `VisionFeatureCache` | 多ターンで prompt 処理 **11×+**、メモリほぼフラット | [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm) |
| vllm-mlx content-hash | **28×**（同一画像再クエリ） | [arXiv:2601.19139](https://arxiv.org/html/2601.19139v2) |
| 解像度が高いほど cache 効果大 | 512² で 6.7× → 1024² で 13× 級 | 同論文 Table 5 |

**作業ログへの適用パターン:**
1. フレームの **perceptual hash / OCR text hash** で「画面が変わっていない」判定  
2. 変わっていなければ **VLM スキップ** または **cached vision features を再利用**  
3. 変わっていても UI のヘッダー固定領域は token 削減候補

#### Speculative decoding for VLM

| 手法 | 報告 | 注意 | 出典 |
|------|------|------|------|
| **Gemma4 MTP (mlx-vlm)** | 最大 **3.94×**（26B-A4B, B=4） | 対応モデル限定 | [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) |
| **DFlash** | code/math で **~2.1×** | 雑談は accept 低 | [X @_ARahim_](https://x.com/_ARahim_/status/2072060611517902908) |
| **MTPLX (M5 Max)** | 17→50 tok/s（**2.24×**） | 新ハード | [YouTube](https://www.youtube.com/watch?v=Bd0q3cOWY90) |
| **HunyuanOCR-1.5 + DFlash** | OCR 長出力向け speculative | CUDA/vLLM 主戦場 | [arXiv:2607.04884](https://arxiv.org/html/2607.04884v1) |
| **Apple Silicon 単一ユーザ** | multi-token verify が **量子化 GEMV の高速パスから外れる** → accept 高くないと壁時間で負け | 実務注意 | [X @_ARahim_](https://x.com/_ARahim_/status/2072060611517902908) |

**作業ログ特有の制約:**  
生成が「Excel — セル入力」のような **短い構造化出力** なら、speculative の恩恵は **decode が長いとき** に限られる。支配項が **vision prefill + フレーム数** なら、**キャッシュと間引きの方が効く**。

---

## 2. OCR の高速化

### 2.1 PaddleOCR PP-OCRv6

公式主張（[PaddleOCR README](https://github.com/PaddlePaddle/PaddleOCR)、[HF PP-OCRv6](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det_onnx)）:

| 指標 | 値 |
|------|-----|
| vs PP-OCRv5 | 検出 **+4.6%**、認識 **+5.1%** |
| CPU OpenVINO | medium で最大 **5.2×** |
| **Apple M4 + ONNX Runtime (tiny)** | **約 0.35 s/image**（公式デプロイ連載） |
| A100 tiny | **0.13 s/image** |
| サイズ | tiny **1.5M** / small 7.7M / medium 34.5M |

**推奨設定（M4 Air）:**

```python
# 概念: engine=onnxruntime、tiny または small、解像度を落とす、batch はメモリと相談
TextDetection(model_name="PP-OCRv6_tiny_det", engine="onnxruntime")
# 認識も同様に tiny/small + ONNX
```

- **バッチ:** フレーム単位より、検出→認識のパイプラインで **rec をバッチ** する方が効く（公式 high-performance inference ドキュメント）。
- **解像度:** 画面キャプチャは 2x Retina のまま投げない。OCR 用に **長辺 1280 前後** へ縮小が定石（VLM 用と解像度を分ける）。
- **CoreML ラッパ:** 中国語圏で `ppocrv6-studio` が **Apple Silicon 上 CoreML 加速** を宣伝（[X @QingQ77](https://x.com/QingQ77/status/2068583192651534428)、[X @berryxia](https://x.com/berryxia/status/2067083628824404342)）。

**中国語ソース要約（Paddle公式/コミュニティ）:**
- 「専用OCRは軽量アーキ + 高品質データが、巨大VLMより実用」— PP-OCRv6 デプロイ連載の結論。
- Tech Lead @slimcat0101: 精度・速度とも PP-OCRv6 を推しつつ、**Apple OCR は前処理・後処理の工学最適化が進んでいる**。Paddle はモデル中心で、**最適化後の最小モデルは 50ms 以下を目指す** と発言（[X](https://x.com/slimcat0101/status/2075966696452739579)）。
- MinerU が OCR を PP-OCRv6 に更新し **速度約2倍・精度+11%** と報告（日本語・中国語 X 両方）。

### 2.2 macOS ネイティブ OCR（Apple Vision / Live Text）

- API: [`VNRecognizeTextRequest` / `RecognizeTextRequest`](https://developer.apple.com/documentation/vision/recognizing-text-in-images)
- **Fast path**（文字ベース・低メモリ・リアルタイム）vs **Accurate path**（NN・高精度・非同期向き）— [WWDC19](https://developer.apple.com/videos/play/wwdc2019/234/)
- オンデバイス・ANE/Metal 最適化済み。

**中国語実務報告（重要）:**  
@huangyun_122: Mac Air でスキャンPDFの RAG 前処理に **Mac VisionOCR が PaddleOCR より速度で圧倒**（[X 投稿](https://x.com/huangyun_122/status/2075610056457072686)、3万表示級）。

**使い分け:**

| 用途 | 推奨 |
|------|------|
| UI 英語・日本語の画面文字、速度優先 | **Apple Vision Accurate or Fast** |
| 日本語+中国語混在、特殊フォント、表セル | **PP-OCRv6 medium** を残す or フォールバック |
| 作業ログの「一次情報保持」 | Vision を主、失敗時のみ Paddle |

Python からは `ocrmac` / `pyobjc` / 薄い Swift CLI 経由が現実的。

### 2.3 中国発の新世代 OCR（速度評判）

| モデル | 規模感 | 速度評判 | 精度・注意 | 出典 |
|--------|--------|----------|------------|------|
| **GLM-OCR** | **0.9B** | OmniDocBench 比較で **PDF 1.86 pages/s** で最速クラス。multi-token pred で ~50% 高速化主張 | 精度トップ級（94.62） | [arXiv:2603.10910](https://arxiv.org/html/2603.10910v2), [regolo benchmark](https://regolo.ai/deepseek-ocr-vs-glm-ocr-vs-paddleocr-benchmark-2026/) |
| **PaddleOCR-VL 1.5/1.6** | ~0.9B | PDF **1.22 pages/s**（同論文比較） | OmniDocBench で SOTA 主張（1.6で 96.3%） | 同上 / Paddle X |
| **DeepSeek-OCR / OCR-2** | 3B 級 | **圧縮効率**が売り。A100 で ~20万 pages/day 級の話も。ただし **生産スループットで GLM に大きく負ける** 報告（「DeepSeek 14.8s/page vs GLM 約16×速い」） | 圧縮比と精度の乖離を実測で指摘する声 | [instavar 2026](https://instavar.com/blog/ai-production-stack/DeepSeek_OCR_Production_Notes_2026), [X @witcheer](https://x.com/witcheer/status/2072592890962854123) |
| **Unlimited-OCR（百度）** | 3B / 570M active MoE | DeepSeek-OCR 系 DeepEncoder + 長文書の速度維持 | 5日で Star 1万級。mlx-vlm 対応 | [X @Fenng](https://x.com/Fenng/status/2071478374875455791) |
| **GOT-OCR2.0** | 0.5B 級 | 軽量エンドツーエンドだが、専用軽量OCR（PP-OCR）に速度・コストで負けやすい | Paddle 技術報告で知識蒸留の教師として言及 | [PaddleOCR 3.0 tech report](https://arxiv.org/html/2507.05595v1) |

**MLX 上の注目:**  
- DeepSeek-OCR を mlx-vlm で回し **GLM より約2×速い** という Mac 実測動画あり（[YouTube GLM vs DeepSeek OCR](https://www.youtube.com/watch?v=Bf_KCiAeaAU) — 文脈依存）。  
- GLM-OCR が **Apple Core AI に移植**（[X @JackdeS11](https://x.com/JackdeS11/status/2074061741953319023)）— オンデバイス文書OCRの最短経路候補。  
- MinerU の **MLX/Metal 版が Python 版比 3.3×**（31p PDF: 66.5s → 19.8s）（[X @Qurao1](https://x.com/Qurao1/status/2070698850051072343)）。

**作業ログ用途の判断:**  
- 「画面の文字を正確に残す」→ **軽量専用 OCR（PP-OCRv6 / Vision）** がコスパ最良。  
- 「文書PDFを丸ごと Markdown」→ GLM-OCR / PaddleOCR-VL / Unlimited-OCR。  
- **Qwen3-VL 8B を OCR 代わりに使うのは速度的に最悪**（用途が違う）。

---

## 3. パイプライン設計の高速化パターン

画面録画→作業ログは、**モデル単体最適化よりパイプライン設計の方が効く**。

### 3.1 フレーム間引き（最大ROI）

| 手法 | 内容 | 出典・根拠 |
|------|------|------------|
| **固定間隔** | 0.5–1 fps（会議）/ 1–2 fps（操作） | 既存 skill のモード分離と同思想 |
| **シーン変化検出** | フレーム差分・ヒストグラム・SSIM | 動画OCRで「近傍フレーム集約」が定石（[Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generating-ocr-insight-in-videos-%E2%80%93-the-story-of-a-successful-microsoft-collabora/3642553)） |
| **MaxInfo 等** | visual embedding の情報量で代表フレーム選抜 | [Moments Lab: Frame Sampling](https://research.momentslab.com/blog-posts/frame-sampling-vlm) |
| **滞留時間ベース** | 同じウィンドウが N 秒続いたら 1 回だけ VLM | 作業ログの「アプリ別滞在」と相性良い |

**経験則:** 30fps を全部 VLM に入れるのは論外。**「変化があった境界 + 長滞留の代表1枚」** が標準形。

### 3.2 キャッシュ階層

```
L0: フレーム差分 / pHash        → 変化なしなら全スキップ
L1: OCR テキストハッシュ         → 文字が同じなら VLM スキップ（説明だけ再利用）
L2: Vision embedding cache     → mlx-vlm / vllm-mlx
L3: プロンプト prefix KV (APC)  → システムプロンプト共通化
L4: アプリ別テンプレ出力         → 既知アプリはルールベース短縮
```

vllm-mlx の ablation: **vision cache が 7.8×、KV が 1.2×** — 録画では L0–L2 が本体。

### 3.3 並列化（24GB での安全域）

| やり方 | 可否 | 理由 |
|--------|------|------|
| **OCR ∥ ASR** | ◎ | メモリ小、CPU/ANE と GPU を分けられる |
| **OCR バッチ → VLM 逐次** | ◎ | VLM がメモリを占有 |
| **VLM 複数プロセス並列** | × | 24GB で 8B×2 はスワップ死。skill も「複数本は1コマンド」禁止と同趣旨 |
| **VLM プロセスチャンク再起動** | ◎ | Metal 腐敗対策（[X @sudonur](https://x.com/sudonur/status/2070784014055571681)） |

### 3.4 解像度・DPI・出力長

- 文書OCR本番: **DPI 200→100 で品質ほぼ同じまま 2.5×** 近く改善した例（[high-throughput VLM OCR](https://blueguardrails.com/en/blog/high-throughput-vlm-ocr)）。
- 画面: VLM に渡す前に **長辺 768–1024**。Retina 2880 幅は token 爆死。
- 生成: `max_tokens` を **64–128**、temperature 0、JSON/1行フォーマット固定。

### 3.5 ローカル動画エージェント設計論

[Building a Local AI Video Agent](https://medium.com/data-science-collective/building-a-local-ai-video-agent-architecture-patterns-and-the-hard-problems-part-1-7b700273021c) の主張:  
**モデルは仕事の 20%、残り 80% はフレーム選別・証拠化・信頼できるパイプライン**。作業ログも同じ構造。

---

## 4. 「M4 Air 24GB で今すぐ」 vs 「ハード更新が必要」

### 4.1 今すぐ効く（ソフトウェア・設計のみ）

1. **フレームを 1/10〜1/30 に**（変化検出 + 滞留代表）  
2. **Ollama → mlx-vlm 4bit**（同一 Qwen3-VL 系）  
3. **VisionFeatureCache / 画像ハッシュスキップ**  
4. **OCR を PP-OCRv6 tiny+ONNX または Apple Vision に**  
5. **VLM 入力解像度ダウン + max_tokens 短縮**  
6. **システムプロンプト固定 + APC**  
7. **長時間バッチはプロセス分割**（Metal state）  
8. （品質許容なら）**Qwen3-VL 8B → 4B/2B** で説明専用、重要フレームのみ 8B  

### 4.2 試す価値あり（中コスト）

- mlx-vlm の **DFlash / MTP**（短出力では効果限定）  
- **GLM-OCR 0.9B** を「文書が多い会議録画」用にサイドカー  
- **ShowUI 的 UI パッチ削減** の自前実装  
- OCR と VLM の **二段: OCR全文 + VLM は差分フレームのみ**

### 4.3 ハード更新が必要／効果が頭打ち

| 投資 | 得られるもの |
|------|----------------|
| **M4/M5 Pro/Max + メモリ 48–64GB+** | 帯域向上で decode/prefill、8bit・大コンテキスト余裕 |
| **M3/M4 Ultra / Studio** | 大モデル・並列エージェント |
| **NVIDIA eGPU は実質非現実**（Mac） | CUDA 系 vLLM の本場は別マシン |
| **外部 CUDA マシンへオフロード** | DeepSeek-OCR 大規模バッチ、HunyuanOCR+DFlash 等 |

**帯域の現実:** 同一モデルでも prefill は Mac が GPU サーバに **一桁遅く**なりうる（[X @filicroval](https://x.com/filicroval/status/2076343654986203423): 128K TTFT Mac 552s vs GX10 45s）。**録画ログは「トークン/秒」より「フレーム数 × TTFT」** を見ること。

---

## 5. screen-activity-logger 向けの実装ロードマップ（推奨順）

```
Phase 1（1–2日）: フレーム間引き + OCR hash スキップ + 解像度分離
Phase 2（2–4日）: VLM バックエンドを mlx-vlm 4bit に切替 + VisionFeatureCache
Phase 3（1–2日）: OCR を Vision or PP-OCRv6 tiny ONNX に
Phase 4（任意）  : 4B 既定 / 8B 重要フレーム、プロセスチャンク、APC
Phase 5（研究）  : ShowUI 風 pruning / FastVLM 系へのモデル変更
```

**成功指標の測り方:**
- `frames_to_vlm / total_frames`  
- `vlm_ttft_p50` / `vlm_decode_tok_s`  
- `ocr_ms_per_frame`  
- 壁時間 / 録画時間（目標: 会議で **≤1×**、操作で **≤2×**）

---

## 6. 主要出典一覧（リンク集）

### 論文・公式
- vllm-mlx: https://arxiv.org/html/2601.19139v2  
- FastVLM: https://arxiv.org/abs/2412.13303 / https://machinelearning.apple.com/research/fast-vision-language-models  
- ShowUI: https://arxiv.org/abs/2411.17465  
- GLM-OCR: https://arxiv.org/html/2603.10910v2  
- HunyuanOCR-1.5: https://arxiv.org/html/2607.04884v1  
- TurboQuant: https://arxiv.org/abs/2504.19874  
- PaddleOCR 3.0: https://arxiv.org/html/2507.05595v1  
- Apple Vision OCR: https://developer.apple.com/documentation/vision/recognizing-text-in-images  

### 実装
- mlx-vlm: https://github.com/Blaizzy/mlx-vlm  
- vllm-mlx: https://github.com/waybarrios/vllm-mlx  
- apple/ml-fastvlm: https://github.com/apple/ml-fastvlm  
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR  

### 英語圏 X / 実務
- Prince Canuma（mlx-vlm）: https://x.com/Prince_Canuma/status/2069336447325290942  
- Core AI Qwen3-VL 速度: https://x.com/JackdeS11/status/2065052688589660433  
- Metal 腐敗とプロセス分割: https://x.com/sudonur/status/2070784014055571681  
- DeepSeek-OCR 圧縮の実測批判: https://x.com/witcheer/status/2072592890962854123  
- KV quant はメモリレバー: https://x.com/danpacary/status/2074912689915330690  

### 中国語圏 X / 実務（内容は本文で日本語要約済み）
- Mac VisionOCR ≫ Paddle 速度: https://x.com/huangyun_122/status/2075610056457072686  
- Paddle Tech Lead 応答: https://x.com/slimcat0101/status/2075966696452739579  
- PP-OCRv6 M4 0.35s: https://x.com/PaddlePaddle （Ep.4 連載） / https://x.com/berryxia/status/2070501462656844044  
- MinerU MLX 3.3×: https://x.com/Qurao1/status/2070698850051072343  
- PP-OCRv6 CoreML スタジオ: https://x.com/berryxia/status/2067083628824404342  
- Unlimited-OCR: https://x.com/Fenng/status/2071478374875455791  

---

## 7. 最後に（調査時点の注意）

- 数値は **機種・量子化・解像度・出力長で桁が変わる**。M4 Air 24GB では論文の M4 Max 128GB 数値をそのまま信じず、**自前 1 本の 5 分録画で A/B** すること。  
- 2026-07 時点で Apple Silicon VLM の本命スタックは **mlx-vlm（+ 任意で vllm-mlx のキャッシュ思想）**。  
- 作業ログの勝ち筋は「より大きいモデル」ではなく **「VLM を呼ばないフレームを増やす」**。

必要なら次のステップとして、現在の `screen-activity-logger` コードに対する **Phase1–3 の具体的パッチ案**（変更ファイル一覧・フラグ設計・ベンチ手順）まで落とし込めます。
