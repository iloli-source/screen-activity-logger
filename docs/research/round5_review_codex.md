Reading additional input from stdin...
OpenAI Codex v0.142.5
--------
workdir: /Users/user/works/iloli/プロジェクト/screen-activity-logger
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019f50b8-6387-76c0-a69d-0b3f2d196f7c
--------
user
あなたは辛口のシステム設計レビュアーです。以下の設計レビュー依頼に、実装者視点で厳密に答えてください。\n\n# 設計レビュー依頼: 会議動画のVLM無駄撃ち抑制の方式選定

## システム概要
画面録画MP4を完全ローカルで解析し「タイムスタンプ付き日本語作業ログ」を生成するツール（M4 Mac/24GB）。
パイプライン: ffmpegフレーム抽出(2秒毎)＋シーン変化検出(閾値0.08) → キーフレームのみVLM(Qwen3-VL 8B, 約30-90秒/回)で「何をしているか」説明 → OCR(PaddleOCR)＋ASR(kotoba-whisper)と時刻統合。
重複除去: 連続する同一(action文字列, resource)エントリは事後に畳む。

## 実測した課題
- 会議録画(Google Meet)では話者ビュー切替が「シーン変化」として発火（5分間に6〜26回）。画面の意味は同じなのにVLMが呼ばれ、処理時間の支配項になる（1本7〜41分）
- VLMの言い回しが毎回変わるため文字列ベースの事後重複除去では畳めない（「挨拶を交わしている」「挨拶をしている」等）
- 一方、作業手順動画（スクリーンキャスト）ではシーン変化＝操作ステップそのもの＝間引いてはいけないシグナル

## 私の現行案（叩き台）
時間ベースの最小キーフレーム間隔を--modeに紐づける:
- --mode screencast(既定): 間隔0秒＝間引きなし
- --mode meeting: 間隔60秒（話者切替ノイズ抑制）
- --min-keyframe-interval N で明示上書き可

## 私が自覚している弱点
**会議中に画面共有で手順デモが始まるケース**。60秒間引きだと共有画面内の操作ステップを取りこぼす。会議と作業手順のハイブリッドな動画は現実に多い（本ツールのテストデータのCircleback録画にも画面共有が含まれる）。

## 検討してほしい代替案（これ以外の提案も歓迎）
A) 時間ベース間引き（現行案）: 単純・確実だがハイブリッド動画で取りこぼし
B) OCRテキスト類似度ベース: 新キーフレームのOCR行集合が「最後にVLMを呼んだキーフレーム」のOCR行集合とほぼ同じ（Jaccard高）ならVLMスキップ。話者切替は文字がほぼ不変なのでスキップされ、画面共有開始は新出文字が増えるので発火する。モード非依存で両方に効く。コスト: キーフレームOCRは既に実施済み（支払い済み計算）
C) 画像類似度ベース: 「最後にVLMを呼んだフレーム」との64x64グレースケール差分（既存のPilFrameComparator流用）。ただし話者切替は全画面の顔が入れ替わるため画素差分は大きく、誤発火しそう
D) その他（レイアウト検出・顔領域マスク・安いモデルでの事前判定など）

## 回答フォーマット
1. 推奨方式（A/B/C/D/組み合わせ）と理由
2. 推奨方式の実装上の落とし穴・エッジケース（3つ以上）
3. 却下した方式の却下理由
4. パラメータの推奨値（閾値等）
簡潔に、実装者視点で。日本語で。
2026-07-11T10:28:11.428467Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer error=\"invalid_token\", error_description=\"Token is not authorized\", resource_metadata=\"https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp\"" })
2026-07-11T10:28:11.809668Z ERROR codex_memories_write::phase2: Phase 2 no changes
warning: Skill descriptions were shortened to fit the 2% skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
Slack作業ログの指定があるので、回答前にSlack送信経路を確認します。あわせて、このリポジトリに関する既存メモリがないか軽く見ます。
exec
/bin/zsh -lc "sed -n '1,240p' /Users/user/.codex/plugins/cache/openai-curated/slack/bd2122cb/skills/slack/SKILL.md" in /Users/user/works/iloli/プロジェクト/screen-activity-logger
 succeeded in 0ms:
