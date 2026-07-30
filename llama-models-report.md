# Meta Llama Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema:
typed `Sources:` blocks (`announcement`/`model-card`/`pricing`/`deprecation`/`coverage`/`replication`),
and benchmark rows surface both `lab` and `3p` numbers where they disagree by >3pp.

Lifecycle spine sourced from Meta's release blogs, HuggingFace model cards, and the
Wikipedia "Llama (language model)" timeline (verified May 2026). Open-weight models do
not get formally "decommissioned" — weights remain downloadable indefinitely; status
field uses "current" / "legacy" (superseded but available) / "preview" / "unreleased"
as appropriate. License terms shift per generation — flagged inline.

**Headline state (May 2026):** Last open-weight Llama release was Llama 4 Scout +
Maverick (April 5 2025). Llama 4 Behemoth was repeatedly delayed and never shipped
public weights. **No Llama 5 was released.** Meta's April 8 2026 flagship launch
was **Muse Spark** — a separate, proprietary, closed-weights line under the newly-formed
Meta Superintelligence Labs. The Llama brand is effectively dormant for new frontier
training; the existing Llama-3/3.x/4 weights remain the open-weight artifacts.

---

### Llama 1 (7B / 13B / 33B / 65B)

- Release: 2023-02-24
- Status: legacy (research-only license; weights leaked, weights remain downloadable from third parties)
- Sizes: 7B, 13B, 33B, 65B
- Context: 2,048 tokens
- Modality: text
- License: **Non-commercial research-only**, granted case-by-case to academic researchers; weights leaked publicly via 4chan within a week of release
- Notable: first major Meta LLM family; 65B trained on 1.4T tokens; 7B on 1T tokens; seeded the open-LLM ecosystem (Alpaca, Vicuna, etc.) via the weight leak
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/large-language-model-llama-meta-ai/
    title: "Introducing LLaMA: A foundational, 65-billion-parameter large language model"
    date: 2023-02-24
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2302.13971
    title: "LLaMA: Open and Efficient Foundation Language Models"
    date: 2023-02-27
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Llama_(language_model)
    publisher: Wikipedia
    title: "Llama (language model)"
    date: 2026-05

Benchmarks (LLaMA-65B, lab paper):
- MMLU (5-shot): 63.4 [lab] src=https://arxiv.org/abs/2302.13971 date=2023-02
- HumanEval (pass@1): 23.7 [lab] src=https://arxiv.org/abs/2302.13971 date=2023-02
- MATH: 10.6 [lab]
- GSM8K (maj1): 50.9 [lab]
- HellaSwag (0-shot): 84.2 [lab]
- ARC-Challenge (0-shot): 56.0 [lab]

Notes: Modern SWE-bench / LiveCodeBench / MMLU-Pro / GPQA did not exist at Llama 1's release. No agentic-coding numbers.

---

### Llama 2 (7B / 13B / 70B — base + Chat variants)

- Release: 2023-07-18
- Status: legacy (superseded by Llama 3; weights remain freely downloadable)
- Sizes: 7B, 13B, 70B (each in base and Chat/Instruct flavors); a 34B base was trained but unreleased due to red-teaming concerns
- Context: 4,096 tokens
- Modality: text
- License: **Llama 2 Community License** — first Meta release with commercial-use permission. Key clause: any licensee whose products exceed **700M monthly active users** as of the release date must request a separate license from Meta.
- Notable: first Meta open-weight commercial-OK release; Llama 2-Chat used RLHF; partnered launch with Microsoft (Azure model catalog).
- Sources:
  - kind: announcement
    tag: lab
    url: https://about.fb.com/news/2023/07/llama-2/
    title: "Meta and Microsoft Introduce the Next Generation of Llama"
    date: 2023-07-18
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2307.09288
    title: "Llama 2: Open Foundation and Fine-Tuned Chat Models"
    date: 2023-07-18
  - kind: pricing
    tag: 3p
    url: https://www.together.ai/pricing
    publisher: Together AI
    title: "Together AI pricing — Llama hosted inference"
    date: 2026-05

