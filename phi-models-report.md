# Microsoft Phi Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** Microsoft Research's Phi series is a small-model
research line built around the "Textbooks Are All You Need" thesis: filtered
web + synthetic textbook-quality data trains models that punch above their
parameter count. Canonical `lab` sources for each generation are (1) the
Microsoft Research blog post or Azure Blog announcement, (2) the arXiv
technical report, and (3) the HuggingFace model card under
`huggingface.co/microsoft`. Wikipedia coverage of Phi is unusually thin —
its article only documents Phi-1, Phi-3-mini and Phi-4-reasoning-vision —
so cross-reference goes to VentureBeat, MarkTechPost, Neowin, and
SiliconANGLE rather than the usual Wikipedia spine.

**Licensing — three buckets.**
1. **Microsoft Research License (non-commercial)** — Phi-1, Phi-1.5, Phi-2
   (initial). Research-only at launch.
2. **MIT** — Phi-2 (relicensed Jan 2024), and every Phi-3, Phi-3.5, Phi-4
   variant since. The defining Phi-3 break: Microsoft committed to MIT for
   the entire generation forward, making Phi the most permissively-licensed
   frontier-adjacent small-model family.
3. **Closed (Windows-bundled)** — Phi-Silica is shipped as a Copilot+ PC
   Windows component (no HF weights, no license terms exposed); functionally
   closed even though derived from Phi-3-mini.

**Frontier benchmark applicability.** Phi models target the <15B parameter
band — they are NOT frontier generalists by SWE-bench / Terminal-Bench
standards. The lineage's primary benchmark claims are MMLU, GSM8K, MATH,
HumanEval, MBPP, GPQA, AIME (reasoning generation), and on the multimodal
side MMMU / MathVista / ChartQA / AI2D. SWE-bench Verified, SWE-bench Pro,
LiveCodeBench v6, and Terminal-Bench 2.0 are NOT reported by Microsoft for
this family — these models are below the size threshold those benches target.
Where third-party LiveCodeBench numbers exist (Phi-4-reasoning-plus) they
are flagged. Treat the Phi table as a "small-model frontier" comparison
rather than a direct apples-to-apples with Opus/Gemini/GPT-5.

**Phi-4-reasoning trunk.** The April 30, 2025 reasoning release was a
coordinated drop: Phi-4-reasoning (SFT only) + Phi-4-reasoning-plus (SFT +
RL, ~50% more tokens) + Phi-4-mini-reasoning (3.8B, DeepSeek-R1 distilled).
This is where Phi crossed from "small-model curiosity" into
o1-mini-competitive territory on math reasoning.

Convention: dates are **announcement / first availability**.

---

### Phi-1

- Release: 2023-06-20 (arXiv "Textbooks Are All You Need")
- Status: legacy (Python-coding research artifact, superseded by Phi-1.5/2)
- Context: 2K
- Modality: text only (code-focused)
- License: Microsoft Research License (non-commercial)
- Price: open weights, no API
- Notable: 1.3B dense decoder. Trained 4 days on 8 A100s on 7B tokens (6B "textbook-quality" web + 1B GPT-3.5 synthetic exercises). The proof-of-concept that small + high-quality data could match much larger code models. Establishes the synthetic-textbook training thesis that defines the entire Phi line.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/publication/textbooks-are-all-you-need/
    title: "Textbooks Are All You Need"
    date: 2023-06
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2306.11644
    title: "Textbooks Are All You Need (Phi-1 technical report)"
    date: 2023-06
  - kind: coverage
    tag: 3p
    url: https://the-decoder.com/microsofts-tiny-phi-1-language-model-shows-the-importance-of-data-quality-in-ai-training/
    title: "Microsoft's tiny Phi-1 language model shows the importance of data quality"
    date: 2023-06
    publisher: The Decoder

Benchmarks (lab, code-focused):
- HumanEval (pass@1): 50.6 [lab] src=https://arxiv.org/abs/2306.11644 date=2023-06
- MBPP (pass@1): 55.5 [lab] src=https://arxiv.org/abs/2306.11644 date=2023-06

Notes: Beat 10× larger code models on HumanEval/MBPP with 100× less data. No MMLU / GSM8K reported (code-only model). Original license blocked commercial use.

---

### Phi-1.5

