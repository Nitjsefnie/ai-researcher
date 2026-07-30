# Alibaba Qwen Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema:
typed `Sources:` blocks (`announcement`/`model-card`/`pricing`/`coverage`/`replication`),
and benchmark rows surface both `lab` and `3p` numbers where they disagree by >3pp.

Lifecycle spine from Qwen team blogs (`qwenlm.github.io/blog/`), HuggingFace, Wikipedia's
"Qwen" article, and QwenLM GitHub orgs (verified May 2026). Status uses "current" / "legacy"
(superseded but available) / "preview" / "proprietary". License shifts flagged inline.

**Headline state (May 2026):** Qwen has the largest open-weight model count of any major lab —
9 numbered generations (Qwen 1, 1.5, 2, 2.5, QwQ, 3, 3-Next, 3.5, 3.6) plus modality forks
(VL, Coder, Math, Audio, Omni) and proprietary Max line. Qwen 3 (Apr 2025) was the first
hybrid-thinking family. Qwen3-Max (Sep 2025) is Alibaba's first proprietary flagship (>1T params,
API-only). Qwen 3.5 (Feb 2026, 0.8B–397B) and Qwen 3.6 (Apr 2026, 27B + 35B-A3B) are the latest
open-weight drops. No Qwen 4 has shipped through May 2026.

---

### Qwen 1 (1.8B / 7B / 14B / 72B base + Chat)

- Release: 2023-08-03 (7B), 2023-09-25 (14B), 2023-11-30 (72B + 1.8B)
- Status: legacy (superseded; weights remain on HuggingFace)
- Sizes: 1.8B, 7B, 14B, 72B (base + Chat); Qwen-Audio also Nov 2023
- Context: 2K → 8K (32K via NTK-aware RoPE in later checkpoints)
- License: **Tongyi Qianwen License** — open weights, commercial use with >100M-MAU restriction; smaller sizes had their own community license variant.
- Notable: first major Chinese open-weight foundation model family; 72B trained on >3T tokens; topped open-source leaderboards on MMLU / C-Eval / CMMLU / GaokaoBench in late 2023.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/QwenLM/Qwen
    title: "Qwen (通义千问) chat & pretrained large language model"
    date: 2023-08-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/Qwen/Qwen-72B
    title: "Qwen-72B model card"
    date: 2023-11-30
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2309.16609
    title: "Qwen Technical Report"
    date: 2023-09-28
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Qwen
    publisher: Wikipedia
    title: "Qwen"
    date: 2026-05

Benchmarks (Qwen-72B base, lab tech report):
- MMLU (5-shot): 77.4 [lab] src=https://arxiv.org/abs/2309.16609
- C-Eval: 83.3 [lab]
- CMMLU: 83.6 [lab]
- GSM8K: 76.9 [lab]
- MATH: 35.2 [lab]
- HumanEval: 35.4 [lab]
- BBH: 65.7 [lab]

Notes: MMLU-Pro, GPQA, LiveCodeBench, SWE-bench, BFCL did not exist or were not standard at Qwen 1's release. No agentic-coding numbers.

---

### Qwen 1.5 (0.5B / 1.8B / 4B / 7B / 14B / 32B / 72B / 110B + MoE-A2.7B)

- Release: 2024-02-04 (initial 7-size drop); 32B added 2024-04-02; 110B added 2024-04-25
- Status: legacy (superseded by Qwen 2)
- Sizes: 0.5B / 1.8B / 4B / 7B / 14B / 32B / 72B / 110B dense; MoE-A2.7B (14.3B total / 2.7B active)
- Context: 32,768 uniformly
- License: **Tongyi Qianwen License** (mostly); smaller sizes more permissive
- Notable: first Qwen drop integrated natively into HF Transformers (v4.37+) without `trust_remote_code`; introduced the wide size spread; 110B was the largest dense open-weight model at release.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen1.5/
    title: "Introducing Qwen1.5"
    date: 2024-02-04
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen1.5-110b/
    title: "Qwen1.5-110B: The First 100B+ Model of the Qwen1.5 Series"
    date: 2024-04-25
  - kind: model-card
    tag: lab
    url: https://huggingface.co/Qwen/Qwen1.5-72B
    title: "Qwen1.5-72B model card"
    date: 2024-02-04

Benchmarks (Qwen1.5-72B-Chat, lab blog):
- MMLU: 77.5 [lab] src=https://qwenlm.github.io/blog/qwen1.5/
- C-Eval: 84.1 [lab]
- GSM8K: 79.5 [lab]
- MATH: 34.1 [lab]
- HumanEval: 41.5 [lab]

Notes: Outperformed Llama2-70B across all reported benchmarks. Qwen1.5-MoE-A2.7B achieved 7B-comparable performance with ~25% inference cost.

---

### Qwen 2 (0.5B / 1.5B / 7B / 57B-A14B / 72B)

