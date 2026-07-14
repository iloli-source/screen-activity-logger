# 4AIダメ出しレビュー 第1周（2026-07-14）

レビュアー: grok（プロンプト同梱方式）／claude（code-reviewerエージェント、リポジトリ自走読取）。
codexは利用枠上限、geminiはCLI認証未設定のため今周は不参加（記録として明記）。
方針: 全指摘を実コードで裏取りし、誤指摘は根拠つきで棄却。CRITICAL/HIGHは必修正。

## 指摘→判定→対応の対応表

| # | 出典 | 重要度 | 指摘 | 判定 | 対応 |
|---|---|---|---|---|---|
| 1 | grok | CRITICAL | バッチでworkdir共有によりフレーム残渣が次動画を汚染 | ✅真 | 抽出前にframe_*.pngを掃除＋回帰テスト |
| 2 | grok/claude | CRITICAL/HIGH | バッチ中1本無音で全動画のASR無効化（all判定） | ✅真 | 動画単位スキップ（SilenceAwareTranscriber）＋any判定化 |
| 3 | grok/claude | CRITICAL/MEDIUM | `.[asr]`がMacで非推奨mlxを導入しauto解決と矛盾 | ✅真 | `.[asr]`=faster-whisper統一（mlxは`.[asr-mlx]`で明示） |
| 4 | claude | CRITICAL | e2eテストのJSONLスキーマ期待値が3フィールド古く常時FAIL | ✅真 | t_end/duration_seconds/summaryを期待値に追加 |
| 5 | grok/claude | HIGH | httpxが直接依存に未宣言（推移的依存頼み） | ✅真 | dependenciesに追加 |
| 6 | grok | HIGH | sal-searchのクエリ埋め込みモデル不一致を検出しない | ✅真 | SearchWorklogsにmodel_name＋load(expected_model)配線、query --model追加 |
| 7 | grok | HIGH | fps=0でZeroDivisionError・フレーム0枚で空min() | ✅真 | __post_init__検証＋空ガード＋CLI検証 |
| 8 | grok/claude | HIGH | subprocess全呼び出しにtimeoutなし（ハングで永久停止） | ✅真 | ffprobe60s/ffmpeg3600s/whisper-cli7200sの上限を設定 |
| 9 | claude | HIGH | ffmpeg不在時に素のFileNotFoundError | ✅真 | 起動前のwhichチェックで親切なエラー |
| 10 | claude | HIGH | OCR失敗が無防備でパイプライン全体をクラッシュ | ✅真 | フレーム単位の空フォールバック（VLMと同方針） |
| 11 | grok | HIGH | whisper.cpp経路で幻覚フィルタの確率防衛線が全滅 | ✅真 | -ojfのトークン確率からavg_logprob算出＋logprob単独シグナル対応 |
| 12 | grok | HIGH | バッチでtranscriber二重生成 | ✅真 | バッチ時はuse_case側をNoneに |
| 13 | grok | HIGH | バッチ「モデルロード1回」がcpp/mlxで虚偽 | ✅真（doc） | READMEをバックエンド毎の真実に修正 |
| 14 | grok | MEDIUM | _collapse_consecutiveがlocation変化（ページ遷移）を消す | ✅真 | 畳み込みキーにlocation追加（focusは推測値のため除外） |
| 15 | grok/claude | MEDIUM | _speech_nearが開始点のみ判定＋毎フレーム再ソート | ✅真 | 区間重複判定＋呼び出し元で1回ソート |
| 16 | grok | MEDIUM | Ollama要旨にtimeoutなし | ✅真 | Client(timeout=60)化＋テスト |
| 17 | grok | MEDIUM | ollamaの事前可用性チェックが空実装 | ✅真 | ollama.list()による到達性チェック追加 |
| 18 | grok/claude | MEDIUM | README不整合（活用層「将来」・1回ロード・無音スキップ等） | ✅真 | 該当箇所を修正 |
| 19 | claude | MEDIUM | CIカバレッジ下限70%がルール（80%）未満 | ✅真 | 実測98% → 下限80%に引き上げ |
| 20 | grok | LOW | build_use_caseの既定asr_backendが非推奨mlx | ✅真 | 既定faster化＋テスト更新 |
| 21 | claude | MEDIUM/LOW | Protocol load署名不一致・裸dict/tuple型注釈 | ✅真 | ports署名整合＋型注釈追加 |

## 保留（意図的に修正しない、理由つき）

| 出典 | 指摘 | 判定 |
|---|---|---|
| grok | VideoTimestamp表示が秒未満切り捨て | 保留。表示仕様として許容（JSONLのduration_secondsはfloat保持）。照合ニーズが出たら再訪 |
| claude | フレーム時刻が実PTSでなく index/fps 合成値 | 保留。CFR前提の均等サンプリングでは同義。VFR録画の実害報告があれば再訪 |
| grok | 部分失敗でも終了コード0 | 保留。バッチ継続を優先する設計。失敗集計のサマリー出力は将来課題 |
| grok | 話者名抽出の正規表現が狭い | 仕様。precision優先・既定OFFの実験機能として文書化済み（#10） |
| grok | requires-python <3.13 上限 | 保留。paddlepaddleの対応状況に依存。動作確認後に緩和 |
| grok | Markdownのバッククォート衝突・doc_id衝突 | 記録のみ（LOW、実害未観測） |
| grok | 機密のローカル成果物ガードが薄い | READMEプライバシー節に取り扱い注記を追加（暗号化等はスコープ外と判断） |

## 結果
- 指摘28件（重複統合後）→ **修正21件 / 保留7件（全て理由つき） / 誤指摘0件**（両者とも正確だった）
- コミット12件、全テストGREEN（カバレッジ98%）