- Release: 2023-09-11
- Status: legacy (superseded by Phi-2)
- Context: 2K
- Modality: text only
- License: Microsoft Research License (non-commercial) → MIT (relicensed alongside Phi-2 in Jan 2024)
- Price: open weights, no API
- Notable: 1.3B dense decoder, same architecture as Phi-1 but generalist. Trained 8 days on 32 A100-40G on 30B tokens (Phi-1 data + NLP-synthetic textbooks). First Phi to demonstrate the synthetic-data thesis works for general reasoning, not just code. Outperformed Llama-2-7B on AGIEval at 5× fewer parameters.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/publication/textbooks-are-all-you-need-ii-phi-1-5-technical-report/
    title: "Textbooks Are All You Need II: phi-1.5 technical report"
    date: 2023-09
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2309.05463
    title: "Textbooks Are All You Need II"
    date: 2023-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/phi-1_5
    title: "phi-1_5 HF model card"
    date: 2023-09
  - kind: coverage
    tag: 3p
    url: https://winbuzzer.com/2023/09/12/microsofts-new-phi-1-5-1-3b-model-outperforms-llama2-7b-in-benchmarks-xcxwbn/
    title: "Microsoft's New Phi-1.5 1.3B Model Outperforms Llama2-7B"
    date: 2023-09
    publisher: WinBuzzer

Benchmarks (lab, base model):
- WinoGrande: 73.4 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09
- ARC-Easy: 75.6 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09
- ARC-Challenge: 48.0 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09
- BoolQ: 76.8 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09
- HumanEval (pass@1): 41.4 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09
- GSM8K: 40.2 [lab] src=https://arxiv.org/abs/2309.05463 date=2023-09

Notes: MMLU not reported in the v1 paper. Base model only, no instruct tune at launch.

---

### Phi-2

- Release: 2023-12-12 (announced); 2024-01-06 (MIT relicense)
- Status: legacy (superseded by Phi-3-mini)
- Context: 2K
- Modality: text only
- License: Microsoft Research License → **MIT** (Jan 6, 2024)
- Price: open weights, no API
- Notable: 2.7B dense decoder. The breakout Phi — matched or beat Mistral 7B and Llama-2 13B on aggregate benchmarks, with 5× fewer parameters. Trained on 1.4T tokens (synthetic + filtered web). The Jan 2024 MIT relicense made it the first commercially-usable Phi and a massive community-distillation backbone. Microsoft explicitly compared to Gemini Nano-2 in the launch blog, calling Phi-2 "matching or outperforming" it.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/
    title: "Phi-2: The surprising power of small language models"
    date: 2023-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/phi-2
    title: "phi-2 HF model card"
    date: 2023-12
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2024/Jan/6/relicense-phi-2-as-mit/
    title: "Microsoft Research relicense Phi-2 as MIT"
    date: 2024-01
    publisher: Simon Willison
  - kind: coverage
    tag: 3p
    url: https://siliconangle.com/2023/12/12/microsoft-debuts-2-7b-parameter-phi-2-model-outperforms-many-larger-language-models/
    title: "Microsoft debuts 2.7B-parameter Phi-2 model"
    date: 2023-12
    publisher: SiliconANGLE

Benchmarks (lab aggregate, base model):
- BBH (3-shot CoT): 59.2 [lab] src=https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/ date=2023-12
- Commonsense Reasoning (avg): 68.8 [lab] src=https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/ date=2023-12
- Language Understanding (avg): 62.0 [lab] src=https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/ date=2023-12
- Math (avg, GSM8K 8-shot): 61.1 [lab] src=https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/ date=2023-12
- Coding (avg, HumanEval+MBPP 3-shot): 53.7 [lab] src=https://www.microsoft.com/en-us/research/blog/phi-2-the-surprising-power-of-small-language-models/ date=2023-12

Notes: No arXiv tech report (only the blog post). Microsoft never published a Phi-2 paper — it's a transitional model bridging Phi-1.5's research artifact and Phi-3's full release apparatus.

---

### Phi-3-mini (3.8B)

- Release: 2024-04-23 (Microsoft Build 2024 preview; weights April)
- Status: legacy (superseded by Phi-3.5-mini → Phi-4-mini)
- Context: 4K and 128K variants
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Studio hosted
- Notable: First Phi with multiple context-length SKUs. 3.8B dense, 3.3T tokens. The "phone-class" model — Microsoft explicitly positioned it as running locally on iPhone with 4-bit quant at 12 tokens/s. The MIT license + small footprint + GPT-3.5-class quality made it the dominant on-device baseline for late 2024.
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/introducing-phi-3-redefining-whats-possible-with-slms/
    title: "Introducing Phi-3: Redefining what's possible with SLMs"
    date: 2024-04
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2404.14219
    title: "Phi-3 Technical Report"
    date: 2024-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3-mini-128k-instruct
    title: "Phi-3-mini-128k-instruct HF model card"
    date: 2024-04

