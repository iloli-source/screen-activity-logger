# ベストプラクティス：ローカルで「画面録画動画 → 作業ログ」を作る（2026-07 時点）

> Claude / Grok / Codex の3AI＋GitHub直接調査を統合した技術選定ドキュメント。
> 生の調査結果は [`docs/research/`](./docs/research/) を参照。
> 調査日: **2026-07-11**。VRAM数値はコミュニティ報告中心で、解像度・フレーム数・KVキャッシュで大きく変動する点に注意。

## 0. 前提と結論

- **やりたいこと**: PC画面を録画したMP4を入力に、**完全ローカル**で ①画面の文字（OCR）と ②「今この画面で何をしているか」の日本語説明（VLM）を両立し、タイムスタンプ付き作業ログを生成する。
- **ハード制約**: VRAM 8〜12GB（RTX 3060/4060相当）、4bit/AWQ/GGUF量子化前提。
- **3AIが一致した結論**:

> **PaddleOCR（密にOCR）＋ Qwen3-VL-4B/8B-Q4（疎にVLM）＋ ffmpeg/PySceneDetectで間引き＋ Transformers or Ollama で実行。**
> VLM単体にOCRを兼ねさせず、OCRは専用エンジンで確定テキスト化し、VLMには「代表フレーム＋OCR結果＋前後文脈」を渡すのが最も安定する。

「録画MP4をバッチ処理して作業ログを出す」成熟オールインワンOSSは**存在しない**（近い `screenpipe` は"常時キャプチャ"型）。**自前パイプラインの組み立てが現実解。**

### 0.1 ターゲット環境（実測 2026-07-11）

開発機を `system_profiler` で実測した結果、**CUDA GPU機ではなく Apple Silicon** と判明。構成前提を以下に更新する。

| 項目 | 実測値 | 影響 |
|------|--------|------|
| 機種 | MacBook Air / **Apple M4**（10コアCPU・10コアGPU・Metal 4） | CUDA系（AWQ/bitsandbytes/paddlepaddle-gpu）は**使用不可** |
| メモリ | **24GB ユニファイドメモリ**（モデル実効 約16GB） | **Qwen3-VL-8B Q4が余裕で動く**。4Bへの妥協不要 |
| OS | macOS 26.5.2 | — |
| 導入済み | **Ollama 0.30.10** / **ffmpeg 8.1.1** / Python 3.14.6 | MiniCPM-V 4.6の対応条件（Ollama≥0.30）クリア済み。追加導入ほぼ不要 |
| 冷却 | ファンレス | 長時間バッチは熱制限に注意 → 夜間バッチ or 分割処理 |

**M4 Air向け本命構成**:
```
ffmpeg(済) + PaddleOCR PP-OCRv6 tiny/small(CPU) + Qwen3-VL-8B Q4(Ollama or mlx-vlm) + 階層型間引き
```
- ランタイムは **Ollama / llama.cpp(Metal) / mlx-vlm** の三択（CUDA系は全て対象外）
- **mlx-vlm** はQwen3-VLでメモリ10GB→5.5GB・約2倍速の報告あり（Mac最速ルート、§4参照）
- **PP-OCRv6 は論文にApple M4実測あり**（tiny 0.96秒/画像、6.1倍速）→ CPU動作で実用十分

---

## 1. VLM候補（画面理解＝「何をしているか」を説明）

