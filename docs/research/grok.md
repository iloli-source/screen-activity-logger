PC画面録画→作業ログのローカル化について、2025後半〜2026の実在モデル・リポジトリ・使用報告を優先して調査します。有望なオールインワン候補と日本語VLMの詳細を掘ります。# 調査報告：PC画面録画 → 作業ログ（ローカル OCR + VLM）2026年ベストプラクティス

調査時点: **2026-07-11**。実在確認できたモデル・リポジトリ・使用報告のみを記載します。VRAM数値はコミュニティ報告中心で、解像度・フレーム数・KV cacheで大きく変動します。

---

## 1. ローカルVLM候補（2025後半〜2026現役）

### 1.1 第一候補帯（8–12GBで現実的）

| モデル | パラメータ | VRAM目安 | 量子化 | 日本語 | 動画/連続F | ライセンス |
|--------|-----------|----------|--------|--------|-----------|-----------|
| **Qwen3-VL-4B-Instruct** | ~4B | BF16 ~8GB / 4bit **4–6GB** | GGUF (llama.cpp 2025-10-30以降), AWQ/FP8系 | ◎（多言語強い。JAベンチでも上位） | ◎ 長尺動画・timestamp grounding公式対応 | Apache-2.0 |
| **Qwen3-VL-8B-Instruct** | ~8B | 4bit **~6–10GB** / BF16 ~16GB | 同上 | ◎ | ◎ | Apache-2.0 |
| **Qwen2.5-VL-3B / 7B** | 3B / 7B | 3B: 8GB可 / 7B-AWQ INT4 **~4.5–7GB** | 公式AWQ, Ollama `qwen2.5vl:3b/7b` | ◎ | ○ 動画対応（Qwen3-VLより旧世代） | Apache-2.0 |
| **MiniCPM-V 4.5** | 8B (Qwen3-8B + SigLIP2) | int4/GGUFで **8–12GB帯** | GGUF, int4, AWQ, Ollama | ○ 多言語OCR強 | ◎ High-FPS video | Apache-2.0系 |
| **MiniCPM-V 4.6** | 小規模 (~0.8B LLM + SigLIP2) | エッジ向け **超低VRAM** | Ollama公式 `minicpm-v4.6` (2026-06) | ○ | ◎ 効率重視 | Apache-2.0系 |
| **Sarashina2.2-Vision-3B** | ~3.8B | BF16で **~8GB前後**（推定） | HF quantあり | **特化◎**（BusinessSlide/Heron/JDocQAで同規模Qwenに競合〜優位） | △ 画像中心（長尺動画は弱い想定） | **MIT** |
| **llm-jp-4-vl-9b-beta** | ~9B | 4bitで **~8–12GB帯**（推定） | transformers中心 | 特化◎ | △ 画像中心 | 要確認（llm-jp系列は多くApache-2.0） |

### 1.2 各候補の長短

**Qwen3-VL（最有力）**  
- 公式: [github.com/QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)  
- サイズ: 2B / 4B / 8B / 30B-A3B MoE / 32B / 235B-A22B（2025-09〜10リリース）  
- **長所**: PC/mobile GUI agent cookbookあり、OCR 32言語、256K〜1M context、動画の text–timestamp alignment、vLLM/SGLang/llama.cpp/Ollama対応が進んでいる  
- **短所**: 高解像度スクショは visual token が増え 8GB で OOMしやすい → `max_pixels` / `longest_edge` 制御必須  
- **実使用**: 2026-07 X上で「ローカルOCR・代替テキスト生成に `qwen3-vl:8b-instruct` が最強」報告あり  

**Qwen2.5-VL**  
- 長所: 実績・量子化・Ollama成熟、RTX 3080 10GBで3B-AWQ動作報告  
- 短所: Qwen3-VLにGUI/動画で後塵。7Bは8GBだと解像度制限が厳しい  