Benchmarks (lab, instruct, 128k variant):
- MMLU (5-shot): 69.7 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04
- HumanEval (0-shot): 60.4 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04
- GSM8K (8-shot CoT): 85.3 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04
- MBPP (3-shot): 70.0 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04
- BBH (3-shot): 72.1 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04
- GPQA (0-shot): 29.7 [lab] src=https://huggingface.co/microsoft/Phi-3-mini-128k-instruct date=2024-04

Notes: Both 4K and 128K context SKUs ship simultaneously — atypical pattern. Released a 4-bit ONNX build for on-device deployment from day one.

---

### Phi-3-small (7B)

- Release: 2024-05-21 (Microsoft Build 2024)
- Status: legacy (line dead-ended; replaced by Phi-3.5-MoE for the >mini slot)
- Context: 8K and 128K variants
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Studio hosted
- Notable: 7B dense decoder. Mid-tier of the Phi-3 release. Tokenizer switch (tiktoken-100k vocab) vs mini. Trained on 4.8T tokens. The "small" slot was the only Phi-3 SKU NOT carried forward — Phi-3.5 jumped to MoE for the mid-size; Phi-4 went 14B-only.
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/new-models-added-to-the-phi-3-family-available-on-microsoft-azure/
    title: "New models added to the Phi-3 family"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3-small-128k-instruct
    title: "Phi-3-small-128k-instruct HF model card"
    date: 2024-05

Benchmarks (lab, instruct, 128k variant):
- MMLU (5-shot): 75.5 [lab] src=https://huggingface.co/microsoft/Phi-3-small-128k-instruct date=2024-05
- HumanEval (0-shot): 59.1 [lab] src=https://huggingface.co/microsoft/Phi-3-small-128k-instruct date=2024-05
- GSM8K (8-shot CoT): 87.3 [lab] src=https://huggingface.co/microsoft/Phi-3-small-128k-instruct date=2024-05
- MBPP (3-shot): 70.3 [lab] src=https://huggingface.co/microsoft/Phi-3-small-128k-instruct date=2024-05
- BBH (3-shot): 77.6 [lab] src=https://huggingface.co/microsoft/Phi-3-small-128k-instruct date=2024-05

Notes: MATH, MMLU-Pro, GPQA not separately reported in the model card.

---

### Phi-3-medium (14B)

- Release: 2024-05-21 (Microsoft Build 2024)
- Status: legacy (superseded by Phi-4 at the same 14B parameter slot)
- Context: 4K and 128K variants
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Studio hosted
- Notable: 14B dense. Top of the Phi-3 family. Trained 42 days on 512 H100-80G on 4.8T tokens. The direct architectural predecessor to Phi-4 — same parameter count, refined recipe.
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/new-models-added-to-the-phi-3-family-available-on-microsoft-azure/
    title: "New models added to the Phi-3 family"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3-medium-128k-instruct
    title: "Phi-3-medium-128k-instruct HF model card"
    date: 2024-05

Benchmarks (lab, instruct, 128k variant):
- MMLU (5-shot): 76.6 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05
- BBH (3-shot): 77.9 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05
- HumanEval (0-shot): 58.5 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05
- MATH: 52.9 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05
- GSM8K (8-shot CoT): 87.5 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05
- MBPP (3-shot): 73.8 [lab] src=https://huggingface.co/microsoft/Phi-3-medium-128k-instruct date=2024-05

Notes: MMLU-Pro and GPQA not reported in this generation's cards.

---

### Phi-3-vision (4.2B)

- Release: 2024-05-21 (Microsoft Build 2024)
- Status: legacy (superseded by Phi-3.5-vision)
- Context: 128K
- Modality: text + image (in), text (out)
- License: MIT
- Price: open weights; Azure AI Studio hosted
- Notable: 4.2B (3.8B Phi-3-mini backbone + image encoder + connector). First multimodal Phi. Targeted chart/graph/table reasoning + general visual QA.
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/new-models-added-to-the-phi-3-family-available-on-microsoft-azure/
    title: "Phi-3-vision announced"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3-vision-128k-instruct
    title: "Phi-3-vision-128k-instruct HF model card"
    date: 2024-05

Benchmarks (lab claimed): outperforms Claude 3 Haiku and Gemini 1.0 Pro V on chart/graph/table reasoning at 128K context. Detailed per-bench scores not consolidated in the model card.

Notes: Released alongside Phi-3-small and Phi-3-medium at Build 2024. First Phi multimodal capability.

---

### Phi-3.5-mini (3.8B)

