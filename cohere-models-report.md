# Cohere Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** Cohere is a Canadian lab (Toronto), founded
2019 by ex-Google Brain alums Aidan Gomez, Nick Frosst, Ivan Zhang.
Open-weights research releases live under the **CohereLabs** HF org
(formerly `CohereForAI`); production / hosted models live at
`api.cohere.com`. Most open weights ship under **CC-BY-NC 4.0** (research
only) — commercial use requires a separate Cohere commercial license —
with two notable exceptions: Command A+ (May 2026, first **Apache 2.0**
release) and the legacy Aya 101 (Apache 2.0).

**Lineage breakpoints.**
1. **Command** (Nov 2022 → Mar 2025): xlarge / medium / Light tiers,
   then the `-r` / `-r-plus` (Mar/Apr 2024) RAG-and-tool generation,
   refreshed `08-2024`, capped by `R7B` (Dec 2024). All deprecated
   Sep 15, 2025.
2. **Command A** trunk (Mar 2025 → present): 111B dense, 256K ctx;
   spawned **Reasoning** (Aug 2025), **Vision** (Jul 2025), **Translate**
   (Aug 2025).
3. **Command A+** (May 2026): 218B sparse MoE / 25B active, unifies the
   A-trunk specialists, Apache 2.0, runs on 2×H100 or 1×B200.
4. **Aya** open-research lineage (Feb 2024 → present): 101 (mT5-13B
   FT, 101 langs) → 23 (May 2024, 8B/35B, 23 langs) → Expanse (Oct 2024,
   8B/32B) → Vision (Mar 2025, 8B/32B multimodal) → tiny-Aya (2026,
   3.35B regional variants).

**Cohere also ships non-generative specialists** — Embed (v3, v4),
Rerank (v3, v3.5, v4 pro/fast), and Cohere Transcribe (Mar 2026
speech-to-text). They are not generalist LLMs and don't sit on the
frontier comparison table; we list them at the bottom for completeness.

Convention: dates are **announcement / first availability**.

---

### Command (xlarge, original)

- Release: 2022-11-08 (beta; `xlarge-20221108` / `medium-20221108`)
- Status: deprecated (long-superseded; final shutdown Sep 15, 2025 alongside the R-line)
- Context: 2K (initial) → 4K (early 2023)
- Modality: text only
- License: closed (API-only, hosted)
- Notable: Cohere's first instruction-tuned generative model on the public API; "conditioned to respond well to single-statement commands." Two sizes — `xlarge` (~52B) and `medium` (~6B, later rebranded Command Light). Pre-RAG, pre-tool-use; positioned as a GPT-3.5-class API-only offering.
- Sources:
  - kind: announcement
    tag: lab
    url: https://docs.cohere.com/changelog/improvements-to-current-models-new-beta-model-command
    title: "Improvements to Current Models + New Beta Model (Command)!"
    date: 2022-11

Benchmarks: No formal model card / arXiv report; Cohere did not publish a standard eval matrix for the original Command. Numbers in the wild are 3p / inferred.

Notes: Available on Cohere API and (Nov 2023) Amazon Bedrock. Decommissioned Sep 15, 2025.

---

### Command Light

- Release: 2023 (companion small tier; became broadly available on Bedrock Nov 2023)
- Status: deprecated (Sep 15, 2025)
- Context: 4K
- Modality: text only
- License: closed
- Notable: ~6B-parameter sibling to original Command. Fine-tunable on Bedrock from Nov 2023 — first Cohere model to expose customer fine-tuning at provider scale. Positioned for cost-sensitive enterprise classification / extraction / summarization, not reasoning.
- Sources:
  - kind: announcement
    tag: 3p
    url: https://aws.amazon.com/about-aws/whats-new/2023/11/amazon-bedrock-coheres-light-english-multilingual/
    title: "Cohere's Command Light, Embed English, and multilingual models now available in Amazon Bedrock"
    publisher: AWS
    date: 2023-11
  - kind: deprecation
    tag: lab
    url: https://docs.cohere.com/docs/models
    title: "Cohere model overview — deprecated models list"
    date: 2025-09

---

### Aya 101

