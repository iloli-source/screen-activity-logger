# VLM ベストプラクティス／流行 網羅調査（2025後半〜2026-07）

**調査方針**: X上の実利用・言及・使用報告を最優先ソースとし、BentoMLガイド、デプロイ記事、GitHub、Hugging Face、r/LocalLLaMA系二次情報で補強。  
**期間**: おおむね 2025-09〜2026-07。  
**注意**: ベンチ数値・星数・「最強」主張は時点依存。推測・未検証は「未確認」と明記。ハルシネーション回避のため、一次情報で確認できなかった細部は断定しない。

---

## 1. 中国発 VLM の最新動向

### 1.1 Qwen3-VL / Qwen3.5 系（ローカル実務の中心）

| モデル／運用 | 要旨 |
|---|---|
| **Qwen3-VL**（旗艦〜小規模） | BentoML（2025-12）: 旗艦 `Qwen3-VL-235B-A22B` がプロプライエタリ級を狙うと紹介。**32言語OCR・UI操作・長尺動画（256K〜1Mコンテキスト主張）**を前面に。`30B-A3B` 等の中規模も併記。 |
| **Qwen3-VL-8B（実務）** | X: アクセシビリティ用途で `qwen3-vl:8b-instruct`（thinking off）を推奨。代替テキスト生成・OCR・指示追従で Gemma4 より幻覚が少ない、という実利用報告（2026-07）。 |
| **Qwen3-VL-4B（画面監視）** | X: Mac mini M4 32GB + Ollama で `qwen3-vl:4b` を画像解析、`gemma4:12b-it-qat` で日次サマリ。集中／スマホ／離席程度ならローカルVLMで十分、という運用例。 |
| **Qwen3-VL-30B（大量画像）** | X: iPhone 写真約1万枚を `qwen3-vl:30b` に読ませ「食事写真」抽出など、バッチ画像理解の実利用報告。 |
| **Qwen3.5 量子化** | X（Benjamin Marie, 2026-03）: 9B GGUF で **UD-Q4_K_L / Q4_K_L が原盤に近く ~6GB**。UD-IQ3_XXS や Q2 は避ける、という評価。 |
| **超小型 edge** | X: Ollama で `qwen3.5:0.8b` を在庫/OCR パイプライン専用に。thinking 抑制・低温度・stop token でレイテンシ改善の詳細設定共有。 |
| **MLX 最適化** | X（Prince Canuma）: mlx-vlm の Qwen3-VL 修正で **VRAM 約10GB→5.5GB、約2倍速**の報告。 |

**コミュニティ感**: r/LocalLLaMA 系の「best local VLM」（2026-06 頃）でも **Qwen3-VL 8B を「何でも1本」**とする声が強い、という二次まとめが存在する。

### 1.2 MiniCPM-V 系（エッジ・軽量の定番）

| 項目 | 内容 |
|---|---|
| **MiniCPM-V 4.6** | OpenBMB 公式（2026-05頃）: **1.3B級**、LLaVA-UHD v4 で vision FLOPs 約55%削減。高解像度でもエッジ向け。SGLang / vLLM / llama.cpp / Ollama 対応を主張。 |
| **実利用デモ（X）** | 監視カメラ的エージェント（平常/異常判定）、工業計器読み取り→構造化JSON、会計OCRの検証層、**TeXada**（手書き数式→LaTeX のローカル数学エージェント）。 |
| **OCRスタック** | Ollama-OCR 系投稿で MiniCPM-V を LLaVA / Llama 3.2 Vision / Granite / Moondream と並ぶ選択肢として紹介。 |
| **llama.cpp** | OpenBMB 自身: GGUF はコミュニティ経由で動くが upstream 完全公式ではない、と説明。 |

### 1.3 DeepSeek-OCR / DeepSeek 系

