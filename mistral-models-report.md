# Mistral Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** Mistral AI (French lab, founded April 2023) ships
open-weights through `huggingface.co/mistralai` and a hosted API at
`api.mistral.ai` (La Plateforme). Unlike DeepSeek, Mistral rarely publishes
arXiv tech reports — the canonical `lab` source is usually a `mistral.ai/news/`
blog post + HF model card. Wikipedia and issarice timelines are useful
secondary cross-checks.

**Licensing — five buckets.**
1. **Apache 2.0** — 7B, Mixtral 8x7B/8x22B, NeMo, Mathstral, Codestral Mamba,
   Pixtral 12B, Small 3/3.1, Devstral Small (v1/v2), Magistral Small,
   Voxtral Small/Mini, Ministral 3 family, Small 4, Large 3.
2. **Mistral Research License (MRL)** — Large 2, Ministral 8B (initial),
   Pixtral Large. Research only.
3. **Mistral Non-Production License (MNPL)** — Codestral 22B v0.1. Gated.
4. **Modified MIT** — Devstral 2 (Dec 2025), Medium 3.5 (Apr 2026).
   Apache-grade with attribution / patent terms.
5. **Mistral Commercial License** (closed, API-only) — Large v1, Medium v1,
   Medium 3 / 3.1, Magistral Medium, Codestral 25.01 / 25.08, Devstral
   Medium, Saba, OCR.

**Mistral 3 trunk.** The "Mistral 3" family (December 2025) is a coordinated
release: Large 3 (675B MoE) + Ministral 3 (3B/8B/14B) + OCR 3 + Devstral 2 —
all open, mostly Apache. This is the lineage breakpoint where Mistral
reopened after the MRL middle period.

Convention: dates are **announcement / first availability**.

---

### Mistral 7B (v0.1 base)

- Release: 2023-09-27 (first Mistral model)
- Status: legacy (superseded by NeMo for the 7-13B slot)
- Context: 8K (v0.1) → 32K (v0.2, Mar 2024)
- Modality: text only
- License: Apache 2.0
- Price: not on a paid API at launch; later listed on La Plateforme (deprecated)
- Notable: 7.3B dense decoder; first frontier-grade Apache-2.0 model from a non-US lab; introduced SWA + GQA into the open-weights mainstream. Outperformed Llama-2-13B everywhere; matched Llama-1-34B on reasoning.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/announcing-mistral-7b
    title: "Mistral 7B — the best 7B model to date"
    date: 2023-09
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2310.06825
    title: "Mistral 7B technical report"
    date: 2023-10

Benchmarks (5-shot, base model, lab numbers):
- MMLU: 60.1 [lab] src=https://arxiv.org/abs/2310.06825 date=2023-10
- HellaSwag: 81.3 [lab] src=https://arxiv.org/abs/2310.06825 date=2023-10
- GSM8K (maj@8): 52.1 [lab] src=https://arxiv.org/abs/2310.06825 date=2023-10
- HumanEval (pass@1): 30.5 [lab] src=https://arxiv.org/abs/2310.06825 date=2023-10

Notes: Released as raw weights (torrent magnet link in the blog post — Mistral's signature launch style at the time). Instruct variant followed within days.

---

### Mistral Medium (v1, legacy)

- Release: 2023-12-11 (announced alongside Mixtral 8x7B)
- Status: deprecated (retired April 2024, replaced by Large)
- Context: 32K
- Modality: text only
- License: Mistral Commercial (closed, API-only)
- Price (at launch): $2.70 / $8.10 per M tokens (input/output)
- Notable: Mistral's first closed-weight commercial offering; positioned as a GPT-3.5-class model on La Plateforme. Distinct from later "Mistral Medium 3" (May 2025) — different model, same brand reused.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/la-plateforme/
    title: "La Plateforme launch — Mistral Medium API"
    date: 2023-12

Benchmarks (lab claimed at launch, no detailed eval card published):
- MMLU: 75.3 [lab] src=https://mistral.ai/news/la-plateforme/ date=2023-12

Notes: Closed-weight; never released to HF. Retired when Mistral Large shipped.

---

### Mixtral 8x7B

- Release: 2023-12-11
- Status: legacy (superseded by 8x22B and the modern Mistral 3 trunk)
- Context: 32K
- Modality: text only (5 languages: EN, FR, IT, DE, ES)
- License: Apache 2.0
- Price (La Plateforme, when offered): ~$0.70 / $0.70 per M tokens
- Notable: First widely-used MoE open-weight model. 46.7B total / 12.9B active (8 experts × 7B, top-2 routing). Matched GPT-3.5 + Llama-2-70B at a fraction of inference cost; 6× faster than Llama-2-70B. Catalyzed the open-MoE wave (DeepSeek-V2, Qwen-MoE, Llama-4).
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mixtral-of-experts
    title: "Mixtral of Experts"
    date: 2023-12
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2401.04088
    title: "Mixtral of Experts technical report"
    date: 2024-01

Benchmarks (lab, base model):
- MMLU: 70.6 [lab] src=https://arxiv.org/abs/2401.04088 date=2024-01
- HellaSwag: 84.4 [lab] src=https://arxiv.org/abs/2401.04088 date=2024-01
- GSM8K (maj@8): 58.4 [lab] src=https://arxiv.org/abs/2401.04088 date=2024-01
- HumanEval (pass@1): 40.2 [lab] src=https://arxiv.org/abs/2401.04088 date=2024-01

Notes: Same magnet-link launch style as 7B. Mixtral-Instruct (RLHF) shipped the same day.

---

### Mistral Large (v1)

- Release: 2024-02-26
- Status: deprecated (retired 2024-11; superseded by Large 2)
- Context: 32K
- Modality: text only (EN/FR/ES/DE/IT)
- License: Mistral Commercial (closed)
- Price (at launch): $8 / $24 per M tokens
- Notable: Mistral's first GPT-4-tier closed-weight flagship; debuted with Azure partnership announcement. Ranked second to GPT-4 on MMLU at launch (Mistral's claim). Replaced "Mistral Medium" as the top La Plateforme SKU.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-large
    title: "Au Large — Mistral Large"
    date: 2024-02
  - kind: deprecation
    tag: lab
    url: https://docs.mistral.ai/getting-started/models/models_overview/
    title: "Model deprecation timeline"
    date: 2024-11

