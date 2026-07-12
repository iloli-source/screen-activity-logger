# screen-activity-logger

PC画面を録画した動画（MP4）を入力に、**完全ローカル**で **3つのコンテキスト**──①画面の文字（OCR）②何をしているかの日本語説明（VLM）③発話（ASR）──を抽出・統合し、**構造化されたタイムスタンプ付き日本語作業ログ**を生成するツール。

> クラウドAPIに一切送らない。会議録画・機密画面・顧客環境の録画も安心して処理できる。

*English: [README.en.md](./README.en.md)*

## 出力例

```markdown
## 00:05:12 — Excel — 見積書_2026Q2.xlsx（Sheet1）   ← アプリ・ファイル・位置（OCR事実＋VLM）
👁 D列の単価合計を確認しながら                        ← 注視箇所（VLM推測）
🗣️ この単価、先月と変わってますね                     ← 発話（kotoba-whisper）
単価セルを修正している                                ← 動作理解（Qwen3-VL）
- `見積書_2026Q2.xlsx - Excel`                       ← 一次情報（生OCR、常に保持）
```

## なぜ作るか

- 画面録画を見返して「何の作業をしていたか」を手で書き起こすのは重い。
- OCRだけでは「何をしているか」が、音声だけでは「画面で何が起きたか」が分からない。
- 市場調査の結論: 録画済みMP4を「目（OCR+VLM）と耳（ASR）」の両方からローカルで理解するツールは存在しない（docs/research/round4参照）。

## 技術選定サマリ

3AI（Claude / Grok / Codex）調査×5ラウンドで確定したスタック。根拠は [BEST_PRACTICES.md](./BEST_PRACTICES.md)、生データは [docs/research/](./docs/research/)。

| 層 | 採用 | 補足 |
|----|------|------|
| **フレーム抽出** | ffmpeg（fps均等サンプリング＋シーン変化検出、長辺1024px縮小） | 視覚トークン超過の実測に基づく |
| **OCR層** | PaddleOCR PP-OCRv6 tiny/small/medium（日本語、CPU） | 画面差分によるスキップ＋会議モードでキーフレーム限定 |
| **VLM層** | Qwen3-VL:8B（Ollama、タイムアウト＋フォールバック付き） | 構造化5フィールド出力（app/resource/location/focus/action） |
| **ASR層** | kotoba-whisper v2.0（Mac: MLX / Windows・Linux: faster-whisper、自動選択） | 日本語特化。音声トラックなしは自動スキップ |
| **VLMゲート** | OCRトークンJaccard（meetingモード） | 話者切替のVLM無駄撃ちを抑制（3者設計協議で採択、Issue #13） |
| **出力** | JSONL（機械用・一次情報保持）＋Markdown（人間用） | |
| **活用層（将来）** | Ruri v3 + Faiss / Qwen3-VL-Embedding | 意味検索・分類・RAG（Issue #5） |

## パイプライン

```
[video.mp4]
   ├─ 音声 ──► kotoba-whisper(MLX) ─────────────► 発話セグメント
   └─ 映像 ──► ffmpeg（2秒毎＋シーン変化＝キーフレーム、長辺1024px）
                 │
                 ├─► PaddleOCR … 画面差分でスキップ（会議モード: キーフレームのみ）
                 │      │
                 │      ├─► ScreenContext抽出（ファイル名・URL・ページ位置＝事実）
                 │      └─► VLMゲート（meetingモード: 文字が変わった時だけVLMへ）
                 │              │
                 └──────────────┴─► Qwen3-VL（＋OCR/発話をプロンプト同梱）
                                        │
                        Merge: 時刻 | app | resource | 位置 | 👁 | 🗣️ | 動作 | 生OCR
                                        │
                          worklog.jsonl / worklog.md（動画ごと）
```

## 使い方

```bash
# セットアップ（初回のみ）
uv venv -p 3.12 .venv
uv pip install -e . && uv pip install -e ".[dev]" && uv pip install -e ".[asr]"
ollama pull qwen3-vl:8b

# 実行（単一動画）
.venv/bin/python -m screen_activity_logger.cli 録画.mp4 -o out/
# → out/worklog.md（人間用）と out/worklog.jsonl（機械用）が生成される

# 会議録画なら
.venv/bin/python -m screen_activity_logger.cli 会議.mp4 --mode meeting -o out/

# オプション
#   --mode meeting            会議向け: OCRキーフレーム限定＋VLMゲート有効
#   --fps 0.5                 サンプリング頻度（既定0.5=2秒に1枚）
#   --scene-threshold 0.08    シーン変化の閾値
#   --model qwen3-vl:8b       OllamaのVLMモデル
#   --ocr-tier small          OCRモデル規模 tiny/small/medium（既定small）
#   --diff-threshold 0.02     画面差分によるOCRスキップの閾値
#   --asr-backend auto        ASRバックエンド auto/mlx/faster（auto: Apple Silicon→mlx、それ以外→faster）
#   --asr-model <repo>        音声認識モデル（未指定時はバックエンド既定:
#                             mlx=kaiinui/kotoba-whisper-v2.0-mlx / faster=kotoba-tech/kotoba-whisper-v2.0-faster）
#   --no-asr                  音声認識を無効化（音声トラックなしは自動スキップ）
#   --vlm-skip-threshold 0.85 VLMゲートのJaccard閾値（meeting時）
#   --vlm-min-gap 10          VLM呼び出しの最小間隔秒（debounce）
#   --vlm-max-gap 120         VLM強制実行の最大間隔秒（安全弁）
```