---
name: slack
description: Read Slack context, route to the right Slack workflow, and prepare or perform Slack writes that match the user's intent.
---

# Slack

## Overview

Use this skill as the router for Slack work. Read the relevant Slack context first, then hand off to the most specific Slack workflow.
If the task will produce outgoing Slack text or perform a Slack write, switch to [../slack-outgoing-message/SKILL.md](../slack-outgoing-message/SKILL.md) before finalizing and reread that file's `## Formatting Rules` section immediately before any send, draft, schedule, or canvas creation.

## Related Skills

| Workflow | Skill |
| --- | --- |
| Message composition, rewrites, drafts, and canvas-writing workflows | [../slack-outgoing-message/SKILL.md](../slack-outgoing-message/SKILL.md) |
| Bounded channel recaps and thematic Slack summaries | [../slack-channel-summarization/SKILL.md](../slack-channel-summarization/SKILL.md) |
| Daily digests across selected channels or topics | [../slack-daily-digest/SKILL.md](../slack-daily-digest/SKILL.md) |
| Find messages that likely need a response and prepare reply drafts | [../slack-reply-drafting/SKILL.md](../slack-reply-drafting/SKILL.md) |
| Triage for what the user needs to read, reply to, or do next | [../slack-notification-triage/SKILL.md](../slack-notification-triage/SKILL.md) |

## Reference Notes

| Task | Reference |
| --- | --- |
| Slack Markdown formatting rules and examples | [references/markdown.md](./references/markdown.md) |

## Support Checks

- Confirm the requested action is supported before asking the user for more input. If Slack does not support the action, say so immediately and offer the closest supported path instead of collecting unnecessary details.
- For broad Slack analysis requests, fail fast if the connector cannot establish the needed coverage or signals reliably. Do not invent channel names, imply the user is in a channel, or present workspace-wide conclusions as authoritative. Ask for a candidate list, a narrower scope, or a question that can be answered from specific channels, threads, profiles, or search results.
- The current Slack app surface here supports reading/searching channels, users, threads, and canvases plus writing messages, drafts, scheduled messages, and canvases. Do not claim support for creating channels, editing messages, deleting messages, or other unsupported Slack admin actions.

## Intent Routing

- If the user explicitly asks to send, post, reply, share, or create something in Slack, follow that write intent directly. Do not downgrade the request into a draft unless the user asked for a draft or review-first flow.
- If the user explicitly asks for a draft, rewrite, or review-first workflow, use a draft.
- If the user asks for Slack analysis only, return the result in chat unless they also asked for Slack delivery.
- If the user asks for an unsupported Slack write action, say so and offer the closest supported path instead of forcing a draft.

## Tool Rate Limits

- Slack tools have per-minute RPM quotas by bucket, not by individual tool. Treat `slack_search_*` tools as the search bucket, `slack_read_*`, `slack_list_*`, and lookup-style tools as the read bucket, and message, draft, schedule, or canvas creation tools as the send/write bucket.
- If a Slack tool returns a 429, do not retry immediately and do not switch to an equivalent tool in the same bucket. If the response includes `Retry-After` or another explicit wait hint, follow it. Otherwise wait about 30 seconds before calling that bucket again.
- If the same bucket returns another 429 during the task, wait about 1 minute before the next retry, then about 2 minutes after the next 429, continuing with exponential backoff as needed.
- A 429 in one bucket does not imply the other buckets are exhausted. While waiting on one bucket, continue making useful progress with other buckets when that can advance the task safely.
- If the task cannot be completed without the exhausted bucket after reasonable backoff, explain the rate limit to the user and return the best partial result or next step.

## DM Routing

- When the same message is meant for multiple specific people, first look for an existing group DM with the right people and prefer that over duplicate one-to-one DMs.
- If there is no suitable group DM, do not silently fan out separate DMs. Ask whether the user wants individual DMs instead, or ask them to create the group DM if that is the better path and the connector cannot create it.

## Write Safety

- Preserve exact channel names, thread context, links, code snippets, and owners from the source conversation unless the user asks for changes.
- Before acting on a relative message target such as "last message", "latest reply", "above", or "that message", re-read the destination channel or thread and resolve the target from fresh results. Do not reuse earlier reads for reactions, replies, edits, or other writes.
- Treat @channel, @here, mass mentions, and customer-facing channels as high-impact. Call them out before posting.
- Keep post-ready drafts short enough to scan quickly unless the user asks for a long-form announcement.
- If there are multiple channels or threads with similar topics, identify the intended destination before drafting or posting.