| 項目 | 内容 |
|---|---|
| **DeepSeek-OCR（2025-11前後バズ）** | X: 約3B、**視覚トークン圧縮（〜10×）**、ページあたりトークン大幅削減、A100で大量ページ処理、などの紹介が広く拡散。GitHub 星数は投稿により 2万超と触れられるが**時点依存**。 |
| **DeepSeek-OCR 2（2026-01）** | vLLM 公式: **Visual Causal Flow**、固定ラスター走査の代わりに学習済み因果的トークン並べ替え。OmniDocBench v1.5 で改善主張、day-0 対応。 |
| **ローカル周辺** | デスクトップGUIクライアント、オフラインOCRラッパー等がXで共有。**チャット用汎用VLMというより文書専用**という位置づけが多い。 |

### 1.4 GLM-4.6V / GLM-OCR（智譜／Z.ai）

| 項目 | 内容 |
|---|---|
| **GLM-4.6V** | BentoML: **106B（クラウド）**と **Flash 9B（ローカル/低遅延）**。ネイティブ multimodal tool use、UIスクショ→HTML/CSS、128Kコンテキスト、長尺動画・多文書を主張。英中中心。 |
| **エージェント実験（X, 2026-07）** | Browser Use × GLM-4.6V を90回実行: 単純抽出90% / ライブサイト30% / Webフォーム0%。**数字より失敗モードが本題**という実測系投稿。 |
| **GLM-OCR** | LMSYS/SGLang（2026-02）: **約0.9B**、OmniDocBench v1.5 でSOTA主張、表・数式・印章・雑多レイアウト向け。Niels Rogge が llama.cpp + GGUF + LM Studio のローカル手順動画を投稿。 |

※ **GLM-4.7-Flash** 等はテキスト/エージェント向けのローカル話題が強い。VLM本体というより「GLMファミリー全体の勢い」としてXに並ぶ。

### 1.5 InternVL 系

- モバイル／オンデバイス一覧に **InternVL3** が並ぶ（iPhone オフラインアプリ等）。
- OpenGVLab の評価スイート整備がXで紹介（2026-04）。
- **2026H1のX「日常ドライバ」としての熱量は Qwen3-VL / MiniCPM / DeepSeek-OCR に劣る印象**。ベンチ比較の文脈では引き続き名前が出る。

### 1.6 Kimi-VL / Step 系 / SenseTime

| 系統 | 確認できた事実 | X上の「実務で使っている」密度 |
|---|---|---|
| **Kimi-VL（Moonshot）** | GitHub/HF: MoE VLM、**活性約2.8B / 総約16B**、長コンテキスト・エージェント主張。Thinking-2506 更新あり。2025春〜夏が大きな発表波。 | 2026中盤Xでは **Qwenほど「毎日回している」報告が少ない**（未確認: ローカル定番化の度合い）。 |
| **Kimi K2.5 等** | 二次情報: 大規模 visual agentic / swarm の話あり。コンシューマGPU日常運用の一次報告は本調査では薄い。 | 要個別検証 |
| **StepFun Step3 / Step-3.7-Flash** | Step3: 321B total / 38B active の multimodal reasoning。**Step-3.7-Flash（2026-05）**: 198B sparse MoE + vision encoder、エージェント/コーディング寄り。vLLM recipes あり。 | コンシューマローカルより **クラスタ/API寄り**。 |
| **SenseNova-Vision（商湯）** | 2026-07前後: 検出・OCR・depth・segmentation・GUI grounding 等を **タスク専用ヘッドなしの統一生成**で扱う。ModelScope に 7B-MoT。CC BY-NC 等のライセンス注意。 | 研究/統一ビジョンとしての注目。日常チャットVLMとしての使用報告はまだ限定的。 |

### 1.7 中国発「画面エージェント」周辺（モデル＋プロダクト）

- **UI-TARS / UI-TARS-desktop（ByteDance Seed）**  
  - UI-TARS-2（2025-09, Yujia Qin）: multi-turn agent RL。Computer/Phone/Browser/Terminal 等ベンチ数値を公式が提示。  
  - Desktop は X 上で **2.9万〜3.7万⭐** などと繰り返し紹介（時点で変動）。**Anthropic Computer Use のOSS平替**という語り方が定着。  
  - 駆動: UI-TARS + **Seed-1.5-VL / 1.6** 系。Agent TARS は任意マルチモーダルLLM（Claude/GPT/豆包等）接続の枠組みとしても言及。

