# formal/ — TLA+ モデル

保存途中の停止やスレッドの割り込みなど、「タイミング次第で起きる不具合」を小さな TLA+ モデルで再現し、TLC で検査した記録です（Issue #32）。

ここで言えるのは **「有界の TLA+ モデルをモデル検査した」** ことまでです。モデルと実装の対応は下の対応表と回帰テストで確認しており、コードそのものを形式検証したわけではありません。

各不具合は次の流れで追えます。

観測される不具合 → 破れる性質 → TLC の反例 → コード修正 → 検査を通るモデル → 回帰テスト

## 検査一覧（tlc-checks.json）

| モデル | 設定 | 期待結果 | 意味 |
|---|---|---|---|
| IndexSave.tla | IndexSaveBug.cfg | `LoadedIndexIsConsistent` 違反 | 旧実装（固定名を上書き・件数照合のみ）の再現 |
| IndexSave.tla | IndexSaveInPlaceChecksumBug.cfg | `LoadedIndexIsConsistent` 違反 | 固定名のままチェックサムだけ足す案は、旧形式の索引を更新する間は防げない |
| IndexSave.tla | IndexSaveInPlaceLosesIndexBug.cfg | `CommittedGenerationIsComplete` 違反 | 同じ案は、停止すると検出はできても索引そのものを失う |
| IndexSave.tla | IndexSaveFixed.cfg | 通過 | 修正後（世代つきファイル名＋manifest 差し替え＋チェックサム） |
| IndexSave.tla | IndexSaveFixedLegacy.cfg | 通過 | 修正後の実装で旧形式の索引を更新する場合 |
| ModelInit.tla | ModelInitBug.cfg | `AtMostOneLoad` 違反 | 旧実装（排他なしの遅延初期化）の再現 |
| ModelInit.tla | ModelInitFixed.cfg | 通過 | 修正後（ロックを取って再確認）、3スレッド |

Bug 設定は対象の性質だけを検査します（別の違反で「再現した」ことにならないようにするため）。Bug 設定が通過したら、それは検査の失敗です。

## 1. 索引の保存（IndexSave.tla）

**観測される不具合**: `sal-search index` で既存の索引を更新している途中でプロセスが止まる、または更新中に `sal-search query` が走ると、新しいベクトルと古い文書（あるいは古い manifest）が組み合わさる。件数が同じだと読み込み時の件数照合を通り、検索結果に別の文書が黙って返る。manifest が古いままだと、モデル名の不一致検出も働かない。

**性質**

- `LoadedIndexIsConsistent` — load が成功を返すなら、ベクトル・文書・manifest は同じ1世代のもの。
- `CommittedGenerationIsComplete` — manifest が指す世代のデータは常に揃っている（どこで止まっても、直前の索引か新しい索引のどちらかが読める）。

**反例（IndexSaveBug.cfg、最短）**

| # | モデルの動作 | 実装（旧） |
|---|---|---|
| 1 | `WriteVec` | `save` が `vectors.npz` を新しい内容で上書き |
| 2 | `ReadMan` | `load` が古い `manifest.json` を読む |
| 3 | `ReadVec` | `load` が新しい `vectors.npz` を読む |
| 4 | `ReadDoc` | `load` が古い `documents.jsonl` を読む |
| 5 | `Decide` → `ok` | 件数が同じなので照合を通り、世代の混ざった索引で検索する |

1 の直後に `Crash`（保存プロセスの停止）が入り、そのあとで 2〜5 が起きる筋も同じ長さの反例です。この場合は混ざった状態がディスクに残り続けます。

**修正**（`src/screen_activity_logger/infrastructure/numpy_index.py`）

- データ2ファイルを世代つきの新しい名前（`vectors-<世代>.npz` / `documents-<世代>.jsonl`）で書く。既存のファイルには触れない。
- 最後に `manifest.json` を一時ファイル経由の `os.replace` で差し替える。ここがコミット点。
- manifest は自分の世代のファイル名と SHA-256 を持ち、load は読んだバイト列をそれと照合する。
- コミット後に旧世代のファイルを削除する。保存が例外で中断した場合は書きかけの世代を削除する。
- `files` を持たない旧形式の manifest は、従来どおり固定名のファイルを件数照合つきで読む。

**回帰テスト**（`tests/unit/test_numpy_index.py`）

- `TestCrashConsistentSave::test_crash_during_save_keeps_previous_generation`
- `TestCrashConsistentSave::test_load_during_save_sees_single_generation`
- `TestCrashConsistentSave::test_swapped_data_file_is_reported_as_corruption`
- `TestCrashConsistentSave::test_missing_data_file_is_reported_as_corruption`
- `TestLegacyIndexCompatibility::test_crash_while_upgrading_legacy_index_keeps_it_loadable`

**モデルの仮定**

- ライターは1つ、リーダーは1つ、世代は2つ（保存前と今回）。
- `os.replace` による manifest の差し替えは原子的（読み手は旧か新のどちらかを見る）。
- 1ファイルの読み込みは1ステップ。実装はファイル全体を読んでからハッシュを照合するので、読みかけの内容を使うことはない。
- チェックサムが一致することを「同じ世代である」ことと同一視している。
- `SameCount = TRUE`（世代間で件数が同じ）という、件数照合にとって最悪の場合で検査している。