## Output Conventions

- Prefer a short opener, a few tight bullets, and a clear ask or next step.
- Use Markdown formatting rules from `references/markdown.md` for emphasis, lists, links, quotes, mentions, and code.
- For any outgoing Slack text, use the `slack-outgoing-message` skill.
- Distinguish clearly between a private summary for the user and a post-ready message for Slack.
- When summarizing a thread, lead with the latest status and then list blockers, decisions, and owners.
- When drafting a reply, match the tone of the channel and avoid over-formatting.

## Example Requests

- "Summarize the incident thread in #ops and draft a calm update for leadership."
- "Turn these meeting notes into a short Slack post for the team channel."
- "Read the product launch thread and draft a reply that confirms the timeline."
- "Rewrite this long update so it lands well in Slack and still keeps the important links."

## Light Fallback

If Slack messages are missing, say that Slack access may be unavailable, the workspace may be disconnected, or the wrong channel or thread may be in scope, then ask the user to reconnect or clarify the destination.

exec
/bin/zsh -lc 'rg -n "screen-activity-logger|VLM|Qwen|会議|OCR|キーフレーム|作業ログ" /Users/user/.codex/memories/MEMORY.md' in /Users/user/works/iloli/プロジェクト/screen-activity-logger
 exited 1 in 0ms:
codex
メモリにはこの設計テーマの既存ヒットはありませんでした。Slack送信は専用ワークフローの指示に従って、送信直前に書式ルールを確認します。
exec
/bin/zsh -lc "sed -n '1,220p' /Users/user/.codex/plugins/cache/openai-curated/slack/bd2122cb/skills/slack/references/markdown.md" in /Users/user/works/iloli/プロジェクト/screen-activity-logger
exec
/bin/zsh -lc "sed -n '1,260p' /Users/user/.codex/plugins/cache/openai-curated/slack/bd2122cb/skills/slack-outgoing-message/SKILL.md" in /Users/user/works/iloli/プロジェクト/screen-activity-logger
 succeeded in 0ms:
# Slack Authoring Reference

Use this reference when writing Slack-ready text for these skills.

## Authoring Contract

- Write clean Markdown-style text plus explicit Slack mention syntax.
- The active Slack runtime may convert Markdown into Slack mrkdwn or blocks before sending. Follow the live tool contract if it is more specific than this file.
- Keep Slack-specific mention syntax for users and channels. Use user-group mention syntax only when the runtime can actually resolve the group.

## Common Syntax

| Intent | Preferred authoring |
| --- | --- |
| Strong emphasis | `**text**` in Markdown-converting paths, or the live tool's required bold syntax |
| Emphasis | `*text*` or the live tool's required italic syntax |
| Strikethrough | `~~text~~` |
| Inline code | `` `code` `` |
| Code block | `` ```text``` `` |
| Quote | `> text` |
| Link | `[label](https://example.com)` |
| User mention | `<@U123456>` |
| Channel mention | `<#C123456>` |
| User group mention | `<!subteam^S123456>` |
| Bulleted list | `- item` |
| Numbered list | `1. item` |

## Usage Notes

- Prefer short paragraphs and `-` bullets for Slack posts.
- Use heading-like standalone lines sparingly. Keep them short.
- Do not rely on bare `@name` text for mentions.
- Avoid `@here`, `@channel`, and similar broad notifications unless the user explicitly asked for them.

 succeeded in 0ms:
---
name: slack-outgoing-message
description: Primary skill for composing, drafting, or refining any outbound Slack content. Use this whenever the task will require using `slack_send_message`, `slack_send_message_draft`, or `slack_create_canvas`. Use `slack` to read or analyze Slack context; use this skill to produce the final outgoing message.
---

# Slack Outgoing Message

## Overview

Use this skill whenever the task involves producing final Slack text for a send, draft, scheduled message, or canvas.
If another Slack skill is used to read or summarize source context, switch to this skill before finalizing outgoing text.

## Intent Rules

