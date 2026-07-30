# Allen Institute (AI2) OLMo Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** AI2's OLMo line is the **most transparent open
release in the field** — they ship weights + training data (Dolma corpus) +
training code (OLMo-core) + intermediate checkpoints + training logs + tech
reports, all under permissive licenses (Apache 2.0). Canonical `lab` source
is `allenai.org/blog/...` post + HuggingFace `allenai/...` model card +
arXiv tech report. Models are hosted on HuggingFace and Together; no
proprietary API tier. No pricing column applies — open-weights only.

**Licensing.** Every OLMo / OLMoE / Molmo / Tülu (post-Tülu 2) model is
**Apache 2.0**. Training datasets (Dolma, Dolma 2, Dolma 3, Tülu 3 mix,
PixMo, Dolci) ship under ODC-BY / Apache, with the standard caveat that
some upstream third-party data carries non-commercial restrictions. The
"fully open" claim is genuine — AI2 publishes the actual pretraining
corpus, not just the recipe.

**Lineage shape (Feb 2024 → May 2026).**

1. **OLMo 1** (Feb 2024) — 1B + 7B, 2.5T tokens — first **fully open** LM.
2. **OLMo 1.7** (Apr 2024) — 7B with +24 MMLU points via Dolma 1.7 + staged training.
3. **OLMo July 2024** (Jul 2024) — interim 7B update, hf-transformers-native.
4. **OLMoE 1B-7B** (Sep 2024) — first fully-open MoE; 1B active / 7B total.
5. **Molmo** (Sep 2024) — vision-language family (1B / 7B-O / 7B-D / 72B).
6. **Tülu 3** (Nov 2024) — post-training recipe on Llama 3.1; 8B / 70B / later 405B.
7. **OLMo 2** (Nov 2024) — 7B + 13B, dense; 5T tokens; SFT→DPO→RLVR pipeline.
8. **OLMo 2 32B** (Mar 2025) — first **fully open** model to beat GPT-3.5 / GPT-4o-mini.
9. **OLMo 3** (Nov 2025) — 7B + 32B Base / Instruct / Think; first fully-open thinking model.
10. **OLMo 3.1** (Dec 2025) — extended RL run on 32B Think + Instruct.
11. **Molmo 2** (Dec 2025) — video understanding + Qwen-3 / OLMo backbones.
12. **OLMo Hybrid** (Mar 2026) — 7B transformer + Gated DeltaNet linear-RNN hybrid.

Convention: dates are **announcement / first availability**. Tülu 1 (2023,
pre-OLMo) is out of scope; the lineage proper starts at OLMo 1.

---

### OLMo 1 (7B base)

- Release: 2024-02-01 (first OLMo release)
- Status: legacy (superseded by OLMo 1.7)
- Size / active: 7B dense
- Context: 2,048 tokens
- Modality: text only
- License: Apache 2.0
- Training tokens: 2.5T (Dolma 1.0)
- Notable: First **truly open** LM — AI2 released model weights, the full
  Dolma pretraining corpus, training code, training logs, and intermediate
  checkpoints. The "Accelerating the Science of Language Models" thesis.
  Performance was modest by the standards of even early 2024 (Llama-2-7B
  outperformed it on most benches), but the openness was the point.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmo-open-language-model-87ccfc95f580
    title: "OLMo: Open Language Model"
    date: 2024-02
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMo-7B
    title: "allenai/OLMo-7B"
    date: 2024-02
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2402.00838
    title: "OLMo: Accelerating the Science of Language Models"
    date: 2024-02

Benchmarks (base model, lab numbers from HF model card):
- MMLU (5-shot MC): 28.3 [lab] src=https://huggingface.co/allenai/OLMo-7B date=2024-02
- GSM8K (8-shot CoT): 8.5 [lab] src=https://huggingface.co/allenai/OLMo-7B date=2024-02
- HellaSwag: 76.4 [lab] src=https://huggingface.co/allenai/OLMo-7B date=2024-02
- ARC Challenge: 48.5 [lab] src=https://huggingface.co/allenai/OLMo-7B date=2024-02

Notes: 1B variant (`allenai/OLMo-1B`) shipped alongside, trained on 3T
tokens; benchmarks similarly modest. Both retired from active development
once OLMo 2 1B-13B / OLMo 3 7B-32B lines took over.

---

### OLMo 1.7 (7B base, `OLMo-7B-0424`)