Benchmarks (lab, instruct):
- MMLU (5-shot): 81.2 [lab] src=https://mistral.ai/news/mistral-large date=2024-02
- HellaSwag (10-shot): 89.2 [lab] src=https://mistral.ai/news/mistral-large date=2024-02
- GSM8K (8-shot): 81.0 [lab] src=https://mistral.ai/news/mistral-large date=2024-02
- HumanEval: 45.1 [lab] src=https://mistral.ai/news/mistral-large date=2024-02

Notes: Also launched alongside Mistral Small v1 ("Mistral Small 2402", a closed, smaller-tier model — not to be confused with the 2025 open-weights "Small 3" line).

---

### Mixtral 8x22B

- Release: 2024-04-17
- Status: legacy (deprecated on La Plateforme; weights still public)
- Context: 64K (initially announced; 65K context window)
- Modality: text only
- License: Apache 2.0
- Price (La Plateforme, when offered): $2 / $6 per M tokens
- Notable: 141B total / 39B active. Set new high-water marks among Apache-2.0 models: best open MMLU, coding, math, multilingual. Magnet-link launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mixtral-8x22b
    title: "Cheaper, Better, Faster, Stronger — Mixtral 8x22B"
    date: 2024-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/mistralai/Mixtral-8x22B-v0.1
    title: "Mixtral-8x22B-v0.1 model card"
    date: 2024-04

Benchmarks (lab, base):
- MMLU: 77.3 [lab] src=https://mistral.ai/news/mixtral-8x22b date=2024-04
- HellaSwag: 88.9 [lab] src=https://mistral.ai/news/mixtral-8x22b date=2024-04
- GSM8K (8-shot, maj@1): 78.6 [lab] src=https://mistral.ai/news/mixtral-8x22b date=2024-04
- HumanEval (pass@1): 45.1 [lab] src=https://mistral.ai/news/mixtral-8x22b date=2024-04
- MATH (4-shot): 41.8 [lab] src=https://mistral.ai/news/mixtral-8x22b date=2024-04

Notes: Trained with 32K context but with rope-scaling supports 64K effectively.

---

### Codestral 22B (v0.1)

- Release: 2024-05-29
- Status: legacy (superseded by Codestral 25.01 / 25.08)
- Context: 32K
- Modality: text (code) — 80+ programming languages
- License: **Mistral Non-Production License (MNPL)** — first model under this license; non-commercial / non-production only without negotiated commercial license
- Price (La Plateforme, when offered): $1 / $3 per M tokens
- Notable: First Mistral specialty-code model. 22B dense; native FIM. Beat Code-Llama-70B (67%) and DeepSeek-Coder-33B (~79%) on HumanEval at a third the size. MNPL caused community backlash; kicked off the "Mistral is closing up" narrative.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/codestral
    title: "Codestral — code generation"
    date: 2024-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/mistralai/Codestral-22B-v0.1
    title: "Codestral-22B-v0.1 model card"
    date: 2024-05