**MiniCPM-V 4.5 / 4.6**  
- 公式: [github.com/OpenBMB/MiniCPM-V](https://github.com/OpenBMB/MiniCPM-V)  
- 長所: **OCRと動画が同時に強い**、edge向け、Ollama統合が2026も活発  
- 短所: 日本語の自然な作業説明はQwen/Sarashina比で劣ることがある（未確認の体感差を含む）  

**Sarashina2.2-Vision-3B / Sarashina2.2-OCR**  
- HF: `sbintuitions/sarashina2.2-vision-3b`, `sbintuitions/sarashina2.2-ocr`  
- 長所: **日本語UI・文書・スライドに特化**、MIT、3Bで8–12GBに収まる  
- 短所: 汎用動画理解・GUI agent能力はQwen3-VLより弱い。ランタイム生態系（Ollama等）はQwen/MiniCPMより薄い  

**llm-jp-4-vl-9b-beta**  
- HF: `llm-jp/llm-jp-4-vl-9b-beta`  
- 長所: 日本語学術コミュニティのオープンVL  
- 短所: ローカル運用・量子化・動画パイプラインの実務報告はまだ少ない  

**InternVL3.5-8B**  
- 2025-08リリース、vLLM/LMDeploy対応  
- 長所: 汎用マルチモーダル強い  
- 短所: 8B BF16は16GB寄り。日本語特化・Ollama簡便さではQwen/MiniCPMに劣る  

**LLaVA-NeXT-Video**  
- 2024世代。2026時点では**レガシー**。新規採用は非推奨（Qwen3-VL / MiniCPM-Vに置換）  

### 1.3 未確認・注意

| 名称 | 状態 |
|------|------|
| 「LLM-jp-VL」という単一製品名 | **未確認**（実体は `llm-jp-4-vl-*` 系列） |
| UI-TARS 2 の 230B MoE を 12GB でフル推論 | **非現実的**（7B版が現実的） |
| 特定ベンチの「絶対王者」宣言 | 条件依存が多く断定不可 |

---

## 2. OCRエンジン

| エンジン | 日本語精度 | 速度 | GPU | 動画ラッパー | 備考 |
|----------|-----------|------|-----|-------------|------|
| **PaddleOCR / PP-OCRv5〜v6** | **◎ 最強帯**（CJK特化） | 高速（GPUで大幅加速） | 任意（CPU可） | **videocr-PaddleOCR**, **VideOCR** GUI | 2026-05: PaddleOCR 3.6 / **PaddleOCR-VL-1.6** |
| **PaddleOCR-VL** | ◎ 文書・レイアウト | VLMなので中速 | 要GPU（小モデル） | フレーム単位で呼び出し | OmniDocBench上位。画面OCRにも流用可 |
| **Tesseract 5** | ○（jpn traineddata） | 遅め | **CPUのみ** | 自前ループ | 依存軽量。UI/低コントラストに弱い |
| **EasyOCR** | ○ | 中 | GPU可 | 自前 | セットアップ簡単、精度はPaddleに劣ることが多い |
| **RapidOCR** | ○〜◎ | 高速 | ONNX | 自前 | Paddle系の軽量実装として r/LocalLLaMA で言及 |
| **DeepSeek-OCR / OCR-2** | ◎（文書レイアウト） | 中〜高 | GPU | 文書向け | 2025–26で急成長。**スクショUI特化は未検証** |
| **GOT-OCR 2.0** | ◎ | 中 | GPU | 文書 | end-to-end OCR VLM |
| **Sarashina2.2-OCR** | **日本語文書◎** | 中 | GPU ~3B | フレーム単位 | 日英ドキュメント特化 |
| **dots.ocr / LightOnOCR / GLM-OCR** | 文書SOTA争い | 各様 | GPU | 文書 | 2026 OCR戦争の参加者。画面録画用途の報告は少ない |

### 実務推奨（OCR層）

```text
画面UI・メニュー・エラーログ:  PaddleOCR (PP-OCR, lang=japan)  or RapidOCR
日本語ドキュメント寄り:         Sarashina2.2-OCR / PaddleOCR-VL
字幕抽出（参考）:               VideOCR + PaddleOCR
```

**videocr 系**  
- [devmaxxing/videocr-PaddleOCR](https://github.com/devmaxxing/videocr-PaddleOCR)  
- [timminator/VideOCR](https://github.com/timminator/VideOCR)（GUI、ローカルPaddleOCR）

---

## 3. GUI / スクリーン理解特化

| モデル/データ | 規模 | 用途 | VRAM | 作業ログへの流用 |
|---------------|------|------|------|------------------|
| **UI-TARS-1.5-7B** | 7B | GUI agent（ByteDance） | 4bitで8–12GB帯 | **「今何をしているか」に最適**。操作説明・要素認識 |
| **UI-TARS-2** | 大（MoE報告あり） | All-in-one agent | 12GBでは非現実的 | レポート・デモ用途 |
| **UI-TARS-desktop** | アプリ | ローカル操作agent | Ollama/LM Studio連携 | [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop)（**~23k stars** 言及あり） |
| **OS-Atlas** 4B/7B | 4B/7B | GUI grounding | 4Bは12GB可 | 要素bbox・「どこをクリック対象か」 |
| **ShowUI-2B** | 2B | VLA for GUI | **2Bで軽い** | 軽量GUI記述。CVPR 2025 |
| **CogAgent-9B** (2024-12) | 9B | GUI特化VLM | 4bitで12GBギリギリ | 高解像度UI理解。18B旧版は重い |
| **Qwen3-VL Computer-Use cookbook** | — | PC操作エージェント | モデル依存 | 公式がスクショ→操作理解を想定 |

**データセット（学習・評価用）**  
- OS-Atlas grounding corpus（**1300万+ GUI要素**、オープン）  
- ShowUI-desktop-8K  
- ScreenSuite（2025-06、GUI agent評価スイート）

**注意**: GUI agent系は「次のクリック」向けに訓練されている。作業ログには  
`「この画面では VS Code で pytest の失敗を確認し、terminal にエラーを表示している」`  
のような **caption/説明プロンプト** に載せ替えると効く。

---

## 4. フレーム抽出・差分検出（VLM間引き）

全フレームVLMは 8–12GB では破綻します。**OCRは密、VLMは疎**が定石です。

### 4.1 実務パイプライン

```
動画
 ├─ (A) 1fps or 2fps 固定サンプリング  →  OCR全適用（軽い）
 ├─ (B) シーン変化 / 画面差分         →  VLMキーフレーム
 └─ (C) キーフレーム前後 ±0.5s         →  文脈用マルチ画像
```

### 4.2 具体コマンド

**ffmpeg シーン変化**
```bash
# 閾値 0.3 は画面録画だとやや高く、0.05–0.15 から調整
ffmpeg -i screen.mp4 \
  -vf "select='gt(scene,0.08)',showinfo" \
  -vsync vfr frames/kf_%06d.png 2>&1 | tee scene.log

# タイムスタンプ付きメタ
ffmpeg -i screen.mp4 -filter_complex \
  "select='gt(scene,0.08)',metadata=print:file=times.txt" \
  -vsync vfr frames/kf_%06d.png
```

**固定間隔（作業ログ向けベースライン）**
```bash
# 2秒に1枚（OCR用）
ffmpeg -i screen.mp4 -vf "fps=0.5" -q:v 2 ocr_frames/f_%06d.png
```

**PySceneDetect**
```bash
pip install scenedetect[opencv]
scenedetect -i screen.mp4 detect-content list-scenes save-images
# ContentDetector の threshold を画面録画向けに下げると窓切替を拾いやすい
```

**OpenCV 差分（実装パターン）**
```python
# 擬似コード
prev = gray(frame0)
for t, frame in frames:
    d = mean(abs(gray(frame) - prev))
    if d > TH or (t - last_vlm) > MAX_GAP_SEC:
        vlm_queue.append((t, frame))
        prev = gray(frame)
```

### 4.3 画面録画特有のコツ

| 問題 | 対策 |
|------|------|
| カーソル点滅で誤検出 | 差分前にカーソル領域マスク / モルフォロジー |
| 動画プレイヤー等の常時変化 | ROIを作業ウィンドウに限定 |
| 同一IDEで文字だけ変化 | OCR diff（テキスト差分）をVLMトリガに |
| 高解像度4K | VLM前に longest edge 1280–1600 に縮小 |

---

## 5. 推論ランタイム（8–12GB現実構成）

| ランタイム | 向き | 8–12GBでの使い方 | 備考 |
|-----------|------|------------------|------|
| **Ollama** | 最短で動かす | `ollama run qwen3-vl:4b` / `minicpm-v4.6` | 手軽さ最優先。速度は llama-server に劣る報告あり |
| **llama.cpp** | 量子化・CPUオフロード | GGUF Q4_K_M + mmproj | Qwen3-VL GGUFは 2025-10-30 以降サポート |
| **LM Studio** | GUI運用 | UI-TARS-desktop と連携例あり | Windowsユーザー向き |
| **vLLM** | バッチ・サーバ | `vllm serve Qwen/...-AWQ` + max_pixels制限 | 依存重め。単発ローカルなら過剰になりがち |
| **SGLang** | 同上 | Qwen3-VL公式推奨の一角 | サーバ用途 |
| **MLX** | Apple Silicon | Qwen/MiniCPMのMLXポート（モデル次第） | Mac加点用 |
| **Transformers + bitsandbytes** | 実験・Sarashina | `load_in_4bit` | 日本語特化モデルの一次起動に便利 |

### 現実的な起動例

```bash
# Ollama（手軽）
ollama pull qwen2.5vl:3b          # 確実に8GB
# またはコミュニティ/公式に出ている qwen3-vl タグを確認
ollama run qwen2.5vl:3b

# MiniCPM-V 4.6（エッジ）
ollama run minicpm-v4.6

# vLLM + AWQ（スループット）
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
  --quantization awq --max-model-len 8192 \
  --limit-mm-per-prompt image=1
```

**8GB RTX 3060 向け**: Qwen3-VL-4B Q4 / Qwen2.5-VL-3B AWQ / MiniCPM-V 4.6  
**12GB RTX 3060/4060 向け**: Qwen3-VL-8B Q4 または Qwen2.5-VL-7B AWQ + 解像度制限

---

## 6. オールインワンOSS（動画/画面 → 理解ログ）

| リポジトリ | Stars目安 | 何をするか | 本用途への適合 |
|-----------|-----------|-----------|----------------|
| **[screenpipe/screenpipe](https://github.com/screenpipe/screenpipe)** | **~19.7k** | 24/7画面+音声キャプチャ、Accessibility優先+OCR、ローカル検索、Ollama連携 | **最有力**。ただし「録画ファイル入力」より**常時キャプチャ**が主眼。YC S26 |
| **[openrecall/openrecall](https://github.com/openrecall/openrecall)** | **~2.9k** | Windows Recall代替。定期スクショ+OCR+ローカル検索 | 軽量。VLM作業説明は弱い |
| **[bytedance/UI-TARS](https://github.com/bytedance/UI-TARS)** + desktop | 高 | GUI操作エージェント | リアルタイム操作向き。事後ログ生成は自前パイプライン要 |
| **VideOCR** | 中 | 動画→字幕OCR | OCR層のみ |
| **ai_driven_video_understanding** 等 | 小 | 動画要約デモ | 参考実装。プロダクション品質は要検証 |
| **完全な「録画MP4→タイムスタンプ作業ログ」専用OSS** | — | — | **未確認**（screenpipe + 自前VLMバッチが実質ベスト） |

**重要な設計判断**  
「既に撮ったMP4をバッチ処理」なら **自前パイプライン**（ffmpeg + PaddleOCR + Qwen3-VL）が本命。  
「これから作業を記録する」なら **screenpipe** を土台にし、Ollama VLMで要約する方が速い。

---

## 7. GitHub / X トレンド（2025後半〜2026）

| トピック | 兆候 |
|----------|------|
| **screenpipe** | ~20k stars、YC S26、ローカルAIスクリーンメモリとして継続言及 |
| **UI-TARS / UI-TARS-desktop** | 2025-01 OSS化 → 2025-04 1.5 → 2025-09 UI-TARS-2。desktop ~23k級の言及。ローカルOllama/LM Studio運用記事多数 |
| **Qwen3-VL** | 2025-09〜10連続リリース。Computer-Use / Video cookbook。2026-07 XでローカルVLM本命扱い |
| **MiniCPM-V 4.5/4.6** | Ollama公式取り込み（2026-06）。edge + OCR + video の実演がYouTube/Xで継続 |
| **PaddleOCR-VL / DeepSeek-OCR** | 2025–26「OCR VLM戦争」。文書SOTA争い。画面録画用途の直接報告はまだ少ないが、PaddleOCR本体は日本語実務の定番 |
| **日本語VLM** | Sarashina2.2-Vision-3B（2025-11公開）、llm-jp-4-vl-9b-beta、JAMMEval/Jagle等の評価整備 |
| **r/LocalLLaMA** | 2026も「best OCR」「best local VLM」スレが活発。古典OCR→VLM-OCRへの移行が主流コメント |

---

## 推奨スタック（制約: VRAM 8–12GB / 完全ローカル / 日本語作業ログ）

### 構成（1つに絞る）

```
┌─────────────────────────────────────────────────────────┐
│  Input: screen.mp4                                      │
├─────────────────────────────────────────────────────────┤
│  [Frame] ffmpeg fps=0.5 + scene(0.05–0.12) + OCR-diff   │
├──────────────────────┬──────────────────────────────────┤
│  OCR層               │  VLM層                           │
│  PaddleOCR (japan)   │  Qwen3-VL-4B (8GB) or            │
│  CPU/軽GPU           │  Qwen3-VL-8B-Q4 (12GB)           │
│  全キーフレーム       │  Ollama or llama.cpp             │
│                      │  シーン変化フレームのみ            │
├──────────────────────┴──────────────────────────────────┤
│  Merge: timestamp | OCR text | 日本語作業説明            │
│  → worklog.md / JSONL                                   │
└─────────────────────────────────────────────────────────┘
```

| 層 | 選定 | 理由 |
|----|------|------|
| **OCR** | **PaddleOCR（日本語）** | CJK精度・速度・CPU可・videocr実績。VLMと役割分離でVRAMをVLMに全振りできる |
| **VLM** | **Qwen3-VL-4B**（8GB）/ **8B Q4**（12GB） | 2026現役、GUI/OCR/動画/タイムスタンプが公式に強い、量子化生態系が厚い、日本語も十分 |
| **ランタイム** | **Ollama**（運用簡単）または **llama.cpp GGUF**（速度・制御） | 8–12GBでの実運用報告が最多。vLLMはバッチ大量時のみ |
| **間引き** | **ffmpeg scene + OCRテキスト差分 + 最大間隔キャップ** | VLM呼び出しを 1/10〜1/30 に削減 |
| **日本語強化オプション** | 重要UIは **Sarashina2.2-OCR** を第2パス | 日本語メニュー/エラーの取りこぼし低減（VRAM交互ロード or CPU OCR） |

### 代替プラン（用途別）

| 優先 | スタック |
|------|----------|
| 日本語説明の自然さ最優先 | OCR: Paddle / VLM: **Sarashina2.2-Vision-3B**（または Qwen3-VL-4B 出力を小さなJA LLMでリライト） |
| 常時記録・検索 | **screenpipe** + Ollama（Qwen3-VL/MiniCPM） |
| 超軽量・バッテリー | MiniCPM-V 4.6 + PaddleOCR CPU |
| GUI操作説明特化 | UI-TARS-1.5-7B Q4（ログ用キャプションプロンプト） |

### 最小プロトタイプ手順（骨子）

```bash
# 1) フレーム
mkdir -p frames && ffmpeg -i screen.mp4 -vf "fps=0.5" frames/f_%06d.png

# 2) OCR（例: paddleocr CLI / Python）
# paddleocr ocr -i frames/ --lang japan

# 3) VLM（Ollama）
# シーン変化フレームだけ:
# ollama run qwen2.5vl:3b "この画面でユーザーは何の作業をしていますか？日本語で1-3文。見えるエラーやアプリ名を含めて。"
```

出力JSONL例:
```json
{"t": "00:12:34", "app_guess": "VS Code", "ocr": ["pytest", "FAILED test_auth.py"], "action": "テスト失敗箇所をエディタで確認している"}
```

### プロンプト雛形（作業ログ用）

```text
あなたはPC作業の記録係です。スクリーンショットから:
1) 使用中アプリ/画面
2) ユーザーが今している操作（クリック/入力/確認など）
3) 見えるエラー・ファイル名・URLの要点
を日本語で2〜4文。推測は推測と明記。OCRテキスト:
{ocr_text}
```

---

## リスクと注意

1. **VRAMは解像度で死ぬ** — 4Kフル解像度をVLMに渡さない。`max_pixels` / リサイズ必須。  
2. **VLM単独OCRは遅い** — 正確な文字起こしはPaddleOCR、意味理解はVLMの二層が2026の実務解。  
3. **プライバシー** — 画面録画にはパスワード・個人情報が含まれる。完全ローカルでもログ保存先の暗号化を検討。  
4. **「一発OSS」は未成熟** — 録画バッチ→作業ログは **自前パイプライン** が現実解。screenpipeは常時キャプチャ向け。  
5. **ライセンス** — 商用は各モデルのLICENSEを都度確認（Qwen系Apache-2.0、Sarashina VisionはMIT確認済み）。

---

## 結論（一行）

**2026・VRAM 8–12GB制約下のベストは「PaddleOCR（密）＋ Qwen3-VL 4B/8B-Q4（疎）＋ ffmpeg/scene間引き＋ Ollama or llama.cpp」**。日本語をさらに詰めたいなら Sarashina2.2-OCR/Vision を第2パス、常時記録なら screenpipe を土台にする。

必要なら次のステップとして、この推奨スタックの **最小動作スクリプト（Python: フレーム抽出→OCR→VLM→JSONL）** をリポジトリ構成まで落とし込みます。
