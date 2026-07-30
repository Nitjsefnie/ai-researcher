# DeepSeek Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** DeepSeek (Hangzhou DeepSeek AI, a subsidiary of
High-Flyer Quant) ships open-weights through `huggingface.co/deepseek-ai`
and a hosted API at `api.deepseek.com`. Almost every release ships an
arXiv tech report — those are the canonical `lab` source. The HuggingFace
model card is the canonical eval surface (the README tables on `V3`,
`R1`, `V3.1`, `V3.2-Exp`, `V3.2` carry the lab numbers). The change log
at `api-docs.deepseek.com/updates` is the canonical hosted-SKU timeline.
Wikipedia's DeepSeek article is well-maintained and useful as a
secondary cross-check; `timelines.issarice.com/wiki/Timeline_of_DeepSeek`
is a third independent timeline.

**Licensing convention.** DeepSeek's early releases (V1/Coder/V2/Coder-V2/V2.5)
used a custom **DeepSeek License** (source-available, commercial use allowed
with restrictions). The model weights for **V3, R1, R1-Distill, V3.1, V3.2,
V4** are released under the **MIT License** — both code and weights — which
is unusual generosity for a frontier-tier lab. R1 in particular is the
first widely-deployed open-weight reasoning model released MIT.

**Open-weight ≠ no API.** DeepSeek runs its own hosted API at
`api.deepseek.com` (separately priced) and also publishes the weights for
download. Pricing rows below cite the hosted API; third-party hosts
(Fireworks, Together, DeepInfra, OpenRouter) typically charge similar or
lower rates.

**R2 status.** A successor named "R2" has been rumored since Reuters'
Feb 2025 report. As of May 2026, **no R2 has shipped**. The hybrid-thinking
direction in V3.1 → V3.2 → V4 appears to have absorbed the R-line's
reasoning specialization into the V-line trunk, so R2 may not ship as a
distinct model. The change log shows `deepseek-reasoner` is now the
thinking-mode endpoint of V4-Flash.

Convention: dates are **announcement / first availability**.

---

### DeepSeek Coder (V1)

- Release: 2023-11-02 (first DeepSeek model shipped)
- Status: legacy (superseded by Coder-V2)
- Context: 16K tokens
- Modality: text only (code-focused, 87 programming languages)
- License: DeepSeek License (source-available, commercial allowed with restrictions)
- Price: not hosted on a paid API at launch
- Notable: 1.3B / 5.7B / 6.7B / 33B sizes; first frontier-grade open-weight code model from a Chinese lab; 33B-Base outperformed CodeLlama-34B by 7.9 pp on HumanEval Python.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/deepseek-ai/DeepSeek-Coder
    title: "DeepSeek Coder: Let the Code Write Itself"
    date: 2023-11
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2401.14196
    title: "DeepSeek-Coder: When the Large Language Model Meets Programming"
    date: 2024-01
  - kind: coverage
    tag: 3p
    url: https://timelines.issarice.com/wiki/Timeline_of_DeepSeek
    publisher: issarice timelines
    title: "Timeline of DeepSeek — DeepSeek Coder release Nov 2 2023"
    date: 2026-05

Benchmarks (lab from tech report):
- HumanEval (33B-Base, pass@1): 50.3 [lab] src=https://arxiv.org/abs/2401.14196 date=2024-01
- MBPP (33B-Base): 66.0 [lab] src=https://arxiv.org/abs/2401.14196 date=2024-01
- HumanEval Python (33B-Base): 56.1 [lab] src=https://github.com/deepseek-ai/DeepSeek-Coder date=2023-11

Notes: Pretrained on 2T tokens across 87 languages; training corpus restricted to repos created before Nov 2023.

---

### DeepSeek LLM (V1)

- Release: 2023-11-29 (paper); 2023-12-02 model release on HF
- Status: legacy (superseded by V2)
- Context: 4,096 tokens
- Modality: text only (English + Chinese)
- License: DeepSeek License (source-available)
- Price: not on a paid API at launch
- Notable: 7B and 67B in Base + Chat variants; trained from scratch on 2T tokens; 67B-Base outperformed Llama-2-70B-Base on reasoning, code, math, and Chinese understanding.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/deepseek-ai/DeepSeek-LLM
    title: "DeepSeek LLM: Let there be answers"
    date: 2023-11
  - kind: model-card
    tag: lab
    url: https://huggingface.co/TheBloke/deepseek-llm-67b-base-GGUF
    title: "DeepSeek-LLM-67B-Base model card"
    date: 2023-12
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2023/12/04/deepseek-open-sources-deepseek-67b-model-the-latest-chatgpt-rival-from-china/
    publisher: MarkTechPost
    title: "DeepSeek Open-Sources DeepSeek-67B Model"
    date: 2023-12