Benchmarks (lab):
- HumanEval (pass@1, Python): 81.1 [lab] src=https://mistral.ai/news/codestral date=2024-05
- MBPP: 78.2 [lab] src=https://mistral.ai/news/codestral date=2024-05
- HumanEvalPlus avg (multi-language): 61.5 [lab] src=https://mistral.ai/news/codestral date=2024-05
- RepoBench EM: 34.0 [lab] src=https://mistral.ai/news/codestral date=2024-05

Notes: First-day API rollout via `codestral-latest`. MNPL license blocked Cursor / Continue from defaulting to it commercially.

---

### Mathstral 7B

- Release: 2024-07-16
- Status: legacy (research / specialty release)
- Context: 32K
- Modality: text (math / STEM)
- License: Apache 2.0
- Price: not on paid API (download-only)
- Notable: 7B fine-tune of Mistral 7B v0.3 for math + STEM; collaboration with Project Numina. Set SOTA among open 7B models on MATH and GSM8K.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mathstral
    title: "Mathstral — math reasoning specialist"
    date: 2024-07

Benchmarks (lab):
- MATH (maj@64): 56.6 [lab] src=https://mistral.ai/news/mathstral date=2024-07
- MMLU: 63.5 [lab] src=https://mistral.ai/news/mathstral date=2024-07
- GSM8K: 77.1 [lab] src=https://mistral.ai/news/mathstral date=2024-07

---

### Mistral NeMo (12B)

- Release: 2024-07-18 (joint with NVIDIA)
- Status: still listed; superseded operationally by Ministral 8B → Ministral 3 8B
- Context: 128K
- Modality: text only (multilingual; new Tekken tokenizer)
- License: Apache 2.0
- Price (La Plateforme, when offered): $0.15 / $0.15 per M tokens
- Notable: First NVIDIA-collab Mistral release; drop-in replacement for 7B. New "Tekken" tokenizer (~30% more efficient on code + CN/KR). QAT enables FP8 on single A100/H100.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-nemo
    title: "Mistral NeMo 12B (with NVIDIA)"
    date: 2024-07

Benchmarks (lab, instruct):
- MMLU (5-shot): 68.0 [lab] src=https://mistral.ai/news/mistral-nemo date=2024-07
- HellaSwag: 83.5 [lab] src=https://mistral.ai/news/mistral-nemo date=2024-07
- HumanEval: 56.7 [lab] src=https://mistral.ai/news/mistral-nemo date=2024-07
- MT-Bench: 7.84 [lab] src=https://mistral.ai/news/mistral-nemo date=2024-07

---

### Mistral Large 2 (24.07)

- Release: 2024-07-24
- Status: deprecated (retirement: 2025-03-30 for the 24.07 build; 24.11 build retired 2026-05-31)
- Context: 128K
- Modality: text only (12 languages, 80+ coding languages)
- License: **Mistral Research License (MRL)** — research-only without paid commercial license
- Price (La Plateforme): $2 / $6 per M tokens
- Notable: 123B dense, weights released under MRL — first Mistral flagship downloadable. SOTA HumanEval among open weights at launch (92.0%, matched only by Claude 3.5 Sonnet). Narrower hallucination footprint vs Large v1.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-large-2407
    title: "Large Enough — Mistral Large 2"
    date: 2024-07
  - kind: model-card
    tag: lab
    url: https://huggingface.co/mistralai/Mistral-Large-Instruct-2407
    title: "Mistral-Large-Instruct-2407 model card"
    date: 2024-07

Benchmarks (lab, instruct):
- MMLU (5-shot): 84.0 [lab] src=https://mistral.ai/news/mistral-large-2407 date=2024-07
- HumanEval: 92.0 [lab] src=https://mistral.ai/news/mistral-large-2407 date=2024-07
- GSM8K: 93.0 [lab] src=https://mistral.ai/news/mistral-large-2407 date=2024-07
- MATH: 71.5 [lab] src=https://mistral.ai/news/mistral-large-2407 date=2024-07
- MultiPL-E (multi-language code avg): 76.9 [lab] src=https://mistral.ai/news/mistral-large-2407 date=2024-07

Notes: A 24.11 refresh shipped 2024-11-18 alongside Pixtral Large — same weights backbone, sharper instruction-following and function-calling.

---

### Pixtral 12B

- Release: 2024-09-17
- Status: deprecated (retirement: 2026-05-31)
- Context: 128K (text + images)
- Modality: text + vision (variable-resolution image input)
- License: Apache 2.0
- Price (La Plateforme): $0.15 / $0.15 per M tokens
- Notable: First Mistral multimodal model. PixtralViT (from-scratch vision encoder) processes images at native aspect ratio. Beat Llama-3.2-11B-V, Qwen2-VL-7B, Claude 3 Haiku on MM-MT-Bench.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/pixtral-12b
    title: "Pixtral 12B"
    date: 2024-09
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2410.07073
    title: "Pixtral 12B technical report"
    date: 2024-10

