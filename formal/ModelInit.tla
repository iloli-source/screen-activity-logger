------------------------------ MODULE ModelInit ------------------------------
(***************************************************************************)
(* ASRモデルの遅延初期化（FasterWhisperTranscriber._run_whisper）。         *)
(*                                                                         *)
(* チャンク並列転写では複数のワーカースレッドが同じアダプタを同時に呼ぶ。   *)
(* 各スレッドは「未ロードか確認 → ロード → 保存」を行う。                  *)
(*   UseLock = FALSE  確認とロードの間に排他がない（旧実装）                *)
(*   UseLock = TRUE   ロックを取ってから再確認する（修正後）                *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Threads, UseLock

ASSUME UseLock \in BOOLEAN

NoHolder == 0
ASSUME NoHolder \notin Threads

VARIABLES
    pc,       \* 各スレッドの進行位置
    loaded,   \* モデルが保存済みか（self._loaded_model is not None）
    loads,    \* モデルをロードした回数
    lock      \* ロックの保持者（NoHolder=空き）

vars == <<pc, loaded, loads, lock>>

TypeOK ==
    /\ pc \in [Threads -> {"check", "acquire", "recheck", "load",
                           "store", "release", "use", "done"}]
    /\ loaded \in BOOLEAN
    /\ loads \in 0..10
    /\ lock \in Threads \cup {NoHolder}

Init ==
    /\ pc = [t \in Threads |-> "check"]
    /\ loaded = FALSE
    /\ loads = 0
    /\ lock = NoHolder

\* ロックなしの最初の確認（ロード済みなら排他なしで素通り）。
Check(t) ==
    /\ pc[t] = "check"
    /\ pc' = [pc EXCEPT ![t] =
                IF loaded THEN "use"
                ELSE IF UseLock THEN "acquire" ELSE "load"]
    /\ UNCHANGED <<loaded, loads, lock>>

Acquire(t) ==
    /\ pc[t] = "acquire"
    /\ lock = NoHolder
    /\ lock' = t
    /\ pc' = [pc EXCEPT ![t] = "recheck"]
    /\ UNCHANGED <<loaded, loads>>

\* ロック取得後の再確認（待っている間に他スレッドがロード済みかもしれない）。
Recheck(t) ==
    /\ pc[t] = "recheck"
    /\ pc' = [pc EXCEPT ![t] = IF loaded THEN "release" ELSE "load"]
    /\ UNCHANGED <<loaded, loads, lock>>

\* WhisperModel(...) の構築。数秒かかり、その間に他スレッドが動ける。
Load(t) ==
    /\ pc[t] = "load"
    /\ loads' = loads + 1
    /\ pc' = [pc EXCEPT ![t] = "store"]
    /\ UNCHANGED <<loaded, lock>>

Store(t) ==
    /\ pc[t] = "store"
    /\ loaded' = TRUE
    /\ pc' = [pc EXCEPT ![t] = IF UseLock THEN "release" ELSE "use"]
    /\ UNCHANGED <<loads, lock>>

Release(t) ==
    /\ pc[t] = "release"
    /\ lock = t
    /\ lock' = NoHolder
    /\ pc' = [pc EXCEPT ![t] = "use"]
    /\ UNCHANGED <<loaded, loads>>

Use(t) ==
    /\ pc[t] = "use"
    /\ pc' = [pc EXCEPT ![t] = "done"]
    /\ UNCHANGED <<loaded, loads, lock>>

\* 有限シナリオの終端。意図した終了をデッドロックと区別するための空ステップ。
Terminated ==
    /\ \A t \in Threads : pc[t] = "done"
    /\ UNCHANGED vars

Next ==
    \/ \E t \in Threads :
          \/ Check(t) \/ Acquire(t) \/ Recheck(t) \/ Load(t)
          \/ Store(t) \/ Release(t) \/ Use(t)
    \/ Terminated

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* 性質                                                                    *)
(***************************************************************************)
\* モデルのロードは高々1回。
AtMostOneLoad == loads <= 1

\* モデルを使うスレッドは必ずロード済みのモデルを見る。
UseSeesLoadedModel == \A t \in Threads : pc[t] \in {"use", "done"} => loaded
=============================================================================