- Release: 2024-06-07
- Status: legacy (superseded by Qwen 2.5)
- Sizes: 0.5B, 1.5B, 7B dense; 57B-A14B MoE (first MoE in main Qwen line); 72B dense
- Context: 32K base; 7B and 72B Instruct extended to 128K via YaRN; 57B-A14B-Instruct 64K
- Modality: text (Qwen2-Audio and Qwen2-VL released as separate forks; see below)
- License: **Apache 2.0** for 0.5B/1.5B/7B/57B-A14B; **Tongyi Qianwen License** for 72B
- Notable: license bifurcation introduced — smaller sizes became permissively Apache; biggest size kept Tongyi Qianwen; 27 supported languages; significantly improved coding/math vs Qwen 1.5.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2/
    title: "Hello Qwen2"
    date: 2024-06-07
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2407.10671
    title: "Qwen2 Technical Report"
    date: 2024-07-15

Benchmarks (Qwen2-72B-Instruct, lab tech report):
- MMLU: 82.3 [lab] src=https://qwenlm.github.io/blog/qwen2/
- MMLU-Pro: 64.4 [lab]
- GPQA: 42.4 [lab]
- MATH: 59.7 [lab]
- GSM8K: 91.1 [lab]
- HumanEval: 86.0 [lab]
- C-Eval: 83.8 [lab]
- MT-Bench: 9.1 [lab]
- Arena-Hard: 48.1 [lab]
- LiveCodeBench: 35.7 [lab]

Notes: Base-model numbers separately: Qwen2-72B base scored MMLU 84.2, GPQA 37.9, HumanEval 64.6, GSM8K 89.5, BBH 82.4 — generally above Llama-3-70B base.

---

### Qwen2-VL (2B / 7B / 72B — vision-language fork)

- Release: 2024-08-29 (2B/7B); 72B initially API-only
- Status: legacy (superseded by Qwen2.5-VL)
- Sizes: 2B, 7B (open weights); 72B (initially API-only)
- Modality: vision-language (image + video + text); dynamic image resolution; videos to 20+ min
- License: **Apache 2.0** (2B/7B); **Tongyi Qianwen License** (72B)
- Notable: introduced Naive Dynamic Resolution + multimodal RoPE (M-RoPE); 72B claimed to beat GPT-4o and Claude 3.5 Sonnet on several vision benches.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2-vl/
    title: "Qwen2-VL: To See the World More Clearly"
    date: 2024-08-29
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2409.12191
    title: "Qwen2-VL Technical Report"
    date: 2024-09-18

Benchmarks (Qwen2-VL-72B, lab claims): MMMU ~64.5, MathVista ~70.5, DocVQA 96.5, RealWorldQA 77.8 [all lab] src=https://qwenlm.github.io/blog/qwen2-vl/. Qwen2-Audio (Apache 2.0, Aug 2024) is a parallel audio-LM, out of scope here.

---

### Qwen 2.5 (0.5B / 1.5B / 3B / 7B / 14B / 32B / 72B)

- Release: 2024-09-19
- Status: legacy (still widely used; superseded by Qwen 3 family for frontier work, but 2.5 remains a daily-driver workhorse)
- Sizes: 0.5B, 1.5B, 3B, 7B, 14B, 32B, 72B dense (each in base and Instruct)
- Context: 128K supported (32K native, 128K with YaRN); generation up to 8K tokens
- Modality: text (companion Coder/Math/VL/Max/Omni variants released separately)
- License: **Apache 2.0** for all sizes EXCEPT 3B (Qwen Research License) and 72B (Qwen License — community license, allows commercial use under monthly-active-user limit)
- Notable: 18T training tokens (2x Qwen 2); massive open-weight refresh that became the dominant open-source family for late 2024 / early 2025; 32B variant struck the price-performance sweet spot.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5/
    title: "Qwen2.5: A Party of Foundation Models!"
    date: 2024-09-19
  - kind: model-card
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5-llm/
    title: "Qwen2.5-LLM: Extending the boundary of LLMs"
    date: 2024-09-19
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2412.15115
    title: "Qwen2.5 Technical Report"
    date: 2024-12-19

Benchmarks (Qwen2.5-72B-Instruct, lab tech report):
- MMLU: 86.1 [lab] src=https://arxiv.org/abs/2412.15115
- MMLU-Pro: 71.1 [lab]
- GPQA: 49.0 [lab]
- MATH: 83.1 [lab]
- GSM8K: 95.8 [lab]
- HumanEval: 86.6 [lab]
- LiveCodeBench (2305-2409): 55.5 [lab]
- MBPP: 88.2 [lab]
- MultiPL-E: 75.1 [lab]
- BBH: 86.3 [lab]
- IFEval: 84.1 [lab]
- Arena-Hard: 81.2 [lab]
- MT-Bench: 9.35 [lab]

Notes: Qwen2.5-72B-Instruct widely reported to outperform Llama-3.1-405B-Instruct on MMLU-redux, MATH, MBPP, MultiPL-E, LiveCodeBench, Arena-Hard at ~17% the parameter count.

---

### Qwen2.5-Coder (0.5B / 1.5B / 3B / 7B / 14B / 32B — code specialty fork)

