# screen-activity-logger

PC画面を録画した動画（MP4）を入力に、**完全ローカル**で **3つのコンテキスト**──①画面の文字（OCR）②何をしているかの日本語説明（VLM）③発話（ASR）──を抽出・統合し、**構造化されたタイムスタンプ付き日本語作業ログ**を生成するツール。

> クラウドAPIに一切送らない。会議録画・機密画面・顧客環境の録画も安心して処理できる。

*English: [README.en.md](./README.en.md)*

## 出力例

```markdown
## 00:05:12〜00:12:30（7分18秒） — Excel — 見積書_2026Q2.xlsx（Sheet1）   ← 滞留時間つき見出し
👁 D列の単価合計を確認しながら                        ← 注視箇所（VLM推測）
🗣️ この単価、先月と変わってますね                     ← 発話（kotoba-whisper）
単価セルを修正している                                ← 動作理解（Qwen3-VL）
- `見積書_2026Q2.xlsx - Excel`                       ← 一次情報（生OCR、常に保持）

## アプリ別滞在時間                                    ← 動画末尾に自動集計（稼働報告の下資料）
| Excel | 32分10秒 |
```

## なぜ作るか

- 画面録画を見返して「何の作業をしていたか」を手で書き起こすのは重い。
- OCRだけでは「何をしているか」が、音声だけでは「画面で何が起きたか」が分からない。
- 市場調査の結論: 録画済みMP4を「目（OCR+VLM）と耳（ASR）」の両方からローカルで理解するツールは存在しない（docs/research/round4参照）。

## 技術選定サマリ

3AI（Claude / Grok / Codex）調査×6ラウンドで確定したスタック。根拠は [BEST_PRACTICES.md](./BEST_PRACTICES.md)、生データは [docs/research/](./docs/research/)。

| 層 | 採用 | 補足 |
|----|------|------|
| **フレーム抽出** | ffmpeg（fps均等サンプリング＋シーン変化検出、長辺1024px縮小） | 視覚トークン超過の実測に基づく |
| **OCR層** | PaddleOCR PP-OCRv6 tiny/small/medium（日本語、CPU） | 画面差分によるスキップ＋会議モードでキーフレーム限定 |
| **VLM層** | Qwen3-VL 8B（Ollama / vllm-mlx。**Apple Siliconはvllm-mlx推奨・実測約40倍** #8） | 構造化5フィールド出力・タイムアウト＋リトライ＋テレメトリ・幻覚resource品質ゲート（#15/#17） |
| **ASR層** | kotoba-whisper v2.0（Mac: whisper.cpp Metal / Windows・Linux: faster-whisper、自動選択） | 日本語特化・無音幻覚フィルタ（#14）・相槌のみの行をカット（#25、--keep-fillersで無効化）。2時間実測でmlx-whisperは品質崩壊のため非推奨化（#22）。音声なしは自動スキップ |
| **VLMゲート** | OCRトークンJaccard（meetingモード） | 話者切替のVLM無駄撃ちを抑制（3者設計協議で採択、Issue #13） |
| **出力** | JSONL（機械用・一次情報保持）＋Markdown（人間用） | |
| **活用層** | Ruri v3 + numpy索引（`sal-search`実装済み） | 意味検索。分類・RAGは将来 |

## パイプライン

```
[video.mp4]
   ├─ 音声 ──► kotoba-whisper(whisper.cpp) ──────► 発話セグメント
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
#   --asr-backend auto        ASRバックエンド auto/cpp/faster/mlx
#                             （auto: Apple Silicon→cpp、whisper.cpp未導入時とそれ以外のOS→faster。
#                             mlxは長時間入力で品質崩壊のため非推奨・明示指定のみ、Issue #22）
#   --asr-model <repo|path>   音声認識モデル（未指定時はバックエンド既定:
#                             cpp=~/.cache/screen-activity-logger/kotoba-whisper-v2.0-q5_0.bin /
#                             faster=kotoba-tech/kotoba-whisper-v2.0-faster）
#   --no-asr                  音声認識を無効化（音声トラックなしは自動スキップ）
#   --vlm-skip-threshold 0.85 VLMゲートのJaccard閾値（meeting時）
#   --vlm-min-gap 10          VLM呼び出しの最小間隔秒（debounce）
#   --vlm-max-gap 120         VLM強制実行の最大間隔秒（安全弁）
#   --vlm-timeout 300         VLM試行毎タイムアウト秒（タイムアウト時は自動で1回リトライ）
#   --speech-summary          発話の1文要旨（🧭）を付与（VLMと同一モデル、処理+1割弱、既定OFF）
#   --asr-no-speech-prob 0.6  ASR幻覚フィルタ閾値（no_speech_prob）
#   --asr-avg-logprob -1.0    ASR幻覚フィルタ閾値（avg_logprob）
#   --keep-fillers            相槌のみの発話行（「はい」「えーと」等）を残す（既定はカット）
#   --no-asr-filter           ASR幻覚フィルタを無効化（デバッグ用。フィラーカットも無効）
```

