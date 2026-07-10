調査範囲: 2025年後半から2026年7月時点の一次情報、公式リポジトリ、arXiv中心。ベンチ結果は原則「著者報告値」として扱ってください。Slack投稿は送信ツールが未接続で、Slack connector install 要求も未承認だったため未実行です。

**全体傾向**
- 2025後半以降のVLMは「高解像度をそのまま読む」より、`dynamic resolution`、visual token圧縮、timestamp/position encoding、GUI/actionデータ、RL post-training が勝ち筋。
- 画面録画用途では、汎用VLM単体より「フレーム抽出 + OCR/GUI grounding + 時系列要約」のパイプラインが堅い。
- OCRは汎用VLM内蔵より、専用OCRの方が軽量・低幻覚・高速な場面が多い。PP-OCRv6、GLM-OCR、DeepSeek-OCR、GOT-OCR、dots.ocr が重要。
- 8〜12GB VRAMでは、7B/8B級VLMの4bit、または2B〜4B級VLM + 専用OCRの分業が現実的。

**中国発VLM**
| モデル | 論文 / ID | 要点 | 本用途への示唆 |
|---|---|---|---|
| Qwen3-VL | Qwen3-VL Technical Report / arXiv:2511.21631 | dense 2B/4B/8B/32B と MoE 30B-A3B/235B-A22B。256K multimodal context、interleaved-MRoPE、DeepStack、text-timestamp alignment。公式カードではGUI操作、長尺動画、32言語OCRを強調。  | 画面録画理解の本命候補。ローカルなら2B/4B、クラウドなら8B以上。 |
| Qwen2.5-VL | Qwen2.5-VL Technical Report / arXiv:2502.13923 | dynamic resolution ViT、Window Attention、absolute time encoding。文書、図表、GUI、長尺動画を対象。 | Qwen3-VL前の安定候補。実装・量子化資産が多い。 |
| MiniCPM-V 4.5 | MiniCPM-V 4.5 / arXiv:2509.18154 | 8B。3D-Resamplerで画像・動画をコンパクト符号化、document/OCR学習を統合、短/長 reasoning のhybrid RL。VideoMMEでQwen2.5-VL 7B比 `46.7%` メモリ、`8.7%` 推論時間と報告。 | 8〜12GB帯で最有力。動画・OCR・日本語要約の分業パイプに向く。 |
| InternVL3 / 3.5 | InternVL3 / arXiv:2504.10479、InternVL3.5 / arXiv:2508.18265 | native multimodal pretraining、V2PE、SFT/MPO。3.5はCascade RL、Visual Resolution Router、Decoupled Vision-Language Deploymentで高速化。  | 精度重視。8〜12GB単体運用には小型版・量子化が前提。 |
| GLM-4.1V / 4.5V | arXiv:2507.01006 | RLCSでSTEM、動画、OCR、GUI agent、長文書を強化。4.1V-9B-Thinkingが多ベンチで大型モデルに競ると報告。公式repoあり。  | GUI reasoningに強い候補。9B級なので12GBでは4bit前提。 |
| GLM-OCR | GLM-OCR Technical Report / arXiv:2603.10910 | 0.9B。CogViT 0.4B + GLM decoder 0.5B。MTPでOCRデコード高速化、PP-DocLayout-V3との2段構成。 | 画面文字・表・文書抽出はVLMに読ませる前にこれ系で処理する価値が高い。 |
| DeepSeek-VL2 | arXiv:2412.10302 | MoE VLM。dynamic tiling vision encoding、DeepSeekMoE、MLAでKV cache削減。1.0B/2.8B/4.5B activated variants。 | 古めだが軽量MoEの設計参考。2025後半以降のDeepSeek-VL3は今回確認できず未確認。 |
| DeepSeek-OCR | DeepSeek-OCR / arXiv:2510.18234 | DeepEncoder + DeepSeek3B-MoE-A570M。100〜800 visual tokens/page級の文書圧縮OCR。公式repoは2025/10/20 release、vLLM対応も記載。  | 長い画面ログやPDFを「画像トークン圧縮」する発想が重要。 |
| Kimi-VL | Kimi-VL Technical Report / arXiv:2504.07491 | MoE、activated 2.8B。128K context、MoonViT、OSWorld、LongVideoBench、ScreenSpot-Proを報告。Thinking版はCoT SFT + RL。  | 低active parameterでGUI/長動画に強い設計。ローカル候補として要検証。 |