- Release: 2024-11-12 (full family); earlier 7B preview Sep 2024
- Status: legacy (superseded by Qwen3-Coder)
- Sizes: 0.5B, 1.5B, 3B, 7B, 14B, 32B (base and Instruct each)
- Context: 128K
- Modality: code-specialty text
- License: **Apache 2.0** for 0.5B/1.5B/7B/14B/32B; **Qwen Research License** for 3B
- Notable: 32B-Instruct was the first open-source coding model to match GPT-4o on EvalPlus / LiveCodeBench / BigCodeBench; trained on 5.5T code-heavy tokens; supports 40+ programming languages.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5-coder-family/
    title: "Qwen2.5-Coder Series: Powerful, Diverse, Practical."
    date: 2024-11-12
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2409.12186
    title: "Qwen2.5-Coder Technical Report"
    date: 2024-09-18

Benchmarks (Qwen2.5-Coder-32B-Instruct, lab tech report):
- HumanEval (pass@1): 88.4 [lab] src=https://arxiv.org/abs/2409.12186
- MBPP: 84.0 [lab]
- LiveCodeBench: 51.2 [lab]
- BigCodeBench (full): 49.6 [lab]
- BigCodeBench (hard): 27.0 [lab]
- MultiPL-E: 75.4 [lab]
- Aider: 73.7 [lab] (matched GPT-4o)
- McEval (40+ languages): 65.9 [lab]
- MdEval (repair): 75.2 [lab]

Notes: Set the bar for open-weight coding models at end of 2024; quickly integrated into Cursor, Cline, Continue. SWE-bench Verified numbers not reported by lab at this size.

---

### Qwen2.5-Math (1.5B / 7B / 72B — math specialty fork)

- Release: 2024-09-19
- Status: legacy (superseded by Qwen3 reasoning models)
- Sizes: 1.5B, 7B, 72B (base + Instruct each); math-RM reward model
- License: same as parent Qwen 2.5 — Apache 2.0 (1.5B/7B), Qwen License (72B)
- Notable: dual-mode — Chain-of-Thought + Tool-Integrated Reasoning (Python); English + Chinese math benches (CMATH, GaoKao).
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5-math/
    title: "Qwen2.5-Math"
    date: 2024-09-19

Benchmarks (Qwen2.5-Math-72B-Instruct, lab): MATH (TIR + RM@8) 92.9; GSM8K >95; claimed SOTA on AIME 2024 / AMC 2023 / OlympiadBench among open models. 7B matched prior-gen 72B; 1.5B + Python hit ~80 MATH.

---

### QwQ-32B-Preview (reasoning preview)

- Release: 2024-11-28
- Status: legacy preview (superseded by QwQ-32B GA in March 2025)
- Sizes: 32B dense (single SKU)
- Context: 32K
- Modality: text (reasoning specialty)
- License: **Apache 2.0**
- Notable: First Qwen reasoning model — direct response to OpenAI o1; "experimental research model" framing; flagged language-mixing and reasoning-loop limitations.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwq-32b-preview/
    title: "QwQ: Reflect Deeply on the Boundaries of the Unknown"
    date: 2024-11-28

Benchmarks (QwQ-32B-Preview, lab blog):
- AIME: 50.0 [lab] src=https://qwenlm.github.io/blog/qwq-32b-preview/
- MATH-500: 90.6 [lab]
- GPQA Diamond: 65.2 [lab]
- LiveCodeBench: 50.0 [lab]

Notes: Lab acknowledged limitations: language mixing, reasoning loops, safety gaps, common-sense weakness. QVQ-72B-Preview (vision reasoning) shipped Dec 2024 as a parallel exploration.

---

### Qwen2.5-VL (3B / 7B / 32B / 72B)

- Release: 2025-01-26 (3B/7B/72B); 32B later
- Status: legacy (superseded by Qwen3-VL Sep 2025)
- Sizes: 3B, 7B, 32B, 72B (base + Instruct)
- License: **Apache 2.0** (7B/32B); **Qwen Research License** (3B); **Qwen License** (72B)
- Notable: "visual agent" framing (model can drive computer UIs); much better OCR/document/chart parsing than Qwen2-VL; 7B claimed to beat GPT-4o-mini on several vision tasks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5-vl/
    title: "Qwen2.5-VL: Bigger, Better, Stronger"
    date: 2025-01-26

Benchmarks: lab claims SOTA among open models on MMMU / MathVista / DocVQA / ChartQA / VideoMME; per-bench numbers in tech report.

---

### Qwen2.5-Max (proprietary MoE flagship)

