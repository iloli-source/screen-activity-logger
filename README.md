# screen-activity-logger

PC画面を録画した動画（MP4）を入力に、**完全ローカル**で「画面の文字（OCR）」と「今この画面で何をしているか（VLM）」を抽出し、**タイムスタンプ付きの日本語作業ログ**を生成するツール。

> クラウドAPIに送らず、手元のGPU（VRAM 8〜12GB想定）だけで完結させることを目標にする。

## なぜ作るか

- 画面録画を見返して「何の作業をしていたか」を手で書き起こすのは重い。
- 単純なOCRでは「文字」は拾えても「何をしているか（例: VS Codeでpytestの失敗を確認中）」は分からない。
- そこで **OCR（文字の確定抽出）＋ VLM（作業状況の日本語説明）** を二層で組み合わせ、自動で作業ログ化する。

## 技術選定サマリ

3AI（Claude / Grok / Codex）＋GitHub直接調査で結論が一致した推奨スタック。根拠と比較表は [BEST_PRACTICES.md](./BEST_PRACTICES.md)、生の調査結果は [docs/research/](./docs/research/) を参照。

| 層 | 採用 | 理由 |
|----|------|------|
| **フレーム抽出/間引き** | ffmpeg + PySceneDetect + OCR差分 | 全フレームVLMは重い。画面変化時のみVLMを呼びVRAMを節約 |
| **OCR層** | PaddleOCR (PP-OCRv5/v6, 日本語) | CJK精度最強・CPU可・Apache-2.0 |
| **VLM層** | Qwen3-VL-4B (8GB) / 8B-Q4 (12GB) | 2026本命。GUI/OCR/長尺動画/timestamp公式対応、日本語強、Apache-2.0 |
| **ランタイム** | Transformers + AWQ/bitsandbytes（or Ollama） | Qwen3-VLはTransformersが堅い |
| **出力** | JSONL → 日本語Markdown | timestamp / OCR / VLM説明 を蓄積 |
| **活用層（将来）** | Ruri v3 + Faiss | 作業ログの意味検索・分類・RAG（日本語embedding） |

第2候補: Qwen2.5-VL-7B AWQ、MiniCPM-V 4.5（省メモリ）、日本語特化に Sarashina2.2-Vision-3B（MIT）。

## パイプライン

```
[screen.mp4]
   │  ffmpeg fps=1 + scene検出 + OCRテキスト差分
   ▼
 キーフレーム ──► PaddleOCR(japan)  … 全キーフレームに密適用
   │                    │
   │                    ▼
 画面変化フレーム ──► Qwen3-VL       … 変化時のみ疎適用（「何をしているか」を日本語で）
   │                    │
   ▼                    ▼
        Merge: timestamp | OCR text | 作業説明
                     │
                     ▼
          worklog.jsonl → worklog.md
```

## 使い方（Phase 1）

```bash
# セットアップ（初回のみ）
uv venv -p 3.12 .venv
uv pip install -e . && uv pip install -e ".[dev]"
ollama pull qwen3-vl:8b

# 実行
.venv/bin/python -m screen_activity_logger.cli 録画.mp4 -o out/
# → out/worklog.md（人間用）と out/worklog.jsonl（機械用）が生成される

# オプション
#   --fps 0.5              サンプリング頻度（既定0.5=2秒に1枚）
#   --scene-threshold 0.08 シーン変化の閾値
#   --model qwen3-vl:8b    OllamaのVLMモデル
```

```bash
# テスト
.venv/bin/pytest -m "not slow"   # 高速テストのみ
.venv/bin/pytest --cov           # 全テスト＋カバレッジ（OCR/e2e含む）
```

## 開発ロードマップ

- **Phase 0（済）**: 技術調査・選定（本リポジトリの `docs/` と `BEST_PRACTICES.md`）
- **Phase 1**: 最小パイプライン `src/`（`extract_frames.py` → `ocr.py` → `describe.py` → `merge.py`）。短い動画1本で end-to-end 動作
- **Phase 2**: 差分間引きの高度化（カーソルマスク、ROI限定、OCRテキスト差分トリガ）、VRAM実測とチューニング
- **Phase 3**: 日本語作業ログの品質改善（プロンプト、Sarashina2.2による日本語第2パス）
- **Phase 4（活用層）**: 作業ログを **Ruri v3 + Faiss** でインデックス化し、意味検索・分類・RAGを追加

## 動作要件

**ターゲット環境（実測 2026-07-11）**: MacBook Air / Apple M4 / 24GBユニファイドメモリ / macOS 26.5.2

- Python 3.10+（導入済み: 3.14.6）
- ffmpeg（導入済み: 8.1.1）
- Ollama 0.30以降（導入済み: 0.30.10）または mlx-vlm / llama.cpp(Metal)
- 主要依存（Phase1想定）: `paddleocr`, `scenedetect[opencv]`, `ollama`(Pythonクライアント)
- ※ Apple SiliconのためCUDA系（AWQ/bitsandbytes/paddlepaddle-gpu）は使用しない。NVIDIA GPU機で動かす場合は BEST_PRACTICES.md §4 のCUDA構成を参照

## プライバシー

画面録画にはパスワードや個人情報が含まれ得る。本ツールは完全ローカルで動作するが、実録画（`*.mp4`）や生成ログはリポジトリに含めない（`.gitignore` で除外済み）。保存先の暗号化も検討すること。

## ライセンス

未定（実装フェーズで決定）。利用する各モデルのライセンスは個別に確認すること（Qwen系 Apache-2.0、Sarashina Vision MIT、Ruri v3 Apache-2.0）。