**米国発VLM**
| モデル | 論文 / ID | 要点 | 本用途への示唆 |
|---|---|---|---|
| Molmo / PixMo | arXiv:2409.17146 | AI2。open weights + open data。外部VLM蒸留に依存しない高品質データ、詳細caption、free-form QA、2D pointing。 | UI要素のpointing/grounding思想が画面理解に有効。 |
| Llama Vision / Llama 4 | Llama 3.2は11B/90B vision、Llama 4はScout/Maverickがnative multimodal MoE。Llama 4の技術整理論文 arXiv:2601.11659、ただし公式技術レポートそのものではなく公開情報整理。  | 8〜12GBではLlama Vision 11Bも重い。画面録画用途では小型専用VLMに劣る可能性。 |
| NVLM 1.0 | arXiv:2409.11402 | NVIDIA。decoder-onlyとcross-attention型を比較し、1-D tile-taggingで高解像度/OCRを改善。データ品質とタスク多様性を重視。 | OCR/高解像度ではtile設計とデータ品質が効く。 |
| Eagle 2.5 | arXiv:2504.15271 | NVIDIA系。long-context VLM。Automatic Degrade Sampling、Image Area Preservation、Eagle-Video-110K。8BでVideo-MME `72.4%`、512 framesと報告。 | 長尺動画の実務設計に直結。録画解析では「多フレーム投入 + 劣化制御」が重要。 |
| Apple FastVLM | FastVLM / arXiv:2412.13303、公式repo | FastViTHDで高解像度入力時のvision latencyとvisual token数を削減。TTFT `3.2x`改善、LLaVA-OneVision比で最大 `85x` faster TTFTと報告。  | 画面は高解像度なので、モデルサイズよりvision encoder/token設計がボトルネック。 |
| Apple MM1.5 | arXiv:2409.20566 | OCR data、synthetic captions、visual instruction tuningを体系的に検証。MM1.5-Video、MM1.5-UIを提示。 | UI特化データ混合の重要性。 |
| Microsoft Phi-4 multimodal / reasoning vision | arXiv:2503.01743、arXiv:2603.03975 | 3.8B級、LoRA/adapterでvision/speechを統合。reasoning-vision-15BはUI理解と小型推論を重視。  | 小型運用の参考。ただし15Bは12GBでは厳しめ。 |

**画面 / GUI理解**
| 論文 | ID | 要点 | 示唆 |
|---|---|---|---|
| UI-TARS | arXiv:2501.12326 | screenshotのみでGUI操作。GUI screenshot dataset、unified action modeling、System-2 reasoning、reflective online traces。 | 画面録画を「操作履歴」として読むなら、スクショ列だけでなくaction/state推定が必要。 |
| UI-TARS-2 | arXiv:2509.02544 | multi-turn RL、data flywheel、file/terminalを含むhybrid GUI environment。OSWorld、AndroidWorld等で改善。 | 実務では単発画像理解より、複数ステップの状態遷移理解が中心。 |
| OS-ATLAS | arXiv:2410.23218 | 13M超GUI elementsのcross-platform grounding corpus。Windows/Linux/macOS/Android/Web。 | 汎用VLMだけではUI element groundingが弱い。専用groundingモデルが欲しい。 |
| ShowUI | arXiv:2411.17465 | UI-guided visual token selectionで冗長tokenを33%削減、2Bでzero-shot screenshot grounding 75.1%。 | 8〜12GBではこの方向が現実的。 |
| Aguvis | arXiv:2412.04454 | pure vision GUI agent。GUI trajectories、grounding、planning/reasoningの2段訓練。 | アクセシビリティツリー無しの録画解析に近い。 |
| OS-Genesis | arXiv:2412.19723 | reverse task synthesisでGUI trajectoryを自動構築。 | 操作ログ生成には「後からタスク名を復元する」設計が合う。 |
| MS4UI | arXiv:2506.12623 | UI instructional videos 2,413本、167時間。segment、text summary、key framesを人手注釈。既存手法が苦戦と報告。 | 「画面録画→作業手順要約」に最も直結。評価データとして最優先。 |