Benchmarks (lab):
- MMMU: 52.5 [lab] src=https://arxiv.org/abs/2410.07073 date=2024-10
- MathVista: 58.0 [lab] src=https://arxiv.org/abs/2410.07073 date=2024-10
- ChartQA: 81.8 [lab] src=https://arxiv.org/abs/2410.07073 date=2024-10
- DocVQA: 90.7 [lab] src=https://arxiv.org/abs/2410.07073 date=2024-10
- MM-MT-Bench: 6.05 [lab] src=https://arxiv.org/abs/2410.07073 date=2024-10

---

### Ministral 3B / Ministral 8B ("Les Ministraux")

- Release: 2024-10-16 (the 1-year anniversary of Mistral 7B)
- Status: legacy (Ministral 8B still on API; superseded by Ministral 3 family Dec 2025)
- Context: 128K
- Modality: text (edge-focused; function-calling)
- License: 3B → Mistral Commercial (closed); 8B → Mistral Research License (Apache-grade for non-commercial)
- Price (La Plateforme): 3B → $0.04 / $0.04 per M; 8B → $0.10 / $0.10 per M
- Notable: First Mistral "edge" tier; interleaved sliding-window pattern. Ministral 3B beat Mistral 7B on most benchmarks at <half the size.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/ministraux
    title: "Un Ministral, des Ministraux"
    date: 2024-10

Benchmarks (lab, instruct):
- Ministral 3B MMLU: 60.9 [lab] src=https://mistral.ai/news/ministraux date=2024-10
- Ministral 8B MMLU: 65.0 [lab] src=https://mistral.ai/news/ministraux date=2024-10
- Ministral 8B HumanEval: 34.8 [lab] src=https://mistral.ai/news/ministraux date=2024-10

---

### Pixtral Large

- Release: 2024-11-18
- Status: deprecated (deprecation 2026-02-27; retirement 2026-05-31)
- Context: 128K (text + images)
- Modality: text + vision (flagship multimodal)
- License: **Mistral Research License (MRL)**
- Price (La Plateforme): $2 / $6 per M tokens
- Notable: 124B (Large 2 backbone + 1B vision encoder). SOTA on MathVista, DocVQA, VQAv2 among open multimodal models at release. Shipped with Mistral Large 24.11 refresh.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/pixtral-large
    title: "Pixtral Large"
    date: 2024-11

Benchmarks (lab):
- MathVista: 69.4 [lab] src=https://mistral.ai/news/pixtral-large date=2024-11
- ChartQA: 88.1 [lab] src=https://mistral.ai/news/pixtral-large date=2024-11
- DocVQA (ANLS): 93.3 [lab] src=https://mistral.ai/news/pixtral-large date=2024-11
- MMMU: 64.0 [lab] src=https://mistral.ai/news/pixtral-large date=2024-11

---

### Codestral 25.01 / Codestral 25.08

- Release: 25.01 → 2025-01-13 ; 25.08 → 2025-08
- Status: 25.01 retired; 25.08 current (only Codestral on production API as of May 2026)
- Context: 256K
- Modality: text (code)
- License: Mistral Commercial (closed; not on HF)
- Price (La Plateforme): $0.30 / $0.90 per M tokens
- Notable: 25.01 = first "v2" Codestral — 2× faster than 22B v0.1, 256K context, 80+ languages with native FIM. 25.08 added long-context + JSON/tool-use. Open-weights coding role moved to Devstral.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/codestral-2501
    title: "Codestral 25.01"
    date: 2025-01
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/codestral-25-08
    title: "Codestral 25.08"
    date: 2025-08

Benchmarks (lab, 25.01):
- HumanEval (Python pass@1): 86.6 [lab] src=https://mistral.ai/news/codestral-2501 date=2025-01
- MBPP: 80.2 [lab] src=https://mistral.ai/news/codestral-2501 date=2025-01
- RepoBench (EM): 38.0 [lab] src=https://mistral.ai/news/codestral-2501 date=2025-01

---

### Mistral Small 3 (24B, v25.01)

- Release: 2025-01-30
- Status: superseded by Small 3.1 → 3.2 → Small 4
- Context: 32K
- Modality: text only
- License: Apache 2.0
- Price (La Plateforme): $0.10 / $0.30 per M tokens
- Notable: 24B dense; ~150 tok/s on H100; ~3× faster than Llama 3.3 70B at comparable quality. Apache-2.0 release positioned vs. closed GPT-4o-mini. >81% MMLU.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-small-3
    title: "Mistral Small 3"
    date: 2025-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/mistralai/Mistral-Small-24B-Instruct-2501
    title: "Mistral-Small-24B-Instruct-2501"
    date: 2025-01