### モードの使い分け

| | screencast（既定） | meeting |
|---|---|---|
| 想定 | 作業手順・デモ録画 | 会議録画（Meet/Zoom等） |
| OCR | 全フレーム（差分スキップあり） | キーフレームのみ |
| VLM | 全キーフレーム（**ステップを落とさない**） | 文字が変わった時だけ（話者切替を無視） |

複数動画は**バッチ2フェーズ処理**（全動画ASR→各動画OCR/VLM。faster/mlxはモデルロードが1回で済む。whisper.cppは動画毎にプロセス起動だがロードは軽量。無音動画は動画単位で自動スキップ）:
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
- 実会議5分クリップ: **約63秒**（vllm-mlxバックエンド＝実時間の2割。Ollamaでは15分〜80分超）
- **2時間録画: 31分で完走・後半劣化なし**（whisper.cpp ASR＋vllm-mlx、Issue #22で実測検証）
- 画面録画20秒: 約69秒（Ollama利用時。差分OCRスキップ＋small tier。改善前278秒）
- 実会議5分クリップ×10本バッチ: 10/10完走（10並列×各自ロードは0/10で破綻＝バッチ2フェーズが必須）
- VLMタイムアウトのリトライ救済: 劣化環境の実測でタイムアウト4回中3回を救済、説明消失が5件→1件（Issue #15）

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



### ASRセットアップ（Mac推奨: whisper.cpp）

2時間級の長時間録画の実測（Issue #22）で、ASR3実装の適性が確定した:

| バックエンド | 内容の健全性 | 速度（10分音声） | 位置づけ |
|---|---|---|---|
| **cpp**（whisper.cpp Metal） | ✅ 線形 | **39秒** | **Mac既定**（auto解決） |
| faster（CTranslate2 CPU） | ✅ 線形 | 319秒 | Windows/Linux既定・Macフォールバック |
| mlx（mlx-whisper） | ❌ 長尺で内容崩壊（10分で136字） | — | **非推奨**・明示指定のみ |

```bash
# Mac（初回のみ）: whisper.cppバイナリ導入
brew install whisper-cpp
# kotoba-whisper v2.0のGGUF（q5_0）を既定パスに配置
#   ~/.cache/screen-activity-logger/kotoba-whisper-v2.0-q5_0.bin
#   （whisper.cpp付属のconvert-h5-to-ggml.py＋whisper-quantizeで
#    kotoba-tech/kotoba-whisper-v2.0 から変換、または --asr-model <パス> で任意のGGUFを指定）
```

whisper.cpp未導入でも動く（autoがfaster-whisperへフォールバック。遅いが正しい）。

### 発話要旨（オプトイン）

`--speech-summary` で、発話3行以上のエントリに日本語1文の要旨（🧭）を付与する。
VLMと同一バックエンド・同一モデルへのテキストのみ入力で生成するため**追加メモリゼロ**。
実測: 品質10/10・約2秒/エントリ（5分クリップで全体+7%）。詳細は
docs/research/issue3_quality_improvement.md のQ4。

### 話者特定（実験的、オプトイン）

`--mode meeting --speaker-attribution` で、話者ビューの名前ラベル×シーン変化×ASR時刻の突き合わせにより `🗣️ 秋山: …` の実名付き発話を試みる（追加モデルゼロ）。

**実測済みの限界（Issue #10）**: 話者ビューに追従する録画でのみ有効（precision 62-84%）。ギャラリービューやタイル固定のボット録画では帰属をほぼ棄却する（安全側）が、残る帰属も信頼できないため**既定OFF**。音声ベース（pyannote）ハイブリッドは需要実証・GPU環境を再オープン条件として見送り中（Issue #20参照）。