**モデル化していない境界**

- 複数プロセスが同じ索引ディレクトリへ同時に保存する場合。後からコミットした側の世代が、先にコミットした側の後片付けで消されることがある。このとき load は破損として報告する（誤った結果は返さない）が、索引の作り直しが必要。同じディレクトリへの同時保存は避けてください。
- 電源断時のディレクトリエントリの永続化（ファイル内容は fsync しているが、ディレクトリの fsync はしていない）。
- Windows では、読み込み中のファイルの削除や差し替えが `PermissionError` になることがある。旧世代の削除失敗は無視して次回の保存に任せる。manifest の差し替え失敗は保存の失敗として報告され、既存の索引は残る。
- 旧バージョンのこのツールは新形式の索引を読めない（固定名のファイルが無いため）。

## 2. ASR モデルの遅延初期化（ModelInit.tla）

**観測される不具合**: faster-whisper バックエンドでチャンク並列転写（`--asr-workers` が2以上、既定の自動設定でもコア数に応じて最大4）を行うと、ワーカースレッドが同時に初回呼び出しに入り、スレッド数ぶんモデルをロードする。転写結果は変わらないが、ロード時間とメモリ（1モデルあたり数GB）が重複し、メモリの少ない環境では落ちる原因になる。

**性質**: `AtMostOneLoad` — モデルのロードは高々1回。

**反例（ModelInitBug.cfg、最短）**

| # | モデルの動作 | 実装（旧） `FasterWhisperTranscriber._run_whisper` |
|---|---|---|
| 1 | `Check(1)` | スレッド1が `self._loaded_model is None` を確認 |
| 2 | `Load(1)` | スレッド1が `WhisperModel(...)` を構築中（まだ代入していない） |
| 3 | `Check(2)` | スレッド2も `None` を見る |
| 4 | `Load(2)` | スレッド2も `WhisperModel(...)` を構築 → 2回目のロード |

**修正**（`src/screen_activity_logger/infrastructure/faster_whisper_transcriber.py` の `_ensure_model`）: `threading.Lock` を取ってから再確認する。ロード済みならロックを取らずに返す。

**回帰テスト**: `tests/unit/test_faster_whisper_parsing.py::TestLazyModelInitIsThreadSafe::test_concurrent_first_calls_load_model_once`

**モデルの仮定**: ロックは相互排他を守る。属性の読み書きは1ステップ。ロード（`WhisperModel` の構築）は失敗しない。

**モデル化していない境界**: ロードが例外で失敗した場合（実装では `with` がロックを解放し、次の呼び出しが再試行する）。mlx / whisper.cpp バックエンドは既定で並列度1のため対象外。

## モデルを作らなかった修正

次の2件は割り込みに依存しない決定的な不具合のため、モデルは作らず回帰テストだけを置いています。

- **出力ファイルの直接上書き**: `worklog.jsonl` / `worklog.md` / 手順書を直接上書きしていたため、書き込み途中で止まると切り詰められたファイルが残った。一時ファイルに書き切ってから `os.replace` で差し替える（`infrastructure/atomic_write.py`、`tests/unit/test_atomic_write.py`）。
- **失敗チャンクの欠落が見えない**: チャンク転写の失敗は「空として続行」する設計だが、出力からは「発話なし」と区別できなかった。続行はそのままに、失敗件数と欠落区間を最後にまとめて表示する（`infrastructure/chunked_transcriber.py`、`tests/unit/test_audio_chunking.py`）。

## 実行方法

必要なもの: Java 11 以上と、[TLA+ tools の公式リリース](https://github.com/tlaplus/tlaplus/releases)の `tla2tools.jar`（v1.7.4 で確認）。ダウンロードした JAR は公式リリースノートのチェックサムと照合してください。JAR と TLC の生成物（`states/` など）はリポジトリに含めません。

```bash
cd formal
java -cp /path/to/tla2tools.jar tlc2.TLC -config IndexSaveBug.cfg IndexSave.tla     # 違反を報告すれば期待どおり
java -cp /path/to/tla2tools.jar tlc2.TLC -config IndexSaveFixed.cfg IndexSave.tla   # No error has been found
```

`tlc-checks.json` は全検査の一覧です。`checks` の各要素が「どのモデルを、どの設定で検査し、何を期待するか」を表します。

- `spec` / `config` — モデルと設定ファイル（`root` からの相対パス）
- `expect.kind` — `pass`（違反なし）または `invariant-violation`（不変条件の違反）
- `expect.name` — 違反するはずの不変条件の名前

一覧をまとめて実行するランナーは同梱していません。上のコマンドを各行に対して実行し、結果が `expect` と一致することを確認してください。

モデルの終端状態には、何もしない `Terminated` ステップを置いています。意図した終了とデッドロックを区別するためで、`CHECK_DEADLOCK FALSE` は使っていません。