- Release: 2025-01-28
- Status: proprietary (API only; never open-weighted); superseded by Qwen3-Max Sep 2025
- Sizes: undisclosed MoE config (Alibaba did not release parameter count)
- Context: long context via DashScope API
- Modality: text
- License: **proprietary** — Alibaba Cloud commercial terms only; available via Qwen Chat + DashScope/Model Studio API (model name `qwen-max-2025-01-25`)
- Notable: Alibaba's first explicit "we kept this closed" Qwen release; positioned vs DeepSeek V3 and GPT-4o; pretrained on >20T tokens with SFT + RLHF post-training; LMArena ranking placed it competitively with frontier closed models.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen2.5-max/
    title: "Qwen2.5-Max: Exploring the Intelligence of Large-scale MoE Model"
    date: 2025-01-28
  - kind: pricing
    tag: lab
    url: https://www.alibabacloud.com/help/en/model-studio/models
    title: "DashScope / Model Studio models"

Benchmarks (Qwen2.5-Max, lab blog):
- MMLU-Pro: 76.1 [lab] src=https://qwenlm.github.io/blog/qwen2.5-max/
- GPQA Diamond: 60.1 [lab]
- LiveCodeBench: 38.7 [lab]
- LiveBench (overall): 62.2 [lab]
- Arena-Hard: claimed > DeepSeek V3 (exact score not published in blog)

Notes: 3p comparisons (e.g. Vellum, Artificial Analysis) had it within 1–4 pp of DeepSeek V3 on most benchmarks, behind Claude 3.5 Sonnet by 3–5 pp on MMLU-Pro / GPQA.

---

### Qwen2.5-Omni (3B / 7B — multimodal end-to-end)

- Release: 2025-03-26 — first Qwen end-to-end omnimodal; "thinker-talker" architecture; real-time speech out.
- Sizes: 7B (Apache 2.0), 3B (Qwen Research License). Superseded by Qwen3-Omni Sep 2025.
- Source: https://qwenlm.github.io/blog/qwen2.5-omni/ — out of scope for text-LLM benchmarks.

---

### QwQ-32B (reasoning GA)

- Release: 2025-03-06
- Status: legacy (superseded by Qwen3 reasoning models; weights remain on HuggingFace)
- Sizes: 32B dense
- Context: 32K
- Modality: text reasoning
- License: **Apache 2.0**
- Notable: GA reasoning release; lab claimed performance "comparable to DeepSeek-R1" (671B / 37B active) at 32B dense — massive parameter-efficiency win for reasoning; integrated agentic tool use.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwq-32b/
    title: "QwQ-32B: Embracing the Power of Reinforcement Learning"
    date: 2025-03-06

Benchmarks (QwQ-32B, lab + 3p replication):
- AIME 2024: ~79 [lab claim, ~match DeepSeek-R1] src=https://qwenlm.github.io/blog/qwq-32b/
- MATH-500: ~94 [lab claim]
- GPQA Diamond: ~65 [lab claim]
- LiveCodeBench: ~63 [lab claim]
- 3p (Artificial Analysis): in same band as DeepSeek-R1 on AIME / GPQA; trailed on some coding tasks

Notes: Genuine surprise of early 2025 — 32B dense matching 671B sparse on reasoning benches. Established RL-on-strong-base as a viable reasoning recipe outside DeepSeek.

---

### Qwen 3 (0.6B / 1.7B / 4B / 8B / 14B / 32B dense + 30B-A3B / 235B-A22B MoE)

- Release: 2025-04-28
- Status: current open-weight flagship line (with July 2025 "2507" refreshes for 235B-A22B Instruct/Thinking)
- Sizes: dense 0.6B, 1.7B, 4B, 8B, 14B, 32B; MoE 30B-A3B (30B total / 3B active), 235B-A22B (235B / 22B active)
- Context: 32K native (smaller dense); 128K (larger dense); 256K via YaRN for 235B; the 2507 refreshes natively support 262,144 tokens
- Modality: text
- License: **Apache 2.0** across the board (all sizes, all variants)
- Notable: Qwen's first **hybrid-thinking** family — single model supports both thinking and non-thinking modes via prompt-side toggle; thinking duration controllable up to ~38K tokens; ~36T training tokens (2x Qwen2.5); 119 languages.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen3/
    title: "Qwen3: Think Deeper, Act Faster"
    date: 2025-04-28
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2505.09388
    title: "Qwen3 Technical Report"
    date: 2025-05-13
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2025/04/28/alibaba-unveils-qwen-3-a-family-of-hybrid-ai-reasoning-models/
    publisher: TechCrunch
    title: "Alibaba unveils Qwen3, a family of 'hybrid' AI reasoning models"
    date: 2025-04-28

Benchmarks (Qwen3-235B-A22B thinking mode, lab tech report + 3p):
- AIME 2024: 85.7 [lab] src=https://arxiv.org/abs/2505.09388
- AIME 2025: 81.5 [lab]
- MATH-500: ~93 [lab]
- GPQA Diamond: 70.0 [lab]
- MMLU-Pro: 82.8 [lab]
- LiveCodeBench v5: 70.7 [lab]
- 3p Arena-Hard (post-release): ~95 [3p] src=https://designforonline.com/ai-models/qwen-qwen3-235b-a22b/

Benchmarks (Qwen3-32B, lab claims, in thinking mode):
- AIME: claimed competitive with QwQ-32B
- LiveCodeBench: improved on QwQ-32B
- (exact numbers in tech report Table 7+)