---

## 2. 米国発（＋英語圏扱いの欧州）VLM 動向

### 2.1 Allen AI — Molmo / Molmo2 / MolmoPoint

| 項目 | 内容 |
|---|---|
| **Molmo（従来）** | PixMoデータ、pointing、1B/7B/72B。ロボティクスやグラウンディングで定評。 |
| **Molmo2（2025末〜2026）** | X: ロボ向け「一択」に近づいたという研究者言及。**動画pointing・tracking・複数画像**を一モデルで。CVPR 2026 候補として紹介される投稿あり。 |
| **MolmoPoint** | pointing を生文字列座標ではなく **visual grounding tokens** で行う提案。モデル・コード・データ公開を強調。 |

### 2.2 Google — Gemma 3 / Gemma 4（マルチモーダル）

- Gemma 3: 1B〜27B、画像＋短尺動画、多言語、128K（1Bは32K）。画像は **896×896→256トークン** 正規化という制約がデプロイ記事で言及。
- 2026ローカル界隈では **Gemma 4** がLLMとしてもバズ。一方、**厳密な人物カウント等で Qwen3-VL より幻覚する**という比較報告（X）あり。  
- **用途分離**（VisionはQwen、要約はGemma）のハイブリッド運用が実例として出ている。

### 2.3 Meta — Llama Vision 系

- **Llama 3.2 Vision** は2024〜2025のローカル比較記事で定番枠。  
- 2026の「最新最強VLM」議論では **Qwen3-VL / MiniCPM-V 4.x に主役を譲った**印象が強い。  
- Llama 4 Scout 等はローカルLLMリストに出るが、**Vision特化の実務報告は本調査では相対的に薄い**。

### 2.4 Mistral — Pixtral

- **Pixtral 12B**（Apache 2.0）: ネイティブ解像度・複数画像・指示追従に強い、という2024-25系評価がBentoガイドに残る。  
- 2026H1の「今のローカル本命」としては **Qwen系に押されている**が、英語圏OSSの選択肢としては存続。

### 2.5 Apple エコシステム — mlx-vlm

- X（Prince Canuma, 2026-04）: **mlx-vlm v0.4.3** が Gemma 4（vision/audio/MoE）、Falcon-OCR、IBM Granite Vision 4.0、SAM 3.1 等 day-0。TurboQuant（KV圧縮）、一部CUDAも。  
- **Mac でローカルVLMを回す層のインフラ標準**に近い。

### 2.6 OpenAI / Anthropic / NVIDIA

| 主体 | オープン／ローカルVLM文脈 |
|---|---|
| **OpenAI** | Operator / Computer Use 系は **クラウド製品としての参照点**。オープン重みの「ローカル本命VLM」というより、評価軸・競合対象。 |
| **Anthropic** | Claude Computer Use が UI-TARS 比較の基準線として頻出。 |
| **NVIDIA** | 歴史的に NVLM / Eagle 系。2026H1のXトレンドとしては **DeepSeek-OCR 2 on vLLM や Blackwellレシピ**など推論基盤側の言及が目立つ。Eagle/NVLMを「今のローカル定番」と推す声は本調査では弱い。 |

### 2.7 その他英語圏の動き

- **Holo 3.1 35B-A3B Q4** + llama.cpp で **機内MacBook上のフルオンデバイス computer-use**（X, 2026-07）——小型MoE×CUAの実演。  
- 小規模自作VLM教材（ViT+SLM+Q-Former）など教育系投稿は継続。  
- **SmolVLA / ロボVLA** は「動画から動作」文脈で別系統として言及。

---

## 3. 画面理解・スクリーン録画解析・GUI 用途

### 3.1 実務で選ばれているレイヤ（モデル vs ハーネス）

```
[画面キャプチャ] → [VLMで状態理解] → [行動方針] → [マウス/キー/API]
       ↑________________ ループ（失敗時は再スクショ）________________↓
```

