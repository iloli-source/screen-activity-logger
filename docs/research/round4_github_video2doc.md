# 第4回調査: GitHub「動画→作業手順テキスト化」OSS（2026-07-11）

## 結論
「録画済み動画→画面(OCR+VLM)＋音声(ASR)→手順テキスト」の成熟OSSは不在（3度目の確認）。

## A. 直接同一用途（全て実験レベル）
- skyzyx/video-to-documentation ⭐0（AI利用、2026-04）
- Shezan57/Video-to-SOP-Generator ⭐1
- gitmvp-com/youtube-doc-mvp ⭐0（トランスクリプトのみ）

## B. 隣接: 音声書き起こしベース（「耳」だけ）
- DouZin-Inc/sasayaki-transcriber（日本語・話者分離・ローカル）
- naokijodan/mojimoji-kun（YouTube→記事・Chrome拡張・日本語）
- mizuno826/video-transcriber（FastAPI+faster-whisper）

## C. 操作記録系（ライブ記録・録画MP4は不可）
- OpenAdaptAI/OpenAdapt ⭐1,636（記録→自動化。文書は副産物）

## D. 研究
- salesforce/paprika（CVPR2023 手順認識事前学習 ⭐50）
- PedagogyBench（2026-05 教育動画理解ベンチ）