Notes:
- **July 2025 refreshes (`2507`):** Qwen3-235B-A22B-Instruct-2507 (Jul 22) and Qwen3-235B-A22B-Thinking-2507 (Jul 25) were split-mode replacements — Alibaba moved away from the single hybrid checkpoint to dedicated Instruct vs Thinking checkpoints, citing better quality at fixed mode. Thinking-2507 reportedly matched OpenAI o3, o4-mini, Gemini 2.5 Pro, Claude Opus 4 on reasoning benches.
- Smaller dense Qwen3 sizes (4B/8B/14B) were a notable contribution to local-inference quality — Qwen3-4B-Thinking became a workable on-device reasoner.

---

### Qwen3-Coder (480B-A35B + 30B-A3B — coding specialty)

- Release: 2025-07-22
- Status: legacy (superseded by Qwen3-Coder-Next Feb 2026; weights remain)
- Sizes: Qwen3-Coder-480B-A35B-Instruct (480B / 35B active MoE), Qwen3-Coder-30B-A3B
- Context: 256K native, 1M via extrapolation
- Modality: text (code specialty)
- License: **Apache 2.0**
- Notable: claimed comparable to Claude Sonnet 4 on agentic coding; trained on 7.5T tokens with 70% code share; execution-driven RL + long-horizon multi-turn agent RL; designed to slot into Claude Code / Cline / Cursor.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwenlm.github.io/blog/qwen3-coder/
    title: "Qwen3-Coder: Agentic Coding in the World"
    date: 2025-07-22
  - kind: coverage
    tag: 3p
    url: https://www.together.ai/blog/qwen-3-coder
    publisher: Together AI
    title: "Qwen3-Coder on Together AI"
    date: 2025-07

Benchmarks (Qwen3-Coder-480B-A35B-Instruct, lab + 3p):
- SWE-bench Verified: 69.6 [lab] src=https://qwenlm.github.io/blog/qwen3-coder/
- SWE-bench Pro (public, Scale): 38.7 ±3.55 [3p] src=https://labs.scale.com/leaderboard/swe_bench_pro_public
- Agentic Coding, Agentic Browser-Use, Agentic Tool-Use: claimed open-weight SOTA

Notes: SWE-bench Verified at 69.6 was effectively tied with Claude Sonnet 4's non-thinking number at the time. Established Qwen as a real coding-agent alternative to Anthropic for cost-sensitive deployments.

---

### Qwen3-Next-80B-A3B (Instruct + Thinking — hybrid architecture experiment)

- Release: 2025-09-11
- Status: current
- Sizes: 80B total / 3B active MoE (single SKU, two modes — Instruct and Thinking)
- Context: 256K native
- Modality: text
- License: **Apache 2.0**
- Notable: **architectural experiment** — replaces standard attention with hybrid Gated DeltaNet + Gated Attention; "high-sparsity MoE" calls only 9 of 256 experts per token; claimed to match Qwen3-235B-A22B-Instruct-2507 on many benches at 10x throughput on 32K+ contexts. Major "do more with less" story.
- Sources:
  - kind: announcement
    tag: lab
    url: https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking
    title: "Qwen3-Next-80B-A3B-Thinking model card"
    date: 2025-09-11
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2025/Sep/12/qwen3-next/
    publisher: Simon Willison
    title: "Qwen3-Next-80B-A3B: 🐧🦩 Who needs legs?!"
    date: 2025-09-12
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/qwen3-next-80b-a3b-reasoning
    publisher: Artificial Analysis
    title: "Qwen3 Next 80B A3B - Intelligence, Performance & Price Analysis"

Benchmarks (Qwen3-Next-80B-A3B-Thinking, lab claims):
- Outperformed Qwen3-30B-A3B-Thinking-2507 and Qwen3-32B-Thinking on multiple reasoning benches
- Reported above proprietary Gemini-2.5-Flash-Thinking on several benchmarks
- (Per-bench numbers on Artificial Analysis)

Notes: Most significant architectural reshape in the Qwen line since Qwen 2 introduced MoE.

---

### Qwen3-VL (2B / 4B / 8B / 32B dense + 30B-A3B / 235B-A22B MoE)

- Release: 2025-09-22
- Sizes: dense 2B/4B/8B/32B; MoE 30B-A3B, 235B-A22B; each in Instruct + Thinking
- Context: 256K native (text + interleaved multimodal)
- License: **Apache 2.0**
- Notable: vision arm of Qwen 3 — 235B-A22B claimed SOTA open on MMMU, MathVision, MathVista; markedly stronger pure-text capability vs Qwen2.5-VL.
- Sources:
  - kind: model-card
    tag: lab
    url: https://arxiv.org/abs/2511.21631
    title: "Qwen3-VL Technical Report"
    date: 2025-11

---

### Qwen3-Omni (30B-A3B — end-to-end omnimodal)

- Release: 2025-09. Successor to Qwen2.5-Omni at MoE scale (30B total / 3B active); Apache 2.0; text + image + video + audio in/out. Source: https://arxiv.org/html/2509.17765v1 — out of scope for text-LLM benchmarks.