| モデル | パラメータ | VRAM目安(4bit) | 日本語 | 動画/連続F | ライセンス | 位置づけ |
|--------|-----------|----------------|--------|-----------|-----------|----------|
| **Qwen3-VL-4B-Instruct** | ~4B | **4〜6GB** | ◎ | ◎ 長尺・timestamp公式対応 | Apache-2.0 | **本命(8GB機)** |
| **Qwen3-VL-8B-Instruct** | ~8B | **6〜10GB** | ◎ | ◎ | Apache-2.0 | **本命(12GB機)** |
| **Qwen2.5-VL-7B AWQ** | 7B | 8〜12GB | ◎ | ○ | Apache-2.0 | 実績・AWQ成熟の安全牌 |
| **MiniCPM-V 4.5** | 8B | 6〜10GB | ○〜◎ | ◎ High-FPS | Apache-2.0系 | 省メモリ第2候補(Qwen2.5-VL 7B比GPUメモリ46.7%と公称) |
| **Sarashina2.2-Vision-3B** | ~3.8B | ~8GB(BF16) | **特化◎** | △ 画像中心 | **MIT** | 日本語UI/文書の第2パス |
| **InternVL3.5-4B/8B** | 4B/8B | 5〜11GB | 中〜強 | 中 | 各種 | 汎用マルチモーダル |
| **UI-TARS-1.5-7B** | 7B | 10〜14GB | 中 | ─ | Apache-2.0 | GUI操作特化。説明用途には過剰気味 |
| **LLaVA-NeXT-Video** | 7B | 6〜10GB | 弱〜中 | ○ | ─ | **2026ではレガシー。新規採用非推奨** |

### 補足・訂正
- 当初「MiniCPM-V 4.5 は実在未確認」としていたが、**Grok・Codex 双方が実在を確認**（省メモリが強み）。ただし最終的には Ollama / HuggingFace で実物を確認すること。
- 「LLM-jp-VL」という単一製品名は**未確認**。実体は `llm-jp/llm-jp-4-vl-9b-beta` 系列（Grokが具体名を確認）。
- 日本語特化の実在確認できた本命は **`sbintuitions/sarashina2.2-vision-3b`（MIT）** と **`sarashina2.2-ocr`**。

### 選定理由（Qwen3-VLを本命にする根拠）
GUI操作・OCR・長尺動画・タイムスタンプ整合を公式が明記しており、「画面で何をしているか」の日本語説明という本用途に最も素直に載る。2B/4B/8B/32B/MoE と粒度が揃い、8〜12GBに収まるサイズ（4B/8B-Q4）が選べる。Apache-2.0で商用も安心。

---

## 2. OCR候補（画面の文字を確定抽出）

| エンジン | 日本語精度 | 速度 | GPU | 備考 |
|----------|-----------|------|-----|------|
| **PaddleOCR (PP-OCRv5/v6)** | **◎ 最強帯(CJK特化)** | 高速(GPUで加速) | 任意(CPU可) | 85k stars, Apache-2.0, ONNX/OpenVINO/TensorRT対応。**第一候補** |
| **PaddleOCR-VL** | ◎ 文書・レイアウト | 中速 | 要GPU(小) | OmniDocBench上位。画面OCRにも流用可 |
| **Sarashina2.2-OCR** | **日本語文書◎** | 中 | GPU ~3B | 日英ドキュメント特化。重要UIの第2パス |
| **RapidOCR** | ○〜◎ | 高速 | ONNX | Paddle系の軽量ONNX実装 |
| **EasyOCR** | ○ | 中 | GPU可 | セットアップ簡単、精度はPaddleに劣る |
| **Tesseract 5** | ○(jpn) | 遅め | CPUのみ | 依存軽量だが小さいUI文字・低コントラストに弱い(`--psm 6`, `-l jpn+eng`) |

```bash
# PaddleOCR 最短
pip install paddleocr
paddleocr ocr -i frames/key_000123.png --lang japan
```

> 注: 字幕抽出用の `videocr`(apm1467, Tesseractラッパー) は2019年で更新停止。汎用画面ログには古い。PaddleOCRベースの `videocr-PaddleOCR` / `VideOCR`(GUI) の方が新しいが、本用途は「字幕」ではないので **PaddleOCRを直接叩く**のが素直。

---

## 3. フレーム抽出・間引き（VLM呼び出しを削減）

**鉄則: OCRは密（全キーフレーム）、VLMは疎（画面変化時のみ）。** 全フレームVLMは8〜12GBで破綻する。

```bash
# ① ベースライン: 低頻度サンプリング + 縮小（OCR用）
ffmpeg -i screen.mp4 -vf "fps=1,scale=1280:-1" frames/%06d.jpg

# ② 画面変化で間引き（VLMキーフレーム）。閾値0.03〜0.12を画面録画向けに調整
ffmpeg -i screen.mp4 -vf "select='gt(scene,0.08)',showinfo" -vsync vfr keyframes/%06d.jpg

# ③ PySceneDetect（実務で扱いやすい。v0.7=2026-05最新, BSD-3）
pip install "scenedetect[opencv]" --upgrade
scenedetect -i screen.mp4 detect-content list-scenes save-images
```