Benchmarks (Llama 2 70B base, lab paper):
- MMLU (5-shot): 68.9 [lab] src=https://arxiv.org/abs/2307.09288 date=2023-07
- HumanEval (pass@1): 29.9 [lab] src=https://arxiv.org/abs/2307.09288 date=2023-07
- GSM8K (8-shot): 56.8 [lab] src=https://arxiv.org/abs/2307.09288 date=2023-07
- MATH (4-shot): 13.5 [lab]
- HellaSwag (0-shot): 85.3 [lab]
- ARC-Challenge: 57.4 [lab]
- TriviaQA (1-shot): 85.0 [lab]

Notes: 700M MAU clause persists in the Llama brand through Llama 3.x; tightened with Llama 4 (see below). No SWE-bench / LiveCodeBench reported by Meta at this time.

---

### Code Llama (7B / 13B / 34B initial; 70B later)

- Release: 2023-08-24 (7B / 13B / 34B); **2024-01-29** (70B variant — separate later release)
- Status: legacy (largely superseded by Llama 3+ for code; remains downloadable)
- Sizes per variant: each size shipped in three flavors — **base** (`Code Llama`), **Python-specialized** (`Code Llama Python`), and **Instruct** (`Code Llama Instruct`). 70B shipped in the same three flavors in Jan 2024.
- Context: trained on 16K-token sequences; supports up to **100K tokens** at inference via RoPE extrapolation
- Modality: text (code-focused)
- License: same **Llama 2 Community License** (700M MAU clause applies); commercial use permitted
- Notable: Code Llama 34B was the first Meta model to match ChatGPT-tier on HumanEval among open weights; the 70B was Meta's first 70B-class code-tuned release
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/code-llama-large-language-model-coding/
    title: "Introducing Code Llama, an AI Tool for Coding"
    date: 2023-08-24
  - kind: announcement
    tag: lab
    url: https://about.fb.com/news/2024/01/code-llama-large-language-model-coding/
    title: "Code Llama 70B"
    date: 2024-01-29
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2308.12950
    title: "Code Llama: Open Foundation Models for Code"
    date: 2023-08-24

Benchmarks (Code Llama 34B Instruct, lab):
- HumanEval (pass@1): 53.7 [lab] src=https://ai.meta.com/blog/code-llama-large-language-model-coding/ date=2023-08
- MBPP (pass@1): 56.2 [lab] src=https://ai.meta.com/blog/code-llama-large-language-model-coding/ date=2023-08

Benchmarks (Code Llama 70B Instruct, lab):
- HumanEval (pass@1): 67.8 [lab] src=https://about.fb.com/news/2024/01/code-llama-large-language-model-coding/ date=2024-01

Notes: Meta retired Code Llama as a separate line once Llama 3.x's code performance overtook it. No SWE-bench numbers (predates the benchmark's widespread use).

---

### Llama 3 (8B / 70B)

- Release: 2024-04-18
- Status: legacy (superseded by Llama 3.1 with longer context)
- Sizes: 8B, 70B (each in base + Instruct)
- Context: 8,192 tokens
- Modality: text
- License: **Llama 3 Community License** — same 700M MAU clause; one new clause requires "Built with Meta Llama 3" attribution on downstream products
- Notable: 15T-token training corpus (7× Llama 2); first Meta model with Grouped Query Attention on the 8B; 128K-token vocab (more efficient tokenization)
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/meta-llama-3/
    title: "Introducing Meta Llama 3: The most capable openly available LLM to date"
    date: 2024-04-18
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct
    title: "Meta-Llama-3-70B-Instruct model card"
    date: 2024-04-18

Benchmarks (Llama 3 70B Instruct, lab):
- MMLU (5-shot): 82.0 [lab] src=https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct date=2024-04
- GPQA (0-shot): 39.5 [lab] src=https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct date=2024-04
- HumanEval (0-shot): 81.7 [lab] src=https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct date=2024-04
- GSM8K (8-shot, CoT): 93.0 [lab]
- MATH (4-shot, CoT): 50.4 [lab]

Notes: Original Llama 3 lacked the long-context expansion that arrived in 3.1; 8K cap looked dated within weeks of release.

---

### Llama 3.1 (8B / 70B / 405B)