| 用途 | よく挙がる選択 | 備考 |
|---|---|---|
| **デスクトップGUIエージェント** | **UI-TARS Desktop** + UI-TARS/Seed-VL | ローカル完結・OSSの象徴。星数バズ多数。 |
| **ブラウザ自動化** | Browser Use 等 + GLM-4.6V / 商用VLM | 単純抽出は強いが、フォームは失敗しやすい（実測報告）。 |
| **オンデバイスCUA** | Holo 3.1 + llama.cpp | 飛行機内デモ級の「全部ローカル」。 |
| **汎用画面説明・作業ログ** | **Qwen3-VL 4B/8B**（Ollama） | 「何が画面にあるか」日本語/多言語ログ向き。 |
| **UI→コード** | GLM-4.6V のフロント複製主張 | エージェント寄り。 |
| **GUI grounding 研究** | SenseNova-Vision、UI-TARS 系 | タスク統一生成の流れ。 |

### 3.2 コンピュータユース界隈の語り

1. **プロプライエタリ**: Claude Computer Use / OpenAI Operator（または後続の computer-use 機能）＝品質・コスト・プライバシーの比較軸。  
2. **中国発OSS**: UI-TARS 系が「見られる・話される」頻度で突出。  
3. **ローカル小型**: 専用CUAモデル（Holo等）＋llama.cpp。  
4. **失敗の現実**: ライブWeb・認証・フォーム・captcha で成功率急落。**人間介入UI**（エージェントが詰まったらユーザーが操作）が設計論として出る。  
5. **ハーネス重要**: モデル単体より「スクショ→行動→検証」ループ、ファイルシステム共有、サブエージェント、トレース確認（Philipp Schmid 系のエージェント論）が併せて語られる。

### 3.3 画面録画→ログ化に効く周辺パターン

- **フレーム間引き + 状態分類**（集中/スマホ/離席）: 小型Qwen-VLで足りる、という実例。  
- **マルチモーダルRAG**: PDFをページスクショ化→VLM埋め込み→検索（Maryam Miradi 系の「スクショからエージェント」ガイド）。文書UIと画面UIで手法が共通化。  
- **OCR専用モデル併用**: 文字が主なら DeepSeek-OCR / GLM-OCR、意味理解はQwen、と役割分割する設計が合理的。

---

## 4. ローカル VLM 運用のベストプラクティス

### 4.1 定番スタック（X / デプロイ記事の合意に近いもの）

| レイヤ | よく使うもの |
|---|---|
| 簡単導入 | **Ollama**, **LM Studio** |
| 性能・制御 | **llama.cpp / GGUF**, **vLLM**, **SGLang** |
| Mac | **mlx-vlm** |
| 量子化 | Q4_K_M / Q4_K_L、AWQ、GPTQ、FP8（サーバ） |
| OCR特化 | DeepSeek-OCR (+vLLM), GLM-OCR, Ollama-OCR ラッパ |

### 4.2 VRAM 目安（経験則・報告ベース）

| VRAM | 現実的なVLM運用 |
|---|---|
| **〜8GB** | MiniCPM-V 4.6（1.3B）、Qwen3-VL **4B** Q4、Qwen3.5 9B Q4（~6GB報告）、0.8B edge ビジョン。解像度を抑える。 |
| **8〜12GB** | **Qwen3-VL 8B Q4/Q5** が「総合力1本」候補。同時にKVと視覚トークンを食い過ぎないよう max 解像度・ctx を制限。 |
| **16〜24GB** | Qwen3-VL 30B級、より長いコンテキスト、複数画像。 |
| **それ以上** | 旗艦MoE、長コンテキスト動画、マルチユーザー vLLM。 |

※ 視覚トークンは **解像度にほぼ比例してKVを食う**。重み量子化だけでは足りず、**入力ピクセル制御が本丸**。

### 4.3 解像度・トークン制御のコツ（デプロイ記事＋実験）