- Release: 2024-04 (24 April variant)
- Status: legacy (superseded by OLMo 2)
- Size / active: 7B dense
- Context: 4,096 (doubled from 2,048)
- License: Apache 2.0
- Training tokens: 2.05T (Dolma 1.7) + staged annealing
- Notable: Headline number was **+24 points MMLU** in just three months —
  jumped from 28.3 → 52.0 via (a) cleaner Dolma 1.7 data, (b) two-stage
  pretraining with high-quality data in the second stage (the "annealing"
  recipe later canonical at OLMo 2), and (c) longer context. First OLMo
  model to match Llama-2-7B and approach Llama-2-13B on knowledge.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmo-1-7-7b-a-24-point-improvement-on-mmlu-92b43f7d269d
    title: "OLMo 1.7–7B: A 24 point improvement on MMLU"
    date: 2024-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMo-7B-0424
    title: "allenai/OLMo-7B-0424"
    date: 2024-04

Benchmarks (base model, lab numbers):
- MMLU (5-shot): 52.0 [lab] src=https://huggingface.co/allenai/OLMo-7B-0424 date=2024-04
- GSM8K: 29.0 [lab] src=https://huggingface.co/allenai/OLMo-7B-0424 date=2024-04
- ARC Challenge: 42.5 [lab] src=https://huggingface.co/allenai/OLMo-7B-0424 date=2024-04
- HellaSwag: 75.5 [lab] src=https://huggingface.co/allenai/OLMo-7B-0424 date=2024-04