### 画面録画特有のコツ
| 問題 | 対策 |
|------|------|
| カーソル点滅で誤検出 | 差分前にカーソル領域マスク / モルフォロジー処理 |
| 動画プレイヤー等の常時変化 | ROIを作業ウィンドウに限定 |
| 同一IDEで文字だけ変化 | **OCRテキスト差分**をVLMトリガにする |
| 4K高解像度でVRAM死 | VLM前に長辺1280〜1600へ縮小。`max_pixels`必須 |

---

## 4. 推論ランタイム（8〜12GB現実構成）

| ランタイム | 向き | 備考 |
|-----------|------|------|
| **Transformers + AWQ/bitsandbytes** | Qwen3-VL/Qwen2.5-VLの最短・最堅ルート | 動画入力の公式サンプルあり。`qwen-vl-utils`併用 |
| **Ollama** | 最短で動かす | `ollama run qwen2.5vl:3b` / `minicpm-v4.6`。手軽さ優先 |
| **llama.cpp** | 量子化・CPUオフロード | GGUF Q4_K_M + mmproj。Qwen3-VL GGUFは2025-10-30以降 |
| **LM Studio** | GUI運用(Windows向き) | UI-TARS-desktop連携例あり |
| **vLLM / SGLang** | バッチ・API化 | 単発ローカルには過剰になりがち |
| **MLX** | Apple Silicon | Mac加点用。RTX前提なら優先度低 |

> **注意**: 2026時点でも GGUF/llama.cpp の画像・動画プロセッサ互換は**モデル依存**。Qwen3-VLは Transformers の方が堅く、MiniCPM-V系は Ollama/GGUF の期待値が高い。

### 起動例
```bash
# 8GB機: Qwen3-VL-4B Q4 / Qwen2.5-VL-3B AWQ / MiniCPM-V 4.6
# 12GB機: Qwen3-VL-8B Q4 / Qwen2.5-VL-7B AWQ + 解像度制限
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ --quantization awq \
  --max-model-len 8192 --limit-mm-per-prompt image=1
```

---

## 5. パイプライン設計（推奨1本）

```
Input: screen.mp4
  ├─ Frame:  ffmpeg fps=1 + scene(0.05–0.12) + OCRテキスト差分
  ├─ OCR層:  PaddleOCR(japan)  … 全キーフレームに密適用（CPU/軽GPU）
  ├─ VLM層:  Qwen3-VL-4B(8GB) / 8B-Q4(12GB) … 画面変化フレームのみ疎適用
  └─ Merge:  timestamp | OCR text | 日本語作業説明 → worklog.jsonl → worklog.md
```

### 出力JSONL例
```json
{"t": "00:12:34", "app_guess": "VS Code", "ocr": ["pytest", "FAILED test_auth.py"], "action": "テスト失敗箇所をエディタで確認している"}
```

### VLMプロンプト雛形（作業ログ用）
```text
あなたはPC作業の記録係です。スクリーンショットから:
1) 使用中アプリ/画面
2) ユーザーが今している操作（クリック/入力/確認など）
3) 見えるエラー・ファイル名・URLの要点
を日本語で2〜4文。推測は「推測」と明記。OCRテキスト: {ocr_text}
```

---

## 6. リスクと注意

1. **VRAMは解像度で死ぬ** — 4Kフル解像度をVLMに渡さない。リサイズ・`max_pixels`必須。
2. **VLM単独OCRは遅く不正確** — 文字起こしはPaddleOCR、意味理解はVLMの二層が2026の実務解。
3. **プライバシー** — 画面録画にはパスワード・個人情報が含まれ得る。完全ローカルでも保存先の暗号化を検討。`.gitignore`で実録画(`*.mp4`)とログを除外済み。
4. **「一発OSS」は未成熟** — 録画バッチ→作業ログは自前パイプラインが現実解。常時記録なら `screenpipe` を土台に。
5. **ライセンス** — 商用は各モデルのLICENSE確認（Qwen系Apache-2.0、Sarashina VisionはMIT）。