- Release: 2024-07-23
- Status: current (still actively served by hosted providers; the 405B was the flagship open-weight model of 2024)
- Sizes: 8B, 70B, **405B** (each in base + Instruct); the 405B was Meta's first 100B+ open-weight model
- Context: **128,000 tokens** across all three sizes
- Modality: text
- License: **Llama 3.1 Community License** — same 700M MAU clause; **new clause** explicitly permits using Llama 3.1 outputs to improve other models (distillation/synthetic-data use was previously ambiguous)
- Notable: first frontier-class open-weight release competitive with GPT-4o and Claude 3.5 Sonnet on lab benchmarks; 405B trained on >15T tokens with 16K H100s; the de-facto open-weight reference model through 2024-25.

#### Llama 3.1 405B Instruct

- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/meta-llama-3-1/
    title: "Introducing Llama 3.1: Our most capable models to date"
    date: 2024-07-23
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct
    title: "Llama-3.1-405B-Instruct model card"
    date: 2024-07-23
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2407.21783
    title: "The Llama 3 Herd of Models"
    date: 2024-07-31
  - kind: pricing
    tag: 3p
    url: https://www.together.ai/pricing
    publisher: Together AI
    title: "Hosted inference pricing"
    date: 2026-05

Hosted price (representative): Together hosts at roughly $3.50 / $3.50 per 1M tokens (in/out) historically; open-weight = no Meta-set list price.

Benchmarks (Llama 3.1 405B Instruct, lab):
- MMLU (CoT, 0-shot): 88.6 [lab] src=https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct date=2024-07
- MMLU-Pro (CoT, 5-shot): 73.3 [lab]
- HumanEval (pass@1): 89.0 [lab]
- MBPP++ (pass@1): 88.6 [lab]
- GSM8K (CoT, 8-shot): 96.8 [lab]
- MATH (CoT): 73.8 [lab]
- GPQA Diamond (0-shot): 50.7 [lab]
- IFEval: 88.6 [lab]
- BFCL (tool use): 88.5 [lab]
- ARC-Challenge: 96.9 [lab]

#### Llama 3.1 70B Instruct

Benchmarks (lab, same model card lineage):
- MMLU (CoT, 0-shot): 86.0 [lab] src=https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct date=2024-07
- MMLU-Pro (CoT, 5-shot): 66.4 [lab]
- HumanEval (pass@1): 80.5 [lab]
- MBPP++ (pass@1): 86.0 [lab]
- GSM8K (CoT, 8-shot): 95.1 [lab]
- MATH (CoT): 68.0 [lab]
- GPQA Diamond: 46.7 [lab]
- IFEval: 87.5 [lab]
- BFCL: 84.8 [lab]

#### Llama 3.1 8B Instruct

Benchmarks (lab):
- MMLU (CoT, 0-shot): 73.0 [lab] src=https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct date=2024-07
- MMLU-Pro (CoT, 5-shot): 48.3 [lab]
- HumanEval (pass@1): 72.6 [lab]
- MBPP++ (pass@1): 72.8 [lab]
- GSM8K (CoT, 8-shot): 84.5 [lab]
- MATH (CoT): 51.9 [lab]
- GPQA Diamond: 30.4 [lab]
- IFEval: 80.4 [lab]
- BFCL: 76.1 [lab]

Notes: Llama 3.1 was Meta's last all-dense (non-MoE) flagship. Llama 4 transitioned the family to MoE. No SWE-bench Verified numbers were reported by Meta at launch; third-party SWE-bench rankings place 3.1 405B around 30-35% on agentic harnesses, well behind frontier closed models.

---

### Llama 3.2 (1B / 3B text + 11B / 90B vision)