Notes: A July 2024 variant (`OLMo-7B-0724`, "transformers-native HF
checkpoint") shipped as an interop convenience release, not a capability
update.

---

### OLMoE-1B-7B (sparse MoE)

- Release: 2024-09-04
- Status: current (still the canonical AI2 MoE; no MoE follow-up shipped)
- Size / active: **1B active, 7B total** (64 experts, 8 active per token)
- Context: 4,096 tokens
- License: Apache 2.0
- Training tokens: 5.0T (Dolma-based MoE pretraining mix)
- Notable: First **fully open** Mixture-of-Experts LM (weights + training data
  + code + 244 intermediate checkpoints). Competitive with **Llama-2-13B**
  at 1B inference cost; on the Pareto frontier of cost vs. performance for
  its tier. Instruct variant trained with SFT + DPO (Tülu 2 style mix).
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2409.02060
    title: "OLMoE: Open Mixture-of-Experts Language Models"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMoE-1B-7B-0924
    title: "allenai/OLMoE-1B-7B-0924"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct
    title: "allenai/OLMoE-1B-7B-0924-Instruct"
    date: 2024-09

Benchmarks (Instruct + DPO, lab numbers):
- MMLU (0-shot): 51.9 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09
- GSM8K (8-shot CoT): 45.5 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09
- BBH (3-shot): 37.0 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09
- HumanEval: 54.8 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09
- AlpacaEval 1.0: 84.0 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09
- IFEval: 48.1 [lab] src=https://huggingface.co/allenai/OLMoE-1B-7B-0924-Instruct date=2024-09

Notes: Frontier-18 benchmarks (SWE-bench, LiveCodeBench, AIME, GPQA) not
reported — those weren't standard at MoE release; model is below their
floor anyway. Genuinely useful as a "small-MoE reference" rather than a
frontier comparison row.

---

### Molmo 7B-O / 7B-D / 72B / 1B-MoE (vision-language)

- Release: 2024-09-25
- Status: legacy (superseded by Molmo 2, Dec 2025)
- Variants:
  - **Molmo-1B-MoE-O** — OLMoE 1B-7B backbone + CLIP
  - **Molmo-7B-O** — OLMo-7B-1024 backbone + CLIP
  - **Molmo-7B-D** — Qwen 2 7B backbone + CLIP
  - **Molmo-72B** — Qwen 2 72B backbone + CLIP (flagship)
- Modality: vision-language (image input, text output) + 2D pointing
- License: Apache 2.0 (PixMo dataset Apache 2.0; some upstream caveats)
- Notable: Trained on **PixMo**, a 1M-image dataset collected **without
  using external VLMs** — distillation-free. Innovation: dense captions
  via human voice descriptions (workers describe images aloud for 60-90s,
  then transcribed), and a 2D pointing dataset for grounded tasks. Molmo
  72B matched / beat Claude 3.5 Sonnet and Gemini 1.5 Pro on academic
  benches at release.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2409.17146
    title: "Molmo and PixMo: Open Weights and Open Data for State-of-the-Art Vision-Language Models"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/Molmo-7B-O-0924
    title: "allenai/Molmo-7B-O-0924"
    date: 2024-09

Benchmarks (Molmo-72B, lab numbers, averaged across 11 academic VL benches):
- Academic-11 average: 81.2 [lab] src=https://arxiv.org/abs/2409.17146 date=2024-09
- Human-preference Elo: 1077 [lab] src=https://arxiv.org/abs/2409.17146 date=2024-09

Benchmarks (Molmo-7B-O variant, OLMo-backboned):
- Academic-11 average: 74.6 [lab] src=https://huggingface.co/allenai/Molmo-7B-O-0924 date=2024-09
- Human-preference Elo: 1051 [lab] src=https://huggingface.co/allenai/Molmo-7B-O-0924 date=2024-09

Notes: AI2 positioning — 72B sat between GPT-4V (71.1 avg) and GPT-4o
(78.5 avg). Specialist VL benchmarks (MMMU, MathVista, AI2D, ChartQA,
DocVQA) make up the average; not directly comparable to frontier-18.

---

### Tülu 3 (8B / 70B / 405B post-trained Llama 3.1)

- Release: 2024-11-21 (8B / 70B); 2025-01-30 (405B)
- Status: current (canonical AI2 post-training recipe; flowed into OLMo 2 / OLMo 3)
- Sizes: 8B, 70B, 405B (all built on Llama 3.1 base)
- License: Apache 2.0 (post-training artifacts); base inherits Llama 3.1 license
- Notable: AI2's **fully-open post-training recipe** — SFT on curated mix,
  DPO on AI2-generated preferences, and a novel **RLVR** (RL with
  Verifiable Rewards) stage on math / code / IF tasks. Tülu 3 70B beat
  Claude 3 Haiku, GPT-3.5 Turbo, GPT-4o-mini. The 405B variant matched
  / exceeded DeepSeek V3 (Dec 2024) at release — first fully-open model
  to do so. **Recipe shipped open** is the real artifact; OLMo 2 / 3
  Instruct lines reuse it.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/tulu-3
    title: "Tülu 3 opens language model post-training up to more tasks and more people"
    date: 2024-11
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2411.15124
    title: "Tülu 3: Pushing Frontiers in Open Language Model Post-Training"
    date: 2024-11
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/tulu-3-405B
    title: "Scaling the Tülu 3 post-training recipes to surpass the performance of DeepSeek V3"
    date: 2025-01

Benchmarks (Tülu 3 70B, lab numbers):
- GSM8K: 93.5 [lab] src=https://arxiv.org/abs/2411.15124 date=2024-11
- HumanEval (pass@10): 92.4 [lab] src=https://arxiv.org/abs/2411.15124 date=2024-11
- Safety-6: 88.3 [lab] src=https://arxiv.org/abs/2411.15124 date=2024-11

Benchmarks (Tülu 3 8B, lab numbers):
- GSM8K: 87.6 [lab] src=https://arxiv.org/abs/2411.15124 date=2024-11
- Safety-6: 85.5 [lab] src=https://arxiv.org/abs/2411.15124 date=2024-11

Notes: Tülu 2 (Nov 2023, Llama-2 base + DPO at 7B/13B/70B) is the
predecessor — first big DPO-trained open model. Pre-OLMo-line, mostly
of historical interest now; recipe lives on inside OLMo 2/3 Instruct.

---

### OLMo 2 7B / 13B (`OLMo-2-1124-*`)

- Release: 2024-11-26 (post-trained variants finalized 2025-01-03)
- Status: legacy (superseded by OLMo 3 at the 7B / 32B slots)
- Sizes: 7B, 13B dense
- Context: 4,096 tokens
- License: Apache 2.0
- Training tokens: ~5T (Dolma + Dolmino mid-training mix)
- Notable: First "real frontier-tier" OLMo — 7B beat Llama 3.1 8B, 13B
  matched Qwen 2.5 14B. Two-stage pretraining (Dolma "stable" then
  Dolmino "annealing" with curated high-signal mix) became canonical.
  Instruct pipeline: SFT (Tülu 3 mix) → DPO → RLVR. Jan 2025 retraining
  fixed a pre-tokenization mismatch — current HF checkpoints reflect
  that; "-preview" suffix carries the legacy weights.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmo2
    title: "OLMo 2: The best fully open language model to date"
    date: 2024-11
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2501.00656
    title: "2 OLMo 2 Furious"
    date: 2025-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct
    title: "allenai/OLMo-2-1124-13B-Instruct"
    date: 2024-11

Benchmarks (OLMo 2 13B Instruct, lab numbers):
- MMLU: 68.5 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- MATH: 39.2 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- GSM8K: 87.4 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- IFEval: 82.6 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- AlpacaEval 2 LC: 39.5 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- BBH: 58.8 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- DROP: 71.5 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01
- TruthfulQA: 64.3 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct date=2025-01

Benchmarks (OLMo 2 7B Instruct, lab numbers):
- MMLU: 61.3 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct date=2025-01
- MATH: 32.5 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct date=2025-01
- GSM8K: 85.1 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct date=2025-01
- IFEval: 72.3 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct date=2025-01
- AlpacaEval 2 LC: 29.1 [lab] src=https://huggingface.co/allenai/OLMo-2-1124-7B-Instruct date=2025-01

Notes: Frontier-18 benches (SWE-bench, GPQA Diamond, AIME) not reported
by AI2 — model predates that being standard for this tier; specialist
agentic tasks weren't OLMo 2's positioning.

---

### OLMo 2 32B (`OLMo-2-0325-32B`)

- Release: 2025-03-13
- Status: legacy (superseded by OLMo 3 32B, Nov 2025)
- Size: 32B dense
- Context: 4,096 tokens
- License: Apache 2.0
- Training tokens: 6T (OLMo-Mix-1124 pretraining + Dolmino mid-training)
- Notable: **First fully-open model** to beat GPT-3.5 Turbo and GPT-4o-mini
  on a multi-skill academic suite (MMLU + MATH + GSM8K + IFEval + BBH +
  DROP + AlpacaEval, averaged). Reported as trained at **~1/3 the cost
  of Qwen 2.5 32B**. Matched / approached Llama 3.1-70B and Qwen 2.5-72B
  while being 2x smaller. SFT → DPO → RLVR pipeline (Tülu 3.1 mix).
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmo2-32b
    title: "OLMo 2 32B: First fully open model to outperform GPT 3.5 and GPT 4o mini"
    date: 2025-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct
    title: "allenai/OLMo-2-0325-32B-Instruct"
    date: 2025-03
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2025/03/14/allen-institute-for-ai-ai2-releases-olmo-32b-a-fully-open-model-to-beat-gpt-3-5-and-gpt-4o-mini-on-a-suite-of-multi-skill-benchmarks/
    title: "AI2 Releases OLMo 32B"
    publisher: MarkTechPost
    date: 2025-03

Benchmarks (32B Instruct, lab numbers):
- MMLU: 77.3 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- MATH: 49.7 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- GSM8K: 87.6 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- IFEval: 85.6 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- AlpacaEval 2 LC: 42.8 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- BBH: 70.6 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- DROP: 78.0 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- TruthfulQA: 73.2 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03
- Average (lab 10-bench suite): 68.8 [lab] src=https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct date=2025-03

Notes: SWE-bench / LiveCodeBench / GPQA / AIME still not in AI2's
reported set for OLMo 2 line. These appear at OLMo 3 (the reasoning
variant ships them).

---

### OLMo 3 Base / Instruct / Think (7B + 32B)

- Release: 2025-11-20
- Status: **current frontier OLMo** (joint flagship with OLMo 3.1)
- Sizes: 7B and 32B; variants Base / Instruct / Think / RL-Zero (7B only)
- Context: **65,536 tokens** (16x OLMo 2's 4K)
- License: Apache 2.0
- Training tokens: ~5.9T pretrain + post-train (Dolma 3, ~9.3T corpus total)
- Notable: First **fully open thinking model** — exposes intermediate
  chain-of-thought traces; not just weights, but the entire RL pipeline
  (Dolci-Think-SFT / DPO / RLVR datasets) is open. **Think 32B** narrows
  the gap to Qwen 3-32B-Think while trained on **6x fewer tokens**.
  Beats Marin 32B and Apertus 70B among fully-open peers on math + code.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmo3
    title: "Olmo 3: Charting a path through the model flow to lead open-source AI"
    date: 2025-11
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2512.13961
    title: "Olmo 3" (tech report)
    date: 2025-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/Olmo-3-1125-32B
    title: "allenai/Olmo-3-1125-32B" (Base)
    date: 2025-11
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/Olmo-3-32B-Think
    title: "allenai/Olmo-3-32B-Think"
    date: 2025-11
  - kind: coverage
    tag: 3p
    url: https://www.interconnects.ai/p/olmo-3-americas-truly-open-reasoning
    title: "Olmo 3: America's truly open reasoning models"
    publisher: Nathan Lambert / Interconnects
    date: 2025-11

Benchmarks (OLMo 3 32B Base, lab numbers):
- MMLU: 70.8 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11
- MMLU-Pro: 61.1 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11
- BBH: 81.0 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11
- ARC MC: 94.7 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11
- HumanEval: 66.5 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11
- MATH: 48.7 [lab] src=https://huggingface.co/allenai/Olmo-3-1125-32B date=2025-11

Benchmarks (OLMo 3 32B Think, lab numbers):
- MMLU: 85.4 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- GPQA Diamond: 58.1 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- AIME 2024: 76.8 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- AIME 2025: 72.5 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- MATH: 96.1 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- HumanEval+: 91.4 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- BBH: 89.8 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11
- IFEval: 89.0 [lab] src=https://huggingface.co/allenai/Olmo-3-32B-Think date=2025-11

Benchmarks (OLMo 3 7B Think, lab numbers):
- MMLU-Pro: 65.5 [lab] src=https://allenai.org/blog/olmo3 date=2025-11
- GPQA Diamond: 51.6 [lab] src=https://allenai.org/blog/olmo3 date=2025-11
- AIME 2025: 70.7 [lab] src=https://allenai.org/blog/olmo3 date=2025-11

Notes: SWE-bench / LiveCodeBench / Terminal-Bench are NOT in AI2's
reported set even for OLMo 3 Think — these are agentic-style benches
and AI2's positioning is "open reasoning" (chain-of-thought visibility),
not agent integration. Cell stays as `—` on the frontier table.

---

### OLMo 3.1 32B Think / Instruct

- Release: 2025-12-12
- Status: **current** (extended RL run on top of OLMo 3 32B)
- Size: 32B dense
- Context: 65,536 tokens
- License: Apache 2.0
- Notable: Same base weights as OLMo 3 32B, but RL stage extended on a
  much longer schedule. Net effect: **+5 points on AIME** vs. OLMo 3
  Think 32B. Outperforms Qwen 3 32B on AIME 2025 and approaches Gemma
  3 27B on MMLU. AI2's current "best open thinker".
- Sources:
  - kind: announcement
    tag: lab
    url: https://venturebeat.com/ai/ai2s-new-olmo-3-1-extends-reinforcement-learning-training-for-stronger
    title: "Ai2's new Olmo 3.1 extends RL training for stronger reasoning"
    publisher: VentureBeat
    date: 2025-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/Olmo-3.1-32B-Think
    title: "allenai/Olmo-3.1-32B-Think"
    date: 2025-12
  - kind: model-card
    tag: lab
    url: https://huggingface.co/allenai/Olmo-3.1-32B-Instruct
    title: "allenai/Olmo-3.1-32B-Instruct"
    date: 2025-12

Benchmarks (OLMo 3.1 32B Think, lab numbers):
- MMLU: 86.4 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- GPQA: 57.5 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- AIME 2024: 80.6 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- AIME 2025: 78.1 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- MATH: 96.2 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- HumanEval+: 91.5 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12
- IFEval: 93.8 [lab] src=https://huggingface.co/allenai/Olmo-3.1-32B-Think date=2025-12

Notes: This is the AI2 row to put on the frontier table for "open
thinker @ 32B." Same SWE-bench / LiveCodeBench gap as OLMo 3.

---

### Molmo 2 (vision-language, video)

- Release: 2025-12-11
- Status: current (canonical AI2 VL family)
- Variants:
  - **Molmo 2 (8B)** — Qwen 3 base; best overall
  - **Molmo 2 (4B)** — Qwen 3 base; efficiency tier
  - **Molmo 2-O (7B)** — **OLMo-based**; fully open end-to-end (matters
    for "weights+data+code open" criterion — Qwen-backed variants inherit
    Qwen's training-data opacity)
- Modality: vision-language + **video** (8.7M images + 9.19M videos)
- License: Apache 2.0 (with some third-party dataset academic-only caveats)
- Notable: New positioning — beats Gemini 3 Pro on video tracking among
  open-weight models; top on short-video QA averaged across seven benches;
  top on image QA across 11 benches. Uses < 1/8 the video data of Meta's
  PerceptionLM and still outperforms it.
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/molmo2
    title: "Molmo 2: State-of-the-art video understanding, pointing, and tracking"
    date: 2025-12

Benchmarks (Molmo 2 8B, lab claims — full numbers not yet in 3p
replications):
- Video tracking suite: leads all open-weight; beats Gemini 3 Pro [lab] src=https://allenai.org/blog/molmo2 date=2025-12
- Image-QA 11-bench average: top open-weight [lab] src=https://allenai.org/blog/molmo2 date=2025-12

Notes: VL-specific, not on the frontier-18 sheet. Recorded for the lab's
"current" coverage row but doesn't populate text-bench cells.

---

### OLMo Hybrid (7B transformer + Gated DeltaNet)

- Release: 2026-03-05
- Status: **current** (architecture research release; not a successor
  to OLMo 3 — different positioning)
- Size: 7B
- Context: 64K (post long-context-extension stage)
- License: Apache 2.0
- Training tokens: ~6T
- Notable: Architecture-first release. Interleaves transformer attention
  with **Gated DeltaNet** (linear-RNN) layers in a 3:1 pattern (3
  DeltaNet sublayers, 1 attention sublayer, repeated). Matches OLMo 3 7B
  accuracy on MMLU using **49% fewer training tokens** — ~2x data
  efficiency from architecture alone. At 64K context, RULER score 85.0
  vs. OLMo 3 7B's 70.9 — substantial long-context lift. Trained on 512
  GPUs (H100 + B200 mix, Lambda infrastructure).
- Sources:
  - kind: announcement
    tag: lab
    url: https://allenai.org/blog/olmohybrid
    title: "Introducing Olmo Hybrid: Combining transformers and linear RNNs for superior scaling"
    date: 2026-03

Benchmarks (OLMo Hybrid 7B, lab numbers):
- MMLU: parity with OLMo 3 7B at 49% of training tokens [lab] src=https://allenai.org/blog/olmohybrid date=2026-03
- RULER (64K context): 85.0 [lab] src=https://allenai.org/blog/olmohybrid date=2026-03

Notes: Research-oriented release. AI2 positions it as "architecture lab"
output more than "frontier flagship" — it's not meant to replace OLMo 3
32B Think on the leaderboard, it's meant to demonstrate the DeltaNet
hybrid recipe.

---

## Coverage status — what's missing

- **OLMo 2 32B Base** numbers (un-Instruct) — not pulled into this report;
  AI2 ships them on the HF model card but the headline (vs. GPT-3.5)
  uses Instruct. Add if frontier table needs `base` row separately.
- **OLMES** (AI2's own benchmark suite) — referenced repeatedly but not
  populated here. OLMES is 20-benchmark internal suite; numbers are
  averages, not directly comparable to frontier-18. Treat as lab-internal.
- **SWE-bench / LiveCodeBench / Terminal-Bench** — **none** of the OLMo
  line reports these. AI2's positioning is "fully open knowledge +
  reasoning model"; agentic coding isn't the lane. Cells stay `—` on the
  frontier table. This is intentional, not a research gap.
- **OLMo 1B** (Feb 2024 small variant) — exists, retired with OLMo 1;
  bench numbers similar to / lower than 7B's pre-1.7. Not surfacing it
  as its own row.

## Row recommendations for the frontier table

Promote to default-visible rows:

1. **OLMo 3.1 32B Think** — AI2's current flagship for reasoning.
2. **OLMo 3 32B Base** — for the "open pretraining champion" row.
3. **OLMo 2 32B Instruct** — historical landmark ("first fully-open to
   beat GPT-3.5/4o-mini"); keep visible until OLMo 3 has wider 3p
   replications.
4. **OLMo Hybrid 7B** — architecture-research interest, optional
   visibility behind filter chip.

Keep behind "show legacy" toggle: OLMo 1, OLMo 1.7, OLMoE, OLMo 2 7B/13B,
Molmo 1, Tülu 2. Tülu 3 + Molmo 2 stay visible under their respective
filter chips (post-training and VL).