### モードの使い分け

| | screencast（既定） | meeting |
|---|---|---|
| 想定 | 作業手順・デモ録画 | 会議録画（Meet/Zoom等） |
| OCR | 全フレーム（差分スキップあり） | キーフレームのみ |
| VLM | 全キーフレーム（**ステップを落とさない**） | 文字が変わった時だけ（話者切替を無視） |

複数動画は**バッチ2フェーズ処理**（全動画ASR→各動画OCR/VLM。ASRモデルのロードが1回で済む）:
```bash
.venv/bin/python -m screen_activity_logger.cli 会議1.mp4 会議2.mp4 --mode meeting -o out/
# → out/会議1/worklog.md, out/会議2/worklog.md …
# 注意: N本を別プロセスで並列起動するとASRモデル(約3GB)×Nがメモリを食い潰す（実測済み）。
#       複数本はこのバッチ機能を使うこと。
```

Ollama推奨設定（バッチパイプライン向け、コミュニティ実測に基づく）:
```bash
export OLLAMA_NUM_PARALLEL=1      # バッチ処理では1が単発レイテンシ最速
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0  # KVメモリ約半減（品質はq8が無難）
```

実測性能（M4 Air）:
- 画面録画20秒: 約69秒（差分OCRスキップ＋small tier。改善前278秒。ASR追加コストほぼゼロ）
- 実会議5分クリップ×10本バッチ: 10/10完走（10並列×各自ロードは0/10で破綻＝バッチ2フェーズが必須）

```bash
# テスト
.venv/bin/pytest -m "not slow"   # 高速テストのみ
.venv/bin/pytest --cov           # 全テスト＋カバレッジ（OCR/ASR/e2e含む）
```


### Claude Code から使う（skill）

```bash
ln -s "$(pwd)/skills/screen-activity-logger" ~/.claude/skills/screen-activity-logger
```

以降、Claude Code で「この録画を作業ログにして」と頼むと前提チェック〜実行〜結果要約まで行う。

### Windowsでのセットアップ

```powershell
# ffmpeg（wingetまたはchoco）
winget install Gyan.FFmpeg
# Ollama Windows版: https://ollama.com/download/windows からインストール
ollama pull qwen3-vl:8b

uv venv -p 3.12 .venv
uv pip install -e . ; uv pip install -e ".[dev]" ; uv pip install -e ".[asr-faster]"
# 実行（--asr-backend autoが自動でfasterに解決される）
uv run python -m screen_activity_logger.cli 録画.mp4 -o out/
```

- ASRは faster-whisper（CTranslate2）が **CUDA有無を自動判別**。NVIDIA GPU利用時のみ `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` を追加（CPUなら不要、int8で実用速度）
- PaddleOCR・Ollama・ffmpeg・出力層はOS共通

### 「Macと同じ結果」の定義（Issue #16）

1. **構造的同一（保証）**: domain/application層にOS・バックエンド分岐は1バイトもない。差し替わるのはASRアダプタ1個のみで、セグメント正規化は共通純粋関数（`asr_segments.build_segment`）に一元化 → **同一のセグメント列が入れば下流の出力はビット同一**
2. **意味的同等（実測）**: mlxとfasterは同一モデル（kotoba-whisper v2.0）の変換版だが、トランスクリプトは完全一致しない。差はWhisper自体の実行毎ゆらぎと同オーダー（Issue #16の実測記録参照）
3. **既知の差分**: faster側は `condition_on_previous_text=False`（kotoba公式推奨・幻覚連鎖の抑制）、`chunk_length=15`、beam_size=5。いずれも品質中立〜改善方向

## 開発状況（Issue駆動）

進行状況は [GitHub Issues](https://github.com/iloli-source/screen-activity-logger/issues) が正。
- ✅ 完了: 最小パイプライン(#1)、ASR層(#6)、バッチ2フェーズ＋会議モード(#7)、構造化コンテキスト抽出(#12)
- 🔄 進行中: VLMゲート実測検証(#13)
- 📥 キュー: スクショ付き手順書・滞留時間・実時刻復元(#11)、映像ベース話者特定(#10)
- 🎯 意思決定: ポジショニング・配布戦略(#9)

設計原則（Issue #9）: **コア3軸（正確・速い・安全）を強化するものだけ採用**／タダの付加価値（計算済みデータの再利用）を先に取り尽くす／高価な付加価値はモード化。

## 動作要件

**開発環境（実測 2026-07-11）**: MacBook Air / Apple M4 / 24GBユニファイドメモリ / macOS 26.5.2
**Windows/Linux** も対応（ASRはfaster-whisperに自動切替、Issue #16。BEST_PRACTICES.md §0.2 参照）

- Python 3.12（venvは `uv venv -p 3.12`）
- ffmpeg（フレーム抽出・音声抽出・ffprobe）
- Ollama 0.30以降（qwen3-vl:8b）
- 主要依存: `paddleocr`+`paddlepaddle`（CPU）, `ollama`, `pillow`, （ASR時）`mlx-whisper` または `faster-whisper`

## プライバシー

画面録画にはパスワードや個人情報が含まれ得る。本ツールは完全ローカルで動作するが、実録画（`*.mp4`）や生成ログはリポジトリに含めない（`.gitignore` で除外済み）。保存先の暗号化も検討すること。

## ライセンス

[Apache-2.0](./LICENSE)（Issue #9で決定）。利用する各モデルのライセンスは個別に確認すること（Qwen系 Apache-2.0、Sarashina Vision MIT、Ruri v3 Apache-2.0）。