---

### Qwen3-Max (proprietary trillion-parameter flagship)

- Release: 2025-09-24 (Instruct); preview Sep 6; Thinking variant alongside
- Status: current proprietary flagship
- Sizes: >1T parameters (sparse MoE, exact config undisclosed)
- Context: long context via API
- Modality: text (Max-Thinking also has visual/video gen capability per Alibaba)
- License: **proprietary** — API-only via Qwen Chat + Alibaba Cloud Model Studio + OpenRouter + AnyCoder; weights not released. Marked **departure from Qwen's open-source tradition** explicitly noted in coverage.
- Notable: first Qwen model to cross 1T params; pretrained on ~36T tokens; two variants — Qwen3-Max-Instruct (standard) and Qwen3-Max-Thinking (tool-augmented agentic / "heavy" runtime config); LMArena text leaderboard rank 3 globally at release, above GPT-5-Chat.
- Sources:
  - kind: announcement
    tag: lab
    url: https://x.com/Alibaba_Qwen/status/1963991502440562976
    title: "Qwen3-Max-Preview announcement"
    date: 2025-09-06
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2025/09/24/alibabas-qwen3-max-production-ready-thinking-mode-1t-parameters-and-day-one-coding-agentic-bench-signals/
    publisher: MarkTechPost
    title: "Qwen3-Max: Production-Ready Thinking Mode, 1T+ Parameters, Day-One Bench Signals"
    date: 2025-09-24
  - kind: coverage
    tag: 3p
    url: https://www.opensourceforu.com/2025/09/alibabas-qwen3-max-hits-1-trillion-parameters-but-drops-open-source-access/
    publisher: Open Source For You
    title: "Qwen3-Max Hits 1 Trillion Parameters But Drops Open Source Access"
    date: 2025-09
  - kind: pricing
    tag: 3p
    url: https://pricepertoken.com/pricing-page/model/qwen-qwen3-max
    publisher: pricepertoken.com
    title: "Qwen3 Max API Pricing 2026"

Benchmarks (Qwen3-Max, lab + 3p coverage):
- SWE-bench Verified (Instruct): 69.6 [lab] (above DeepSeek V3.1 non-thinking; below Claude Opus 4 non-thinking)
- AIME 2025 (Thinking, heavy + tools): claimed near-perfect
- LMArena: rank 3 globally (text)

Pricing (2026 via DashScope):
- $0.78 / M input, $3.90 / M output (qwen3-max) [3p] src=https://pricepertoken.com/pricing-page/model/qwen-qwen3-max

---

### Qwen 3.5 (0.8B / 2B / 4B / 9B / 27B / 35B-A3B / 122B-A10B / 397B-A17B)

- Release: 2026-02-16 (397B-A17B flagship); 2026-02-24 (122B/35B-A3B/27B mid); 2026-03-02 (9B/4B/2B/0.8B small)
- Status: current open-weight line (mostly superseded by Qwen 3.6 for the 27B / 35B-A3B tier; flagship 397B-A17B still SOTA for open-source coding)
- Sizes: 0.8B, 2B, 4B, 9B (dense), 27B (dense), 35B-A3B (MoE, 35B total / 3B active), 122B-A10B (MoE), 397B-A17B (MoE flagship)
- Context: long context, up to 256K+ on larger models
- Modality: text (Qwen3.5-Omni also released as separate fork)
- License: **Apache 2.0** for open-weight variants; Qwen3.5-Plus is a separate proprietary variant
- Notable: focused on **complex task completion and AI agents** — tool-use and agent benchmarks were the headline axis; nine-size spread covered edge devices through server-grade infrastructure.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/QwenLM/Qwen3.6
    title: "Qwen3.5 / Qwen3.6 GitHub releases"
    date: 2026-02
  - kind: coverage
    tag: 3p
    url: https://www.digitalapplied.com/blog/qwen-3-5-medium-model-series-benchmarks-pricing-guide
    publisher: Digital Applied
    title: "Qwen 3.5 Medium Models: Benchmarks, Pricing, and Guide"
    date: 2026-02

Benchmarks (Qwen3.5-397B-A17B flagship, 3p coverage):
- GPQA Diamond: 88.4 [3p] src=https://techie007.substack.com/p/qwen-35-the-complete-guide-benchmarks
- AIME 2026: 91.3 [3p]
- LiveCodeBench v6: 83.6 [3p]
- Tau2-Bench (agents): 86.7 [3p]
- SWE-bench Verified: 76.2 [3p] (per Qwen3.6-27B comparison)
- SWE-bench Pro: 50.9 [3p]
- Terminal-Bench 2.0: 52.5 [3p]

Benchmarks (Qwen3.5-122B-A10B):
- BFCL-V4 (tool use): 72.2 [3p] — claimed +30 pp over GPT-5 mini (55.5)
- IFBench: 76.5 [3p] — claimed above GPT-5.2 (75.4) and Claude (58.0)

