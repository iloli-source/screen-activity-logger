# Issue #8 高速化検証の採否判断記録（2026-07-13）

環境: M4 Air 24GB（ファンレス）。持続GPU負荷でスループット19%/分の熱漸減を確認済みのため、
速度比較はABBA交互測定＋ペア比の中央値（熱ドリフト相殺）で実施。

## A. ASR: whisper.cpp（kotoba-whisper-v2.0-ggml q5_0）vs mlx-whisper

導入: `brew install whisper-cpp`（ビルド不要）＋公式GGML q5_0（513MB）。導入コスト小。

### A1 速度（5分実会議クリップ×3、ABBA交互）

| クリップ | mlx-whisper | whisper.cpp q5_0 | 比（mlx/cpp） |
|---|---|---|---|
| 00 | 15.5s | 21.3s | 0.73 |
| 02 | 28.5s | 21.2s | 1.34 |
| 09 | 24.8s | 20.6s | 1.20 |
| **中央値** | | | **1.20** |

判定閾値（≥1.5xで採用候補）未満。whisper.cppは一定して~21s/クリップと安定、mlxはばらつく。

### A2 品質（転写テキスト比較）

| クリップ | mlx文字数 | cpp文字数 |
|---|---|---|
| 00 | 144 | 808 |
| 02 | 447 | 1000 |
| 09 | 271 | 1041 |

**whisper.cppはmlxの2〜4倍のテキストを正しく転写**。mlxは「chchch!」等の退化・大量取りこぼしを起こす
（Issue #16でfaster-whisper(CTranslate2)が示したのと同一傾向）。
→ **品質問題はmlx-whisperバックエンド固有**であることが3実装比較（mlx / CTranslate2 / whisper.cpp）で確定。

### 判断: 見送り（ただし重要な知見つき）
- 速度1.2倍は閾値未満。品質面の優位は**既に統合済みのfaster-whisperバックエンド（#16）と重複**
  — 第3バックエンドを足す保守コストに見合わない
- **推奨アクション**: 品質重視の用途ではApple Siliconでも `--asr-backend faster` を使う
  （README/#16に記録済みの運用で対応可能）
- 再訪条件: mlx-whisper側の品質改善 or faster-whisperが使えない環境要件の出現

## B. lightning-whisper-mlx

### 判断: 見送り（測定なし、調査ベース）
- PyPI最終リリース2024-04-02、**約2年更新停止**
- 対応モデルは組み込みリスト（tiny〜large-v3系）のみで**kotoba-whisper非対応**
  → 速度が出ても日本語品質の比較が成立しない
- 再訪条件: kotoba対応 or 後継（Lightning-SimulWhisper等）の成熟

## C. Ollama公式MLXバックエンド（O1）

### 判断: ウォッチ継続（本機対象外）
- v0.19（2026-03）preview → v0.30（2026-05）でstable化
- ただし**MLXパスは32GB以上のユニファイドメモリでのみ有効**（未満はllama.cpp Metalに自動フォールバック）
  → M4 Air 24GBは対象外。vision（qwen3-vl）のMLX対応の言及もまだない
- 再訪条件: 24GB対応 or qwen3-vlのMLX対応がリリースノートに記載されたとき

## D. VLM: vllm-mlx（Qwen3-VL-8B-Instruct-4bit）vs Ollama qwen3-vl:8b

導入: `pip install vllm-mlx`（v0.4.0、独立venv）は数分で完了。
注意: 計画時の `--enable-mllm-cache` はv0.4.0では `--enable-prefix-cache` に改名されていた。
モデルDL（約5GB）は無認証HFのレート制限で初回停滞 → snapshot_downloadで再開。

### V1 速度（固定ベンチセット: clip 00のゲート通過フレーム3枚＋実プロンプト）

計画のABBA併存測定は**Ollama側が併存下で600秒タイムアウトし不成立**（それ自体がメモリ競合耐性の証拠）。
退避案の片側ずつ測定（同一時刻・同一入力・単独常駐）に切替:

| | Ollama qwen3-vl:8b（単独） | vllm-mlx Qwen3-VL-8B-4bit（単独） |
|---|---|---|
| frame0 | 420.2s | ~10.2s |
| frame1 | 497.0s | ~11.3s |
| frame2 | >600s（タイムアウト） | ~10.8s |
| 中央値 | ≥497s | **11.3s** |

**比: 約40〜50倍**（測定ノイズ・熱ドリフト±20%を考慮しても桁が変わらない）。

### V2/V3 キャッシュ効果
- 同一フレーム再送×5: 9.1〜9.5sで一定 → **prefix cacheの効果は観測されず**（ただし素の速度が速く実害なし）
- 類似フレーム列（隣接・非同一ピクセル）: 9.4〜10.8s → **仮説どおりキャッシュヒットなし**
- → 公称28xの「同一画像マルチターン」はSALのワークロードでは効かない。**採用理由は素の推論速度**

### V4 品質（vllm-mlx出力3件）
- JSONパース: 3/3成功、5フィールド完備、日本語適切
- app_guess=Chrome（正）、action/focusはOllama出力と同等品質
- → **品質同等以上**

### 判断: 条件付き採用（判断樹: 比≥2.0x かつ 品質同等 を大幅クリア）
- **アダプタ実装Issueを起票**（OpenAI互換のSceneDescriber。ベンチはhttpx直叩きで完結済みのため実装は薄い）
- 補足: Ollamaの単独420-600sは朝の90-200sよりさらに悪化しており、llama.cpp Metalの持続劣化が確認された。
  vllm-mlxは同じマシン状態で11.3s＝**マシンではなくランタイムが問題だった**ことの決定的証拠

## 総合結論
1. **VLM: vllm-mlxを条件付き採用**（約40倍、品質同等、導入はpip数分。アダプタ実装は別Issue）
2. **ASR: whisper.cpp見送り**（1.2倍・faster-whisperと役割重複）。品質最優先ならMacでも--asr-backend faster
3. **lightning-whisper-mlx: 見送り**（2年停滞・kotoba非対応）
4. **Ollama MLX: ウォッチ**（32GB要件で本機対象外）

関連: round6調査（grok X英中・codex論文）が docs/research/round6_*.md に。
mlx-vlm（Vision Feature Caching等）はvllm-mlxの代替候補としてアダプタIssueで比較する。
