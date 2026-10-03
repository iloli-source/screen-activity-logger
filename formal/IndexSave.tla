------------------------------ MODULE IndexSave ------------------------------
(***************************************************************************)
(* 検索索引（vectors / documents / manifest の3ファイル）の保存と読み込み。 *)
(*                                                                         *)
(* 登場人物: 索引を保存するライター1つ（任意の時点でクラッシュしうる）と、 *)
(* 3ファイルを1つずつ読むリーダー1つ。世代0=保存前からある索引、          *)
(* 世代1=今回保存する索引。                                                *)
(*                                                                         *)
(* 定数で実装の方式を切り替える:                                           *)
(*   GenerationNamed  TRUE = データファイル名に世代を含める（新方式）       *)
(*                    FALSE = 固定名を上書きする（旧方式）                  *)
(*   VerifyChecksum   TRUE = manifestのチェックサムでデータを照合する       *)
(*                    FALSE = 件数一致のみ確認する（旧方式）                *)
(*   LegacyInitial    TRUE = 世代0のmanifestはチェックサムを持たない        *)
(*   SameCount        TRUE = 世代0と世代1の件数が同じ（件数照合が効かない） *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS GenerationNamed, VerifyChecksum, LegacyInitial, SameCount

ASSUME /\ GenerationNamed \in BOOLEAN
       /\ VerifyChecksum \in BOOLEAN
       /\ LegacyInitial \in BOOLEAN
       /\ SameCount \in BOOLEAN

Gens == {0, 1}
NoFile == 2          \* ファイルが存在しない
Unread == 3          \* リーダーがまだ読んでいない

\* 世代gのデータファイル名。旧方式は世代によらず同じ名前（=0）を上書きする。
NameOf(g) == IF GenerationNamed THEN g ELSE 0

\* 世代gのmanifestがチェックサムを持つか。
HasChecksum(g) == VerifyChecksum /\ ~(LegacyInitial /\ g = 0)

VARIABLES
    vec,      \* vec[n] = 名前nのvectorsファイルが保持する世代（またはNoFile）
    doc,      \* doc[n] = 名前nのdocumentsファイルが保持する世代（またはNoFile）
    man,      \* manifestが指す世代（os.replaceで原子的に切り替わる）
    wpc,      \* ライターの進行位置
    rpc,      \* リーダーの進行位置
    rMan, rVec, rDoc,   \* リーダーが読み取った内容
    result    \* loadの結果

vars == <<vec, doc, man, wpc, rpc, rMan, rVec, rDoc, result>>

TypeOK ==
    /\ vec \in [Gens -> Gens \cup {NoFile}]
    /\ doc \in [Gens -> Gens \cup {NoFile}]
    /\ man \in Gens
    /\ wpc \in {"writeVec", "writeDoc", "writeMan",
                "cleanVec", "cleanDoc", "done", "crashed"}
    /\ rpc \in {"readMan", "readVec", "readDoc", "decide", "done"}
    /\ rMan \in Gens \cup {Unread}
    /\ rVec \in Gens \cup {NoFile, Unread}
    /\ rDoc \in Gens \cup {NoFile, Unread}
    /\ result \in {"none", "ok", "corrupt"}

Init ==
    /\ vec = [n \in Gens |-> IF n = 0 THEN 0 ELSE NoFile]
    /\ doc = [n \in Gens |-> IF n = 0 THEN 0 ELSE NoFile]
    /\ man = 0
    /\ wpc = "writeVec"
    /\ rpc = "readMan"
    /\ rMan = Unread /\ rVec = Unread /\ rDoc = Unread
    /\ result = "none"

(***************************************************************************)
(* ライター: NumpyVectorIndex.save                                         *)
(***************************************************************************)
WriteVec ==
    /\ wpc = "writeVec"
    /\ vec' = [vec EXCEPT ![NameOf(1)] = 1]
    /\ wpc' = "writeDoc"
    /\ UNCHANGED <<doc, man, rpc, rMan, rVec, rDoc, result>>

WriteDoc ==
    /\ wpc = "writeDoc"
    /\ doc' = [doc EXCEPT ![NameOf(1)] = 1]
    /\ wpc' = "writeMan"
    /\ UNCHANGED <<vec, man, rpc, rMan, rVec, rDoc, result>>

\* manifestの差し替えがコミット点。
WriteMan ==
    /\ wpc = "writeMan"
    /\ man' = 1
    /\ wpc' = IF GenerationNamed THEN "cleanVec" ELSE "done"
    /\ UNCHANGED <<vec, doc, rpc, rMan, rVec, rDoc, result>>

\* 新方式のみ: コミット後に旧世代のデータファイルを削除する。
CleanVec ==
    /\ wpc = "cleanVec"
    /\ vec' = [vec EXCEPT ![NameOf(0)] = NoFile]
    /\ wpc' = "cleanDoc"
    /\ UNCHANGED <<doc, man, rpc, rMan, rVec, rDoc, result>>

CleanDoc ==
    /\ wpc = "cleanDoc"
    /\ doc' = [doc EXCEPT ![NameOf(0)] = NoFile]
    /\ wpc' = "done"
    /\ UNCHANGED <<vec, man, rpc, rMan, rVec, rDoc, result>>

\* プロセスはどのステップの間でも落ちうる。ディスクの内容はそのまま残る。
Crash ==
    /\ wpc \notin {"done", "crashed"}
    /\ wpc' = "crashed"
    /\ UNCHANGED <<vec, doc, man, rpc, rMan, rVec, rDoc, result>>

(***************************************************************************)
(* リーダー: NumpyVectorIndex.load                                         *)
(***************************************************************************)
ReadMan ==
    /\ rpc = "readMan"
    /\ rMan' = man
    /\ rpc' = "readVec"
    /\ UNCHANGED <<vec, doc, man, wpc, rVec, rDoc, result>>

ReadVec ==
    /\ rpc = "readVec"
    /\ rVec' = vec[NameOf(rMan)]
    /\ rpc' = "readDoc"
    /\ UNCHANGED <<vec, doc, man, wpc, rMan, rDoc, result>>

ReadDoc ==
    /\ rpc = "readDoc"
    /\ rDoc' = doc[NameOf(rMan)]
    /\ rpc' = "decide"
    /\ UNCHANGED <<vec, doc, man, wpc, rMan, rVec, result>>

CountMatches == SameCount \/ rVec = rDoc

Accepts ==
    /\ rVec # NoFile
    /\ rDoc # NoFile
    /\ IF HasChecksum(rMan)
       THEN rVec = rMan /\ rDoc = rMan
       ELSE CountMatches

Decide ==
    /\ rpc = "decide"
    /\ result' = IF Accepts THEN "ok" ELSE "corrupt"
    /\ rpc' = "done"
    /\ UNCHANGED <<vec, doc, man, wpc, rMan, rVec, rDoc>>

\* 有限シナリオの終端。意図した終了をデッドロックと区別するための空ステップ。
Terminated ==
    /\ wpc \in {"done", "crashed"}
    /\ rpc = "done"
    /\ UNCHANGED vars

Next ==
    \/ WriteVec \/ WriteDoc \/ WriteMan \/ CleanVec \/ CleanDoc \/ Crash
    \/ ReadMan \/ ReadVec \/ ReadDoc \/ Decide
    \/ Terminated

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* 性質                                                                    *)
(***************************************************************************)
\* loadが成功を返すなら、ベクトル・文書・manifestは同じ1世代のものである。
LoadedIndexIsConsistent ==
    result = "ok" => (rVec = rDoc /\ rVec = rMan)

\* manifestが指す世代のデータは常に揃っている（クラッシュしても索引を失わない）。
CommittedGenerationIsComplete ==
    /\ vec[NameOf(man)] = man
    /\ doc[NameOf(man)] = man
=============================================================================