- If the user explicitly asks to send, post, reply, share, or create something in Slack, perform that write action directly. Do not create a draft or ask for approval only because the message text is being generated during the turn.
- Use a draft only when the user explicitly asks for a draft, review-first workflow, or later/manual send.
- If the destination, wording, or requested action is unclear, clarify before writing.
- If the user asks for an unsupported Slack write action, say so immediately and offer the closest supported path instead of drafting something unrelated.

## Reference Notes

Read this reference **before finalizing any outgoing Slack text**:

| Task | Reference |
| --- | --- |
| Exact Slack Markdown syntax for emphasis, lists, links, code, and mentions | [../slack/references/markdown.md](../slack/references/markdown.md) |

## Formatting Rules

- Write concise Slack-ready text that follows the live tool contract plus `../slack/references/markdown.md`.
- Prefer a short opener, a few tight bullets, and a clear ask or next step.
- Use explicit Slack mention syntax only when you resolved the target successfully.
- Preserve source links, code, owners, dates, and commitments unless the user asked for edits.
- Do not invent approvals, decisions, or follow-through.

## Workflow

1. Identify the **intended destination** before drafting: channel, thread, DM, or group DM.
2. Determine the execution mode from the user's request:
   - explicit send/post/reply/share: use the direct write action
   - explicit draft/review/later-send: use the draft action
   - future delivery: use `slack_schedule_message`
   - canvas/doc request: use `slack_create_canvas`
3. Read `../slack/references/markdown.md` and use that authoring contract.

## Tool Guardrails

- Treat optional Slack tool parameters as absent-by-default.
- `thread_ts` is valid only for replies in an existing thread. For normal channel posts, DMs, and new group DMs, omit the `thread_ts` key entirely.
- `slack_create_canvas` is an immediate write, not a draft. Use it only when the user explicitly asked for a canvas, doc, or immediate Slack write of that form.
- Use `slack_schedule_message` only when the user explicitly asked for future delivery or supplied a send time.
- `slack_send_message_draft` cannot overwrite an existing attached draft, and do not claim that you verified the destination is draft-free before calling the tool.
- If `slack_send_message_draft` returns `draft_already_exists`, stop immediately. Tell the user there is already an attached draft in that destination and that Slack cannot overwrite it.
- Current Slack app support here is centered on messages, drafts, scheduled messages, canvases, and read/search flows. Do not claim support for creating channels, editing messages, deleting messages, or resolving Slack user groups when the runtime does not expose those actions.

## Destination Safety

- If the user wants to **cc, mention, or tag** someone, first check whether that person is already in the destination channel or group DM when the connector makes that practical. If you cannot verify it, do not imply the mention will notify them.
- Treat `@here`, `@channel`, `@everyone`, and similar broad notifications as **high-impact**. Do not add them unless the user explicitly asked for them.

## Mention Rules

- Resolve **user mentions** before writing when the message should tag a person, and use Slack mention syntax: `<@U123456>`.
- Resolve **Slack user groups** before writing only when the runtime exposes a way to do so, and use Slack mention syntax: `<!subteam^S123456>`.
- Do not rely on bare `@name` text in outgoing Slack messages.
- If you cannot resolve the correct user or group, **tell the user** and compose the draft or message without implying the mention will work.

codex
レビュー本文を組み立てました。最後に指定チャンネルへ作業ログを直接投稿してから、こちらに回答します。
codex
Slack送信ツールを検索しましたが、最初の候補には送信ツールが露出しませんでした。チャンネル投稿のためにSlack系ツールをもう一度絞って探します。
codex
現セッションではSlack送信ツールがまだ出てきていません。利用可能なインストール候補も確認して、送れない場合は未実行として明記します。
codex
Slackコネクタ自体は候補にありますが、このセッションでは送信ツールとして有効化されていません。投稿必須指定を満たすため、Slackコネクタの有効化を要求します。
codex
Slack投稿は実行できませんでした。現セッションにSlack送信ツールが露出しておらず、Slackコネクタ有効化要求も未承認でした。

1. 推奨方式

**Bを主軸 + Aの上限ガード。Cは補助止まり。**

時間ベース60秒固定は雑すぎます。会議中の画面共有デモを落とすので、実データ要件に対して危ないです。  
推奨は「VLM候補フレームに対してOCR類似度でスキップ判定し、ただし一定時間に1回は必ずVLMを撃つ」方式です。

