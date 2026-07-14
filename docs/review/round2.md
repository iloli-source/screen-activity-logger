# 4AIダメ出しレビュー 第2周（2026-07-14）

レビュアー: grok／claude（第1周と同じ2者。codex=利用枠上限、gemini=CLI未認証のため不参加継続）。
前提として第1周の修正一覧を提示し、「残る問題・修正が生んだ新しい問題」を要求。

## 指摘→判定→対応

| # | 出典 | 重要度 | 指摘 | 判定 | 対応 |
|---|---|---|---|---|---|
| 1 | grok | CRITICAL | ASR導入チェックが無音スキップより先に走る順序バグ（全無音でもASR必須） | ✅真（R1修正の副作用） | 無音判定→必要時のみensureに並べ替え |
| 2 | grok | CRITICAL | R1のOCRフォールバックが差分スキップと結合し空OCRが後続へ伝播 | ✅真（R1修正の副作用） | フォールバックをuse_case層へ移動しNone区別・失敗を キャッシュに載せない＋回帰テスト |
| 3 | grok | HIGH | フレーム0枚で無言の空worklog（ASR結果消失） | ✅真 | 明示エラー化（既存テストも新仕様に更新） |
| 4 | grok | HIGH | ollama.list()にtimeoutなし（チェック自体がハング） | ✅真 | Client(timeout=5)化 |
| 5 | grok | HIGH | バッチのstem衝突で出力上書き | ✅真 | 事前検出してValueError |
| 6 | grok | HIGH | subprocessのstderrが失敗時に埋もれる | ✅真 | run_captured共通ヘルパー（stderr末尾を例外へ） |
| 7 | grok | HIGH | バッチ1本の失敗で全体が死ぬ | ✅真 | Phase A/Bとも動画単位で隔離＋テスト3件 |
| 8 | grok | HIGH | has_audio_streamが破損動画で即死 | ✅真 | 失敗はFalse（ASRスキップ扱い）に |
| 9 | grok | HIGH | 要旨にthink=False未指定（describerと非対称） | ✅真 | think=False付与＋テスト |
| 10 | grok/claude | HIGH/MEDIUM | --vlm-timeoutがsummarizerに未配線 | ✅真（R1半修正） | create_summarizerにtimeout引数＋CLI配線 |
| 11 | claude | HIGH | collapseのlocation None/実値の揺れで畳み込み抑止 | ✅真 | ※判定はR3へ持ち越し（下記保留参照） |
| 12 | grok | MEDIUM | ":"ヒューリスティックがHF形式モデルを潰す | ✅真 | 「:あり かつ /なし」のみ読み替え |
| 13 | grok/claude | MEDIUM | cpp avg_logprobのp=0/p<0ガード | ✅真 | p>0ガード追加 |
| 14 | claude | MEDIUM | 要旨content=Noneで"None"が出力 | ✅真 | Noneガード＋dict/attr両対応（describerと同型） |
| 15 | claude | MEDIUM | 要旨が呼び出し毎にClient生成 | ✅真 | インスタンスキャッシュ |
| 16 | grok | MEDIUM | frame_comparatorの画像破損で全体停止 | ✅真 | 失敗は非類似（再OCR）に倒す |
| 17 | grok | MEDIUM | doc_id衝突（同一親の複数jsonl） | ✅真 | doc_idにファイル名を含める |
| 18 | grok | MEDIUM | CLI数値検証不足（閾値範囲・gap順序等） | ✅真 | 検証追加 |
| 19 | grok | MEDIUM | mlxにcondition_on_previous_textなし | ✅真 | 付与（非推奨経路だが対称性） |
| 20 | grok | MEDIUM | numpy_indexのvectors/documents不整合検出なし | ✅真 | 件数チェック追加 |
| 21 | grok/claude | LOW | help/コメント/型注釈の古さ・search_cliの生traceback | ✅真 | まとめて修正 |

## 保留・棄却（理由つき）

| 出典 | 指摘 | 判定 |
|---|---|---|
| grok | _attach_speechが開始点判定（VLM窓と非対称） | **棄却**。worklogの発話紐付けは窓分割（各発話がちょうど1エントリに属する）の意図的設計。重複判定にすると同一発話が複数エントリに重複掲載される。VLM窓は「文脈提供」目的で重複が無害という別問題 |
| claude #11 | collapseのlocation None揺れ | **一部保留**。R2ではNoneを「不明=比較スキップ」にする案を検討したが、Noneが本当に「位置が変わった」ケースを巻き込む逆リスクがある。実データでの揺れ頻度を見てR3で判定 |
| grok/claude | cpp avg_logprob閾値の未キャリブレーション | 保留。スケール族は同系（トークン対数確率平均）で、実会議スモークでは正常発話が全通過を確認済み。実データでの分布採取を再訪条件として記録 |
| grok | no_speech_prob単独では棄却しない | 棄却（意図的）。no_speech_probは窓単位の共有値で単独棄却は正常発話を巻き込む（Issue #14の設計根拠） |
| grok | duration 0で終端非表示 | **棄却（意図的設計）**。duration 0は「観測が過去のみ」の丸め（Issue #18）で0秒表示はノイズ。コードコメントに設計理由を追記 |
| grok | VideoTimestamp秒未満切り捨て・exit 0（再掲） | 保留継続（R1と同判断） |
| claude | SearchWorklogs.executeが毎回load | 保留。CLI単発利用が主用途。API化時に再訪 |

## 結果
- 指摘26件（重複統合後）→ **修正21件 / 保留・棄却5件（理由つき）**
- 「R1修正が生んだ問題」枠で4件検出（順序バグ・キャッシュ汚染・timeout未配線・think非対称）→ 全修正
- コミット4件、全テストGREEN