### VLMバックエンド（vllm-mlx推奨・実測約40倍）

Apple Siliconでは vllm-mlx バックエンドが Ollama比 **約40倍** 高速（実測11秒/フレーム vs 420-600秒、Issue #8）。

```bash
# 導入（初回のみ）
pip install vllm-mlx   # 専用venv推奨
# サーバー起動（利用時）
vllm-mlx serve mlx-community/Qwen3-VL-8B-Instruct-4bit --port 8991
# 実行
.venv/bin/screen-activity-logger 会議.mp4 --mode meeting --vlm-backend vllm-mlx -o out/
```

実測（M4 Air 24GB）: 5分会議クリップが**約63秒**で完走（Ollamaでは15分〜80分超）。品質は同等（同一プロンプト・同一パース）。

### VLMテレメトリの読み方（Issue #15）

実行ログに全VLM呼び出しの所要時間が出る:

```
VLM推論 t=00:00:12 attempt=1 8.2s            ← 正常
VLM推論 t=00:01:46 attempt=2 121.9s SLOW     ← タイムアウト後のリトライで救済
VLM呼び出し失敗 t=... attempt=2/2 300.0s: ReadTimeout  ← 2回失敗＝フォールバック
```

- `SLOW`（60秒超）が続く場合はマシンが熱制限・メモリスラッシング状態。他の重い処理を止めるか `--vlm-timeout 450` で延長
- `attempt=2` が速く成功する＝一時的ハング（リトライが救済）／`attempt=2` も遅い＝持続的低速（リトライでは救えない）

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
2. **意味的同等（実測）**: cpp/fasterは同一モデル（kotoba-whisper v2.0）の変換版だが、トランスクリプトは完全一致しない。差はWhisper自体の実行毎ゆらぎと同オーダー（Issue #16/#22の実測記録参照）
3. **既知の差分**: faster側は `condition_on_previous_text=False`（kotoba公式推奨・幻覚連鎖の抑制）、`chunk_length=15`、beam_size=5。いずれも品質中立〜改善方向

## 開発状況（Issue駆動）

進行状況は [GitHub Issues](https://github.com/iloli-source/screen-activity-logger/issues) が正。
- ✅ #1〜#23 すべてクローズ済み（2026-07-14時点）。意味検索(#5)・vllm-mlx 40倍高速化(#8)・長時間録画対応(#22)・発話要旨(#23)を含む

設計原則（Issue #9）: **コア3軸（正確・速い・安全）を強化するものだけ採用**／タダの付加価値（計算済みデータの再利用）を先に取り尽くす／高価な付加価値はモード化。

## 動作要件

**開発環境（実測 2026-07-11）**: MacBook Air / Apple M4 / 24GBユニファイドメモリ / macOS 26.5.2
**Windows/Linux** も対応（ASRはfaster-whisperに自動切替、Issue #16。BEST_PRACTICES.md §0.2 参照）

- Python 3.12（venvは `uv venv -p 3.12`）
- ffmpeg（フレーム抽出・音声抽出・ffprobe）
- Ollama 0.30以降（qwen3-vl:8b）
- 主要依存: `paddleocr`+`paddlepaddle`（CPU）, `ollama`, `httpx`, `pillow`, （ASR時）whisper.cpp（brew）または `faster-whisper`

## プライバシー

**ローカル成果物の取り扱い**: フレームPNGは一時領域（自動削除）、worklog.jsonl の
`ocr`/`speech` は一次情報を無加工で保持する（検索・監査価値のため）。機密画面を含む
録画の出力は通常のファイルと同様にアクセス制御下で管理すること。

画面録画にはパスワードや個人情報が含まれ得る。本ツールは完全ローカルで動作するが、実録画（`*.mp4`）や生成ログはリポジトリに含めない（`.gitignore` で除外済み）。保存先の暗号化も検討すること。

## ライセンス

[Apache-2.0](./LICENSE)（Issue #9で決定）。利用する各モデルのライセンスは個別に確認すること（Qwen系 Apache-2.0、kotoba-whisper Apache-2.0、Ruri v3 Apache-2.0）。