Benchmarks (Qwen3.5-9B on laptop):
- GPQA Diamond: 81.7 [3p]

Notes: First time a Qwen flagship clearly leapfrogged the same-generation Max model (Qwen3-Max) on key open-eval benchmarks at the open-source side. The 397B-A17B was briefly the strongest open-weight model on multiple frontier benches.

---

### Qwen3-Coder-Next (80B-A3B — coding specialty)

- Release: 2026-02 (early)
- Status: current open-weight coding flagship
- Sizes: 80B total / 3B active MoE (single SKU)
- Context: long
- Modality: code-specialty text
- License: **Apache 2.0**
- Notable: heir to Qwen3-Coder-480B-A35B at ~1/6 active params; brings coding-agent capability to commodity GPUs; designed for local development (24GB-class VRAM with quantization).
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/abs/2603.00729
    title: "Qwen3-Coder-Next Technical Report"
    date: 2026-03-03
  - kind: model-card
    tag: lab
    url: https://huggingface.co/Qwen/Qwen3-Coder-Next
    title: "Qwen3-Coder-Next model card"
    date: 2026-02
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2026/02/03/qwen-team-releases-qwen3-coder-next-an-open-weight-language-model-designed-specifically-for-coding-agents-and-local-development/
    publisher: MarkTechPost
    title: "Qwen Team Releases Qwen3-Coder-Next"
    date: 2026-02-03

Benchmarks (Qwen3-Coder-Next, lab tech report):
- SWE-bench Verified: 70.6 [lab] src=https://arxiv.org/abs/2603.00729
- SWE-bench Pro: 44.3 [lab]
- SWE-bench Multilingual: 62.8 [lab]
- Terminal-Bench 2.0: 36.2 [lab]

Notes: A 3B-active model matching 480B-A35B Qwen3-Coder on SWE-bench Verified is the headline efficiency claim. Below Kimi K2.6 (Terminal-Bench 2.0 66.7) and Claude Opus 4.7 (69.4) on the most demanding agentic terminal task, but competitive on standard SWE-bench at a fraction of the deployment footprint.

---

### Qwen 3.6 (27B dense + 35B-A3B MoE)

- Release: 2026-04-16 (35B-A3B); 2026-04-22 (27B dense); Qwen3.6-Plus proprietary alongside
- Status: current open-weight refresh of the local-developer tier
- Sizes: Qwen3.6-27B dense, Qwen3.6-35B-A3B MoE (35B total / 3B active, 256 experts / 9 active per token)
- Context: long context
- Modality: text
- License: **Apache 2.0** for 27B and 35B-A3B; Qwen3.6-Plus is **proprietary** (API-only)
- Notable: Qwen's claim is that the 27B dense **beats the prior-gen Qwen3.5-397B-A17B flagship on coding** — SWE-bench Verified 77.2 vs 76.2, SWE-bench Pro 53.5 vs 50.9, Terminal-Bench 2.0 59.3 vs 52.5. Headline "27B beats 397B" story.
- Sources:
  - kind: announcement
    tag: lab
    url: https://qwen.ai/blog?id=qwen3.6-27b
    title: "Qwen3.6-27B: Flagship-Level Coding in a 27B Dense Model"
    date: 2026-04-22
  - kind: model-card
    tag: lab
    url: https://huggingface.co/Qwen/Qwen3.6-27B
    title: "Qwen3.6-27B model card"
    date: 2026-04-22
  - kind: coverage
    tag: 3p
    url: https://www.buildfastwithai.com/blogs/qwen3-6-27b-review-2026
    publisher: BuildFastWithAI
    title: "Qwen3.6-27B: 27B Model Beats 397B on Coding (2026)"
    date: 2026-04

Benchmarks (Qwen3.6-27B vs Qwen3.5-397B-A17B, lab claims):
- SWE-bench Verified: 77.2 vs 76.2 [lab]
- SWE-bench Pro: 53.5 vs 50.9 [lab]
- Terminal-Bench 2.0: 59.3 vs 52.5 [lab]

Notes:
- 27B beats 35B-A3B head-to-head on benchmarks, but 35B-A3B is ~3.5–4x faster at token generation per BuildFastWithAI's testing — classic dense-vs-sparse tradeoff.
- This is the latest open-weight Qwen drop verified for this report (April 22, 2026). A Qwen 4 has not shipped through May 2026.
- Qwen3.6-Plus is the proprietary companion (API-only via DashScope / OpenRouter).

---

## Lineage Summary Table