Benchmarks (lab from technical report / timeline):
- HumanEval (67B-Chat, pass@1): 73.78 [lab] src=https://timelines.issarice.com/wiki/Timeline_of_DeepSeek date=2023-12
- GSM8K (67B-Chat): 84.1 [lab] src=https://timelines.issarice.com/wiki/Timeline_of_DeepSeek date=2023-12

Notes: First DeepSeek release positioned as a frontier open-source generalist; Llama-2-class architecture with no MoE yet.

---

### DeepSeek-MoE

- Release: 2024-01-09
- Status: legacy (research milestone; superseded by V2's MoE architecture)
- Context: 4K tokens
- Modality: text
- License: DeepSeek License
- Notable: 16B total, 2.7B active; introduced the shared-expert + fine-grained-expert variant of MoE that became DeepSeekMoE — the foundation of V2/V3.
- Sources:
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/deepseek-moe-16b-base
    title: "deepseek-moe-16b-base model card"
    date: 2024-01
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/DeepSeek
    publisher: Wikipedia
    title: "DeepSeek — DeepSeek-MoE entry"
    date: 2026-05

Notes: Mostly a stepping-stone architecture paper; not deployed at scale.

---

### DeepSeekMath 7B

- Release: 2024-02-05 (paper); 2024-04 wider weight release
- Status: legacy (techniques folded into V2/V3)
- Context: 4K tokens
- Modality: text (math-focused)
- License: DeepSeek License
- Notable: 7B model that approached Gemini-Ultra / GPT-4 on competition-level MATH without tool use; introduced **Group Relative Policy Optimization (GRPO)** — the RL algorithm that powered R1 a year later.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2402.03300
    title: "DeepSeekMath: Pushing the Limits of Mathematical Reasoning"
    date: 2024-02
  - kind: model-card
    tag: lab
    url: https://github.com/deepseek-ai/DeepSeek-Math
    title: "DeepSeek-Math GitHub README"
    date: 2024-02

Benchmarks (lab):
- MATH (4-shot, no tools): 51.7 [lab] src=https://arxiv.org/abs/2402.03300 date=2024-02
- GSM8K (CoT): 88.2 [lab] src=https://arxiv.org/abs/2402.03300 date=2024-02
- MATH (Base, 4-shot): 36.2 [lab]
- GSM8K (Base): 64.2 [lab]

Notes: GRPO from this paper is the same algorithm later used in R1's RL-only training pipeline. Outperformed all open-source 7B–70B models and most closed models at math.

---

### DeepSeek-VL

- Release: 2024-03-13
- Status: legacy (superseded by VL2)
- Context: 4K
- Modality: text + image (vision-language)
- License: DeepSeek License
- Notable: First DeepSeek multimodal model; hybrid vision encoder for high-resolution images.
- Sources:
  - kind: model-card
    tag: lab
    url: https://github.com/deepseek-ai/DeepSeek-VL
    title: "DeepSeek-VL GitHub README"
    date: 2024-03
  - kind: coverage
    tag: 3p
    url: https://timelines.issarice.com/wiki/Timeline_of_DeepSeek
    publisher: issarice
    title: "Timeline — DeepSeek-VL"
    date: 2026-05

Notes: Mostly a research release; not benchmarked against frontier VLMs.

---

### DeepSeek-V2

- Release: 2024-05-07 (paper + weights); API live shortly after
- Status: legacy (superseded by V2.5)
- Decommissioned: hosted SKU migrated to V2.5 in Sep 2024 and to V3 in Dec 2024
- Context: 128K tokens
- Modality: text
- License: DeepSeek License (commercial allowed)
- Price (in/out per 1M, original): ~$0.14 / $0.28
- Notable: First MoE at frontier scale from DeepSeek — 236B total / 21B active; introduced **Multi-head Latent Attention (MLA)** which cut KV cache 93.3% and boosted throughput 5.76×; 8.1T training tokens; 42.5% cheaper to train than V1 67B.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2405.04434
    title: "DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V2
    title: "DeepSeek-V2 model card"
    date: 2024-05
  - kind: pricing
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "API change log — V2-0517 release"
    date: 2024-05

Benchmarks (lab from V2 paper, base unless tagged Chat):
- MMLU (Base): 78.5 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-V2 date=2024-05
- GSM8K (Chat): 92.2 [lab]
- MATH (Chat): 53.9 [lab]
- HumanEval (Chat): 81.1 [lab]
- MBPP (Chat): 72.0 [lab]
- BBH (Base): 78.9 [lab]
- C-Eval (Base): 81.7 [lab]
- LiveCodeBench (Chat): 32.5 [lab]
- HumanEval (after 0628 update): 84.76 [lab] src=https://api-docs.deepseek.com/updates date=2024-06
- MATH (after 0628 update): 71.02 [lab]

Notes: V2 had a smaller-context **V2-Lite** (15.7B / 2.4B active, 32K context) for self-hosting; not a frontier SKU.

---

### DeepSeek-Coder-V2

- Release: 2024-06-17 (paper + weights); API release tagged `Coder-V2-0614`
- Status: legacy (superseded by V2.5 merger)
- Context: 128K tokens
- Modality: text (code-focused, 338 languages)
- License: DeepSeek License
- Price (in/out per 1M): ~$0.14 / $0.28 (hosted as `deepseek-coder`)
- Notable: 236B / 21B active; built on V2-Base, trained on 6T additional code-heavy tokens; first open-source coder to outperform GPT-4-Turbo on HumanEval and Codeforces.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2406.11931
    title: "DeepSeek-Coder-V2: Breaking the Barrier of Closed-Source Models in Code Intelligence"
    date: 2024-06
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct
    title: "DeepSeek-Coder-V2-Instruct model card"
    date: 2024-06
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/deepseek-coder-v2
    publisher: Artificial Analysis
    title: "DeepSeek-Coder-V2 Intelligence index"
    date: 2024-07

Benchmarks (lab):
- HumanEval: 90.2 [lab] src=https://arxiv.org/abs/2406.11931 date=2024-06
- MBPP: 76.2 [lab] src=https://arxiv.org/abs/2406.11931 date=2024-06
- LiveCodeBench: 43.4 [lab]
- MATH: 75.7 [lab]
- Math Odyssey: 53.7 [lab]

Notes: Also shipped a Coder-V2-Lite (16B / 2.4B active) for self-host. Outperformed Claude 3 Opus and Gemini 1.5 Pro on coding at release.

---

### DeepSeek-V2.5

- Release: 2024-09-05 (`deepseek-chat` and `deepseek-coder` merged into V2.5); refreshed 2024-12-10 as `V2.5-1210`
- Status: legacy (superseded by V3)
- Context: 128K tokens
- Modality: text
- License: DeepSeek License
- Price (in/out per 1M): ~$0.14 / $0.28
- Notable: First time DeepSeek unified the chat and coder paths into one backward-compatible API model; added function calling, JSON mode, FIM.
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "API change log — DeepSeek-V2.5 (2024-09-05) and V2.5-1210 (2024-12-10)"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V2.5
    title: "DeepSeek-V2.5 model card"
    date: 2024-09

Benchmarks (lab from change log):
- HumanEval: 89.0 [lab] src=https://api-docs.deepseek.com/updates date=2024-09
- ArenaHard (after V2.5 launch): 76.3 [lab] (up from 68.3 on V2-0628)
- MATH-500 (after V2.5-1210 refresh): 82.8 [lab] src=https://api-docs.deepseek.com/updates date=2024-12
- LiveCodeBench (V2.5-1210): 34.38 [lab]

Notes: The Dec 2024 `V2.5-1210` refresh was the last V2 generation before V3.

---

### DeepSeek-VL2

- Release: 2024-12-13
- Status: current (still the main DeepSeek VLM until a V4 vision model)
- Context: ~4K
- Modality: text + image (vision-language)
- License: DeepSeek License (model agreement allows commercial use)
- Notable: MoE VLM built on DeepSeekMoE-27B; three sizes (Tiny 1.0B active / Small 2.8B / VL2 4.5B active); beat GPT-4o on OCRBench (834 vs 736).
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2412.10302
    title: "DeepSeek-VL2: Mixture-of-Experts Vision-Language Models for Advanced Multimodal Understanding"
    date: 2024-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/deepseek-vl2
    title: "DeepSeek-VL2 model card"
    date: 2024-12

Benchmarks (lab):
- OCRBench: 834 [lab] src=https://github.com/deepseek-ai/DeepSeek-VL2 date=2024-12
- DocVQA: 93.3 [lab] src=https://github.com/deepseek-ai/DeepSeek-VL2 date=2024-12

Notes: VL2 is the active multimodal SKU but is much smaller than DeepSeek's text-line frontier models — there is no 671B-class DeepSeek VLM.

---

### DeepSeek-V3

- Release: 2024-12-26 (paper, weights, API)
- Status: legacy (superseded by V3-0324, then V3.1)
- Context: 128K tokens
- Modality: text
- License: **MIT License** for both code and weights (first frontier-tier MIT release from DeepSeek)
- Price (in/out per 1M, original launch): $0.27 / $1.10 (cache miss); $0.07 cache-hit input
- Notable: 671B total / 37B active MoE; trained on 14.8T tokens in **2.788M H800-hours (~$5.6M)** — the cost figure that triggered the "DeepSeek moment" in Jan 2025; uses FP8 training; multi-token prediction objective.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2412.19437
    title: "DeepSeek-V3 Technical Report"
    date: 2024-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V3
    title: "DeepSeek-V3 model card"
    date: 2024-12
  - kind: coverage
    tag: 3p
    url: https://siliconangle.com/2024/12/26/deepseek-open-sources-new-ai-model-671b-parameters/
    publisher: SiliconANGLE
    title: "DeepSeek open-sources new AI model with 671B parameters"
    date: 2024-12

Benchmarks (lab, Chat unless tagged):
- MMLU: 88.5 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-V3 date=2024-12
- MMLU-Pro: 75.9 [lab]
- GPQA Diamond: 59.1 [lab]
- AIME 2024 (pass@1): 39.2 [lab]
- MATH-500: 90.2 [lab]
- GSM8K: 89.3 [lab]
- HumanEval: 82.6 [lab]
- MBPP: 75.4 [lab]
- LiveCodeBench: 40.5 [lab]
- Codeforces percentile: 51.6 [lab]
- SWE-bench Verified: 42.0 [lab]

Notes: V3-Base release alongside the chat-aligned V3; both MIT. Used as the foundation for R1's RL training.

---

### DeepSeek-R1 + R1-Zero

- Release: 2025-01-20 (paper, weights, API)
- Status: legacy (superseded by R1-0528, then V3.1-Think)
- Context: 128K tokens
- Modality: text (reasoning)
- License: **MIT** (both R1 and R1-Zero, including the six distilled checkpoints)
- Price (in/out per 1M, original): $0.55 / $2.19 (cache miss); $0.14 cache-hit input
- Notable: First widely-deployed open-weight reasoning model; **R1-Zero is RL-only with no SFT** — the model self-discovered chain-of-thought via GRPO on math/coding reward signals; R1 added a small SFT cold-start pass for readability. Triggered the January 2025 valuation panic in US AI markets.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2501.12948
    title: "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning"
    date: 2025-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-R1
    title: "DeepSeek-R1 model card"
    date: 2025-01
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/deepseek-r1
    publisher: Artificial Analysis
    title: "DeepSeek-R1 intelligence index"
    date: 2025-02

Benchmarks (lab, pass@1 unless tagged):
- AIME 2024: 79.8 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-R1 date=2025-01
- MATH-500: 97.3 [lab]
- GPQA Diamond: 71.5 [lab]
- MMLU: 90.8 [lab]
- MMLU-Pro: 84.0 [lab]
- SWE-bench Verified: 49.2 [lab]
- LiveCodeBench (CoT): 65.9 [lab]
- Codeforces (rating): 2029 [lab]

Notes: Comparable to OpenAI o1 across all reasoning benchmarks at launch; reported training cost was ~$294K (RL phase only, on top of V3 base) — distinct from the V3 ~$5.6M base-training figure.

---

### DeepSeek-R1-Distill (6 variants)

- Release: 2025-01-20 (shipped alongside R1)
- Status: current (long-tail open-weight reasoning models)
- Context: 32K (distill targets' native windows)
- Modality: text
- License: each distill inherits its base model license — Qwen variants Apache 2.0; Llama variants Llama-3.1 / 3.3 community license
- Notable: SFT-only distillation of 800K R1-generated reasoning traces onto open dense bases; the 32B and 70B variants beat OpenAI o1-mini at launch.
- Sources:
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
    title: "DeepSeek-R1-Distill-Qwen-32B model card"
    date: 2025-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B
    title: "DeepSeek-R1-Distill-Llama-70B model card"
    date: 2025-01

Variants and key benchmarks (lab):
- R1-Distill-Qwen-1.5B (base: Qwen2.5-Math-1.5B)
- R1-Distill-Qwen-7B (base: Qwen2.5-Math-7B)
- R1-Distill-Qwen-14B (base: Qwen2.5-14B) — AIME 2024 69.7, MATH-500 93.9
- R1-Distill-Qwen-32B (base: Qwen2.5-32B) — beats o1-mini
- R1-Distill-Llama-8B (base: Llama-3.1-8B) — MATH-500 89.1, GPQA-D 49.0
- R1-Distill-Llama-70B (base: Llama-3.3-70B-Instruct) — MATH-500 94.5

Notes: Distillation pipeline was SFT-only (no RL stage), which is a key training-cost finding from the R1 paper — a small dense student can recover most of an RL-trained large MoE teacher's reasoning behavior.

---

### Janus-Pro

- Release: 2025-01-27 (Lunar New Year's Eve)
- Status: current (open-weights research artifact)
- Context: small (multimodal)
- Modality: **text + image (understanding) + image generation**
- License: MIT
- Notable: 1B and 7B unified multimodal model — decoupled visual encoder (SigLIP-L for understanding, separate VQ tokenizer for generation) routed through one Transformer; 7B beat DALL-E 3 and Stable Diffusion 3 Medium on GenEval / DPG-Bench.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/deepseek-ai/Janus
    title: "Janus-Series: Unified Multimodal Understanding and Generation"
    date: 2025-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/Janus-Pro-7B
    title: "Janus-Pro-7B model card"
    date: 2025-01
  - kind: coverage
    tag: 3p
    url: https://technode.com/2025/01/30/deepseek-releases-new-models-janus-pro-and-janusflow-on-lunar-new-years-eve/
    publisher: TechNode
    title: "DeepSeek releases Janus-Pro and JanusFlow"
    date: 2025-01

Benchmarks (lab):
- GenEval (Janus-Pro-7B): 0.80 [lab] src=https://arxiv.org/abs/2501.17811 date=2025-01
- DPG-Bench: 84.2 [lab] src=https://arxiv.org/abs/2501.17811 date=2025-01

Notes: First and (so far) only DeepSeek image-generation model. The original Janus (Oct 2024) was 1.3B; JanusFlow (also Jan 2025) is a flow-matching variant.

---

### DeepSeek-V3-0324

- Release: 2025-03-24 (API checkpoint refresh of V3)
- Status: legacy (superseded by V3.1)
- Context: 128K
- Modality: text
- License: MIT
- Price (in/out per 1M): $0.27 / $1.10 (same as V3)
- Notable: V3 retrained with techniques imported from R1's RL pipeline; major jumps on MMLU-Pro (+5.3), GPQA (+9.3), AIME (+19.8), LiveCodeBench (+10.0).
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "API change log — V3-0324 release"
    date: 2025-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V3-0324
    title: "DeepSeek-V3-0324 model card"
    date: 2025-03

Benchmarks (lab from change log, deltas vs V3):
- MMLU-Pro: 81.2 [lab] src=https://api-docs.deepseek.com/updates date=2025-03
- GPQA Diamond: 68.4 [lab]
- AIME: 59.4 [lab]
- LiveCodeBench: 49.2 [lab]

Notes: Despite the name, V3-0324 has the same 685B parameter count as V3.1 — the "+R1 training" upgrade was post-training, not architectural.

---

### DeepSeek-Prover-V2

- Release: 2025-04-30
- Status: current (formal math specialist)
- Context: 32K
- Modality: text (Lean 4 formal proofs)
- License: MIT
- Notable: 7B and 671B (built on V3-Base) for formal theorem proving in Lean 4; 88.9% pass on MiniF2F; solved 49/658 PutnamBench problems; ships its own benchmark, **ProverBench** (325 problems including 15 from recent AIME contests).
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2504.21801
    title: "DeepSeek-Prover-V2: Advancing Formal Mathematical Reasoning via RL for Subgoal Decomposition"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-671B
    title: "DeepSeek-Prover-V2-671B model card"
    date: 2025-04

Benchmarks (lab):
- MiniF2F (Lean 4): 88.9 [lab] src=https://arxiv.org/abs/2504.21801 date=2025-04
- PutnamBench: 49/658 [lab]
- ProverBench AIME 15: 6 solved [lab]

Notes: Niche specialist; not used as a general-chat SKU.

---

### DeepSeek-R1-0528

- Release: 2025-05-28
- Status: legacy (R-line frozen; thinking-mode moved into V3.1)
- Context: 128K
- Modality: text (reasoning)
- License: MIT
- Price (in/out per 1M): $0.55 / $2.19
- Notable: Major refresh of R1; uses ~2× more reasoning tokens per problem (12K → 23K on AIME); hallucinations reduced 45–50%; added system-prompt support, function calling, JSON output. The last numbered R-line model — V3.1 absorbed thinking-mode into the trunk three months later.
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "API change log — DeepSeek-R1-0528 release"
    date: 2025-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-R1-0528
    title: "DeepSeek-R1-0528 model card"
    date: 2025-05

Benchmarks (lab, deltas from R1):
- AIME 2025: 87.5 [lab] (was 70.0 on R1) src=https://api-docs.deepseek.com/updates date=2025-05
- AIME 2024: 91.4 [lab]
- GPQA Diamond: 81.0 [lab] (was 71.5)
- SWE-bench Verified: 57.6 [lab] (was 49.2 on R1, also reported as 44.6 on V3.1 model card)
- LiveCodeBench v6: 73.3 [lab] (was 63.5)
- Aider: 71.6 [lab] (was 57.0)
- MMLU-Pro: 85.0 [lab]
- HLE: 17.7 [lab]
- BrowseComp: 8.9 [lab]

Notes: Second-highest AIME 2024/2025 scores at release behind OpenAI o3 only. Distilled into a Qwen3-8B variant the same week.

---

### DeepSeek-V3.1

- Release: 2025-08-21
- Status: legacy (refresh `V3.1-Terminus` on 2025-09-22; superseded by V3.2-Exp / V3.2)
- Context: 128K
- Modality: text
- License: MIT
- Price (in/out per 1M): $0.555 / $1.67 (per Artificial Analysis 3p; off-peak discounts ended 2025-09-05)
- Notable: First DeepSeek with **hybrid thinking / non-thinking modes in a single weight set** — the chat template toggles mode; absorbed R1's reasoning into the main trunk; +840B tokens of continued pretraining at extended context; major SWE-bench / Terminal-Bench gains (agent capability).
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/news/news250821
    title: "DeepSeek-V3.1 Release"
    date: 2025-08
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V3.1
    title: "DeepSeek-V3.1 model card with benchmark table"
    date: 2025-08
  - kind: pricing
    tag: 3p
    url: https://artificialanalysis.ai/models/deepseek-v3-1
    publisher: Artificial Analysis
    title: "DeepSeek V3.1 intelligence index & pricing"
    date: 2025-09

Benchmarks (lab from model card; -Thinking unless tagged):
- SWE-bench Verified (Non-Thinking): 66.0 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-V3.1 date=2025-08
- SWE-bench Multilingual (Non-Thinking): 54.5 [lab]
- AIME 2024: 93.1 [lab]
- AIME 2025: 88.4 [lab]
- GPQA Diamond: 80.1 [lab]
- MMLU-Pro: 84.8 [lab]
- LiveCodeBench: 74.8 [lab]
- HLE: 15.9 [lab]
- BrowseComp: 30.0 [lab]
- Terminal-Bench (Non-Thinking): 31.3 [lab]

Notes: V3.1-Terminus (2025-09-22) addressed language-consistency and agent reliability bugs; same architecture/weights size class. CoT tokens reduced 20–50% vs R1-0528.

---

### DeepSeek-V3.2-Exp

- Release: 2025-09-29
- Status: legacy (experimental — superseded by V3.2 official on 2025-12-01)
- Context: 128K (with sparse attention up to long context)
- Modality: text
- License: MIT
- Price (in/out per 1M): roughly half of V3.1 (DSA cost savings passed through)
- Notable: First DeepSeek to ship **DeepSeek Sparse Attention (DSA)** — fine-grained sparse attention designed to make long-context training and inference cheap; on-par with V3.1-Terminus on standard benchmarks while substantially reducing compute.
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "API change log — V3.2-Exp release"
    date: 2025-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp
    title: "DeepSeek-V3.2-Exp model card with benchmark table"
    date: 2025-09

Benchmarks (lab from model card):
- MMLU-Pro: 85.0 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp date=2025-09
- GPQA Diamond: 79.9 [lab]
- HLE: 19.8 [lab]
- LiveCodeBench: 74.1 [lab]
- AIME 2025: 89.3 [lab]
- HMMT 2025: 83.6 [lab]
- Codeforces (rating): 2121 [lab]
- Aider Polyglot: 74.5 [lab]
- BrowseComp: 40.1 [lab]
- BrowseComp-zh: 47.9 [lab]
- SimpleQA: 97.1 [lab]
- SWE-bench Verified: 67.8 [lab]
- SWE-bench Multilingual: 57.9 [lab]
- Terminal-Bench: 37.7 [lab]

Notes: Near-parity with V3.1-Terminus on standard reasoning + coding while the sparse attention chiefly addresses long-context cost. 685B total parameters.

---

### DeepSeek-V3.2 + V3.2-Speciale

- Release: 2025-12-01 (V3.2 official); V3.2-Speciale ran on a temporary endpoint until 2025-12-15
- Status: legacy (current trunk became V4 on 2026-04-24)
- Context: 128K (DSA-optimized)
- Modality: text
- License: MIT
- Price (in/out per 1M): same as V3.2 (Speciale priced identically)
- Notable: First DeepSeek to **integrate thinking directly into tool-use** — tool-calling works in both modes; **Gold-medal performance in 2025 IMO and IOI**. The **V3.2-Speciale** high-compute variant reportedly surpassed GPT-5 on reasoning and matched Gemini 3.0 Pro — research-tier endpoint, no tool calls, only available two weeks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/news/news251201
    title: "DeepSeek-V3.2 Release"
    date: 2025-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/deepseek-ai/DeepSeek-V3.2
    title: "DeepSeek-V3.2 model card"
    date: 2025-12
  - kind: announcement
    tag: lab
    url: https://x.com/deepseek_ai/status/1995452641430651132
    title: "DeepSeek-V3.2 + V3.2-Speciale launch tweet"
    date: 2025-12
  - kind: coverage
    tag: 3p
    url: https://the-decoder.com/deepseek-v3-2-rivals-gpt-5-and-gemini-3-pro-reaches-imo-gold-level-as-open-source/
    publisher: The Decoder
    title: "DeepSeek V3.2 rivals GPT-5 and Gemini 3 Pro"
    date: 2025-12

Benchmarks (lab from model card):
- SWE-bench Verified: 70 [lab] src=https://huggingface.co/deepseek-ai/DeepSeek-V3.2 date=2025-12
- SWE-bench Pro: 15.56 [lab]
- IMO 2025: Gold-medal [lab] (V3.2-Speciale)
- IOI 2025: Gold-medal [lab] (V3.2-Speciale)
- ICPC World Finals 2025: Gold-tier [lab] (V3.2-Speciale)

Notes: Speciale was an unusual ship — research-tier maxed-out reasoning, two-week availability, then taken down. Hugging Face card shows additional benchmarks are gated behind PDF / expandable images on the model page.

---

### DeepSeek-Math-V2

- Release: 2025-11-27
- Status: current (math specialist)
- Context: 32K
- Modality: text (math)
- License: **Apache 2.0** (note: not MIT — slightly different from the V-line / R-line)
- Notable: Successor to DeepSeekMath 7B with extended reasoning.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/DeepSeek
    publisher: Wikipedia
    title: "DeepSeek — DeepSeek-Math-V2 entry"
    date: 2026-05

Notes: Niche; no headline frontier-bench numbers published vs the V-line trunk.

---

### DeepSeek-V4 (V4-Pro and V4-Flash)

- Release: 2026-04-24 (Preview)
- Status: current (preview — `deepseek-chat` and `deepseek-reasoner` legacy IDs will be retired 2026-07-24)
- Context: **1M tokens** (now the default across DeepSeek services)
- Modality: text (V4-line vision SKU not yet announced)
- License: MIT
- Price (in/out per 1M, current as of May 2026):
  - **V4-Flash**: $0.14 input (cache miss) / $0.0028 input (cache hit) / $0.28 output
  - **V4-Pro**: $0.435 input (cache miss) / $0.003625 input (cache hit) / $0.87 output — a temporary 75% discount through 2026-05-31; regular pricing will be 1/4 of original rates after promo
- Notable:
  - **V4-Pro**: 1.6T total / 49B active
  - **V4-Flash**: 284B total / 13B active
  - Both ship `Non-think` + `Think High` + `Think Max` modes; thinking integrated with tool-use
  - Novel attention: **token-wise compression + DSA**; V4-Pro uses ~27% FLOPs and ~10% KV cache vs V3.2 at 1M tokens
  - Supports both OpenAI ChatCompletions and Anthropic API surface
  - Adopted by Huawei and Cambricon Chinese-chip stacks for inference
- Sources:
  - kind: announcement
    tag: lab
    url: https://api-docs.deepseek.com/news/news260424
    title: "DeepSeek-V4 Preview Release"
    date: 2026-04
  - kind: pricing
    tag: lab
    url: https://api-docs.deepseek.com/quick_start/pricing
    title: "DeepSeek API pricing page"
    date: 2026-05
  - kind: deprecation
    tag: lab
    url: https://api-docs.deepseek.com/updates
    title: "deepseek-chat / deepseek-reasoner retiring 2026-07-24"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://www.nxcode.io/resources/news/deepseek-v4-release-specs-benchmarks-2026
    publisher: NxCode
    title: "DeepSeek V4 (2026): 1T Parameters, 81% SWE-bench, $0.30/MTok"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://www.sitepoint.com/deepseek-v4-released-whats-new-in-the-latest-model-2026/
    publisher: SitePoint
    title: "DeepSeek V4 Released: What's New in the Latest Model (2026)"
    date: 2026-05

Benchmarks (V4-Pro headline; lab from launch slides via 3p coverage):
- SWE-bench Verified: 80.6 [3p:NxCode quoting lab] src=https://www.nxcode.io/resources/news/deepseek-v4-release-specs-benchmarks-2026 date=2026-04
- HumanEval: 90 [lab] (preview, leaked) src=https://macaron.im/blog/deepseek-v4-benchmarks date=2026-02
- Best open-source on world-knowledge / SimpleQA-Verified — "20pp above competitors" [lab claim]
- Gold-tier on Math / STEM / Coding in lab framing
- Full SWE-Pro, Terminal-Bench 2.0, HLE, GPQA, MMLU-Pro, AIME 2025, ARC-AGI, FrontierMath numbers: not yet published in a verifiable lab table — launch announcement uses image charts that 3p have transcribed inconsistently. As of May 2026, treat V4 numbers other than SWE-Verified 80.6 as **preview claims** until independent replications land.

Notes: V4 is a **preview** — DeepSeek explicitly labeled it that way at launch. Independent third-party benchmarking (Artificial Analysis, llm-stats, swebench.com) was still in progress as of May 2026, so the report avoids quoting per-bench lab numbers that aren't backed by HF model-card text or arXiv tables. The deprecation of `deepseek-chat` and `deepseek-reasoner` on 2026-07-24 means the legacy V3.x SKUs lose their API mappings and only V4-Pro / V4-Flash remain hosted.

---

### DeepSeek-R2 — status: **not shipped as of May 2026**

Reuters reported in Feb 2025 that DeepSeek was accelerating an R1 successor named R2 toward an early-May 2025 release; that date passed without a release. As of May 2026:

- No R2 model has been announced or published on `huggingface.co/deepseek-ai`
- The API `deepseek-reasoner` model ID currently maps to V4-Flash thinking mode (previously to V3.2 reasoner, previously to R1-0528)
- The hybrid-thinking direction in V3.1 → V3.2 → V4 appears to have **subsumed** the R-line into the V-line trunk

Sources:
  - kind: coverage
    tag: 3p
    url: https://chat-deep.ai/guide/deepseek-roadmap-rumors/
    publisher: chat-deep.ai
    title: "DeepSeek Roadmap, Rumors & Confirmed Releases — R2 status"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://manifold.markets/Bayesian/when-will-deepseek-release-r2
    publisher: Manifold
    title: "Prediction market on R2 / V4-Thinking release"
    date: 2026-05

---

## Sources

- https://github.com/deepseek-ai/DeepSeek-Coder
- https://arxiv.org/abs/2401.14196
- https://github.com/deepseek-ai/DeepSeek-LLM
- https://huggingface.co/TheBloke/deepseek-llm-67b-base-GGUF
- https://www.marktechpost.com/2023/12/04/deepseek-open-sources-deepseek-67b-model-the-latest-chatgpt-rival-from-china/
- https://huggingface.co/deepseek-ai/deepseek-moe-16b-base
- https://arxiv.org/abs/2402.03300
- https://github.com/deepseek-ai/DeepSeek-Math
- https://github.com/deepseek-ai/DeepSeek-VL
- https://arxiv.org/abs/2405.04434
- https://huggingface.co/deepseek-ai/DeepSeek-V2
- https://arxiv.org/abs/2406.11931
- https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct
- https://artificialanalysis.ai/models/deepseek-coder-v2
- https://huggingface.co/deepseek-ai/DeepSeek-V2.5
- https://arxiv.org/abs/2412.10302
- https://huggingface.co/deepseek-ai/deepseek-vl2
- https://github.com/deepseek-ai/DeepSeek-VL2
- https://arxiv.org/abs/2412.19437
- https://huggingface.co/deepseek-ai/DeepSeek-V3
- https://siliconangle.com/2024/12/26/deepseek-open-sources-new-ai-model-671b-parameters/
- https://arxiv.org/abs/2501.12948
- https://huggingface.co/deepseek-ai/DeepSeek-R1
- https://artificialanalysis.ai/models/deepseek-r1
- https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
- https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B
- https://github.com/deepseek-ai/Janus
- https://huggingface.co/deepseek-ai/Janus-Pro-7B
- https://technode.com/2025/01/30/deepseek-releases-new-models-janus-pro-and-janusflow-on-lunar-new-years-eve/
- https://huggingface.co/deepseek-ai/DeepSeek-V3-0324
- https://arxiv.org/abs/2504.21801
- https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-671B
- https://huggingface.co/deepseek-ai/DeepSeek-R1-0528
- https://api-docs.deepseek.com/news/news250821
- https://huggingface.co/deepseek-ai/DeepSeek-V3.1
- https://artificialanalysis.ai/models/deepseek-v3-1
- https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp
- https://api-docs.deepseek.com/news/news251201
- https://huggingface.co/deepseek-ai/DeepSeek-V3.2
- https://x.com/deepseek_ai/status/1995452641430651132
- https://the-decoder.com/deepseek-v3-2-rivals-gpt-5-and-gemini-3-pro-reaches-imo-gold-level-as-open-source/
- https://api-docs.deepseek.com/news/news260424
- https://api-docs.deepseek.com/quick_start/pricing
- https://api-docs.deepseek.com/updates
- https://www.nxcode.io/resources/news/deepseek-v4-release-specs-benchmarks-2026
- https://www.sitepoint.com/deepseek-v4-released-whats-new-in-the-latest-model-2026/
- https://macaron.im/blog/deepseek-v4-benchmarks
- https://chat-deep.ai/guide/deepseek-roadmap-rumors/
- https://manifold.markets/Bayesian/when-will-deepseek-release-r2
- https://en.wikipedia.org/wiki/DeepSeek
- https://timelines.issarice.com/wiki/Timeline_of_DeepSeek
- https://www.bentoml.com/blog/the-complete-guide-to-deepseek-models-from-v3-to-r1-and-beyond