- Release: 2024-02-13
- Status: legacy (open research; weights still on HF, superseded by Aya 23 → Expanse → Vision)
- Context: 1K (mT5 base limit)
- Modality: text only
- License: Apache 2.0
- Notable: 13B-param instruction-tuned mT5; **101 languages** — more than 2× any prior open-source model at the time. Released alongside the **Aya dataset** (513M instances, 114 langs), the largest multilingual instruction dataset to date. Outperformed mT0 and BLOOMZ on most tasks. The Aya project itself launched January 2023 with >3,000 researchers across 119 countries.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/research/aya
    title: "Aya — Cohere Labs research"
    date: 2024-02
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/aya-101
    title: "CohereLabs/aya-101 model card"
    date: 2024-02
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2402.07827
    title: "Aya Model: An Instruction Finetuned Open-Access Multilingual Language Model"
    date: 2024-02

Notes: Generative-quality is dated by 2026 standards but the *language coverage* still exceeds anything frontier labs ship in 2026. Used today as a base for further multilingual fine-tuning research, not as a deployable assistant.

---

### Command R (`command-r`, 03-2024)

- Release: 2024-03-11
- Status: deprecated (Sep 15, 2025; `08-2024` refresh remains "live" per docs)
- Context: 128K
- Modality: text only
- License (weights): CC-BY-NC 4.0 (research)
- License (hosted): Cohere Commercial
- Price (hosted, at launch): $0.50 / $1.50 per M tokens (input / output)
- Notable: 35B dense; Cohere's first model with **tool use + RAG as first-class features**. 10 languages (EN, FR, ES, IT, DE, PT, JA, KO, AR, ZH). Open-weights research release on HF (`c4ai-command-r-v01`) — first Cohere model with downloadable weights. Pre-RoPE-extension long-context training (full 128K from pretraining, not extended).
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-r
    title: "Command-R: Retrieval-Augmented Generation at Production Scale"
    date: 2024-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/c4ai-command-r-v01
    title: "c4ai-command-r-v01 model card"
    date: 2024-03
  - kind: deprecation
    tag: lab
    url: https://docs.cohere.com/docs/models
    title: "Cohere model overview — deprecated 2025-09-15"
    date: 2025-09

Benchmarks (lab, mostly RAG/tool-focused — no MMLU score in launch card):
- HotpotQA EM (RAG): 49.8 [lab] src=https://cohere.com/blog/command-r date=2024-03
- KILT-Wiki EM (RAG): 60.4 [lab] src=https://cohere.com/blog/command-r date=2024-03
- Multilingual NLG win-rate vs Mixtral 8x7B: 56-69% [lab] src=https://cohere.com/blog/command-r date=2024-03

Notes: Cohere's release emphasis was *RAG-with-citations* and *tool calling*, not raw academic benchmarks — they explicitly did not publish standard MMLU/GSM8K rows at launch. Refreshed as `command-r-08-2024` (Aug 2024) with throughput / latency improvements.

---

### Command R+ (`command-r-plus`, 04-2024)

- Release: 2024-04-04
- Status: deprecated (Sep 15, 2025; `08-2024` refresh still listed live)
- Context: 128K
- Modality: text only
- License (weights): CC-BY-NC 4.0
- License (hosted): Cohere Commercial
- Price (hosted, at launch): $3.00 / $15.00 per M tokens
- Notable: 104B dense; Cohere's flagship for >1 year. **Multi-step tool use** ("agents"); 10 languages; the first Cohere model open-weighted at 100B+ scale on HF. Aug 2024 refresh dropped pricing to **$2.50 / $10.00** per M tokens and improved throughput/latency.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-r-plus-microsoft-azure
    title: "Introducing Command R+: A Scalable LLM Built for Business"
    date: 2024-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/c4ai-command-r-plus
    title: "c4ai-command-r-plus model card"
    date: 2024-04
  - kind: pricing
    tag: lab
    url: https://docs.cohere.com/v2/docs/command-r-plus
    title: "Cohere Command R+ pricing"
    date: 2024-08