Benchmarks (lab):
- MMLU: 81.0 [lab] src=https://mistral.ai/news/mistral-small-3 date=2025-01
- MATH: 70.6 [lab] src=https://mistral.ai/news/mistral-small-3 date=2025-01
- HumanEval: 84.8 [lab] src=https://mistral.ai/news/mistral-small-3 date=2025-01

---

### Mistral Saba

- Release: 2025-02-17
- Status: niche / regional (still listed)
- Context: 32K
- Modality: text only (Arabic + South Asian languages including Tamil, Malayalam, Hindi)
- License: Mistral Commercial (closed); API + on-prem option
- Price (La Plateforme): $0.20 / $0.60 per M tokens
- Notable: First Mistral "regional" specialty model. 24B; ME / South Asia corpora. Beat Small 3, Qwen 2.5 32B, Llama 3.1 70B, Jais 70B on Arabic-MMLU, Arabic-MT-Bench, FLORES-101 Arabic.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-saba
    title: "Mistral Saba"
    date: 2025-02

Benchmarks (lab):
- Arabic MMLU: 67.5 [lab] src=https://mistral.ai/news/mistral-saba date=2025-02
- Arabic MT-Bench Dev: 7.8 [lab] src=https://mistral.ai/news/mistral-saba date=2025-02

---

### Mistral OCR (v25.03) → OCR 3 (v25.12)

- Release: v25.03 → 2025-03-06 ; OCR 3 → 2025-12 (with the Mistral 3 family)
- Status: current (OCR 3 is the active SKU)
- Modality: document-vision (multimodal: tables, equations, LaTeX, complex layouts)
- License: Mistral Commercial (closed, API + selective on-prem)
- Price: $1 per 1000 pages (≈$0.50 per 1000 in batch mode)
- Notable: Document-AI API. 98.96% scanned-doc accuracy; ~2000 pages/min on single node; outputs structured (tables/equations/LaTeX). OCR 3 extended language coverage, 74% win-rate vs competitors.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-ocr
    title: "Mistral OCR"
    date: 2025-03

---

### Mistral Small 3.1