実装方針:

- 初回キーフレームは必ずVLM
- シーン変化候補ごとにOCR済みテキスト集合を取得
- 「最後にVLMを撃ったフレーム」と比較
- OCRがほぼ同じならVLMスキップ
- OCRが変わったらVLM実行
- ただし `max-vlm-skip-interval` を超えたら強制VLM

これは会議ビュー切替には効きます。顔や話者タイルが変わってもMeet画面の文字はほぼ変わらないためです。画面共有開始・資料遷移・アプリ切替はOCR差分が出やすいので拾えます。

2. 落とし穴・エッジケース

- **OCRが少ない画面では判定不能**  
  参加者の顔だけ、白紙、画像中心のスライド、動画再生中などはOCR類似度が使えません。この場合はBに頼らず、時間ガードか画像差分補助にフォールバックすべきです。

- **同じUI内の操作ステップはOCRが変わらないことがある**  
  クリック、ドラッグ、カーソル移動、メニュー展開前後、入力欄フォーカスなどはOCR行集合がほぼ同じです。スクリーンキャストでBを強く効かせると作業ステップを落とします。`meeting`では強め、`screencast`では弱めまたは無効が妥当です。

- **字幕・参加者名・時刻表示がノイズになる**  
  Meetの字幕、参加者名、時計、録画UI、通知バナーがJaccardを壊します。OCRテキストは正規化が必須です。短すぎる行、時刻っぽい行、参加者名だけの行、低信頼度行は除外してください。

- **「新出文字が少しだけ増えた」ケースの扱いが難しい**  
  画面共有開始なら拾いたい。一方、チャット通知1行だけならVLMを撃ちたくない。Jaccard単体では弱いので、`new_text_ratio` も見るべきです。

- **最後のVLMフレームだけ比較だと長時間で状態がズレる**  
  スキップが続くと、比較対象が古くなります。`last_vlm_ocr` に加えて `last_candidate_ocr` も持ち、ログ用には「スキップ区間の代表OCR変化」を保存した方が後段統合が安定します。

3. 却下理由

- **A単体は却下**  
  実装は楽ですが、ハイブリッド動画で落とすべきでない操作ステップを落とします。`meeting=60秒` は会議録画には効くが、画面共有デモには鈍すぎます。デフォルトの中核ロジックにするには粗いです。

- **C単体は却下**  
  話者ビュー切替・顔タイル変化・カメラON/OFFで画素差分が大きくなり、まさに抑制したいケースで誤発火します。64x64グレー差分は安いですが、会議画面の意味変化検出には向いていません。

- **Dの顔マスク・レイアウト検出・安いモデル前段は初手では過剰**  
  顔領域マスクは効果ありそうですが実装と保守が重い。安いモデル前段も「VLM無駄撃ち抑制のために別モデルを運用する」構成になり、ローカルM4/24GBでは複雑さに見合わない可能性が高いです。まずBで詰めるべきです。

4. 推奨パラメータ

- `--mode screencast`
  - `min-keyframe-interval`: `0`
  - OCRスキップ: 既定OFF、入れるならかなり保守的
  - `ocr_jaccard_skip_threshold`: `0.95`
  - `max-vlm-skip-interval`: `30秒`

- `--mode meeting`
  - `min-keyframe-interval`: `0〜10秒`
  - `ocr_jaccard_skip_threshold`: `0.85〜0.90`
  - `new_text_ratio_trigger`: `0.20`
  - `max-vlm-skip-interval`: `60〜90秒`

- OCR正規化
  - confidence `<0.6` 除外
  - 2文字以下の行を除外
  - 時刻、参加者名、録画UI、Meet固定文言を除外
  - 行単位Jaccardに加えて、正規化トークン集合でも比較

結論: **AではなくB中心。meetingでは強め、screencastでは弱め。さらに最大スキップ時間だけAを保険として入れる。**  
これが一番実装コストと取りこぼしリスクのバランスがいいです。
tokens used
32,012
Slack投稿は実行できませんでした。現セッションにSlack送信ツールが露出しておらず、Slackコネクタ有効化要求も未承認でした。

1. 推奨方式