1. **クライアント側でリサイズ**: 多くの用途で **長辺 896〜1024px** がコスト効率良い。OCRでも 1792px の恩恵は限定的でトークンが跳ねる、という実務ガイドあり。  
2. **vLLM**: `max-model-len` は「視覚トークン + テキスト予算 + 余裕」。過大設定はKV事前確保でVRAMを無駄食い。  
3. **連続バッチ**: 静的バッチより continuous batching がVLM向き。  
4. **量子化と視覚表現**: 一実験（Qwen2-VL-7B）では **GPTQ INT4 の方が BnB INT8 より visual token 表現を保つ**、劣化は中間層に集中、という報告。一般則化は未確認だが「INT4=即死」ではない示唆。  
5. **Thinking モデル**: 小Qwenは thinking が遅くノイズ。`enable_thinking false` + stop token + 低温度で **分類・OCR・構造化出力**を安定させる運用が共有されている。  
6. **役割分割**: 軽量VLM（キャプション/OCR/画面状態）＋中型テキストLLM（日本語要約・作業ログ整形）が 8〜12GB で現実的。

### 4.4 品質Tips（実利用から）

- 指示は **短い構造化出力**（JSON / 箇条書き / モード指定）に。  
- 画面系は **「前フレームとの差分観点」**をプロンプトに入れるとログが安定（未確認だがエージェント実装で定石）。  
- 透明PNGは背景を敷く（Molmo系の既知Tips）。  
- UIエージェントは成功率がタスク依存。**ログ化（受動的理解）と操作（能動的CUA）を混同しない**。

---

## 5. 動画理解のトレンド

| 潮流 | 内容 | ソース感 |
|---|---|---|
| **長コンテキストVLM** | Qwen3-VL の「時間単位インデックス・長尺動画」主張。GLM-4.6V も hour-long video を記載。 | ベンダー／ガイド |
| **Pointing / Tracking** | Molmo2 が video pointing・tracking・count-by-pointing を一体で。 | X + 研究 |
| **ストリーミング記憶** | OmAI Lab **VLX-Flow**: 全履歴再処理ではなく **incremental memory**。ライブ映像で「今何が起きたか」を保持。 | X 2026-06 |
| **スパース証拠収集** | TimeProVe: 仮説→必要な区間だけVLM。**OpenTSUBench +7.3%、VLM呼び出し75%減、推論コスト93%減**主張。 | X 二次紹介 |
| **商用動画エージェント** | Orion 2 等: ハイライト検出、15秒クリップ、キーフレーム抽出。 | 製品X |
| **データ** | NBA長尺などドメイン動画データセット提案。 | X |
| **コスト原則** | 「全部見る」から **サンプル→候補区間→高精度VLM** の階層へ。画面録画ログも同じ思想が使える。 | 横断 |

**フレームサンプリング実務（コミュニティ合意に近いもの）**  
- 定常監視: 1〜2 fps または シーンチェンジ検出。  
- 作業ログ: キーイベント（ウィンドウ切替・クリック直後）優先。  
- 長尺Q&A: 粗いサンプリングで候補→該当区間を高解像度で再推論（video-RAG的）。

---

## 6. 2026年上半期に「伸びた／話題になった」もの

| テーマ | 何が起きたか |
|---|---|
| **中国オープンVLMの実務支配** | ローカルVisionの本命議論が **Qwen3-VL / MiniCPM-V 4.6 / GLM-4.6V-Flash** に収束しがち。 |
| **OCR特化の再ブーム** | DeepSeek-OCR（＋OCR2）、GLM-OCR（0.9B）、専用GUI。**「汎用VLMでOCR」から「圧縮OCRモデル」へ**。 |
| **Computer Use のOSS化** | UI-TARS-desktop が数万⭐級で繰り返しバズ。「Claude CU のローカル平替」ナラティブ。 |
| **超小型エッジVLM** | MiniCPM-V 4.6（1.3B）、Qwen 0.8B edge、モバイルInternVL3等。**監視・計器・OCRパイプライン**。 |
| **推論スタック day-0** | vLLM / SGLang が新モデル即日対応を広報（DeepSeek-OCR2, GLM-OCR, DeepSeek V4 長コンテキスト等）。 |
| **統一ビジョン生成** | SenseNova-Vision: 検出〜depth〜GUI grounding を一つの生成パラダイムで。 |
| **オンデバイスCUA** | Holo等 + llama.cpp のデモが「クラウドCU不要」論を刺激。 |
| **ローカルLLM全体** | Qwen3.5 / Gemma 4 / GLM-4.7-Flash 等テキスト側も同時進行。VLMは **Qwen系マルチモーダルが牽引**。 |
| **動画コスト削減** | ストリーミングメモリ・スパースVLM呼び出しが研究＋実装の両面で言及増。 |