- Release: 2024-09-25
- Status: current (the 1B/3B remain the canonical Meta on-device tier; 11B/90B vision largely superseded by Llama 4's native multimodal)
- Sizes: **1B / 3B text-only** (edge/mobile); **11B / 90B vision-language**
- Context: 128,000 tokens
- Modality: 1B/3B text; 11B/90B vision-language (image input → text output)
- License: **Llama 3.2 Community License** — same 700M MAU clause. **New restriction:** vision models (11B/90B) **not licensed for use by entities domiciled in the European Union**, citing EU AI Act regulatory uncertainty. The 1B/3B text-only models are not subject to this EU carve-out.
- Notable: first Meta multimodal release; 1B/3B targeted at on-device (Qualcomm, MediaTek, ARM partnerships)
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/
    title: "Llama 3.2: Revolutionizing edge AI and vision with open, customizable models"
    date: 2024-09-25
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-3.2-90B-Vision-Instruct
    title: "Llama-3.2-90B-Vision-Instruct model card"
    date: 2024-09-25

Benchmarks (Llama 3.2 90B Vision Instruct, lab):
- MMMU (val, CoT): 60.3 [lab] src=https://huggingface.co/meta-llama/Llama-3.2-90B-Vision-Instruct date=2024-09
- ChartQA: 85.5 [lab]
- AI2 Diagram (test): 92.3 [lab]
- DocVQA (test, anls): 90.1 [lab]
- VQAv2: 78.1 [lab]
- MathVista: 57.3 [lab]

Benchmarks (Llama 3.2 3B Instruct, lab):
- MMLU (5-shot): 63.4 [lab]
- IFEval: 77.4 [lab]
- GSM8K: 77.7 [lab]
- ARC-Challenge: 78.6 [lab]

Notes: EU vision-model carve-out was the first geo-restriction Meta introduced into the Llama license. It set the precedent that Llama 4 later expanded.

---

### Llama 3.3 70B Instruct

- Release: 2024-12-06
- Status: current (final dense-architecture Llama; widely used as the 70B-class open-weight baseline)
- Sizes: **70B only** — no 8B / 405B counterpart; positioned as a quality-of-life update to 3.1 70B
- Context: 128,000 tokens
- Modality: text
- License: **Llama 3.3 Community License** (same 700M MAU clause; same EU carve-out language for any future vision use — n/a for 70B text)
- Notable: trained as a post-training / data-curation upgrade rather than a scale-up; explicitly closes most of the gap between 3.1 70B and 3.1 405B on knowledge/coding/math at 5.8× lower active params
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/meta-llama-3-3/
    title: "Llama 3.3 70B announcement"
    date: 2024-12-06
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct
    title: "Llama-3.3-70B-Instruct model card"
    date: 2024-12-06
  - kind: pricing
    tag: 3p
    url: https://www.together.ai/pricing
    publisher: Together AI
    title: "Hosted inference pricing"
    date: 2026-05

Hosted price (Together): $0.88 / $0.88 per 1M tokens.

Benchmarks (Llama 3.3 70B Instruct, lab):
- MMLU (CoT, 0-shot): 86.0 [lab] src=https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct date=2024-12
- MMLU-Pro (CoT, 5-shot): 68.9 [lab]
- HumanEval (pass@1): 88.4 [lab]
- MBPP++ (pass@1): 87.6 [lab]
- MATH (CoT): 77.0 [lab]
- GPQA Diamond (CoT): 50.5 [lab]
- IFEval: 92.1 [lab]
- BFCL v2: 77.3 [lab]
- MGSM: 91.1 [lab]

Notes: MATH score jump from 3.1 70B (68.0) to 3.3 70B (77.0) was the largest single-bench improvement, driven by post-training math curriculum. Still no Meta-reported SWE-bench Verified.

---

### Llama 4 Scout (17B active / 109B total / 16 experts)

- Release: 2025-04-05
- Status: current (one of Meta's two flagship open-weight Llama 4 models; the other is Maverick)
- Architecture: **Mixture of Experts** — 17B active params, 109B total, 16 experts
- Context: **10,000,000 tokens** (10M — Meta-claimed at launch; the longest open-weight context window at release; not all hosts support the full 10M)
- Modality: **natively multimodal** (text + image input; text + code output) — early-fusion vision encoder integrated into pretraining
- License: **Llama 4 Community License Agreement** — same 700M MAU clause; **EU restriction tightened**: multimodal features explicitly **not licensed to EU-domiciled entities** (and individuals resident there for certain commercial uses); Acceptable Use Policy revised
- Notable: smallest of the two shipped Llama 4 models; positioned for "single-H100" deployment with low active-param count
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/llama-4-multimodal-intelligence/
    title: "The Llama 4 herd: The beginning of a new era of natively multimodal AI innovation"
    date: 2025-04-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
    title: "Llama-4-Scout-17B-16E-Instruct model card"
    date: 2025-04-05

Benchmarks (Llama 4 Scout Instruct, lab):
- MMLU-Pro: 74.3 [lab] src=https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct date=2025-04
- GPQA Diamond: 57.2 [lab]
- LiveCodeBench (Oct-2024 to Feb-2025, pass@1): 32.8 [lab]
- MMMU: 73.4 [lab]
- MMMU Pro: 59.6 [lab]
- MathVista: 73.7 [lab]
- ChartQA: 90.0 [lab]
- DocVQA (test, anls): 94.4 [lab]
- MGSM: 90.6 [lab]

Benchmarks (Llama 4 Scout pretrained):
- MMLU: 79.6 [lab]
- MMLU-Pro: 58.2 [lab]
- MATH (maj1@1): 50.3 [lab]
- MBPP (pass@1): 67.8 [lab]
- ChartQA (pretrained): 83.4 [lab]
- DocVQA (pretrained): 89.4 [lab]

Notes: Hosted at Cerebras / Groq / Together — sub-$1/M-token inference. No Meta-reported SWE-bench Verified.

---

### Llama 4 Maverick (17B active / 400B total / 128 experts)

- Release: 2025-04-05
- Status: current
- Architecture: **MoE** — 17B active params, 400B total, **128 experts**; ~22T training tokens; knowledge cutoff August 2024
- Context: 1,000,000 tokens (1M)
- Modality: natively multimodal (text + image input; text + code output)
- License: same **Llama 4 Community License** as Scout (700M MAU cap + EU carve-out for multimodal)
- Notable: Meta's launch-day LMArena ELO of 1417 was contested — a tuned "experimental chat" variant submitted to the arena differed from the released weights, triggering a transparency dispute that prompted LMArena to update its submission rules
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/llama-4-multimodal-intelligence/
    title: "The Llama 4 herd"
    date: 2025-04-05
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct
    title: "Llama-4-Maverick-17B-128E-Instruct model card"
    date: 2025-04-05
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/llama-4-maverick
    publisher: Artificial Analysis
    title: "Llama 4 Maverick — Artificial Analysis"
    date: 2026-05

Benchmarks (Llama 4 Maverick Instruct, lab):
- MMLU-Pro: 80.5 [lab] src=https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct date=2025-04
- GPQA Diamond: 69.8 [lab]
- LiveCodeBench (10/2024-02/2025, pass@1): 43.4 [lab]
- MMMU: 73.4 [lab]
- MMMU Pro: 59.6 [lab]
- MathVista: 73.7 [lab]
- ChartQA: 90.0 [lab]
- DocVQA: 94.4 [lab]
- MGSM: 92.3 [lab]

Benchmarks (Llama 4 Maverick pretrained):
- MMLU: 85.5 [lab]
- MMLU-Pro: 62.9 [lab]
- MATH (maj1@1): 61.2 [lab]
- MBPP (pass@1): 77.6 [lab]

3p replication: Artificial Analysis Intelligence Index v4.0 = **18** (median for open-weight non-reasoning models of similar size = 23). Maverick lands **below open-weight peer median** on AA's reasoning/coding mixture, contradicting lab framing.
- AA Intelligence Index: 18 [3p] src=https://artificialanalysis.ai/models/llama-4-maverick date=2026-05

Notes: Maverick is the larger of the two released Llama 4 weights; Behemoth was intended as the teacher above it but never shipped (see next entry).

---

### Llama 4 Behemoth (288B active / ~2T total / 16 experts) — UNRELEASED

- Release: **never publicly released** (status as of May 2026)
- Status: **preview / paused / effectively cancelled**
- Architecture: announced as MoE — 288B active params, ~2T total, 16 experts
- Modality: would have been natively multimodal
- License: would have been Llama 4 Community License
- Timeline:
  - 2025-04-05: Announced as "still in training" alongside Scout/Maverick
  - 2025-05-15: Reports surface that release is being delayed from "early summer" to "fall 2025 or later"
  - 2025-fall: Meta organizational restructure (creation of Meta Superintelligence Labs under Alexandr Wang; talent hires from OpenAI/Anthropic/Google)
  - 2026-04-08: Meta launches **Muse Spark** (separate, **proprietary** model) as its first MSL product. Behemoth never ships.
- Notable: was designed as a "teacher model" for codistillation into Scout and Maverick; reportedly underperformed Meta's own internal targets, with engineers split on whether to ship; no formal cancellation announcement, but no signs of imminent release as of May 2026
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/llama-4-multimodal-intelligence/
    title: "The Llama 4 herd (Behemoth section — still in training)"
    date: 2025-04-05
  - kind: coverage
    tag: 3p
    url: https://www.axios.com/2025/05/15/meta-behemoth-llama-scaling-delays
    publisher: Axios
    title: "Meta delays 'Behemoth' AI model release, per report"
    date: 2025-05-15
  - kind: coverage
    tag: 3p
    url: https://www.computerworld.com/article/3987990/meta-hits-pause-on-llama-4-behemoth-ai-model-amid-capability-concerns.html
    publisher: Computerworld
    title: "Meta hits pause on 'Llama 4 Behemoth' AI model amid capability concerns"
    date: 2025-05-15
  - kind: coverage
    tag: 3p
    url: https://zapier.com/blog/llama-meta/
    publisher: Zapier
    title: "Meta AI: What is Muse Spark? And what happened to Llama?"
    date: 2026-04

Benchmarks: Meta's April-2025 announcement claimed Behemoth "outperforms GPT-4.5, Claude Sonnet 3.7, and Gemini 2.0 Pro on several STEM benchmarks" but published no concrete percentages. With no public weights and no released technical report, **no verified benchmark numbers exist**.

Notes: This is the most consequential gap in the Llama lineage between April 2025 and May 2026 — Meta's intended frontier open-weight model simply never materialized.

---

### Llama Guard family (safety classifier line)

- Status: **current** (Llama Guard 4 is the active version)
- The Llama Guard family ships as a **safety classifier** — used as input/output filtering layer on top of any LLM (not just Llama). Each Llama Guard release tracks the model generation it accompanies.

#### Llama Guard 1 / 2 / 3

- Llama Guard 1 (2023-12-07, 7B) — Llama 2-based classifier
- Llama Guard 2 (2024-04-18, 8B) — released alongside Llama 3
- Llama Guard 3 (2024-07-23, 8B + 1B "Guard 3 Mini") — released alongside Llama 3.1; later joined by Llama Guard 3 Vision (11B, Sep 2024 with Llama 3.2 vision)
- License: same Llama Community License as the corresponding generation
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/meta-llama-3-1/
    title: "Llama 3.1 release — Llama Guard 3"
    date: 2024-07-23

#### Llama Guard 4 (12B)

- Release: **2025-04-30**
- Sizes: **12B**
- Context: ~163,800 tokens
- Modality: **natively multimodal** (text + multi-image input)
- License: Llama 4 Community License
- Notable: first Llama Guard built jointly for text + multiple-image inputs; aligns to the MLCommons hazards taxonomy; deployed as the default safety layer in the (limited-preview) Llama API
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/ai-defenders-program-llama-protection-tools/
    title: "Sharing new open source protection tools (Llama Guard 4, LlamaFirewall, Prompt Guard 2)"
    date: 2025-04-29
  - kind: model-card
    tag: lab
    url: https://huggingface.co/meta-llama/Llama-Guard-4-12B
    title: "Llama-Guard-4-12B model card"
    date: 2025-04-30

#### Companion protection tools (announced 2025-04-29, alongside Guard 4)

- **LlamaFirewall** — orchestration layer that combines guard models with prompt/output filters
- **Llama Prompt Guard 2** — two sizes (86M and 22M) — jailbreak/injection classifier; the 22M variant cuts latency ~75% vs Prompt Guard 1
- **CyberSecEval 4** — Meta's cyber-eval benchmark suite (not a model — included for ecosystem completeness)
- Sources: same as Llama Guard 4 announcement above

---

### Specialty / experimental — what did NOT ship

- **MobileLLM** — research line published in 2024 (sub-billion-parameter models for on-device); shipped as research code + arXiv paper but never elevated to a flagship product line. Llama 3.2 1B/3B effectively absorbed Meta's on-device strategy.
  - Source: kind: model-card, tag: lab, url: https://arxiv.org/abs/2402.14905, title: "MobileLLM: Optimizing Sub-billion Parameter Language Models for On-Device Use Cases", date: 2024-02

- **Llama 5** — **does not exist** as of May 2026. Multiple secondary sources (including one financial-press article dated 2026-04-08) erroneously refer to Meta's Muse Spark launch as "Llama 5." Meta's actual blog post (`ai.meta.com/blog/introducing-muse-spark-msl/`) and contemporaneous CNBC / VentureBeat / AI News coverage all confirm Muse Spark is a **separate, proprietary, closed-weights** model line from Meta Superintelligence Labs, not a Llama release. The Llama brand has no announced Llama 5 timeline.

- **Llama 4.1 / 4.2** — no incremental Llama 4 updates shipped between April 2025 and May 2026. Meta's LlamaCon (April 29 2025) added the Llama API (developer platform) and the Llama protection tools (Guard 4, Firewall, Prompt Guard 2), but no new base-model checkpoints.

---

### Sidebar — Muse Spark (proprietary, separate line, included for completeness)

Muse Spark is **not a Llama model** but is included briefly because the public discourse has conflated it with "Llama 5" and the coordinator's checklist asked us to verify the Llama-5 gap.

- Release: 2026-04-08
- Status: current (proprietary; private API preview at launch)
- Lab org: Meta Superintelligence Labs (MSL), led by Alexandr Wang post-2025 reorg
- License: **closed-weights, proprietary** — first major Meta LLM since LLaMA 1 to ship without open weights. Available only via meta.ai, the Meta AI app, and a private API preview
- Modality: natively multimodal; reasoning-tier model with three operational modes — Instant / Thinking / Contemplating (parallel multi-agent)
- Notable: Meta's framing positions Muse Spark as an order-of-magnitude more compute-efficient than Llama 4 Maverick at equivalent capability; the launch acknowledges the Llama line is no longer Meta's frontier path. MSL has stated "bigger models are already in development with plans to open-source future versions" — taken with caution given the Behemoth precedent.
- Sources:
  - kind: announcement
    tag: lab
    url: https://ai.meta.com/blog/introducing-muse-spark-msl/
    title: "Introducing Muse Spark: Scaling Towards Personal Superintelligence"
    date: 2026-04-08
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/technology/goodbye-llama-meta-launches-new-proprietary-ai-model-muse-spark-first-since
    publisher: VentureBeat
    title: "Goodbye, Llama? Meta launches new proprietary AI model Muse Spark"
    date: 2026-04-08
  - kind: coverage
    tag: 3p
    url: https://www.artificialintelligence-news.com/news/meta-muse-spark-ai-model-open-source/
    publisher: AI News
    title: "Did Meta Sacrifice Its Open-Source Identity for a Competitive AI Model?"
    date: 2026-04

Benchmarks (Muse Spark, lab Contemplating mode):
- Humanity's Last Exam: 58 [lab] src=https://ai.meta.com/blog/introducing-muse-spark-msl/ date=2026-04
- FrontierScience Research: 38 [lab]

3p:
- Artificial Analysis Intelligence Index v4.0: 52 [3p] src=https://artificialanalysis.ai/ date=2026-04 — ranks 4th overall behind Gemini 3.1 Pro, GPT-5.4, Claude Opus 4.6 (per the AI News writeup)

---

## Cross-cutting notes

**License-by-generation summary table:**

| Generation | License | Commercial use | MAU cap | EU restriction | Output-for-training |
|---|---|---|---|---|---|
| Llama 1 | Non-commercial research | no | n/a | no | no |
| Llama 2 | Llama 2 Community | yes | 700M MAU | no | ambiguous |
| Code Llama | Llama 2 Community | yes | 700M MAU | no | ambiguous |
| Llama 3 | Llama 3 Community | yes | 700M MAU | no (added "Built with Llama" clause) | ambiguous |
| Llama 3.1 | Llama 3.1 Community | yes | 700M MAU | no | **explicitly permitted** |
| Llama 3.2 | Llama 3.2 Community | yes | 700M MAU | **vision models blocked for EU entities** | permitted |
| Llama 3.3 | Llama 3.3 Community | yes | 700M MAU | (text-only — n/a) | permitted |
| Llama 4 | Llama 4 Community | yes | 700M MAU | **multimodal blocked for EU entities** (broader carve-out than 3.2) | permitted |

**Why no SWE-bench Verified column:** Meta has not reported SWE-bench Verified in any Llama model card or release blog through May 2026. Third-party leaderboards (swebench.com) show open-weight Llama models posting sub-frontier SWE-bench numbers (typically 25-40% range on Verified for 3.1 405B / 3.3 70B / Llama 4 Maverick when run via SWE-agent), well behind Claude/GPT/Gemini frontier models. The omission is itself a finding.

**Pricing convention:** Open-weight models have no Meta-set API list price. Representative third-party hosted pricing pulled from Together AI:
- Llama 3.3 70B: $0.88 / $0.88 per 1M tokens (in/out)
- Llama 3.1 8B: ~$0.18 / $0.18 per 1M (historical, varies by host)
- Llama 4 Scout / Maverick: available through Cerebras, Groq, Together, Fireworks; sub-$1/M typical for Scout, $0.50-$2/M for Maverick depending on host
- Llama 1, Llama 2, Code Llama: legacy, prices have largely been deprecated from hosted pricing pages

---

## Sources

- kind: announcement, tag: lab, url: https://ai.meta.com/blog/large-language-model-llama-meta-ai/ — Llama 1 announcement
- kind: model-card, tag: lab, url: https://arxiv.org/abs/2302.13971 — LLaMA paper
- kind: announcement, tag: lab, url: https://about.fb.com/news/2023/07/llama-2/ — Llama 2 announcement
- kind: model-card, tag: lab, url: https://arxiv.org/abs/2307.09288 — Llama 2 paper
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/code-llama-large-language-model-coding/ — Code Llama (Aug 2023)
- kind: announcement, tag: lab, url: https://about.fb.com/news/2024/01/code-llama-large-language-model-coding/ — Code Llama 70B (Jan 2024)
- kind: model-card, tag: lab, url: https://arxiv.org/abs/2308.12950 — Code Llama paper
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/meta-llama-3/ — Llama 3 announcement
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct — Llama 3 70B model card
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/meta-llama-3-1/ — Llama 3.1 announcement
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct — Llama 3.1 405B model card
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct — Llama 3.1 70B model card
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct — Llama 3.1 8B model card
- kind: model-card, tag: lab, url: https://arxiv.org/abs/2407.21783 — The Llama 3 Herd of Models paper
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/ — Llama 3.2 announcement
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-3.2-90B-Vision-Instruct — Llama 3.2 90B Vision model card
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/meta-llama-3-3/ — Llama 3.3 announcement
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct — Llama 3.3 70B model card
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/llama-4-multimodal-intelligence/ — Llama 4 launch (Scout / Maverick / Behemoth)
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct — Llama 4 Scout model card
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct — Llama 4 Maverick model card
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/llamacon-llama-news/ — LlamaCon 2025 (Llama API preview, Guard 4 ecosystem)
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/ai-defenders-program-llama-protection-tools/ — Llama Guard 4, LlamaFirewall, Prompt Guard 2
- kind: model-card, tag: lab, url: https://huggingface.co/meta-llama/Llama-Guard-4-12B — Llama Guard 4 model card
- kind: model-card, tag: lab, url: https://arxiv.org/abs/2402.14905 — MobileLLM paper
- kind: announcement, tag: lab, url: https://ai.meta.com/blog/introducing-muse-spark-msl/ — Muse Spark launch (Meta Superintelligence Labs, proprietary; included for "no Llama 5" verification)
- kind: coverage, tag: 3p, url: https://en.wikipedia.org/wiki/Llama_(language_model) — Wikipedia lineage spine
- kind: coverage, tag: 3p, url: https://venturebeat.com/technology/goodbye-llama-meta-launches-new-proprietary-ai-model-muse-spark-first-since — "Goodbye Llama" coverage
- kind: coverage, tag: 3p, url: https://zapier.com/blog/llama-meta/ — Zapier: state of Meta AI / what happened to Llama
- kind: coverage, tag: 3p, url: https://www.artificialintelligence-news.com/news/meta-muse-spark-ai-model-open-source/ — Muse Spark proprietary status confirmation
- kind: coverage, tag: 3p, url: https://www.axios.com/2025/05/15/meta-behemoth-llama-scaling-delays — Behemoth delay (Axios)
- kind: coverage, tag: 3p, url: https://www.computerworld.com/article/3987990/meta-hits-pause-on-llama-4-behemoth-ai-model-amid-capability-concerns.html — Behemoth pause (Computerworld)
- kind: coverage, tag: 3p, url: https://siliconangle.com/2025/05/15/meta-postpone-release-llama-4-behemoth-model-report-claims/ — Behemoth postpone (SiliconANGLE)
- kind: replication, tag: 3p, url: https://artificialanalysis.ai/models/llama-4-maverick — Llama 4 Maverick 3p Intelligence Index
- kind: pricing, tag: 3p, url: https://www.together.ai/pricing — Together AI hosted Llama pricing