- Release: 2025-03-18
- Status: superseded by Small 3.2 → Small 4
- Context: 128K (expanded from 3's 32K)
- Modality: text + vision (multimodal added in 3.1)
- License: Apache 2.0
- Price (La Plateforme): $0.10 / $0.30 per M tokens
- Notable: 24B; first multimodal Small. Avg vision-benchmark 81.39%. Beat Gemma 3, Claude 3.5 Haiku, GPT-4o-mini on Mistral's published comparison.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-small-3-1
    title: "Mistral Small 3.1"
    date: 2025-03

Benchmarks (lab):
- MMLU: 80.6 [lab] src=https://mistral.ai/news/mistral-small-3-1 date=2025-03
- ChartQA: 86.2 [lab] src=https://mistral.ai/news/mistral-small-3-1 date=2025-03
- DocVQA: 94.1 [lab] src=https://mistral.ai/news/mistral-small-3-1 date=2025-03

---

### Mistral Medium 3

- Release: 2025-05-07
- Status: superseded by Medium 3.1 → 3.5
- Context: 131K
- Modality: text + vision (multimodal)
- License: Mistral Commercial (closed)
- Price (La Plateforme): $0.40 / $2.00 per M tokens
- Notable: ≥90% of Claude Sonnet 3.7 on Mistral's evals; beats Llama 4 Maverick + Cohere Command A. Hybrid / in-VPC / on-prem from day one. Reuses "Mistral Medium" brand from Dec 2023 but unrelated, much stronger model.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-medium-3
    title: "Medium is the new large — Mistral Medium 3"
    date: 2025-05
  - kind: pricing
    tag: lab
    url: https://mistral.ai/pricing
    title: "La Plateforme pricing"
    date: 2025-05

Benchmarks (3p; Mistral declined to publish granular benchmark cards):
- Artificial Analysis Intelligence Index: 19 [3p] src=https://artificialanalysis.ai/models/mistral-medium-3 date=2025-05

---

### Devstral (Small v1) — May 2025

- Release: 2025-05-21 (with All Hands AI collaboration)
- Status: superseded by Devstral Small 1.1 → Devstral 2 family
- Context: 128K
- Modality: text only (agentic coding)
- License: Apache 2.0
- Price (La Plateforme): $0.10 / $0.30 per M tokens
- Notable: 24B; first open-weight agentic-coding specialist. SWE-Bench Verified 46.8% (+6 pp over open SoTA, +20 pp over GPT-4.1-mini). Single RTX 4090 / 32GB Mac. With Mistral's first OpenHands integrations.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/devstral
    title: "Devstral — agentic coding"
    date: 2025-05

Benchmarks (lab):
- SWE-Bench Verified: 46.8 [lab] src=https://mistral.ai/news/devstral date=2025-05

---

### Magistral Small / Magistral Medium (v1.0)

- Release: 2025-06-10
- Status: superseded by Magistral 1.2 (Sept 2025)
- Context: 128K (40K reasoning budget recommended)
- Modality: text (reasoning) — Small is open, Medium is API-only
- License: Magistral Small → Apache 2.0 ; Magistral Medium → Mistral Commercial
- Price (Magistral Medium, La Plateforme): $2 / $5 per M tokens
- Notable: Mistral's first reasoning models; competitor to DeepSeek R1, o1, Claude 3.7-thinking. RLVR training. ~10× faster streaming than other frontier reasoners. arXiv tech report — rare for Mistral.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/magistral
    title: "Magistral — Mistral's first reasoning models"
    date: 2025-06
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2506.10910
    title: "Magistral technical report"
    date: 2025-06

Benchmarks (lab, Magistral Medium 1.0):
- AIME-24: 73.6 [lab] src=https://arxiv.org/abs/2506.10910 date=2025-06
- AIME-24 (maj@64): 90.0 [lab] src=https://arxiv.org/abs/2506.10910 date=2025-06
- AIME-25: 72.1 [lab] src=https://arxiv.org/abs/2506.10910 date=2025-06
- GPQA Diamond: 70.0 [lab] src=https://arxiv.org/abs/2506.10910 date=2025-06

---

### Mistral Small 3.2

- Release: 2025-06-20
- Status: deprecated (deprecation 2026-04-30; retirement 2026-07-31)
- Context: 128K
- Modality: text + vision
- License: Apache 2.0
- Price (La Plateforme): $0.10 / $0.30 per M tokens
- Notable: Instruction-following + JSON robustness refresh of 3.1 with same weights backbone; not a new architecture. Reduced infinite-generation failure mode.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-small-3-2
    title: "Mistral Small 3.2"
    date: 2025-06

---

### Devstral Small 1.1 / Devstral Medium 1.0

- Release: 2025-07-10
- Status: superseded by Devstral 2 (Dec 2025)
- Context: 256K
- Modality: text (agentic coding)
- License: Small 1.1 → Apache 2.0 ; Medium → Mistral Commercial (closed)
- Price (Devstral Medium): $0.40 / $2.00 per M tokens
- Notable: Small 1.1 pushed SWE-Bench Verified to 53.6%; Devstral Medium (closed) reached 61.6%. Both designed for OpenHands / All Hands AI agent loops.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/devstral-2507
    title: "Upgrading agentic coding capabilities with the new Devstral models"
    date: 2025-07

Benchmarks (lab):
- Devstral Small 1.1 SWE-Bench Verified: 53.6 [lab] src=https://mistral.ai/news/devstral-2507 date=2025-07
- Devstral Medium SWE-Bench Verified: 61.6 [lab] src=https://mistral.ai/news/devstral-2507 date=2025-07

---

### Voxtral Mini / Voxtral Small (v1)

- Release: 2025-07-15
- Status: superseded by Voxtral Realtime / Voxtral TTS (2026)
- Context: 32K (text + audio tokens)
- Modality: audio-in (speech understanding) + text-out
- License: Apache 2.0
- Price (Voxtral Mini Transcribe): $0.001 per minute audio
- Notable: Mistral's first speech / audio models. Voxtral Mini = 3B (built on Ministral 3B); Voxtral Small = 24B. Multi-language transcription + understanding (Q&A, summarization on audio).
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/voxtral
    title: "Voxtral — speech understanding"
    date: 2025-07

---

### Mistral Medium 3.1

- Release: 2025-08
- Status: still on API (alongside 3.5)
- Context: 131K
- Modality: text + vision
- License: Mistral Commercial (closed)
- Price (La Plateforme): $0.40 / $2.00 per M tokens
- Notable: Tone + reasoning refresh of Medium 3; same weights backbone with stronger RLHF. Same SKU price.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-medium-3-1
    title: "Mistral Medium 3.1"
    date: 2025-08

---

### Magistral 1.2 (Small + Medium)

- Release: 2025-09-18
- Status: current
- Context: 128K
- Modality: Magistral Medium 1.2 added **vision**; Small 1.2 also multimodal
- License: Small → Apache 2.0 ; Medium → Mistral Commercial
- Price (Magistral Medium 1.2): $2 / $5 per M tokens
- Notable: Major quality jump (AIME-24 73.6 → 91.8) + multimodal added — Mistral's first multimodal reasoner. Closes gap to DeepSeek-R1-0528 (R1: 91.4) on AIME-24.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/magistral-1-2
    title: "Magistral 1.2"
    date: 2025-09

Benchmarks (lab, Magistral Medium 1.2):
- AIME-24: 91.8 [lab] src=https://mistral.ai/news/magistral-1-2 date=2025-09
- GPQA Diamond: 76.3 [lab] src=https://mistral.ai/news/magistral-1-2 date=2025-09

---

### Mistral 3 family — December 2025

The "Mistral 3" rebrand (announced 2025-12-02) shipped four open-weight
SKUs together: **Large 3**, **Ministral 3** (3B / 8B / 14B), **OCR 3**,
and (a week later, 2025-12-09) **Devstral 2** (123B + Small 2 24B).
All Apache-2.0 except Devstral 2 (Modified MIT) and OCR 3 (Mistral
Commercial). This is the lineage breakpoint where Mistral resumed
flagship-tier open releases after the 2024-mid MRL period.

#### Mistral Large 3 (v25.12)

- Release: 2025-12-02
- Status: current flagship
- Context: 256K
- Modality: text + vision
- License: Apache 2.0
- Price (La Plateforme): $2 / $6 per M tokens
- Notable: 675B total / 41B active MoE — first Mistral MoE flagship since 8x22B; largest Mistral open-weight model. LMSYS Arena ELO ~1418; #2 open-source non-reasoning, #6 overall open-weight.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-3
    title: "Introducing Mistral 3"
    date: 2025-12
  - kind: replication
    tag: 3p
    url: https://www.vals.ai/models/mistralai_mistral-large-2512
    publisher: Vals AI
    title: "Mistral Large 3 (2512) — independent evals"
    date: 2026-01

Benchmarks (lab):
- MMLU (8-language): 85.5 [lab] src=https://mistral.ai/news/mistral-3 date=2025-12
- GPQA Diamond: 43.9 [lab] src=https://mistral.ai/news/mistral-3 date=2025-12
- HumanEval (pass@1): 92.0 [lab] src=https://mistral.ai/news/mistral-3 date=2025-12
- LMSYS Arena ELO: 1418 [3p] src=https://www.vals.ai/models/mistralai_mistral-large-2512 date=2026-01

Notes: GPQA soft — Mistral leans the model toward instruction-following over multi-step reasoning (Magistral handles that). Large 3 + Magistral 1.2 = recommended reasoning stack.

#### Ministral 3 (3B / 8B / 14B)

- Release: 2025-12-02
- Status: current edge tier
- Context: 128K
- Modality: text + vision (all three sizes multimodal)
- License: Apache 2.0
- Price (La Plateforme): 3B → $0.04 / $0.04 ; 8B → $0.10 / $0.10 ; 14B → $0.15 / $0.30 per M tokens
- Notable: All three sizes ship vision; 14B is new. Replaces "Les Ministraux" (Oct 2024). On-device / edge tier.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-3
    title: "Introducing Mistral 3 — Ministral 3 family"
    date: 2025-12

#### Devstral 2 / Devstral Small 2

- Release: 2025-12-09
- Status: current agentic-coding flagship
- Context: 256K
- Modality: text only
- License: Devstral 2 (123B) → **Modified MIT** ; Devstral Small 2 (24B) → Apache 2.0
- Price (La Plateforme): Devstral 2 → $0.40 / $2.00 per M ; Devstral Small 2 → $0.10 / $0.30
- Notable: 123B dense (not MoE) coding flagship. SWE-Bench Verified 72.2 — beats every open coding model <200B at release. Devstral Small 2 framed as ">Qwen 3 Coder Flash (30B)". Ships with Mistral Vibe CLI (free) for local agent loops.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/devstral-2-vibe-cli
    title: "Devstral 2 and Mistral Vibe CLI"
    date: 2025-12

Benchmarks (lab):
- Devstral 2 SWE-Bench Verified: 72.2 [lab] src=https://mistral.ai/news/devstral-2-vibe-cli date=2025-12

---

### 2026 releases

#### Voxtral Realtime / Voxtral Mini Transcribe V2

- Release: 2026-02
- Status: current
- Modality: real-time audio transcription + understanding
- License: Voxtral Realtime → Apache 2.0 ; Mini Transcribe V2 → Mistral Commercial
- Notable: 4B params (Voxtral Realtime); designed for sub-100ms streaming-transcription. Sets up the Voxtral TTS launch a month later.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/voxtral-realtime
    title: "Voxtral Realtime"
    date: 2026-02

#### Voxtral TTS

- Release: 2026-03-23
- Status: current
- Modality: text-to-speech (zero-shot voice cloning)
- License: CC BY-NC 4.0 (non-commercial; commercial via La Plateforme)
- Price: tier-based, audio-second pricing
- Notable: Mistral's first TTS — built on Ministral 3B. 8GB BF16, single-GPU (16GB+ VRAM). 70ms latency on H200 (~90ms real-world TTFA). 9 languages (EN/FR/DE/ES/NL/PT/IT/HI/AR). 68.4% preference win vs ElevenLabs Flash v2.5 (zero-shot cloning).
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/voxtral-tts
    title: "Voxtral TTS"
    date: 2026-03

#### Mistral Small 4 (v26.03)

- Release: 2026-03 (announced at GTC 2026)
- Status: current
- Context: 256K
- Modality: text + vision (multimodal)
- License: Apache 2.0
- Price (La Plateforme): $0.20 / $0.50 per M tokens
- Notable: 119B total / **128 experts** MoE — first MoE "Small" (line was 24B dense). **Hybrid** unifying instruct + reasoning + coding in one weight set (cf. DeepSeek-V3.2, Qwen3). Beats Small 3.2 by ~15-20 pp on reasoning while single-node deployable.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-small-4
    title: "Mistral Small 4"
    date: 2026-03

#### Leanstral (v26.03)

- Release: 2026-03 (announced at GTC 2026)
- Status: current (Mistral Labs)
- Modality: text (Lean 4 formal proof engineering)
- License: Apache 2.0 (open-source code agent)
- Notable: Lean 4 theorem-proving specialist. Mistral claims +8 pp over Claude Sonnet at pass@16 on FLTEval at 15× lower cost; beats GLM-5 (744B), Kimi K2.5 (1T), Qwen 3.5 (397B). Claude Opus still leads on quality at 92× cost. Mistral Labs (Forge platform).
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/leanstral
    title: "Leanstral — open-source Lean 4 proof agent"
    date: 2026-03

#### Mistral Moderation 2 (v26.03)

- Release: 2026-03
- Status: current
- Context: 128K
- Modality: text classifier (safety / jailbreak detection)
- License: Mistral Commercial
- Notable: Refresh of original Mistral Moderation (Nov 2024 launch). Adds jailbreak / prompt-injection detection and 128K context input.
- Sources:
  - kind: announcement
    tag: lab
    url: https://docs.mistral.ai/capabilities/guardrailing/
    title: "Mistral Moderation 2"
    date: 2026-03

#### Mistral Medium 3.5

- Release: 2026-04-29
- Status: current top closed-tier model
- Context: 256K
- Modality: text + vision
- License: **Modified MIT** — released as open weights on HF (significant lineage move: Medium 3 / 3.1 were closed; 3.5 reopens the tier)
- Price (La Plateforme): $1.50 / $7.50 per M tokens
- Notable: 128B dense; "first flagship merged model" — instruct + reasoning + coding in one weight set (same philosophy as Small 4). From-scratch vision encoder (variable-res / aspect-ratio). Ships with Vibe CLI ("Work mode" for agentic tasks). Self-host on 4 GPUs via vLLM / SGLang / Ollama; NVIDIA NIM available. GPQA / MMLU-Pro / LiveCodeBench not published at launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://mistral.ai/news/mistral-medium-3-5
    title: "Mistral Medium 3.5"
    date: 2026-04
  - kind: pricing
    tag: lab
    url: https://mistral.ai/pricing
    title: "La Plateforme pricing"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://artificialanalysis.ai/models/mistral-medium-3-5
    publisher: Artificial Analysis
    title: "Mistral Medium 3.5 — performance & price analysis"
    date: 2026-05

Benchmarks (lab):
- SWE-Bench Verified: 77.6 [lab] src=https://mistral.ai/news/mistral-medium-3-5 date=2026-04
- Tau3-Telecom (agentic): 91.4 [lab] src=https://mistral.ai/news/mistral-medium-3-5 date=2026-04

Notes: GPQA Diamond, MMLU-Pro, LiveCodeBench scores not published by Mistral at launch — gap to be filled by community evals over coming weeks.

---

## Key trends

1. **License whiplash → reopening.** Apache opening (7B, Mixtral) → mid-2024
   tightening (Codestral MNPL, Large 2 + Pixtral Large MRL) → hard reopening
   with Mistral 3 (Dec 2025). Medium 3.5 (Modified MIT) reopened the closed
   Medium tier — first downloadable Medium-class flagship.
2. **MoE comeback.** Dense-only through 2024-25 after Mixtral. Large 3
   (675B/41B active) is the first MoE flagship in 20 months; Small 4
   (119B/128 experts) brings MoE to the Small tier.
3. **Hybrid models.** Small 4 and Medium 3.5 fuse instruct + reasoning +
   coding into single weights. Magistral may not need a v2 if hybrid
   trunks subsume it.
4. **Specialty surface expansion** — OCR, regional language (Saba), audio
   (Voxtral), TTS, formal proofs (Leanstral), moderation. Surface looks
   more like OpenAI's than DeepSeek's.
5. **Pricing aggression.** Medium 3 ($0.40/$2.00) and Large 3 ($2/$6)
   undercut comparable closed APIs 30-60% at launch.