- Release: 2024-08-20
- Status: legacy (superseded by Phi-4-mini)
- Context: 128K
- Modality: text only, **multilingual** (22+ languages)
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 3.8B dense. Same parameter count as Phi-3-mini but trained on more multilingual data. Major bump on long-context (RepoQA, GovReport). Often outperformed Gemini 1.5 Flash on targeted long-context benches.
- Sources:
  - kind: announcement
    tag: lab
    url: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/discover-the-new-multi-lingual-high-quality-phi-3-5-slms/4225280
    title: "Discover the new multi-lingual Phi-3.5 SLMs"
    date: 2024-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3.5-mini-instruct
    title: "Phi-3.5-mini-instruct HF model card"
    date: 2024-08
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/microsoft-releases-powerful-new-phi-3-5-models-beating-google-openai-and-more
    title: "Microsoft releases powerful new Phi-3.5 models"
    date: 2024-08
    publisher: VentureBeat

Benchmarks (lab, instruct):
- MMLU (5-shot): 69.0 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- MMLU-Pro (0-shot CoT): 47.4 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- GPQA (0-shot CoT): 27.2 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- HumanEval (0-shot): 62.8 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- MATH (0-shot CoT): 48.5 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- GSM8K (8-shot CoT): 86.2 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08
- BBH (3-shot): 69.0 [lab] src=https://huggingface.co/microsoft/Phi-3.5-mini-instruct date=2024-08

Notes: First Phi with credible multilingual claims.

---

### Phi-3.5-MoE (16×3.8B / 6.6B active)

