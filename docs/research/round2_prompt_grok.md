# 調査依頼：X(旧Twitter)発、中国・米国のVLMベストプラクティス/流行の網羅調査（2025後半〜2026-07）

あなたはXのリアルタイムトレンドに強いリサーチャーです。X上の実際の投稿・言及・使用報告を最優先ソースに、中国圏（Weibo/知乎/WeChat発の情報がXに転載されたものも含む）と米国圏のVLM（Vision-Language Model）の流行とベストプラクティスを網羅的に調査してください。

## 特に知りたいこと
1. **中国発VLMの最新動向**: Qwen3-VL / Qwen3.5系, MiniCPM-V, InternVL, GLM-4V/GLM-OCR, DeepSeek-VL/DeepSeek-OCR, Kimi-VL, Step系, SenseTime系など。X上で「実際に使っている」報告、ベンチ結果への反応、量子化・ローカル運用の報告
2. **米国発VLMの最新動向**: Llama系Vision, Molmo(AI2), Pixtral(Mistral=欧だが英語圏扱い可), Apple/Google/OpenAI/AnthropicのオープンorローカルVLM関連、NVIDIA系(NVLM, Eagle等)
3. **「画面理解・スクリーン録画解析・GUI理解」用途での流行**: どのモデルが実務で選ばれているか、computer-use/GUI agent界隈の動き（UI-TARS, Claude computer use, OpenAI operator系への言及含む）
4. **ローカルVLM運用のベストプラクティス**: r/LocalLLaMAやX上で語られる定番構成（量子化、Ollama/llama.cpp/vLLM、VRAM別の推奨、解像度制御のコツ）
5. **動画理解のトレンド**: 長尺動画理解、フレームサンプリング戦略、video-RAGなどの言及
6. **2026年上半期に「伸びた」「話題になった」もの**: スター急増リポジトリ、バズった技術投稿、注目論文への反応

## 出力形式
- 中国発 / 米国発 / 画面理解用途 / ローカル運用Tips / 動画理解 / 2026H1トレンド のセクション分け
- 可能な限り具体的なモデル名・リポジトリ・投稿の要旨を挙げる
- 実在・出典が怪しいものは必ず「未確認」と明記。ハルシネーション禁止
- 最後に「VRAM 8〜12GBで画面録画→日本語作業ログ化」という用途への示唆を3〜5行でまとめる