**Bを主軸 + Aの上限ガード。Cは補助止まり。**

時間ベース60秒固定は雑すぎます。会議中の画面共有デモを落とすので、実データ要件に対して危ないです。  
推奨は「VLM候補フレームに対してOCR類似度でスキップ判定し、ただし一定時間に1回は必ずVLMを撃つ」方式です。

実装方針:

- 初回キーフレームは必ずVLM
- シーン変化候補ごとにOCR済みテキスト集合を取得
- 「最後にVLMを撃ったフレーム」と比較
- OCRがほぼ同じならVLMスキップ
- OCRが変わったらVLM実行
- ただし `max-vlm-skip-interval` を超えたら強制VLM

これは会議ビュー切替には効きます。顔や話者タイルが変わってもMeet画面の文字はほぼ変わらないためです。画面共有開始・資料遷移・アプリ切替はOCR差分が出やすいので拾えます。

2. 落とし穴・エッジケース

- **OCRが少ない画面では判定不能**  
  参加者の顔だけ、白紙、画像中心のスライド、動画再生中などはOCR類似度が使えません。この場合はBに頼らず、時間ガードか画像差分補助にフォールバックすべきです。

- **同じUI内の操作ステップはOCRが変わらないことがある**  
  クリック、ドラッグ、カーソル移動、メニュー展開前後、入力欄フォーカスなどはOCR行集合がほぼ同じです。スクリーンキャストでBを強く効かせると作業ステップを落とします。`meeting`では強め、`screencast`では弱めまたは無効が妥当です。

- **字幕・参加者名・時刻表示がノイズになる**  
  Meetの字幕、参加者名、時計、録画UI、通知バナーがJaccardを壊します。OCRテキストは正規化が必須です。短すぎる行、時刻っぽい行、参加者名だけの行、低信頼度行は除外してください。

- **「新出文字が少しだけ増えた」ケースの扱いが難しい**  
  画面共有開始なら拾いたい。一方、チャット通知1行だけならVLMを撃ちたくない。Jaccard単体では弱いので、`new_text_ratio` も見るべきです。

- **最後のVLMフレームだけ比較だと長時間で状態がズレる**  
  スキップが続くと、比較対象が古くなります。`last_vlm_ocr` に加えて `last_candidate_ocr` も持ち、ログ用には「スキップ区間の代表OCR変化」を保存した方が後段統合が安定します。

3. 却下理由

- **A単体は却下**  
  実装は楽ですが、ハイブリッド動画で落とすべきでない操作ステップを落とします。`meeting=60秒` は会議録画には効くが、画面共有デモには鈍すぎます。デフォルトの中核ロジックにするには粗いです。

- **C単体は却下**  
  話者ビュー切替・顔タイル変化・カメラON/OFFで画素差分が大きくなり、まさに抑制したいケースで誤発火します。64x64グレー差分は安いですが、会議画面の意味変化検出には向いていません。

- **Dの顔マスク・レイアウト検出・安いモデル前段は初手では過剰**  
  顔領域マスクは効果ありそうですが実装と保守が重い。安いモデル前段も「VLM無駄撃ち抑制のために別モデルを運用する」構成になり、ローカルM4/24GBでは複雑さに見合わない可能性が高いです。まずBで詰めるべきです。

4. 推奨パラメータ

- `--mode screencast`
  - `min-keyframe-interval`: `0`
  - OCRスキップ: 既定OFF、入れるならかなり保守的
  - `ocr_jaccard_skip_threshold`: `0.95`
  - `max-vlm-skip-interval`: `30秒`

- `--mode meeting`
  - `min-keyframe-interval`: `0〜10秒`
  - `ocr_jaccard_skip_threshold`: `0.85〜0.90`
  - `new_text_ratio_trigger`: `0.20`
  - `max-vlm-skip-interval`: `60〜90秒`

- OCR正規化
  - confidence `<0.6` 除外
  - 2文字以下の行を除外
  - 時刻、参加者名、録画UI、Meet固定文言を除外
  - 行単位Jaccardに加えて、正規化トークン集合でも比較

結論: **AではなくB中心。meetingでは強め、screencastでは弱め。さらに最大スキップ時間だけAを保険として入れる。**  
これが一番実装コストと取りこぼしリスクのバランスがいいです。