- Release: 2024-08-20
- Status: legacy (no direct successor — MoE line was a one-off; Phi-4 went back to dense 14B)
- Context: 128K
- Modality: text only, multilingual
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 41.9B total / 6.6B active (16 experts × 3.8B, top-2 routing). Trained on 4.9T tokens (10% multilingual) on 512 H100s. The only Phi MoE. Close to GPT-4o-mini on aggregate (lab claims 69.2 average across 80 benchmarks vs GPT-4o-mini's 74.9). MoE direction was abandoned in Phi-4 — Microsoft preferred dense scaling.
- Sources:
  - kind: announcement
    tag: lab
    url: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/discover-the-new-multi-lingual-high-quality-phi-3-5-slms/4225280
    title: "Phi-3.5 SLMs"
    date: 2024-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3.5-MoE-instruct
    title: "Phi-3.5-MoE-instruct HF model card"
    date: 2024-08
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2024/08/21/microsoft-ai-releases-phi-3-5-mini-moe-and-vision-with-128k-context-multilingual-and-mit-license/
    title: "Microsoft Releases Phi-3.5 mini, MoE and Vision"
    date: 2024-08
    publisher: MarkTechPost

Benchmarks (lab, instruct):
- MMLU (5-shot): 78.9 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- MMLU-Pro (0-shot CoT): 54.3 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- BBH (0-shot CoT): 79.1 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- GPQA (0-shot CoT): 36.8 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- HumanEval (0-shot): 70.7 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- MATH (0-shot CoT): 59.5 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- GSM8K (8-shot CoT): 88.7 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08
- MBPP (3-shot): 80.8 [lab] src=https://huggingface.co/microsoft/Phi-3.5-MoE-instruct date=2024-08

Notes: 22-language multilingual support. Aggregate 69.2 score across 80 benchmarks vs Llama-3.1-8B 61.0 and Mistral-Nemo-12B 61.3.

---

### Phi-3.5-vision (4.2B)

- Release: 2024-08-20
- Status: legacy (multimodal line continued via Phi-4-multimodal)
- Context: 128K
- Modality: text + image (in), text (out); enhanced multi-image / video frame reasoning
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 4.2B. Multi-frame and chart/table reasoning improvements over Phi-3-vision. Same Phi-3-mini backbone + tuned vision encoder.
- Sources:
  - kind: announcement
    tag: lab
    url: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/discover-the-new-multi-lingual-high-quality-phi-3-5-slms/4225280
    title: "Phi-3.5-vision announced"
    date: 2024-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-3.5-vision-instruct
    title: "Phi-3.5-vision-instruct HF model card"
    date: 2024-08

Benchmarks: Microsoft reports gains over Phi-3-vision across MMMU-mini, ScienceQA, ChartQA, AI2D. Detailed numbers in the HF model card but consistent with 4B-tier multimodal models — not frontier.

---

### Phi-Silica (3.3B)

- Release: 2024-05 (announced at Build); shipped Late 2024 via Windows
- Status: current (Windows-bundled, regularly updated via Windows Update)
- Context: ~2K (on-device tuned)
- Modality: text only
- License: closed (Windows component; no HF weights, no public terms)
- Price: free with Copilot+ PC
- Notable: 3.3B parameter NPU-optimized derivative of Phi-3-mini. Distilled and quantized to fit Snapdragon X / Intel Lunar Lake / AMD Ryzen AI NPUs. Powers Copilot+ PC features: Click-to-Do, Recall summarization, contextual local AI. Updated independently of Windows via dedicated AI Component Update channel (KB articles e.g. KB5075032, KB5084167, KB5089865 through 2025-2026). Not a research model — pure productization.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blogs.windows.com/windowsexperience/2024/12/06/phi-silica-small-but-mighty-on-device-slm/
    title: "Phi Silica, small but mighty on-device SLM"
    date: 2024-12
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/microsoft-introduces-phi-silica-a-3-3b-parameter-model-made-for-copilot-pc-npus
    title: "Microsoft introduces Phi-Silica"
    date: 2024-05
    publisher: VentureBeat

Benchmarks: not published. Microsoft does not release per-benchmark scores for Phi-Silica.

Notes: Specialist on-device productized model — listed for lineage completeness, not for the frontier table.

---

### Phi-4 (14B)

- Release: 2024-12-12 (research preview on Azure AI Foundry); HF weights early Jan 2025
- Status: current (flagship dense Phi)
- Context: 16K
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 14B dense decoder. Trained 21 days on 1920 H100-80G on 9.8T tokens (synthetic + filtered web; GPT-4o used as a teacher). The first Phi to claim **above-teacher** performance on hard benchmarks: GPQA 56.1 vs GPT-4o 50.6, MATH 80.4 vs GPT-4o 74.6. Marks the transition from "small-model curiosity" to "frontier-adjacent at 14B."
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/blog/phi-4-microsofts-newest-small-language-model-specializing-in-complex-reasoning/
    title: "Phi-4: Microsoft's newest small language model"
    date: 2024-12
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2412.08905
    title: "Phi-4 Technical Report"
    date: 2024-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/phi-4
    title: "phi-4 HF model card"
    date: 2025-01
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/microsoft-makes-powerful-phi-4-model-fully-open-source-on-hugging-face
    title: "Microsoft makes powerful Phi-4 model fully open-source on Hugging Face"
    date: 2025-01
    publisher: VentureBeat

Benchmarks (lab, instruct):
- MMLU: 84.8 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- GPQA Diamond: 56.1 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- MATH: 80.4 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- MGSM: 80.6 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- HumanEval: 82.6 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- DROP: 75.5 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- SimpleQA: 3.0 [lab] src=https://huggingface.co/microsoft/phi-4 date=2024-12
- AMC-10/12: 91.8 [lab] src=https://arxiv.org/abs/2412.08905 date=2024-12

Notes: Knowledge weakness — SimpleQA 3.0 vs GPT-4o 39.4 — highlights the Phi tradeoff: math/code/reasoning at the cost of factual world-knowledge breadth. MIT license, fits consumer GPUs with 4-bit quant.

---

### Phi-4-multimodal (5.6B)

- Release: 2025-02-27
- Status: current
- Context: 128K
- Modality: text + image + audio (in), text (out)
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 5.6B. Phi-4-mini-instruct backbone + vision encoder + speech encoder + adapters (mixture-of-LoRAs architecture). First Phi unified multimodal model handling text/audio/vision in one representation space. Ranked #1 on HuggingFace OpenASR leaderboard at launch (WER 6.14%).
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/empowering-innovation-the-next-generation-of-the-phi-family/
    title: "Empowering innovation: The next generation of the Phi family"
    date: 2025-02
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-multimodal-instruct
    title: "Phi-4-multimodal-instruct HF model card"
    date: 2025-02
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2503.01743
    title: "Phi-4-Mini Technical Report (covers multimodal extension)"
    date: 2025-03
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/microsofts-new-phi-4-ai-models-pack-big-performance-in-small-packages
    title: "Microsoft's new Phi-4 AI models pack big performance in small packages"
    date: 2025-02
    publisher: VentureBeat

Benchmarks (lab):
- MMMU: 55.1 [lab] src=https://huggingface.co/microsoft/Phi-4-multimodal-instruct date=2025-02
- MMBench: 86.7 [lab] src=https://huggingface.co/microsoft/Phi-4-multimodal-instruct date=2025-02
- DocVQA: 93.2 [lab] src=https://huggingface.co/microsoft/Phi-4-multimodal-instruct date=2025-02
- TextVQA: 75.6 [lab] src=https://huggingface.co/microsoft/Phi-4-multimodal-instruct date=2025-02
- OpenASR WER: 6.14 [lab] src=https://huggingface.co/microsoft/Phi-4-multimodal-instruct date=2025-03

Notes: 23 text languages, 8 audio languages, English vision only.

---

### Phi-4-mini (3.8B)

- Release: 2025-02-27
- Status: current
- Context: 128K
- Modality: text only, multilingual (23 languages)
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: 3.8B dense, 32 transformer layers, grouped-query attention, 200K vocab. Trained 21 days on 512 A100-80G on 5T tokens. Direct successor to Phi-3.5-mini at the 3.8B slot. Tokenizer expanded from 32K to 200K (multilingual + code).
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/empowering-innovation-the-next-generation-of-the-phi-family/
    title: "Empowering innovation: The next generation of the Phi family"
    date: 2025-02
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-mini-instruct
    title: "Phi-4-mini-instruct HF model card"
    date: 2025-02
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2503.01743
    title: "Phi-4-Mini Technical Report"
    date: 2025-03

Benchmarks (lab, instruct):
- MMLU (5-shot): 67.3 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- GPQA (0-shot CoT): 25.2 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- MATH (0-shot CoT): 64.0 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- GSM8K (8-shot CoT): 88.6 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- BBH (0-shot CoT): 70.4 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- Arena Hard: 32.8 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02
- MGSM (0-shot CoT): 63.9 [lab] src=https://huggingface.co/microsoft/Phi-4-mini-instruct date=2025-02

Notes: 23-language support; "ground truth" mini for the Phi-4-multimodal backbone.

---

### Phi-4-reasoning (14B)

- Release: 2025-04-30
- Status: current
- Context: 32K (extended to 64K experimentally)
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: Phi-4 base + SFT only (no RL). 16B-token SFT corpus (~8.3B unique). Output structured as `<think>...</think>` reasoning + summary. First Phi to claim o1-mini-class math performance at 14B.
- Sources:
  - kind: announcement
    tag: lab
    url: https://azure.microsoft.com/en-us/blog/one-year-of-phi-small-language-models-making-big-leaps-in-ai/
    title: "One year of Phi"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2504.21318
    title: "Phi-4-reasoning Technical Report"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-reasoning
    title: "Phi-4-reasoning HF model card"
    date: 2025-04

Benchmarks (lab):
- AIME 2024: 75.3 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- AIME 2025: 62.9 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- GPQA Diamond: 65.8 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- MATH-500: ~91.4 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- HumanEvalPlus: 88.8 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- LiveCodeBench (Aug 24-Feb 25): 51.4 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- MMLU-Pro: 75.4 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04
- IFEval: 83.4 [lab] src=https://arxiv.org/abs/2504.21318 date=2025-04

Notes: Trained 2.5 days on 32 H100-80G. SFT-only baseline against which `-plus` (with RL) is compared.

---

### Phi-4-reasoning-plus (14B)

- Release: 2025-04-30
- Status: current (flagship Phi reasoning)
- Context: 32K
- Modality: text only
- License: MIT
- Price: open weights; Azure AI Foundry hosted
- Notable: Phi-4-reasoning + reinforcement learning. Generates ~50% more reasoning tokens for ~3-5pp accuracy gain. Approaches full DeepSeek-R1 on math reasoning at 14B vs R1's 671B-MoE.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/articles/phi-reasoning-once-again-redefining-what-is-possible-with-small-and-efficient-ai/
    title: "Phi-Reasoning: redefining what is possible with small and efficient AI"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-reasoning-plus
    title: "Phi-4-reasoning-plus HF model card"
    date: 2025-04
  - kind: coverage
    tag: 3p
    url: https://siliconangle.com/2025/05/01/microsoft-releases-small-mighty-phi-4-reasoning-models-outperform-larger-models/
    title: "Microsoft releases small but mighty Phi-4 reasoning AI models"
    date: 2025-05
    publisher: SiliconANGLE

Benchmarks (lab):
- AIME 2024: 81.3 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- AIME 2025: 78.0 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- OmniMath: 81.9 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- GPQA Diamond: 68.9 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- LiveCodeBench: 53.1 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- MMLU-Pro: 76.0 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- HumanEvalPlus: 92.3 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- IFEval Strict: 84.9 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04
- ArenaHard: 79.0 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-plus date=2025-04

Notes: Note LiveCodeBench (without v6 specification, contemporary window Aug 24-Feb 25) is reported but is NOT the frontier LiveCodeBench v6 — direct comparison to v6 numbers from frontier labs is unsafe.

---

### Phi-4-mini-reasoning (3.8B)

- Release: 2025-04-30
- Status: current (smallest reasoning Phi)
- Context: 128K
- Modality: text only
- License: MIT
- Price: open weights
- Notable: Phi-4-mini + reasoning distillation from DeepSeek-R1. Math-specialized for mobile/embedded. Base model's AIME-2024 jumped from 10% (Phi-4-mini) to 57.5% with distilled reasoning.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/articles/phi-reasoning-once-again-redefining-what-is-possible-with-small-and-efficient-ai/
    title: "Phi-Reasoning announcement"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2504.21233
    title: "Phi-4-Mini-Reasoning: Exploring the Limits of Small Reasoning Language Models in Math"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-mini-reasoning
    title: "Phi-4-mini-reasoning HF model card"
    date: 2025-04

Benchmarks (lab):
- AIME 2024: 57.5 [lab] src=https://arxiv.org/abs/2504.21233 date=2025-04
- MATH-500: 94.6 [lab] src=https://arxiv.org/abs/2504.21233 date=2025-04
- GPQA Diamond: 52.0 [lab] src=https://arxiv.org/abs/2504.21233 date=2025-04

Notes: Specialized for math; matches o1-mini on MATH-500 at 3.8B. Trained primarily on R1-distilled math traces.

---

### Phi-Ground (research; "Phi-Ground-Any" on HF)

- Release: 2026 (Microsoft Research Asia article + HF preview)
- Status: current (specialist; GUI grounding)
- Context: not specified (vision-language)
- Modality: text + screen image (in), grounding coordinates (out)
- License: MIT (per HF org convention; HF card to confirm)
- Price: open weights
- Notable: Family of GUI-grounding models for computer-use agents. Built on Phi backbone, fine-tuned on ~450K computer-use records + Phi-Ground-specific reference-expression data. State-of-the-art on five grounding benches at its parameter band; on Showdown surpasses OpenAI Operator and Claude Computer Use.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/articles/phi-ground-improving-how-ai-agents-navigate-screen-interface/
    title: "Phi-Ground: Improving how AI agents navigate screen interface"
    date: 2026
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-Ground-Any
    title: "Phi-Ground-Any HF model card"
    date: 2026

Benchmarks (lab):
- ScreenSpot-Pro: 55.0 [lab] src=https://www.microsoft.com/en-us/research/articles/phi-ground-improving-how-ai-agents-navigate-screen-interface/ date=2026
- UI-Vision: 36.2 [lab] src=https://www.microsoft.com/en-us/research/articles/phi-ground-improving-how-ai-agents-navigate-screen-interface/ date=2026

Notes: Specialist model. Listed for lineage completeness — not a frontier generalist; benchmark slate doesn't overlap with the standard 18.

---

### Phi-4-reasoning-vision-15B

- Release: 2026-03-04
- Status: current (latest Phi flagship as of May 2026)
- Context: 16,384
- Modality: text + image (in), text (out); **hybrid reasoning** (`<think>` vs `<nothink>`)
- License: MIT
- Price: open weights; Microsoft Foundry hosted
- Notable: Phi-4-reasoning backbone + SigLIP-2 vision encoder, mid-fusion architecture. **Self-selects between thinking and direct inference** — the headline behavior: spends tokens only when the task warrants. Trained on 200B multimodal tokens (atop the 16B reasoning tokens, atop Phi-4's 400B unique base tokens) on 240 B200 GPUs over 4 days. Dynamic resolution up to 3,600 visual tokens. Bidirectional intra-image attention for spatial reasoning.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.microsoft.com/en-us/research/blog/phi-4-reasoning-vision-and-the-lessons-of-training-a-multimodal-reasoning-model/
    title: "Phi-4-reasoning-vision and the lessons of training a multimodal reasoning model"
    date: 2026-03
  - kind: model-card
    tag: lab
    url: https://www.microsoft.com/en-us/research/wp-content/uploads/2026/03/Phi-4-reasoning-vision-15B-Tech-Report.pdf
    title: "Phi-4-reasoning-vision-15B Technical Report"
    date: 2026-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B
    title: "Phi-4-reasoning-vision-15B HF model card"
    date: 2026-03
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/technology/microsoft-built-phi-4-reasoning-vision-15b-to-know-when-to-think-and-when
    title: "Microsoft built Phi-4-reasoning-vision-15B to know when to think"
    date: 2026-03
    publisher: VentureBeat
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2026/03/06/microsoft-releases-phi-4-reasoning-vision-15b-a-compact-multimodal-model-for-math-science-and-gui-understanding/
    title: "Microsoft Releases Phi-4-Reasoning-Vision-15B"
    date: 2026-03
    publisher: MarkTechPost

Benchmarks (lab, default hybrid mode):
- AI2D: 84.8 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- ChartQA: 83.3 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- MathVista (mini): 75.2 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- MMMU (val): 54.3 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- MathVerse (mini): 44.9 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- MathVision (mini): 36.2 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- MMStar: 64.5 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- OCRBench: 76.0 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- ScreenSpot-v2: 88.2 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03
- HallusionBench: 64.4 [lab] src=https://huggingface.co/microsoft/Phi-4-reasoning-vision-15B date=2026-03

Notes: ScienceQA and AIME explicitly omitted from the model card. Safety defect rates: text-to-text 1.4%, image-to-text 4.5%.

---

## Lineage summary table

| Model | Date | Size | License | Modality | Status |
|---|---|---|---|---|---|
| Phi-1 | 2023-06 | 1.3B | MS-Research (later MIT) | text (code) | legacy |
| Phi-1.5 | 2023-09 | 1.3B | MS-Research → MIT | text | legacy |
| Phi-2 | 2023-12 | 2.7B | MS-Research → MIT (2024-01) | text | legacy |
| Phi-3-mini | 2024-04 | 3.8B | MIT | text | legacy |
| Phi-3-small | 2024-05 | 7B | MIT | text | legacy |
| Phi-3-medium | 2024-05 | 14B | MIT | text | legacy |
| Phi-3-vision | 2024-05 | 4.2B | MIT | text+image | legacy |
| Phi-3.5-mini | 2024-08 | 3.8B | MIT | text | legacy |
| Phi-3.5-MoE | 2024-08 | 42B (6.6B active) | MIT | text | legacy |
| Phi-3.5-vision | 2024-08 | 4.2B | MIT | text+image | legacy |
| Phi-Silica | 2024-05/12 | 3.3B | closed | text (on-device) | current (Windows) |
| Phi-4 | 2024-12 | 14B | MIT | text | current |
| Phi-4-multimodal | 2025-02 | 5.6B | MIT | text+image+audio | current |
| Phi-4-mini | 2025-02 | 3.8B | MIT | text | current |
| Phi-4-reasoning | 2025-04 | 14B | MIT | text (reasoning) | current |
| Phi-4-reasoning-plus | 2025-04 | 14B | MIT | text (reasoning+RL) | current (flagship) |
| Phi-4-mini-reasoning | 2025-04 | 3.8B | MIT | text (reasoning) | current |
| Phi-Ground | 2026 | varies | MIT | text+image (GUI) | current (specialist) |
| Phi-4-reasoning-vision-15B | 2026-03 | 15B | MIT | text+image (hybrid reasoning) | current (newest) |

## Frontier-table designation

For the `frontier-models` comparison page:

- **Flagship for deep-fill**: `Phi-4-reasoning-plus` (April 2025) — the most-cited Phi for reasoning comparisons, with the broadest reported benchmark slate (AIME 24/25, GPQA-D, OmniMath, LiveCodeBench, MMLU-Pro, HumanEval+, IFEval, ArenaHard). Phi-4-reasoning-vision-15B (March 2026) is newer but its slate is vision-bench-heavy and doesn't slot into the standard 18-column frontier table directly.
- **Other `current` text models for frontier-18 fill**: Phi-4, Phi-4-mini, Phi-4-reasoning, Phi-4-mini-reasoning.
- **Multimodal current**: Phi-4-multimodal, Phi-4-reasoning-vision-15B — list with multimodal benches; don't fill SWE-bench cells.
- **Specialists** (skip frontier-18 fill, note as specialists): Phi-Silica (on-device closed), Phi-Ground (GUI agent).
- **Legacy** (no chasing missing cells): everything 2024 and prior.

## Open questions / data gaps

1. **Phi-3-vision detailed benchmarks** — Microsoft published comparative chart-reasoning claims but no consolidated MMMU / MathVista numbers in the HF card. Deep-fill agent should pull from the Phi-3 technical report (arXiv 2404.14219) directly.
2. **Phi-4 MMLU-Pro** — not in the standard model card; arXiv tech report may have it.
3. **Phi-Ground HF card status** — `microsoft/Phi-Ground-Any` is visible on the org page but a direct HF fetch may surface additional variants (e.g., size-specific Phi-Ground-* models). Worth a deep-fill pass if Phi-Ground is promoted to current-frontier-fill rather than specialist.
4. **SWE-bench Verified / Terminal-Bench 2.0** — Microsoft has not reported these for any Phi model. Phi models are below the typical SWE-bench parameter threshold; absence is structural, not a gap to be filled.
5. **LiveCodeBench version mismatch** — Phi-4-reasoning-plus's reported 53.1 is on the Aug-2024-Feb-2025 contemporary window, NOT LiveCodeBench v6. Do not place this in the v6 column of the frontier table without that caveat.