**スター急増リポジトリ（X言及ベース・時点依存）**  
- `bytedance/UI-TARS-desktop`（Xで 29k〜37k+ と複数回言及）  
- DeepSeek-OCR 関連（2万⭐超言及あり）  
- MiniCPM-V / Qwen3-VL 公式・cookbook  
※ 正確な現在星数は本レポートでは再取得していない。

---

## 7. 用途別クイックマップ

| やりたいこと | 2026中盤の第一候補（オープン寄り） | 代替 |
|---|---|---|
| 総合ローカルVLM | **Qwen3-VL 8B** | InternVL3、Gemma vision |
| エッジ・低VRAM | **MiniCPM-V 4.6** / Qwen-VL 4B | 0.8B edge |
| 文書OCR大量 | **DeepSeek-OCR (2)** / **GLM-OCR** | Qwen3-VL |
| GUI操作エージェント | **UI-TARS Desktop** | Holo等オンデバイスCUA、商用CU |
| ロボ・ポインティング | **Molmo2** | 専用VLA |
| Mac最適化 | **mlx-vlm + Qwen/Gemma** | Ollama |
| 長尺動画Q&A | Qwen3-VL（大）+ スパース戦略 | VLX-Flow系、階層RAG |

---

## 8. 示唆：VRAM 8〜12GB で「画面録画 → 日本語作業ログ化」

1. **本命構成**: Ollama または llama.cpp で **`Qwen3-VL 4B〜8B` のQ4系**をビジョン担当にし、必要なら同VRAM内の **中〜小型テキストモデル**で日本語の日次ログ整形（実例に近い: 小VLM + Gemma系サマリ）。  
2. **全フレームを食わせない**: 1〜2fpsまたはシーン変化・アクティブウィンドウ変化だけ送り、長辺 **896〜1024px** に落とす。8〜12GBでは視覚トークンとKVがボトルネックになりやすい。  
3. **プロンプトはログ専用**: 「時刻・アプリ名・ユーザー操作の推定・画面上の主要テキスト・次に続きそうな作業」を短い箇条書き／JSONで固定。thinking は切る。  
4. **操作エージェントと分離**: 作業ログ化は **受動的理解**で足りる。UI-TARS級のクリック自動化は成功率・権限・VRAMの別問題として切る方が安全。  
5. **文字が主なら二段構成**: 画面テキスト抽出に **GLM-OCR / DeepSeek-OCR**、文脈理解に Qwen-VL、という分割も 12GB 近辺で検討価値あり（同時ロードは厳しいので**逐次ロードまたはCPUオフロード**）。

---

### 出典メモ（調査時に触れた主な一次・準一次）

- X: OpenBMB, vLLM, UI-TARS関連（Yujia Qin / 中文紹介多数）, Benjamin Marie, José María Fernández, うめぼし, Emrick（Holo）, Molmo2/MolmoPoint, SenseNova, GLM-4.6V browser 実験, DeepSeek-OCR紹介 等  
- Web: BentoML “Best Open-Source VLMs 2026”, Spheron VLMデプロイ記事, GitHub UI-TARS-desktop / Kimi-VL / Step3, HF MiniCPM-V 4.6, r/LocalLLaMA 系二次まとめ  

**未確認・要注意**: 個別ベンチの最新SOTA順位、各リポジトリの現在星数、Kimi/StepのコンシューマGPU日常利用率、NVIDIA Eagleの2026H1実務シェア、一部投稿のベンチ数値の再現性。

---

以上が、調査済み内容に基づく**完全版レポート全文**です。追加調査は行っていません。