---

## 7. GitHub / X トレンド（2025後半〜2026）

| トピック | 兆候 |
|----------|------|
| **Qwen3-VL** | 2025-09〜10連続リリース。Computer-Use/Video cookbook。2026-07 XでローカルVLM本命扱い。~19.6k stars |
| **screenpipe** | ~20k stars、YC S26。ローカルAIスクリーンメモリ（常時キャプチャ型） |
| **UI-TARS / desktop** | GUI agentトレンド。ローカルOllama/LM Studio運用記事多数 |
| **MiniCPM-V 4.5/4.6** | Ollama公式取り込み(2026-06)。edge+OCR+video。~25.8k stars |
| **PaddleOCR / PaddleOCR-VL / DeepSeek-OCR** | 2025–26「OCR VLM戦争」。PaddleOCR本体は日本語実務の定番(~85k stars) |
| **日本語VLM** | Sarashina2.2-Vision-3B(2025-11)、llm-jp-4-vl-9b-beta |

---

## 8. 参考リポジトリ

- [QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) — 本命VLM
- [OpenBMB/MiniCPM-V](https://github.com/OpenBMB/MiniCPM-V) — 省メモリVLM
- [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR第一候補
- [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) — シーン検出
- [sbintuitions/sarashina2.2-vision-3b](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b) — 日本語特化VLM(MIT)
- [screenpipe/screenpipe](https://github.com/screenpipe/screenpipe) — 常時キャプチャ型の参考
- [bytedance/UI-TARS](https://github.com/bytedance/UI-TARS) — GUI操作理解

---

## 9. 補遺：作業ログの「活用層」（日本語embedding）

コアの3層（Frame → OCR → VLM）は「動画をテキストにする」までの工程。その先、**生成した作業ログ（日本語テキスト）を検索・分類・要約する層**では、OCR/VLMとは別カテゴリの**日本語テキスト埋め込み（embedding）モデル**が効く。

| モデル | 種別 | 規模 | 用途 | 備考 |
|--------|------|------|------|------|
| **Ruri v3 (`cl-nagoya/ruri-v3-*`)** | 日本語テキスト埋め込み | 30m/130m/310m | 作業ログの意味検索・分類・RAG | ModernBERT-Jaベース、Apache-2.0、最大8192トークン。JMTEB平均77.2で国内SOTA級。**30mでOpenAI text-embedding-3-largeを上回る**軽量さでローカル完結に最適 |

**位置づけの整理（重要）**:
- **OCR** = 画面の文字を読む / **VLM** = 画面で何をしているか説明する / **embedding(Ruri)** = 出力テキストをベクトル化して検索・分類する
- Ruri は **コア（動画→テキスト化）には不要**。ただし作業ログが蓄積したら「過去の似た作業を検索」「作業の自動分類」「RAGで過去ログ参照要約」で本領を発揮する。
- 完全ローカル・日本語・省リソースという本プロジェクトの方針と合致するため、**活用層の第一候補**として採用候補にする。

```text
[動画] → Frame → OCR(PaddleOCR) → VLM(Qwen3-VL) → worklog.md   ← コア（今回の主対象）
                                                      │
                                                      ▼
                                      Ruri v3 で embedding → Faiss 検索/分類/RAG  ← 活用層（Phase4）
```

---

## 10. 第2回調査アップデート（2026-07-11：中国・米国トレンド／論文／GitHub実測）

Grok(X)・Codex(Web+arXiv)・Claude(GitHub実測)による第2回調査の反映。生データは `docs/research/round2_*.md`。

### 10.1 事実訂正（Fable 5再検証）
- **MiniCPM-V 4.6**: 2026-05-11リリース、**1.3B**（SigLIP2-400M＋Qwen3.5-0.8B）、Ollama v0.30以降で公式対応（初回調査の「2026-06」を訂正）
- **llm-jp-4-vl-9b-beta**: 評価を格上げ。日本語10タスク平均で **Qwen3-VL-8Bと同等**（学習トークン180B vs 2T超）。日本語説明重視ならVLM層の実測比較候補
- **PP-OCRv6**: 2026-06-11リリース確定（arXiv:2606.13108）。**論文が「VLMはOCRで幻覚・位置誤差・コスト問題」と明記** → 本設計のOCR/VLM二層分離が学術的に裏付けられた

### 10.2 推奨スタックの更新点
| 項目 | 更新 |
|------|------|
| 解像度 | 長辺1280-1600 → **長辺896〜1024px** に引き下げ（X実運用の合意点。「重み量子化より入力ピクセル制御が本丸」） |
| 間引き | **階層型に強化**: 1fps uniform＋変化点検出 → 重要区間のみ高fps再解析（TimeProVe系でVLM呼び出し75%減の報告） |
| 日本語整形 | **VLM＋小型テキストLLMの分業**を追加。小型VLMはthinking off＋低温度＋短い構造化出力(JSON)で安定 |
| OCR代替 | PaddleOCR本命は維持。**GLM-OCR(0.9B)/DeepSeek-OCR(-2)** を比較検証候補に追加（2026H1のOCR特化再ブーム: baidu/Unlimited-OCRは3週間で⭐13.9k） |
| 評価 | **MS4UI**(arXiv:2506.12623) をベンチマーク採用候補に。UI操作動画2,413本/167時間の「録画→手順要約」評価データセット |
| 活用層 | Ruri v3(テキスト検索)＋ **Qwen3-VL-Embedding**(スクショ直接検索)の併用を検討 |

### 10.3 直結論文リスト
| 論文 | arXiv | 本用途への示唆 |
|------|-------|----------------|
| MS4UI | 2506.12623 | **同一課題のベンチマーク**。既存手法が苦戦＝空白地帯の証明 |
| Qwen3-VL Technical Report | 2511.21631 | interleaved-MRoPE、text-timestamp alignment、256K context |
| MiniCPM-V 4.5 | 2509.18154 | 3D-Resamplerで動画圧縮符号化。Qwen2.5-VL 7B比メモリ46.7% |
| Eagle 2.5 (NVIDIA) | 2504.15271 | 長尺動画のAutomatic Degrade Sampling（フレーム投入と劣化制御） |
| ShowUI | 2411.17465 | UI誘導の視覚トークン33%削減（低VRAM向き） |
| UI-TARS / UI-TARS-2 | 2501.12326 / 2509.02544 | 録画理解の本質は単発画像でなく**状態遷移の推定** |
| PP-OCRv6 | 2606.13108 | 34.5MパラでVLM超えOCR。VLM-OCRの幻覚を明記 |
| GLM-OCR | 2603.10910 | 0.9BのOCR特化。layout＋region認識の2段構成 |
| DeepSeek-OCR | 2510.18234 | 視覚トークン圧縮(100〜800 tokens/page)という発想 |
| FastVLM (Apple) | 2412.13303 | 画面系はモデルサイズよりvision encoder/token設計がボトルネック |

### 10.4 競合状況（GitHub実測 2026-07-11）
- 「録画MP4→ローカル作業ログ」の成熟OSSは**第2回調査でも未発見**
- 先行例 `PBLIZZ/Screen-Recording-OCR` は同一用途だが**Geminiクラウド依存・⭐0**
- → **完全ローカル版は依然として空白地帯**。詳細は `docs/research/round2_claude_github.md`

---

## 11. 次アクション（実装フェーズ）

GitHub Issues で管理（`gh issue list` 参照）。

1. `src/` に最小パイプライン実装：`extract_frames.py` → `ocr.py`(PaddleOCR) → `describe.py`(Qwen3-VL) → `merge.py`(JSONL→Markdown)
2. サンプル動画1本で動作検証、VRAM実測、間引き閾値チューニング（解像度は長辺896〜1024pxから）
3. 日本語作業ログの品質評価（MS4UI参考）、プロンプト改善、小型テキストLLM分業の検証
4. OCR比較検証: PaddleOCR PP-OCRv6 vs GLM-OCR vs DeepSeek-OCR（日本語UI文字）
5. （活用層）作業ログを **Ruri v3 + Faiss** でインデックス化。Qwen3-VL-Embeddingとの併用検討