| Generation | Release | Open-weight sizes | Max context | License notes |
|---|---|---|---|---|
| Qwen 1 | Aug–Nov 2023 | 1.8B / 7B / 14B / 72B | 8K (32K via NTK) | Tongyi Qianwen License |
| Qwen 1.5 | Feb–Apr 2024 | 0.5B / 1.8B / 4B / 7B / 14B / 32B / 72B / 110B + MoE-A2.7B | 32K | Tongyi Qianwen (mostly) |
| Qwen 2 | Jun 2024 | 0.5B / 1.5B / 7B / 57B-A14B / 72B | 128K (7B/72B Instruct) | Apache 2.0 (≤57B); Tongyi Qianwen (72B) |
| Qwen 2-VL | Aug 2024 | 2B / 7B (+ 72B API) | dynamic | Apache 2.0 (≤7B); Tongyi Qianwen (72B) |
| Qwen 2.5 | Sep 2024 | 0.5B / 1.5B / 3B / 7B / 14B / 32B / 72B | 128K | Apache 2.0 except 3B (Research) and 72B (Qwen License) |
| Qwen 2.5-Coder | Nov 2024 | 0.5B / 1.5B / 3B / 7B / 14B / 32B | 128K | Apache 2.0 (≠3B Research) |
| Qwen 2.5-Math | Sep 2024 | 1.5B / 7B / 72B | std | per parent Qwen 2.5 |
| QwQ-32B-Preview | Nov 2024 | 32B | 32K | Apache 2.0 |
| Qwen 2.5-VL | Jan 2025 | 3B / 7B / 32B / 72B | dynamic | Apache 2.0 mid; Research 3B; Qwen License 72B |
| Qwen 2.5-Max | Jan 2025 | none (proprietary) | API | Proprietary |
| Qwen 2.5-Omni | Mar 2025 | 3B / 7B | std | Apache 2.0 (7B); Research (3B) |
| QwQ-32B | Mar 2025 | 32B | 32K | Apache 2.0 |
| Qwen 3 | Apr 2025 | 0.6B / 1.7B / 4B / 8B / 14B / 32B + 30B-A3B / 235B-A22B | 32K–256K | Apache 2.0 |
| Qwen 3-Coder | Jul 2025 | 480B-A35B + 30B-A3B | 256K–1M | Apache 2.0 |
| Qwen 3-Next | Sep 2025 | 80B-A3B (Instruct + Thinking) | 256K | Apache 2.0 |
| Qwen 3-VL | Sep 2025 | 2B / 4B / 8B / 32B + 30B-A3B / 235B-A22B | 256K | Apache 2.0 |
| Qwen 3-Omni | Sep 2025 | 30B-A3B | std omni | Apache 2.0 |
| Qwen 3-Max | Sep 2025 | none (proprietary, >1T params) | API | Proprietary |
| Qwen 3.5 | Feb–Mar 2026 | 0.8B / 2B / 4B / 9B / 27B / 35B-A3B / 122B-A10B / 397B-A17B | long (256K+) | Apache 2.0; Plus is proprietary |
| Qwen 3-Coder-Next | Feb 2026 | 80B-A3B | long | Apache 2.0 |
| Qwen 3.6 | Apr 2026 | 27B / 35B-A3B (+ Plus proprietary) | long | Apache 2.0; Plus proprietary |

---

## Cross-cutting notes

**License evolution:** Qwen 1 / 1.5 started under Tongyi Qianwen Community License (permissive but with a 100M-MAU clause). Apache 2.0 entered with smaller Qwen 2 sizes (Jun 2024). By Qwen 3 (Apr 2025), the full open-weight lineup including 235B was Apache 2.0. Countertrend: proprietary Max/Plus variants (Qwen2.5-Max, Qwen3-Max, Qwen3.5-Plus, Qwen3.6-Plus) are API-only, never weights-released. Two-track strategy: Apache-2.0 open-weight + closed Max/Plus frontier — mirroring DeepSeek's bifurcation.

**Naming:** Qwen interleaves four axes — generation (1 → 3.6), modality (text / VL / Coder / Math / Omni / Audio), size suffix (A22B = active 22B), and refresh-date stamp (2507, etc.). Qwen-Image / Qwen-Image-Edit (Aug 2025, 20B MMDiT) and Qwen3Guard (Sep 2025 safety guardrail) are out of scope for this LLM lineage.

**Pricing (May 2026, DashScope/OpenRouter):** qwen-turbo ~$0.05/M in; qwen-plus ~$0.40/$1.20; qwen-max / qwen3-max ~$0.78/$3.90 per M in/out; open-weight self-hosted free (compute only).

**Frontier-bench position (May 2026):**
- Reasoning: Qwen3-235B-A22B-Thinking-2507 and Qwen3.5-397B-A17B are top-tier open-source on AIME / GPQA / MATH; competitive with o3 / o4-mini and Claude Opus 4 in thinking mode.
- Agentic coding: Qwen3-Coder-480B-A35B (69.6 SWE-Verified) and Qwen3-Coder-Next 80B-A3B (70.6); Qwen3.6-27B at 77.2 SWE-Verified is the 2026 headline — dense 27B beating MoE 397B on coding.
- Proprietary: Qwen3-Max (1T+) hit LMArena rank 3 at release; still trails Claude Opus 4.7 / GPT-5.x on SWE-bench Pro and Terminal-Bench 2.0.
- No Qwen 4 through May 2026. Largest open-weight Qwen weights today: Qwen3.5-397B-A17B and Qwen3-235B-A22B MoE.