**動画理解**
- 長尺動画ではuniform samplingだけだと操作の細部を落とす。Eagle 2.5のAutomatic Degrade Sampling / Image Area Preservation、LongVILA-R1の8192 frames対応、MS4UIのsegment/keyframe設計が実務寄り。  
- token圧縮は3系統: visual token selection、KV compression、query/task-aware compression。Video-X²Lはbi-level KV compression + selective KV re-loading、FLoCはtraining-free/model-agnosticな代表token選択。 
- 実務では「1〜2fps uniform + scene/keyframe検出 + UI変化点抽出」を併用し、重要区間だけ高fps再解析するのが妥当。

**OCRとVLMの使い分け**
- PP-OCRv6 / arXiv:2606.13108: 1.5M〜34.5M parametersでbillion-scale VLMをOCRタスクで上回ると報告。VLMはOCRで幻覚・局在誤差・コスト問題があると明記。
- GLM-OCR / arXiv:2603.10910: 小型0.9B、layout analysis + region recognitionの実務型。
- GOT-OCR2.0 / arXiv:2409.01704: 580M、markdown/TikZ/SMILES/Kernなど構造出力、region-level interactive OCR。
- dots.ocr / arXiv:2512.02498: layout detection、text recognition、relation理解を単一VLMで統合。126言語XDocParseも提示。
- 結論: 画面録画では、まずOCRで文字・UIラベルを確定し、VLMには「画像全体の意味」「操作意図」「変化理由」を担当させる方が安定。

**8〜12GB VRAM運用**
- AWQはsalient weight channelをactivation分布で保護し、4bit VLM/LLMを実用化する代表手法。初期論文はmultimodalにも有効と報告。
- GGUF/llama.cppは2〜8bit量子化、KV cache量子化、部分offloadが強み。ただしGGUF量子化には安全性・改ざん検知上のリスク研究もある。 
- Qwen3系量子化の実証では、中程度bit幅は有望だがultra-low precisionでは劣化が出る。
- 現実的構成: `MiniCPM-V 4.5 8B 4bit`、`Qwen3-VL 2B/4B`、`ShowUI 2B`、`GLM-OCR/GOT-OCR/PP-OCR`の分業。7B/8Bで動画を長く入れる場合はFlashAttention、frame数制限、解像度制限が必須。
- 解像度は最初から上げすぎない。UI文字が読める最低限、例: 720p相当またはクロップ再解析。全フレーム高解像度投入はVRAMを食うだけでなく要約品質も落ちやすい。

**画面録画→日本語作業ログ化への5行示唆**
1. まず録画を `変化点/keyframe + 1fps程度uniform` に分解し、重要区間だけ高fpsで再解析する。  
2. OCR専用モデルで画面文字、ボタン名、ファイル名、URLを先に確定し、VLMの幻覚を抑える。  
3. VLMは「何をしたか」「なぜ次の画面になったか」「作業単位の区切り」を推定させる。  
4. 8〜12GBならQwen3-VL 2B/4BまたはMiniCPM-V 4.5 4bit + OCR専用が現実的。  
5. 最終ログは時刻、アプリ、操作、観測結果、未確定事項を分け、日本語で短く構造化するのがよい。  
