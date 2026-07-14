# 4AIダメ出しレビュー 第3周・最終収束確認（2026-07-14）

レビュアー: grok／claude（codex=利用枠上限、gemini=CLI未認証で全周不参加）。
観点を「第2周修正の副作用」「残存CRITICAL/HIGH級」に限定した収束確認。

## 判定と対応

| # | 出典 | 重要度 | 指摘 | 判定 | 対応 |
|---|---|---|---|---|---|
| 1 | grok | HIGH | cppのpreflight（ensure_backend_available）に--asr-modelが未配線。任意GGUF指定時に既定パスで誤検知 | ✅真 | preflightへ実際のモデルパスを配線 |
| 2 | grok | HIGH | バッチPhase Bの出力（mkdir/write）がtry外で、I/O失敗が残り全動画を殺す | ✅真（claudeは既存設計と判定したが、R2の隔離意図に照らして穴） | 出力もtry内に移動＋隔離テスト |
| 3 | claude | MEDIUM | R2で追加した_run_with_friendly_errorsが未配線のdead code | ✅真（自己修正の配線漏れ） | index/query両経路に配線 |

## 両者の収束判定
- **claude: 収束（APPROVE）** — 新規CRITICAL/HIGH 0件。R2修正8系統（例外隔離・キャッシュ非汚染・subprocess_runner・ensure順序・SilenceAware・空フレーム・timeout配線・型）をすべて再検証し健全と確認。テスト382件全pass・新仕様と整合
- **grok: CRITICAL収束・HIGH2件残存** → 上記#1/#2を本周内で修正済みのため、**修正後は両者の基準で収束**

## 3周の総括

| 周 | 指摘（統合後） | 修正 | 保留・棄却（理由つき） | 主な成果 |
|---|---|---|---|---|
| 第1周 | 28 | 21 | 7 | バッチ残渣汚染・ASR全滅条件・extras矛盾・e2eスキーマ等のリリースブロッカー級を排除 |
| 第2周 | 26 | 21 | 5 | R1修正の副作用4件（順序バグ・キャッシュ汚染・timeout未配線・think非対称）を検出・修正 |
| 第3周 | 3 | 3 | 0 | 残存HIGH2件＋自己配線漏れ1件を修正し収束 |
| **計** | **57** | **45** | **12** | 誤指摘0件（全指摘がコード裏取りで真または意図的設計） |

保留12件はすべて docs/review/round{1,2}.md に理由と再訪条件を記録済み
（主なもの: VideoTimestamp表示粒度・部分失敗時の終了コード・cpp logprob閾値の実データキャリブレーション・collapseのlocation None揺れ）。
