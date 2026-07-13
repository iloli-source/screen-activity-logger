codex
調査時点: **2026-07-13**。結論から言うと、M4 Air 24GBで一番効くのは「モデルを替える」より先に、**入力ピクセル・VLM呼び出し回数・同一/類似フレームの画像特徴キャッシュ**を潰すことです。既存方針の「PaddleOCRで文字を確定、Qwen3-VLは疎に呼ぶ」は正しいです。

**既存記載との差分**
- [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:13) の「OCR専用 + VLM疎」は、PP-OCRv6論文が「VLM OCRは幻覚・局在誤差・コスト問題」と明記しており、より強く支持されます。出典: [PP-OCRv6 arXiv:2606.13108](https://arxiv.org/abs/2606.13108)
- [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:36) の「MLXはMac加点」扱いは更新推奨。2026-07時点では **MLX-VLM / vllm-mlx がM4系の本線候補**です。出典: [mlx-vlm GitHub](https://github.com/Blaizzy/mlx-vlm), [vllm-mlx arXiv:2601.19139](https://arxiv.org/abs/2601.19139)
- [docs/research/issue8_speedup_verification.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/docs/research/issue8_speedup_verification.md:56) の vllm-mlx 検証は未完了。ここが最優先の実測穴です。
- [ffmpeg_extractor.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/src/screen_activity_logger/infrastructure/ffmpeg_extractor.py:52) の長辺1024px制限は妥当。Qwen3-VL公式も `max_pixels` / `fps` / `num_frames` 制御を前提化しています。出典: [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
- [paddle_ocr.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/src/screen_activity_logger/infrastructure/paddle_ocr.py:39) は、doc orientation / unwarping / textline orientation をOFFにしており、画面OCR用途では速度面で正しいです。

**M4 Air 24GBで今すぐ効くもの**
1. **vllm-mlx / mlx-vlm のA/B実測を完了**
   - vllm-mlx論文はM4 Maxで、テキストは llama.cpp 比 `21-87%`高スループット、同一画像再質問は最大`28x`、動画は`24.7x`キャッシュ高速化を報告。M4 Airでは熱制限があるので、既存のABBA測定で確認が必要。
   - 既存ベンチ [scripts/bench_vlm_ab.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/scripts/bench_vlm_ab.py:1) は方向性が良いです。`--mode cache` を同一画像・隣接類似フレーム・OCR同一フレームで分けて測るべきです。

2. **VLM入力を「長辺」ではなく「視覚トークン予算」で管理**
   - Qwen3-VL公式は画像で `256-1280` visual token、動画で `256-16384` visual token相当の予算指定を例示しています。画面ログではまず **256-512 token相当** から始め、読めないROIだけ再解析がよいです。
   - `max_tokens` も作業ログ用途なら `128-256` で十分。長い自然文を出させるとdecodeが無駄です。

3. **OCR Jaccardゲート + max_gap は維持**
   - 会議・画面共有混在には、scene差分よりOCR内容差分が効きます。既存 [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:245) の階層型間引き方針は妥当。
   - 推奨初期値: `vlm-skip-threshold=0.82-0.88`, `vlm-min-gap=5-10s`, `vlm-max-gap=120s`。screencastでは閾値を高め、meetingでは低め。

4. **OCRは PP-OCRv6 tiny/small + バッチ/ROI化**
   - PP-OCRv6は tiny/small/medium の3階層。tinyはIntel XeonでPP-OCRv5 mobile比`3.9x`高速と報告。出典: [PP-OCRv6](https://arxiv.org/abs/2606.13108)
   - 画面全体OCRより、前フレーム差分のbounding box周辺だけ再OCRする方が効く可能性が高いです。
   - Apple Vision `VNRecognizeTextRequest` は比較価値あり。macOSネイティブで導入が軽く、低精度でも「ゲート用OCR」には使える可能性があります。出典: [Apple Vision text recognition](https://developer.apple.com/documentation/vision/recognizing-text-in-images)

5. **並列化はASR/OCR/VLMの段階分離**
   - OCRとフレーム差分はCPU寄り、VLMはGPU/Metal寄り。M4 Airはファンレスなので、VLM中に重いOCRを並列しすぎると熱で逆効果です。
   - 推奨: `ASR先行一括 → OCR/差分キュー → VLM単一ワーカー + cache`。長時間動画は5-10分単位に分割。

**ハード更新が必要・効果が大きいもの**
- **32GB以上のApple Silicon**: Ollama公式MLXバックエンドが32GB以上で有効という既存調査があり、24GBでは恩恵が限定的です。M4 Pro/Max以上なら持続GPU負荷とメモリ帯域で効きます。
- **NVIDIA CUDA機**: vLLM本体、AWQ/GPTQ、FlashAttention、TensorRT/OpenVINO/Paddle GPUの最適化が使えます。vLLM量子化の対応表でもAWQ/GPTQはCUDA系が中心です。出典: [vLLM Quantization](https://docs.vllm.ai/en/latest/features/quantization/)
- **ANE直接活用**: Apple Neural EngineはCore ML経由が公式ルートで、PaddleOCRやQwen3-VLをそのままANEで速くする現実解は薄いです。研究的にはANEForge等がありますが、本番向きではありません。出典: [ANEForge arXiv:2606.17090](https://arxiv.org/abs/2606.17090)

**VLM高速化の論文・実務知見**
- **FastVLM**: Apple発。高解像度VLMのボトルネックはvision encoder/token数。TTFT `3.2x`改善、LLaVA-OneVision比で最大`85x`高速TTFT。今のQwen3-VLを直接速くするというより、次期軽量VLM選定の基準。出典: [arXiv:2412.13303](https://arxiv.org/abs/2412.13303)
- **ShowUI**: UI画面向けvisual token selection。冗長token `33%`削減、`1.4x`高速化。GUI画面録画には直結。出典: [arXiv:2411.17465](https://arxiv.org/abs/2411.17465)
- **FocusUI**: UI groundingで30% token保持でも性能低下`3.2%`、最大`1.44x`高速、peak GPU memory `17%`減。出典: [arXiv:2601.03928](https://arxiv.org/abs/2601.03928)
- **FasterVLM / OccamToken / PIO-FVLM**: training-free token pruning系。FasterVLMは95% pruneで90%性能維持、PIO-FVLMは11.1% token保持で97.2%性能維持、OccamTokenはQwen3-VLも対象。実装負荷は高いので、今すぐより研究枠。出典: [FasterVLM](https://arxiv.org/abs/2412.01818), [PIO-FVLM](https://arxiv.org/abs/2602.04657), [OccamToken](https://arxiv.org/abs/2605.29657)
- **Q-VLM / AWQ**: 4bitはメモリ削減には確実。速度はランタイム依存。Q-VLMは13B LLaVAでメモリ`2.78x`圧縮、生成`1.44x`高速。AWQはTinyChatでFP16 HF比`3x+`を報告。出典: [Q-VLM](https://arxiv.org/abs/2410.08119), [AWQ](https://arxiv.org/abs/2306.00978)

**中国語圏・中国系研究のOCR/VLM要約**
- **Qwen3-VL / 通義千問**: 中国語圏ではGUI agent、長動画、32言語OCRを強く押している。日本語作業ログでは本命維持。出典: [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL), [通义千问 中文概要](https://zh.wikipedia.org/wiki/%E9%80%9A%E4%B9%89%E5%8D%83%E9%97%AE)
- **GLM-OCR**: 智譜系。0.9B、MTPでOCRデコードを高速化、PP-DocLayout-V3 + region recognitionの2段構成。画面UIより文書/表/数式向き。出典: [arXiv:2603.10910](https://arxiv.org/abs/2603.10910)
- **DeepSeek-OCR**: 100-800 visual tokens/pageという「光学的コンテキスト圧縮」が特徴。長文書・PDFには強いが、画面録画の逐次UIには重め。出典: [arXiv:2510.18234](https://arxiv.org/abs/2510.18234)
- **GOT-OCR 2.0**: 580Mの統一OCRモデル。markdown/TikZ/SMILES等の構造出力に強い。画面OCRの第一候補ではなく、難読領域の第2パス向き。出典: [arXiv:2409.01704](https://arxiv.org/abs/2409.01704)
- **HunyuanOCR-1.5 / Unlimited OCR**: Tencent/Baidu系。DFlashや定数KV cacheで長いOCR出力を速くする流れ。スクショ単発より、長文書バッチで効く。出典: [HunyuanOCR-1.5](https://arxiv.org/abs/2607.04884), [Unlimited OCR](https://arxiv.org/abs/2606.23050)

**実装優先順位**
1. Issue #8の vllm-mlx vs Ollama 実測を完了。同一画像・類似画像・異なる画像でcache効果を分ける。
2. VLM呼び出し単位を「画像全体」から「全体低解像度 + OCR差分ROI再解析」にする。
3. Apple Vision OCRを「ゲート用OCR」としてPP-OCRv6 tiny/smallと比較する。
4. `PaddleOcrRecognizer` の直接利用時defaultが `medium` なので、CLI外利用も速くしたいなら `small` default化を検討。
5. token pruning論文は今すぐ移植せず、Qwen3-VL/MLX側が対応した時に採用する。

Slack作業ログは投稿できていません。`slack_send_message` がこの実行環境に露出しておらず、Slackコネクタの有効化要求も `user_confirmed=false` で未承認でした。
tokens used
317,577
調査時点: **2026-07-13**。結論から言うと、M4 Air 24GBで一番効くのは「モデルを替える」より先に、**入力ピクセル・VLM呼び出し回数・同一/類似フレームの画像特徴キャッシュ**を潰すことです。既存方針の「PaddleOCRで文字を確定、Qwen3-VLは疎に呼ぶ」は正しいです。

**既存記載との差分**
- [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:13) の「OCR専用 + VLM疎」は、PP-OCRv6論文が「VLM OCRは幻覚・局在誤差・コスト問題」と明記しており、より強く支持されます。出典: [PP-OCRv6 arXiv:2606.13108](https://arxiv.org/abs/2606.13108)
- [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:36) の「MLXはMac加点」扱いは更新推奨。2026-07時点では **MLX-VLM / vllm-mlx がM4系の本線候補**です。出典: [mlx-vlm GitHub](https://github.com/Blaizzy/mlx-vlm), [vllm-mlx arXiv:2601.19139](https://arxiv.org/abs/2601.19139)
- [docs/research/issue8_speedup_verification.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/docs/research/issue8_speedup_verification.md:56) の vllm-mlx 検証は未完了。ここが最優先の実測穴です。
- [ffmpeg_extractor.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/src/screen_activity_logger/infrastructure/ffmpeg_extractor.py:52) の長辺1024px制限は妥当。Qwen3-VL公式も `max_pixels` / `fps` / `num_frames` 制御を前提化しています。出典: [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
- [paddle_ocr.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/src/screen_activity_logger/infrastructure/paddle_ocr.py:39) は、doc orientation / unwarping / textline orientation をOFFにしており、画面OCR用途では速度面で正しいです。

**M4 Air 24GBで今すぐ効くもの**
1. **vllm-mlx / mlx-vlm のA/B実測を完了**
   - vllm-mlx論文はM4 Maxで、テキストは llama.cpp 比 `21-87%`高スループット、同一画像再質問は最大`28x`、動画は`24.7x`キャッシュ高速化を報告。M4 Airでは熱制限があるので、既存のABBA測定で確認が必要。
   - 既存ベンチ [scripts/bench_vlm_ab.py](/Users/user/works/iloli/プロジェクト/screen-activity-logger/scripts/bench_vlm_ab.py:1) は方向性が良いです。`--mode cache` を同一画像・隣接類似フレーム・OCR同一フレームで分けて測るべきです。

2. **VLM入力を「長辺」ではなく「視覚トークン予算」で管理**
   - Qwen3-VL公式は画像で `256-1280` visual token、動画で `256-16384` visual token相当の予算指定を例示しています。画面ログではまず **256-512 token相当** から始め、読めないROIだけ再解析がよいです。
   - `max_tokens` も作業ログ用途なら `128-256` で十分。長い自然文を出させるとdecodeが無駄です。

3. **OCR Jaccardゲート + max_gap は維持**
   - 会議・画面共有混在には、scene差分よりOCR内容差分が効きます。既存 [BEST_PRACTICES.md](/Users/user/works/iloli/プロジェクト/screen-activity-logger/BEST_PRACTICES.md:245) の階層型間引き方針は妥当。
   - 推奨初期値: `vlm-skip-threshold=0.82-0.88`, `vlm-min-gap=5-10s`, `vlm-max-gap=120s`。screencastでは閾値を高め、meetingでは低め。

4. **OCRは PP-OCRv6 tiny/small + バッチ/ROI化**
   - PP-OCRv6は tiny/small/medium の3階層。tinyはIntel XeonでPP-OCRv5 mobile比`3.9x`高速と報告。出典: [PP-OCRv6](https://arxiv.org/abs/2606.13108)
   - 画面全体OCRより、前フレーム差分のbounding box周辺だけ再OCRする方が効く可能性が高いです。
   - Apple Vision `VNRecognizeTextRequest` は比較価値あり。macOSネイティブで導入が軽く、低精度でも「ゲート用OCR」には使える可能性があります。出典: [Apple Vision text recognition](https://developer.apple.com/documentation/vision/recognizing-text-in-images)

5. **並列化はASR/OCR/VLMの段階分離**
   - OCRとフレーム差分はCPU寄り、VLMはGPU/Metal寄り。M4 Airはファンレスなので、VLM中に重いOCRを並列しすぎると熱で逆効果です。
   - 推奨: `ASR先行一括 → OCR/差分キュー → VLM単一ワーカー + cache`。長時間動画は5-10分単位に分割。

**ハード更新が必要・効果が大きいもの**
- **32GB以上のApple Silicon**: Ollama公式MLXバックエンドが32GB以上で有効という既存調査があり、24GBでは恩恵が限定的です。M4 Pro/Max以上なら持続GPU負荷とメモリ帯域で効きます。
- **NVIDIA CUDA機**: vLLM本体、AWQ/GPTQ、FlashAttention、TensorRT/OpenVINO/Paddle GPUの最適化が使えます。vLLM量子化の対応表でもAWQ/GPTQはCUDA系が中心です。出典: [vLLM Quantization](https://docs.vllm.ai/en/latest/features/quantization/)
- **ANE直接活用**: Apple Neural EngineはCore ML経由が公式ルートで、PaddleOCRやQwen3-VLをそのままANEで速くする現実解は薄いです。研究的にはANEForge等がありますが、本番向きではありません。出典: [ANEForge arXiv:2606.17090](https://arxiv.org/abs/2606.17090)

**VLM高速化の論文・実務知見**
- **FastVLM**: Apple発。高解像度VLMのボトルネックはvision encoder/token数。TTFT `3.2x`改善、LLaVA-OneVision比で最大`85x`高速TTFT。今のQwen3-VLを直接速くするというより、次期軽量VLM選定の基準。出典: [arXiv:2412.13303](https://arxiv.org/abs/2412.13303)
- **ShowUI**: UI画面向けvisual token selection。冗長token `33%`削減、`1.4x`高速化。GUI画面録画には直結。出典: [arXiv:2411.17465](https://arxiv.org/abs/2411.17465)
- **FocusUI**: UI groundingで30% token保持でも性能低下`3.2%`、最大`1.44x`高速、peak GPU memory `17%`減。出典: [arXiv:2601.03928](https://arxiv.org/abs/2601.03928)
- **FasterVLM / OccamToken / PIO-FVLM**: training-free token pruning系。FasterVLMは95% pruneで90%性能維持、PIO-FVLMは11.1% token保持で97.2%性能維持、OccamTokenはQwen3-VLも対象。実装負荷は高いので、今すぐより研究枠。出典: [FasterVLM](https://arxiv.org/abs/2412.01818), [PIO-FVLM](https://arxiv.org/abs/2602.04657), [OccamToken](https://arxiv.org/abs/2605.29657)
- **Q-VLM / AWQ**: 4bitはメモリ削減には確実。速度はランタイム依存。Q-VLMは13B LLaVAでメモリ`2.78x`圧縮、生成`1.44x`高速。AWQはTinyChatでFP16 HF比`3x+`を報告。出典: [Q-VLM](https://arxiv.org/abs/2410.08119), [AWQ](https://arxiv.org/abs/2306.00978)

**中国語圏・中国系研究のOCR/VLM要約**
- **Qwen3-VL / 通義千問**: 中国語圏ではGUI agent、長動画、32言語OCRを強く押している。日本語作業ログでは本命維持。出典: [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL), [通义千问 中文概要](https://zh.wikipedia.org/wiki/%E9%80%9A%E4%B9%89%E5%8D%83%E9%97%AE)
- **GLM-OCR**: 智譜系。0.9B、MTPでOCRデコードを高速化、PP-DocLayout-V3 + region recognitionの2段構成。画面UIより文書/表/数式向き。出典: [arXiv:2603.10910](https://arxiv.org/abs/2603.10910)
- **DeepSeek-OCR**: 100-800 visual tokens/pageという「光学的コンテキスト圧縮」が特徴。長文書・PDFには強いが、画面録画の逐次UIには重め。出典: [arXiv:2510.18234](https://arxiv.org/abs/2510.18234)
- **GOT-OCR 2.0**: 580Mの統一OCRモデル。markdown/TikZ/SMILES等の構造出力に強い。画面OCRの第一候補ではなく、難読領域の第2パス向き。出典: [arXiv:2409.01704](https://arxiv.org/abs/2409.01704)
- **HunyuanOCR-1.5 / Unlimited OCR**: Tencent/Baidu系。DFlashや定数KV cacheで長いOCR出力を速くする流れ。スクショ単発より、長文書バッチで効く。出典: [HunyuanOCR-1.5](https://arxiv.org/abs/2607.04884), [Unlimited OCR](https://arxiv.org/abs/2606.23050)

**実装優先順位**
1. Issue #8の vllm-mlx vs Ollama 実測を完了。同一画像・類似画像・異なる画像でcache効果を分ける。
2. VLM呼び出し単位を「画像全体」から「全体低解像度 + OCR差分ROI再解析」にする。
3. Apple Vision OCRを「ゲート用OCR」としてPP-OCRv6 tiny/smallと比較する。
4. `PaddleOcrRecognizer` の直接利用時defaultが `medium` なので、CLI外利用も速くしたいなら `small` default化を検討。
5. token pruning論文は今すぐ移植せず、Qwen3-VL/MLX側が対応した時に採用する。

Slack作業ログは投稿できていません。`slack_send_message` がこの実行環境に露出しておらず、Slackコネクタの有効化要求も `user_confirmed=false` で未承認でした。