Benchmarks (lab claimed at launch):
- Multi-step tool use win-rate vs GPT-4 Turbo (Berkeley Tool Use): wins [lab] src=https://cohere.com/blog/command-r-plus-microsoft-azure date=2024-04
- HumanEval pass@1: 64.0 [lab] src=https://cohere.com/blog/command-r-plus-microsoft-azure date=2024-04
- MMLU: 75.7 [lab] src=https://cohere.com/blog/command-r-plus-microsoft-azure date=2024-04

3p replications (Aug 2024 refresh, evalry / openrouter aggregates):
- MMLU: 75.4 [3p] src=https://openrouter.ai/cohere/command-r-plus date=2024-09 publisher=OpenRouter aggregate

Notes: First model to put Cohere on the chatbot-arena map (Apr 2024 peak rank #6). Distinct from later "Command A" — different architecture, different lineage.

---

### Aya 23 (8B / 35B)

- Release: 2024-05-23
- Status: legacy research release (superseded by Aya Expanse)
- Context: 8K
- Modality: text only
- License: CC-BY-NC 4.0
- Notable: Step away from 101-lang shallow coverage toward **23-language deep coverage**. Built on Command R-class architecture (not mT5). 8B and 35B variants. Reported +14% discriminative / +20% generative / +41.6% mMMLU improvement vs Aya 101; 6.6× improvement on multilingual math reasoning.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/aya23
    title: "Aya 23: Open Weight Releases to Further Multilingual Progress"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://cohere.com/research/aya/aya-23-technical-report.pdf
    title: "Aya 23 technical report"
    date: 2024-05

Benchmarks (lab, multilingual MMLU 23-lang average):
- mMMLU: ~57 (35B) [lab] src=https://cohere.com/research/aya/aya-23-technical-report.pdf date=2024-05
- mARC: ~52 (35B) [lab] src=https://cohere.com/research/aya/aya-23-technical-report.pdf date=2024-05
- mMGSM: ~37 (35B) [lab] src=https://cohere.com/research/aya/aya-23-technical-report.pdf date=2024-05

---

### Command R / R+ (`08-2024` refresh)

- Release: 2024-08-30
- Status: "live" per docs (kept available; legacy compared to A-trunk)
- Context: 128K
- Modality: text only
- License: CC-BY-NC 4.0 (weights) / Cohere Commercial (hosted)
- Price: $0.15 / $0.60 (R-08-2024) ; $2.50 / $10.00 (R+ 08-2024) per M tokens
- Notable: Pure throughput / latency refresh of the Mar/Apr 2024 base models — no architecture change. R-08-2024 dropped price 3.3× vs original. Both refreshes remain in production today as cheap RAG workhorses.
- Sources:
  - kind: announcement
    tag: 3p
    url: https://www.marktechpost.com/2024/09/01/updated-versions-of-command-r-35b-and-command-r-104b-released-two-powerful-language-models-with-104b-and-35b-parameters-for-multilingual-ai/
    title: "Updated Versions of Command R (35B) and Command R+ (104B) Released"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/c4ai-command-r-plus-08-2024
    title: "c4ai-command-r-plus-08-2024 model card"
    date: 2024-08

---

### Aya Expanse (8B / 32B)

- Release: 2024-10-24
- Status: "live" per Cohere docs (8B retired 2026-04, 32B still listed)
- Context: 128K
- Modality: text only
- License: CC-BY-NC 4.0
- Notable: 23-language model trained with **data arbitrage + preference training + model merging** (paper key contributions). 32B beats Llama-3.1 70B at half the parameter count on multilingual evals.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/research/aya
    title: "Aya Expanse — pushing the multilingual frontier"
    date: 2024-10
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2412.04261
    title: "Aya Expanse: Combining Research Breakthroughs for a New Multilingual Frontier"
    date: 2024-12

Benchmarks (lab, m-ArenaHard win rates):
- vs Gemma 2 9B (8B model): 60.4% [lab] src=https://arxiv.org/abs/2412.04261 date=2024-12
- vs Llama-3.1 70B (32B model): 54.0% [lab] src=https://arxiv.org/abs/2412.04261 date=2024-12
- vs Mistral 8x22B (32B model): 76.6% [lab] src=https://arxiv.org/abs/2412.04261 date=2024-12

---

### Command R7B (`command-r7b-12-2024`)

- Release: 2024-12-13
- Status: live
- Context: 128K
- Modality: text only
- License: CC-BY-NC 4.0 (weights) / Cohere Commercial (hosted)
- Price (hosted): $0.0375 / $0.15 per M tokens
- Notable: **Smallest, fastest, final** model in the R-series. 7B dense; designed for edge/on-prem deployment. RAG + tool use feature-parity with R+, just smaller. Closed Cohere's "R" branding before the "A" trunk took over.
- Sources:
  - kind: announcement
    tag: lab
    url: https://docs.cohere.com/v2/changelog/command-r-7b
    title: "Announcing Command R7B"
    date: 2024-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/c4ai-command-r7b-12-2024
    title: "c4ai-command-r7b-12-2024 model card"
    date: 2024-12

Benchmarks (lab):
- MMLU: 64.6 [lab] src=https://cohere.com/blog/command-r7b date=2024-12
- HumanEval+: 75.6 [lab] src=https://cohere.com/blog/command-r7b date=2024-12
- BFCL-v3: 63.0 [lab] src=https://cohere.com/blog/command-r7b date=2024-12
- IFEval: 77.9 [lab] src=https://cohere.com/blog/command-r7b date=2024-12

Notes: Best-in-class 7B for RAG / tool use at launch (vs Llama 3.1 8B, Gemma 2 9B, Ministral 8B).

---

### Aya Vision (8B / 32B)

- Release: 2025-03-03
- Status: 8B retired 2026-04-04; 32B still listed live
- Context: 16K
- Modality: image + text (vision)
- License: CC-BY-NC 4.0
- Notable: First Cohere multimodal release. Built on Aya Expanse text tower + SigLIP-class vision encoder. 23 languages. 32B beats much larger Llama-3.2 90B Vision, Molmo 72B, Qwen2-VL 72B on multilingual multimodal benchmarks per Cohere's own AyaVisionBench / m-WildVision.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/aya-vision
    title: "Aya Vision: Expanding the worlds AI can see"
    date: 2025-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/aya-vision-32b
    title: "CohereLabs/aya-vision-32b model card"
    date: 2025-03
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/coheres-first-vision-model-aya-vision-is-here-with-broad-multilingual-understanding-and-open-weights-but-theres-a-catch
    title: "Cohere's first vision model Aya Vision is here … but there's a catch"
    publisher: VentureBeat
    date: 2025-03

Benchmarks (lab, win rates):
- AyaVisionBench (8B vs Qwen2.5-VL 7B / Llama-3.2 11B / Gemini 1.5 Flash 8B / Pangea 7B): up to 70% [lab] src=https://cohere.com/blog/aya-vision date=2025-03
- m-WildVision (8B): 79% [lab] src=https://cohere.com/blog/aya-vision date=2025-03
- AyaVisionBench (32B vs Llama-3.2 90B / Molmo 72B / Qwen2-VL 72B): 64% [lab] src=https://cohere.com/blog/aya-vision date=2025-03
- m-WildVision (32B): 72% [lab] src=https://cohere.com/blog/aya-vision date=2025-03

Notes: VentureBeat "catch" is the CC-BY-NC license — research-only weights.

---

### Command A (`command-a-03-2025`)

- Release: 2025-03-13
- Status: live
- Context: 256K
- Modality: text only
- License (weights): CC-BY-NC 4.0
- License (hosted): Cohere Commercial
- Price (hosted): $2.50 / $10.00 per M tokens
- Notable: 111B dense, 256K ctx. **2 GPU deployment target** (2×A100 or 2×H100). 156 t/s — 1.75× GPT-4o on Cohere's bench. 23 languages. Cohere's hard turn from "R = retrieval" to "A = agents" — flagship until Aug 2025.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-a
    title: "Introducing Command A: Max performance, minimal compute"
    date: 2025-03
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2504.00698
    title: "Command A: An Enterprise-Ready Large Language Model"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://cohere.com/research/papers/command-a-technical-report.pdf
    title: "Command A technical report (Cohere PDF)"
    date: 2025-04
  - kind: pricing
    tag: lab
    url: https://artificialanalysis.ai/models/command-a
    title: "Cohere Command A — Artificial Analysis pricing"
    date: 2026-05

Benchmarks:
- MMLU: 85.5 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- MMLU-Pro: 70.4 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- GPQA Diamond: 50.8 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- BFCL-v3 (tool use): 63.3 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- Tau-bench airline+retail avg: 51.3 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- MBPP+: 78.6 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- HumanEval+: 81.7 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- SWE-bench Verified: 25.2 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- IFEval: 90.9 [lab] src=https://arxiv.org/abs/2504.00698 date=2025-04
- AA Intelligence Index: 13 [3p] src=https://artificialanalysis.ai/models/command-a date=2025-03 publisher=Artificial Analysis

Notes: AA Intelligence Index of 13 is below frontier (Opus 4.7 ~65, GPT-5 ~70 era models). Cohere positions Command A as best-on-the-frontier-*at-its-size-and-cost-tier* — not absolute top.

---

### Command A Vision (`command-a-vision-07-2025`)

- Release: 2025-07-31
- Status: live
- Context: 128K
- Modality: image + text (vision); up to 20 images per request, 20MB total
- License (weights): CC-BY-NC 4.0
- License (hosted): Cohere Commercial
- Notable: 112B (= Command A 111B + SigLIP2 vision encoder). Beats GPT-4.1 on 7 of 9 visual benchmarks per Cohere; trails it on MMMU. 6 languages official (EN, PT, IT, FR, DE, ES) — narrower than Aya Vision (23) by design (production-focused).
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-a-vision
    title: "Introducing Command A Vision: Multimodal AI built for Business"
    date: 2025-07
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/command-a-vision-07-2025
    title: "CohereLabs/command-a-vision-07-2025 model card"
    date: 2025-07

Benchmarks (lab, vs GPT-4.1):
- DocVQA: leads GPT-4.1 by +7.3 pp [lab] src=https://cohere.com/blog/command-a-vision date=2025-07
- OCRBench: leads GPT-4.1 by +6.7 pp [lab] src=https://cohere.com/blog/command-a-vision date=2025-07
- ChartQA: leads GPT-4.1 by +8.2 pp [lab] src=https://cohere.com/blog/command-a-vision date=2025-07
- MMMU: 65.3 (vs GPT-4.1 74.8) [lab] src=https://cohere.com/blog/command-a-vision date=2025-07

---

### Command A Reasoning (`command-a-reasoning-08-2025`)

- Release: 2025-08-21
- Status: live (superseded by A+ for top-end agentic; still listed)
- Context: 256K
- Modality: text only
- License (weights): CC-BY-NC 4.0
- License (hosted): Cohere Commercial
- Notable: 111B dense, Cohere's **first reasoning model**. Toggle-able reasoning via `reasoning=on/off` API param; configurable reasoning budgets. Single H100/A100 for 128K ctx; 4× H100 for 256K. Knowledge cutoff Jun 1 2024.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-a-reasoning
    title: "Introducing Command A Reasoning"
    date: 2025-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/command-a-reasoning-08-2025
    title: "CohereLabs/command-a-reasoning-08-2025 model card"
    date: 2025-08
  - kind: coverage
    tag: 3p
    url: https://the-decoder.com/cohere-unveils-command-a-reasoning-a-model-for-enterprise-research-and-workflows/
    title: "Cohere unveils Command A Reasoning"
    publisher: The Decoder
    date: 2025-08

Benchmarks (lab, comparator set: gpt-oss-120b, DeepSeek-R1-0528, Mistral Magistral Medium):
- BFCL-v3: leads comparator set [lab] src=https://cohere.com/blog/command-a-reasoning date=2025-08
- Tau-bench: leads comparator set [lab] src=https://cohere.com/blog/command-a-reasoning date=2025-08
- DeepResearch Bench (RACE): leads comparator set [lab] src=https://cohere.com/blog/command-a-reasoning date=2025-08
- τ²-Bench Telecom: 37 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05 (cited via the A+ blog's comparison chart)
- Terminal-Bench Hard: 3 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05 (same chart)
- MathVista: 73.5 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- CharXiv reasoning: 46.9 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05

Notes: Cohere did not publish a Command A Reasoning arXiv tech report with full eval matrix; available numbers come from the blog + the A+ launch's back-reference comparisons.

---

### Command A Translate (`command-a-translate-08-2025`)

- Release: 2025-08-28
- Status: live (specialist; not on the frontier table)
- Context: 8K in / 8K out
- Modality: text only
- License (weights): CC-BY-NC 4.0
- License (hosted): Cohere Commercial
- Notable: 111B dense; pure MT specialist (no chat, no tool use). 23 languages. Single-GPU deployable (A100/H100). Knowledge cutoff Jun 1 2024.
- Sources:
  - kind: announcement
    tag: lab
    url: https://docs.cohere.com/changelog/2025-08-28-command-a-translate
    title: "Announcing Cohere's Command A Translate Model"
    date: 2025-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/command-a-translate-08-2025
    title: "CohereLabs/command-a-translate-08-2025 model card"
    date: 2025-08
  - kind: coverage
    tag: 3p
    url: https://slator.com/cohere-enterprise-ai-translation-command-a-translate/
    title: "Cohere Targets Enterprise AI Translation with Command A Translate"
    publisher: Slator
    date: 2025-08

Notes: Specialist; not benchmarked on frontier-generalist evals. Cohere claims SoTA on standard MT benches (FLORES, WMT) — exact numbers in the docs page.

---

### tiny-Aya family (global / earth / fire / water)

- Release: early 2026 (rolling)
- Status: live
- Context: 8K
- Modality: text only
- License: CC-BY-NC 4.0
- Notable: 3.35B-parameter regional variants. `global` = 70 languages; `earth` = West Asian/African focus; `fire` = South Asian focus; `water` = European / Asia-Pacific focus. Cohere's edge-device tier for the Aya line.
- Sources:
  - kind: model-card
    tag: lab
    url: https://docs.cohere.com/docs/models
    title: "Cohere model overview — tiny-Aya entries"
    date: 2026-04

Notes: No formal launch blog; surfaced via the model-overview doc. Specialist multilingual edge models; not on the frontier generalist table.

---

### Command A+ (`command-a-plus-05-2026`) — current flagship

- Release: 2026-05-20
- Status: live
- Context: 128K in / 64K out
- Modality: image + text (multimodal; absorbs Command A Vision)
- License: **Apache 2.0** (Cohere's first fully Apache 2.0 release)
- License (hosted): Cohere Commercial (still offered for managed deployments)
- Notable: 218B total / 25B active sparse MoE (128 experts, 8 active + 1 shared per token). Runs on **1× B200 or 2× H100** at W4A4 quantization with "negligible quality loss". **48 languages** (up from 23 in A-trunk). Native citations / grounding spans (Cohere's signature). Unifies Command A / A Reasoning / A Vision / A Translate into one model. Up to 63% higher TPS and 17% lower TTFT vs A Reasoning. 1.5-1.6× extra speedup with speculative decoding.
- Sources:
  - kind: announcement
    tag: lab
    url: https://cohere.com/blog/command-a-plus
    title: "Introducing Command A+"
    date: 2026-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/CohereLabs/command-a-plus-05-2026-w4a4
    title: "CohereLabs/command-a-plus-05-2026-w4a4 model card"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/technology/cohere-cracks-lossless-quantization-and-native-citations-with-first-full-apache-2-0-licensed-open-model-command-a
    title: "Cohere cracks lossless quantization and native citations with first full Apache 2.0 licensed open model Command A+"
    publisher: VentureBeat
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2026/05/21/cohere-releases-command-a-a-218b-sparse-moe-model-for-agentic-workflows-that-runs-on-as-few-as-two-h100-gpus/
    title: "Cohere Releases Command A+: A 218B Sparse MoE Model for Agentic Workflows"
    publisher: MarkTechPost
    date: 2026-05

Benchmarks (lab, from launch blog):
- AA Intelligence Index: 37 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- τ²-Bench Telecom: 85 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- Terminal-Bench Hard (agentic coding): 25 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- MMMU: 75.1 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- MMMU Pro: 63 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- MathVista: 80.6 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- CharXiv reasoning: 52.7 [lab] src=https://cohere.com/blog/command-a-plus date=2026-05
- AA non-hallucination rank: #1 (~86%) [3p] src=https://venturebeat.com/technology/cohere-cracks-lossless-quantization-and-native-citations-with-first-full-apache-2-0-licensed-open-model-command-a date=2026-05 publisher=Artificial Analysis

Notes: AA Intelligence Index of **37** is a major jump from Command A's **13** — but still below Opus 4.7 / GPT-5.5 frontier band (~65-70). Cohere's pitch is *open-weights frontier non-hallucination leadership*, not absolute IQ leadership. The Apache 2.0 license is the load-bearing strategic shift — it allows commercial deployment without Cohere's commercial license, opening the model to all enterprise / sovereign use.

---

## Specialist (non-generalist) models

### Embed family

- `embed-english-v3.0` / `embed-multilingual-v3.0` / light variants (Nov 2023, live; 512 ctx, 1024/384 dims)
- `embed-v4.0` (live; 128K ctx, variable 256-1536 dims, multimodal text+image)
- Pricing: $0.10 / M input tokens (v3); v4 priced per docs
- Sources:
  - kind: model-card
    tag: lab
    url: https://docs.cohere.com/docs/cohere-embed
    title: "Cohere Embed v3 / v4"
    date: 2026-05

### Rerank family

- `rerank-english-v3.0` / `rerank-multilingual-v3.0` (Oct 2023, live; 4K ctx)
- `rerank-v3.5` (live; 4K ctx, JSON support)
- `rerank-v4.0-pro` / `rerank-v4.0-fast` (live; 32K ctx, multilingual+JSON)
- Pricing: $2.00 / M search-input tokens (v3)
- Sources:
  - kind: model-card
    tag: lab
    url: https://docs.cohere.com/docs/rerank-overview
    title: "Cohere Rerank overview"
    date: 2026-05

### Cohere Transcribe (`cohere-transcribe-03-2026`)

- Release: 2026-03
- Status: live
- Modality: audio in / text out; 25MB file limit
- License (hosted): Cohere Commercial
- Notable: Multilingual STT specialist; Cohere's first audio model. Listed in `docs.cohere.com/docs/models` but no detailed blog at time of compile.
- Sources:
  - kind: model-card
    tag: lab
    url: https://docs.cohere.com/docs/models
    title: "Cohere model overview — cohere-transcribe-03-2026"
    date: 2026-04

---

## Deprecated / decommissioned

All deprecated **2025-09-15** per `docs.cohere.com/docs/models`:
- `command` (original xlarge / medium, 2022-11)
- `command-light`
- `command-r` (the standalone short-name endpoint pre-`-03-2024`)
- `command-r-plus` (standalone short-name endpoint pre-`-04-2024`)
- `command-r-03-2024` (the original Mar 2024 release)
- `command-r-plus-04-2024` (the original Apr 2024 release)

Retired **2026-04-04**:
- `c4ai-aya-expanse-8b`
- `c4ai-aya-vision-8b`

The `-08-2024` refresh endpoints for both R and R+ are still listed
live as of May 2026 per the model overview doc, but are functionally
legacy — Cohere is pushing customers toward the A-trunk.

---

## Sources summary (top-level URLs)

- Cohere blog: https://cohere.com/blog
- Cohere changelog: https://docs.cohere.com/changelog
- Cohere model overview: https://docs.cohere.com/docs/models
- Cohere research / papers: https://cohere.com/research
- HuggingFace CohereLabs org: https://huggingface.co/CohereLabs
- Command A tech report (arXiv): https://arxiv.org/abs/2504.00698
- Aya Expanse tech report (arXiv): https://arxiv.org/abs/2412.04261
- Artificial Analysis Cohere pages: https://artificialanalysis.ai/providers/cohere
- VentureBeat Cohere coverage (Command A+, Aya Vision, Command A Reasoning):
  https://venturebeat.com/technology/cohere-cracks-lossless-quantization-and-native-citations-with-first-full-apache-2-0-licensed-open-model-command-a
