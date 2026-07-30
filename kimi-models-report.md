# Kimi (Moonshot AI) Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema: typed
`Sources:` blocks (`announcement` / `model-card` / `pricing` / `deprecation` /
`coverage` / `replication`), and benchmark rows surface both `lab` and `3p`
numbers where they disagree by >3 pp.

**Methodology caveats.** Moonshot AI (Beijing, founded March 2023; Yang
Zhilin / Zhou Xinyu / Wu Yuxin) ships two product surfaces with different
licensing:

1. **Closed-weight Kimi Chat product** — the consumer/enterprise chatbot
   at `kimi.com` (originally `kimi.moonshot.cn`); the hosted API exposes
   it as the `moonshot-v1-{8k,32k,128k}` SKU family. Closed weights,
   commercial pricing on `platform.moonshot.ai` (recently redirected to
   `platform.kimi.ai`).
2. **Open-weight Kimi K-series + variants** — released through
   `huggingface.co/moonshotai` and the `MoonshotAI` GitHub org under a
   **Modified MIT License**. The MIT modification adds an attribution
   clause: products with MAU > 100M **or** monthly revenue > $20M must
   display "Powered by Kimi K-series" prominently in UI. This clause
   became prominent in the Mar 2026 Cursor Composer 2 non-disclosure
   episode (see K2.5 entry below).

The Kimi-series tech reports (K1.5, K2, K2 Thinking, K2.5, K2.6, Kimi
VL, Kimi Linear, Kimi Audio) are the canonical `lab` source — each on
arXiv with a paired HuggingFace model card. The Wikipedia pages for
**Moonshot AI** and **Kimi (chatbot)** are well-maintained third-party
timelines.

**Pricing convention.** Hosted API USD pricing pulled from
`platform.kimi.ai/docs/pricing/*` and the K2.6 / K2 / V1 sub-pages
on 2026-05-22; cached-input rate uses Moonshot's automatic context
caching feature (no opt-in required).

**Naming note — be careful with K2.x.** K2 (Jul 2025, 1T MoE,
text-only), K2-Instruct-0905 (Sep 2025, same architecture, 256K
context), K2 Thinking (Nov 2025, reasoning fork, INT4 native), K2.5
(Jan 2026, adds MoonViT vision encoder), and K2.6 (Apr 2026, mature
multimodal + 300-agent swarm) all share the same 1T / 32B-active /
384-expert MoE trunk. The version numbers reflect post-training and
adapter additions, not a new pretrain.

Convention: dates are **announcement / first availability**.

---

### Kimi Chat (initial release)

- Release: 2023-10-09 (closed beta); 2023-11-16 (public)
- Status: superseded by the `moonshot-v1` API SKUs and then by the
  K-series; legacy product surface
- Context: 200,000 Chinese characters (≈128K tokens) — claimed at
  launch as the world's longest production context window
- Modality: text (Chinese + English)
- License: closed-weight, consumer/enterprise product
- Price: free consumer tier on kimi.moonshot.cn at launch; no public
  API yet
- Notable: First Moonshot product; long-context novelty (200K Chinese
  characters) drove the early hype cycle in mainland China; Kimi
  rapidly became the most-visited AI chatbot in China during Q1 2024.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.kimi.com/
    title: "Kimi — Moonshot AI chatbot product"
    date: 2023-10
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Kimi_(chatbot)
    publisher: Wikipedia
    title: "Kimi (chatbot)"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Moonshot_AI
    publisher: Wikipedia
    title: "Moonshot AI"
    date: 2026-05

Notes: No published parameter count or arch details — Moonshot
positioned this as a product launch, not a model launch.

---

### Kimi Chat 2M (long-context upgrade)

- Release: 2024-03-18 (beta); 2024-07 (context-caching feature GA)
- Status: legacy (long-context feature subsumed into K-series)
- Context: 2 million Chinese characters (≈1.5M tokens) in beta
- Modality: text
- License: closed product
- Notable: 10x context extension over launch version; first commercial
  deployment of context-caching at this scale (entered public beta
  Jul 2024), which became the template for the auto-caching now used
  across the K-series API.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Kimi_(chatbot)
    publisher: Wikipedia
    title: "Kimi (chatbot) — March 2024 2M character beta"
    date: 2026-05

---

### Moonshot V1 (hosted API SKUs)

- Release: 2024-01-31 (`moonshot-v1-128k` on `platform.moonshot.cn`)
- Status: **active**, still listed on the pricing page as of May 2026
- Context: 8K / 32K / 128K variants (the SKU suffix is the context window)
- Modality: text (vision variants `moonshot-v1-*-vision-preview` added
  later, 2024)
- License: closed-weight; hosted API only
- Price (per Moonshot pricing page, May 2026):
  - `moonshot-v1-8k`: $0.20 input / $2.00 output per 1M tokens
  - `moonshot-v1-32k`: $1.00 input / $3.00 output per 1M tokens
  - `moonshot-v1-128k`: $2.00 input / $5.00 output per 1M tokens
  - Vision-preview variants priced identically to the text variants at
    each context tier.
- Notable: Same model quality across the three context tiers — only the
  context window differs. This is the API SKU layer over Kimi Chat
  (the consumer product); enterprises building on Moonshot historically
  went through `moonshot-v1-*`.
- Sources:
  - kind: pricing
    tag: lab
    url: https://platform.kimi.ai/docs/pricing/chat-v1
    title: "Moonshot V1 chat pricing"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://developer.puter.com/ai/moonshotai/moonshot-v1-128k/
    publisher: Puter
    title: "Moonshot v1 128K spec page"
    date: 2026-05

---

### Kimi k0-math

- Release: 2024-11-16
- Status: legacy research milestone (superseded by K1.5)
- Context: not publicly specified
- Modality: text (math-specialized)
- License: closed; accessible via Kimi Chat → "Kimi-Math" mode at
  kimi.moonshot.cn
- Notable: Moonshot's **first reasoning model**; chain-of-thought + RL
  fine-tuning targeting math. The first non-o1 reasoning model from a
  Chinese lab to claim parity with o1-mini, alongside DeepSeek-R1-Lite
  (released same week).
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.globaltimes.cn/page/202411/1323248.shtml
    title: "Chinese AI start-up unveils latest reasoning model — k0-math"
    date: 2024-11
  - kind: coverage
    tag: 3p
    url: https://recodechinaai.substack.com/p/openais-o1-faces-competition-meet
    publisher: Recode China AI
    title: "OpenAI's o1 Faces Competition: DeepSeek-R1-Lite, k0-math, Marco-o1"
    date: 2024-11

Benchmarks (lab, from Moonshot announcement):
- Gaokao math: outperformed o1-mini and o1-preview [lab] src=https://www.globaltimes.cn/page/202411/1323248.shtml date=2024-11
- OMNI-MATH: ~90% of o1-mini's score [lab] src=https://www.globaltimes.cn/page/202411/1323248.shtml date=2024-11
- AIME: ~83% of o1-mini's score [lab] src=https://www.globaltimes.cn/page/202411/1323248.shtml date=2024-11

Notes: Acknowledged limitation on geometry problems not expressible in
LaTeX, plus "overthinking" failure mode on trivial problems.

---

### Kimi K1.5

- Release: 2025-01-20
- Status: legacy reasoning model (superseded by K2 Thinking)
- Context: 128K tokens
- Modality: text + vision (early multimodal reasoning)
- License: closed (paper + benchmarks published, weights not released)
- Price: hosted via Kimi Chat product
- Notable: Moonshot's first **general-purpose** reasoning model (vs.
  k0-math's math-only focus). The K1.5 tech report introduced
  **MuonClip** — the optimizer used at trillion-parameter scale in K2
  six months later. Claimed parity with OpenAI o1 on long-CoT, +550%
  over Claude Sonnet 3.5 / GPT-4o on short-CoT.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-k1.5
    title: "Kimi k1.5: Scaling Reinforcement Learning with LLMs"
    date: 2025-01
  - kind: model-card
    tag: 3p
    url: https://llm-stats.com/models/kimi-k1.5
    publisher: llm-stats.com
    title: "Kimi-k1.5 specs page"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://www.testingcatalog.com/kimi-k1-5-by-moonshotai-achieves-sota-benchmarks-in-reasoning/
    publisher: Testing Catalog
    title: "Kimi k1.5 by MoonshotAI achieves SOTA benchmarks in reasoning"
    date: 2025-01

Benchmarks (lab from tech report):
- AIME: 77.5 [lab] src=https://github.com/MoonshotAI/Kimi-k1.5 date=2025-01
- MATH-500: 96.2 [lab] src=https://github.com/MoonshotAI/Kimi-k1.5 date=2025-01
- Codeforces: 94th percentile [lab] src=https://github.com/MoonshotAI/Kimi-k1.5 date=2025-01

Notes: Long-CoT mode claimed parity with o1 across math/code/vision.

---

### Kimi-VL-A3B (Instruct / Thinking / Thinking-2506)

- Release: 2025-04-10 (Instruct + Thinking); 2025-06-23 (Thinking-2506
  revision)
- Status: active (compact multimodal reference model)
- Context: 128K tokens
- Modality: text + vision (native-resolution images, up to 3.2M total
  pixels / 1792×1792 on the 2506 revision); video understanding
- License: Modified MIT
- Price: open-weights; third-party hosting on OpenRouter etc.
- Architecture: **MoE language decoder** (Moonlight-based), ~16B total
  parameters, ~3B active per token; native-resolution vision encoder
  **MoonViT**; two-layer MLP projector.
- Notable: Moonshot's first open-weight release. Compact (3B active)
  alternative to large frontier VLMs; sets up the MoonViT pipeline that
  is later folded into K2.5 and K2.6 as native multimodal.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-VL
    title: "Kimi-VL: Mixture-of-Experts Vision-Language Model"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-VL-A3B-Instruct
    title: "Kimi-VL-A3B-Instruct model card"
    date: 2025-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-VL-A3B-Thinking
    title: "Kimi-VL-A3B-Thinking model card"
    date: 2025-04

Benchmarks (lab from tech report):
- LongVideoBench: 64.5 [lab] src=https://github.com/MoonshotAI/Kimi-VL date=2025-04
- MMLongBench-Doc: 35.1 [lab] src=https://github.com/MoonshotAI/Kimi-VL date=2025-04

---

### Kimi-Audio-7B (Instruct + Base)

- Release: 2025-04-25 (Instruct); 2025-04-27 (Base pretrained)
- Status: active research release
- Context: audio + text inputs
- Modality: audio understanding, generation, conversation (ASR, AQA,
  AAC, SER, sound event classification, end-to-end speech dialogue)
- License: Modified MIT (open weights)
- Notable: First Moonshot audio foundation model; unified single-model
  framework rather than ASR+TTS pipeline. Shipped with the
  **Kimi-Audio-Evalkit** evaluation toolkit on the same day.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-Audio
    title: "Kimi-Audio: open-source audio foundation model"
    date: 2025-04

---

### Kimi-Dev-72B

- Release: 2025-06 (announced via Moonshot socials)
- Status: active (open-weight coding specialist)
- Context: dense 72B model (Qwen2.5-72B base) — context inherited from
  base
- Modality: text / code
- License: Modified MIT (with Qwen2.5 base lineage caveat)
- Notable: Dense (not MoE) coding specialist; reached **SWE-bench
  Verified 60.4%**, SOTA among open-weights at release. Built on
  Qwen2.5-72B with ~150B-token mid-training corpus of GitHub issues +
  PR commits, then RL on real-repo patching in Docker sandboxes (reward
  only when full test suite passes).
- Sources:
  - kind: announcement
    tag: lab
    url: https://moonshotai.github.io/Kimi-Dev/
    title: "Kimi-Dev-72B project page"
    date: 2025-06
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-Dev-72B
    title: "Kimi-Dev-72B HF model card"
    date: 2025-06

Benchmarks (lab):
- SWE-bench Verified: 60.4 [lab] src=https://moonshotai.github.io/Kimi-Dev/ date=2025-06

---

### Kimi-Researcher (autonomous agent)

- Release: 2025-06-24
- Status: active product feature inside Kimi Chat / App
- Context: end-to-end RL agent
- Modality: text + tool use (web search, browsing)
- License: closed product feature; not open-weight
- Notable: Moonshot's deep-research agent; end-to-end RL training (not
  workflow-orchestrated). Performs avg ~23 reasoning steps and explores
  200+ URLs per task. Reached **69% Pass@1 on xbench-DeepSearch**,
  outperforming o3-with-search at the time. Historically important as a
  public demonstration that agentic behavior can emerge from end-to-end
  RL rather than hand-written workflows.
- Sources:
  - kind: announcement
    tag: lab
    url: https://moonshotai.github.io/Kimi-Researcher/
    title: "Kimi-Researcher: End-to-End RL Training for Emerging Agentic Capabilities"
    date: 2025-06
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2025/06/24/moonshot-ai-unveils-kimi-researcher-an-reinforcement-learning-rl-trained-agent-for-complex-reasoning-and-web-scale-search/
    publisher: MarkTechPost
    title: "Moonshot AI Unveils Kimi-Researcher"
    date: 2025-06

---

### Kimi K2 (Base + Instruct)

- Release: 2025-07-11 (paper + weights)
- Status: superseded by K2-Instruct-0905, K2 Thinking, K2.5, K2.6
- Context: 128K tokens
- Modality: text (no vision)
- License: Modified MIT
- Architecture: **1T total / 32B active** Mixture-of-Experts; **384
  experts**, 8 selected per token + 1 shared; 61 layers (incl. 1 dense);
  64 attention heads; MLA attention; SwiGLU; 160K vocab; trained on
  **15.5T tokens** with the MuonClip optimizer (zero training
  instability claimed). Stored as block-FP8 on HuggingFace.
- Variants: `Kimi-K2-Base` (foundation), `Kimi-K2-Instruct` (chat /
  agentic).
- Price (Kimi hosted API, K2-0905-preview SKU, used as legacy K2 price
  point):
  - Input (cache miss): $0.60 / 1M
  - Input (cache hit): $0.15 / 1M
  - Output: $2.50 / 1M
- Notable: Moonshot's first frontier-tier open-weight release. Most
  prominent third-party deployment is **Cursor's Composer 2 / 2.5**,
  built on K2.5 (the multimodal successor — see below).
- Sources:
  - kind: announcement
    tag: lab
    url: https://moonshotai.github.io/Kimi-K2/
    title: "Kimi K2: Open Agentic Intelligence"
    date: 2025-07
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-K2-Instruct
    title: "Kimi-K2-Instruct HF model card"
    date: 2025-07
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-K2
    title: "MoonshotAI/Kimi-K2 GitHub"
    date: 2025-07
  - kind: pricing
    tag: lab
    url: https://platform.kimi.ai/docs/pricing/chat-k2
    title: "Kimi K2 hosted API pricing"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://www.hpcwire.com/aiwire/2025/07/14/chinas-moonshot-ai-releases-trillion-parameter-model-kimi-k2/
    publisher: AIwire
    title: "China's Moonshot AI Releases Trillion Parameter Model Kimi K2"
    date: 2025-07
  - kind: coverage
    tag: 3p
    url: https://huggingface.co/blog/fdaudens/moonshot-ai-kimi-k2-explained
    publisher: HuggingFace blog
    title: "5 Things You Need to Know About Kimi K2"
    date: 2025-07

Benchmarks (lab from Instruct model card):
- SWE-bench Verified (agentic, single attempt): 65.8 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- SWE-bench Verified (multi-attempt): 71.6 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- SWE-bench Multilingual: 47.3 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- LiveCodeBench v6: 53.7 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- MultiPL-E: 85.7 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- AIME 2024: 69.6 (avg@64) [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- AIME 2025: 49.5 (avg@64) [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- MATH-500: 97.4 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- GPQA-Diamond: 75.1 (avg@8) [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- MMLU: 89.5 (EM) [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- MMLU-Pro: 81.1 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07
- Tau2 Retail (tool use): 70.6 (avg@4) [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Instruct date=2025-07

---

### Kimi K2-Instruct-0905

- Release: 2025-09-09
- Status: legacy (current K2 hosted SKU is `kimi-k2-0905-preview`,
  still active; superseded by K2.5/K2.6 on quality)
- Context: **256K tokens** (doubled from K2's 128K)
- Modality: text
- License: Modified MIT
- Notable: Refresh of K2-Instruct with extended context and improved
  agentic-coding post-training. Same underlying 1T MoE trunk.
- Sources:
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-K2-Instruct-0905
    title: "Kimi-K2-Instruct-0905 HF model card"
    date: 2025-09
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Moonshot_AI
    publisher: Wikipedia
    title: "Moonshot AI — Kimi K2-Instruct-0905 release"
    date: 2026-05

---

### Kimi Linear-48B-A3B

- Release: 2025-10 (tech report on arXiv 2510.26692)
- Status: active research release
- Context: up to 1M tokens (claimed efficiency at long context)
- Modality: text
- License: Modified MIT
- Architecture: 48B total / 3B active MoE; **hybrid attention** with
  3:1 ratio of **KDA (Kimi Delta Attention)** to global MLA blocks. KDA
  is a refined Gated DeltaNet variant — finite-state RNN memory with an
  efficient gating mechanism. Claims 75% KV-cache reduction and up to
  6× decoding throughput at 1M context.
- Notable: Architecture research vehicle, not the production trunk. The
  open-sourced **FlashKDA** CUTLASS kernel makes it a drop-in
  replacement for full attention in Moonshot's own stack and
  third-party stacks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://arxiv.org/pdf/2510.26692
    title: "Kimi Linear: An Expressive, Efficient Attention Architecture"
    date: 2025-10
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct
    title: "Kimi-Linear-48B-A3B-Instruct HF model card"
    date: 2025-10
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-Linear
    title: "MoonshotAI/Kimi-Linear"
    date: 2025-10

---

### Kimi K2 Thinking

- Release: 2025-11-06
- Status: active (open-weight reasoning model)
- Context: 256K tokens
- Modality: text
- License: Modified MIT
- Architecture: same 1T / 32B-active 384-expert MoE trunk as K2;
  **native INT4** via quantization-aware training (QAT). On-disk
  ~594GB (vs. K2-Instruct's ~1TB), ~2× generation speedup. Stable
  long-horizon agency: 200–300 consecutive tool invocations.
- Training cost: ~$4.6M, per Moonshot disclosure
- Notable: Open-weight reasoning peer to GPT-5 / Claude Sonnet 4.5;
  outperformed both on HLE and BrowseComp at release. The interleaved
  thinking + function-call schedule is the template later inherited by
  K2.6's thinking mode.
- Sources:
  - kind: announcement
    tag: lab
    url: https://moonshotai.github.io/Kimi-K2-Thinking/
    title: "Kimi K2 Thinking project page"
    date: 2025-11
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-K2-Thinking
    title: "Kimi-K2-Thinking HF model card"
    date: 2025-11
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/moonshots-kimi-k2-thinking-emerges-as-leading-open-source-ai-outperforming
    publisher: VentureBeat
    title: "Moonshot's Kimi K2 Thinking emerges as leading open source AI"
    date: 2025-11
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2025/Nov/6/kimi-k2-thinking/
    publisher: Simon Willison's Weblog
    title: "Kimi K2 Thinking"
    date: 2025-11
  - kind: coverage
    tag: 3p
    url: https://www.deeplearning.ai/the-batch/kimi-k2-thinking-outperforms-proprietary-models-with-new-techniques-for-agentic-tool-use
    publisher: DeepLearning.AI The Batch
    title: "Kimi K2 Thinking Outperforms Proprietary Models"
    date: 2025-11

Benchmarks (lab, INT4 precision per model card):
- SWE-bench Verified (w/ tools): 71.3 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- Humanity's Last Exam (w/ tools): 44.9 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- Humanity's Last Exam (no tools): 23.9 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- BrowseComp (w/ tools): 60.2 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- BrowseComp-ZH (w/ tools): 62.3 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- AIME 2025 (w/ python): 99.1 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- AIME 2025 (no tools): 94.5 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11
- GPQA-Diamond (no tools): 84.5 [lab] src=https://huggingface.co/moonshotai/Kimi-K2-Thinking date=2025-11

Notes: Moonshot reports HLE 44.9 — ahead of GPT-5's 41.7 at release;
this is the most-cited K2 Thinking benchmark.

---

### Kimi K2.5

- Release: 2026-01-27
- Status: active (open-weights), supplanted on Moonshot's hosted API
  by K2.6 for new builds
- Context: 256K tokens
- Modality: **native multimodal** — text + images + video via MoonViT
  (400M-param vision encoder)
- License: Modified MIT (the modification includes the $20M monthly
  revenue / 100M MAU "Powered by Kimi K2.5" attribution clause)
- Architecture: same 1T / 32B-active 384-expert MoE trunk as K2,
  continual pretrain on ~15T mixed visual + text tokens; agent swarm
  support up to **100 concurrent sub-agents**.
- Notable: **The base model for Cursor's Composer 2** (Mar 2026) and
  **Composer 2.5** (May 2026). The Composer 2 launch initially
  described the model as "self-developed" and "first continued
  pretraining run" without disclosing Kimi K2.5 as the base, prompting
  the **Cursor non-disclosure scandal** (Mar 2026). Cursor's
  internal SKU identifier
  `accounts/anysphere/models/kimi-k2p5-rl-0317-s515-fast` leaked via
  Cursor's OpenAI-compatible base URL, after which Aman Sanger (Cursor
  co-founder) and Lee Robinson (VP DevEx) publicly acknowledged the
  Kimi K2.5 base. Sanger added that K2.5 had "the best perplexity
  scores" among bases evaluated. The episode also raised the
  attribution-clause licensing question, since Anysphere's reported
  monthly revenue (~$167M) is ~8× the $20M attribution-clause
  threshold.
- Sources:
  - kind: announcement
    tag: lab
    url: https://github.com/MoonshotAI/Kimi-K2.5
    title: "Kimi K2.5: Moonshot's most powerful model"
    date: 2026-01
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-K2.5
    title: "Kimi K2.5 HF model card"
    date: 2026-01
  - kind: model-card
    tag: 3p
    url: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-moonshot-ai-kimi-k2-5.html
    publisher: AWS Bedrock
    title: "Kimi K2.5 on Bedrock"
    date: 2026-02
  - kind: coverage
    tag: 3p
    url: https://www.infoq.com/news/2026/02/kimi-k25-swarm/
    publisher: InfoQ
    title: "Moonshot AI Releases Open-Weight Kimi K2.5 Model with Vision and Agent Swarm Capabilities"
    date: 2026-02
  - kind: coverage
    tag: 3p
    url: https://cursor.com/resources/Composer2.pdf
    publisher: Cursor Research
    title: "Composer 2 Technical Report (K2.5 base disclosure)"
    date: 2026-03
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/technology/cursors-composer-2-was-secretly-built-on-a-chinese-ai-model-and-it-exposes-a
    publisher: VentureBeat
    title: "Cursor's Composer 2 was secretly built on a Chinese AI model"
    date: 2026-03

Benchmarks (lab from K2.5 model card):
- SWE-bench Verified: 76.8 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- SWE-bench Multilingual: 73.0 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- LiveCodeBench v6: 85.0 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- MMMU-Pro: 78.5 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- MMVU: 80.4 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- VideoMME: 87.4 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01
- OCRBench: 92.3 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.5 date=2026-01

---

### Kimi K2.6

- Release: 2026-04-20
- Status: **active flagship** (open-weight + hosted)
- Context: 256K tokens across all variants
- Modality: text + image + video (native multimodal via MoonViT)
- License: Modified MIT (same attribution-clause structure as K2.5)
- Architecture: same 1T / 32B-active 384-expert MoE trunk; 61 layers;
  64 attention heads; MLA; SwiGLU; 160K vocab; MoonViT 400M vision
  encoder. **Native INT4** quantization (inherits the K2 Thinking QAT
  pipeline). Agent Swarm scales to **300 concurrent sub-agents** and
  **4,000 coordinated steps** (up from K2.5's 100 / 1,500). Four
  product modes: instant chat → thinking → agent → swarm.
- Price (Kimi hosted API):
  - Input (cache miss): $0.95 / 1M
  - Input (cache hit): $0.16 / 1M
  - Output: $4.00 / 1M
  - Tier 0: 1.5M tokens/day cap; Tier 1+: unlimited daily
  - Third-party providers (Parasail, DeepInfra FP4): as low as $0.75
    input / $3.50 output per 1M
- Notable: Reaches **80.2% on SWE-bench Verified**, putting K2.6 on
  the SWE-bench frontier band alongside Opus 4.7 (87.6%) and Sonnet 4.6
  (79.6%) — see CLAUDE.md context. First Moonshot release where the
  open-weight artifact matches the hosted-API SKU at parity (no
  silent in-house improvements held back from the open release).
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.kimi.com/blog/kimi-k2-6.html
    title: "Kimi K2.6 launch blog"
    date: 2026-04
  - kind: model-card
    tag: lab
    url: https://huggingface.co/moonshotai/Kimi-K2.6
    title: "Kimi K2.6 HF model card"
    date: 2026-04
  - kind: pricing
    tag: lab
    url: https://platform.kimi.ai/docs/pricing/chat-k26
    title: "Kimi K2.6 hosted API pricing"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2026/04/20/moonshot-ai-releases-kimi-k2-6-with-long-horizon-coding-agent-swarm-scaling-to-300-sub-agents-and-4000-coordinated-steps/
    publisher: MarkTechPost
    title: "Moonshot AI Releases Kimi K2.6"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://artificialanalysis.ai/models/kimi-k2-6
    publisher: Artificial Analysis
    title: "Kimi K2.6 — Intelligence, Performance & Price Analysis"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://blog.kilo.ai/p/kimi-k26-has-arrived-an-open-weight
    publisher: Kilo Code blog
    title: "Kimi K2.6 Has Arrived: An Open-Weight Powerhouse for Agentic Work"
    date: 2026-04
  - kind: replication
    tag: 3p
    url: https://llm-stats.com/models/kimi-k2.6
    publisher: llm-stats.com
    title: "Kimi K2.6 benchmarks / pricing"
    date: 2026-05

Benchmarks (lab from K2.6 HF model card):

**Coding**
- SWE-bench Verified: 80.2 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- SWE-bench Pro: 58.6 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- SWE-bench Multilingual: 76.7 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- LiveCodeBench v6: 89.6 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- Terminal-Bench 2.0: 66.7 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04

**Reasoning / Knowledge**
- AIME 2026: 96.4 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- HMMT 2026 (Feb): 92.7 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- GPQA-Diamond: 90.5 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- IMO-AnswerBench: 86.0 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04

**Vision**
- MMMU-Pro: 79.4 (80.1 w/ Python) [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- MathVision: 87.4 (93.2 w/ Python) [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- CharXiv (RQ): 80.4 (86.7 w/ Python) [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04

**Agentic**
- HLE-Full (w/ tools): 54.0 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- BrowseComp: 83.2 (86.3 w/ Agent Swarm) [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- DeepSearchQA F1: 92.5 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04
- OSWorld-Verified: 73.1 [lab] src=https://huggingface.co/moonshotai/Kimi-K2.6 date=2026-04

Notes: SWE-bench Verified 80.2% reconciles with CLAUDE.md's cite. The
$0.95 / $4.00 hosted pricing reconciles with CLAUDE.md's pay-per-token
estimate column.

---

### Kimi K3 (status: unshipped)

- Status: **rumored, not shipped as of 2026-05-22**
- Coverage: r/LocalLLaMA community discussion speculates K3 in the
  3–4T total-parameter range; Moonshot has not confirmed.
- Why this matters: K2.6's strong showing on SWE-bench Verified
  (80.2%) and the architectural saturation of the 1T-trunk K2.x line
  suggest K3 would need a new pretrain, not just K2.x post-training
  iteration. No tech report, no model card, no hosted SKU as of the
  cutoff.
- Sources: none authoritative; flagged for tracking.

---

## Cross-references and lineage map

```
Kimi Chat (Oct 2023, closed)
    └─→ moonshot-v1-{8k,32k,128k} API SKUs (Jan 2024, closed, still active)
    └─→ Kimi Chat 2M (Mar 2024, closed, context-cache feature → K-series)

Kimi k0-math (Nov 2024, closed)
    └─→ Kimi K1.5 (Jan 2025, closed; introduced MuonClip)

Kimi-VL-A3B (Apr 2025, MIT) ───┐
Kimi-Audio-7B (Apr 2025, MIT)  │
Kimi-Dev-72B (Jun 2025, MIT)   │  ← open-weight specialists
Kimi-Researcher (Jun 2025, closed product feature)
                               │
Kimi K2 (Jul 2025, MIT, 1T MoE, MuonClip-trained)
    ├─→ K2-Instruct-0905 (Sep 2025, 256K context refresh)
    ├─→ Kimi Linear-48B-A3B (Oct 2025, attention research vehicle)
    ├─→ K2 Thinking (Nov 2025, INT4 reasoning fork) ─┐
    ├─→ K2.5 (Jan 2026, multimodal via MoonViT) ─────┤
    │       └─→ Cursor Composer 2 / 2.5 (Mar/May 2026, undisclosed at launch)
    └─→ K2.6 (Apr 2026, mature multimodal + 300-agent swarm) ←─── inherits QAT from K2 Thinking
                                                                  inherits MoonViT from K2.5
```

## Key takeaways for the comparison page

1. **The K2.x family is one model trunk, four post-training surfaces.**
   K2, K2-0905, K2-Thinking, K2.5, and K2.6 all share the 1T / 32B-active
   / 384-expert MoE trunk. Differences live in context length (128K →
   256K), modality (text → +vision via MoonViT), reasoning post-training
   (Thinking, K2.6 thinking-mode), and agent-swarm scaling (none → 100
   → 300).
2. **Native INT4 is K2 Thinking → K2.6 inheritance.** The QAT pipeline
   that made K2 Thinking ~2× faster and ~40% smaller on disk is now the
   default for K2.6.
3. **Cursor Composer 2 / 2.5 = K2.5 + continued pretrain + RL.** This is
   the most prominent third-party deployment of any Kimi model. Cursor's
   Mar 2026 non-disclosure raised the K2.5 attribution-clause licensing
   question (Anysphere revenue ~8× the $20M threshold).
4. **K2.6 sits in the frontier band on SWE-bench Verified** (80.2% vs.
   Opus 4.7's 87.6%, Sonnet 4.6's 79.6%). On pay-per-token
   ($0.95 / $4.00), it prices like a Sonnet-mini.
5. **K3 has not shipped.** Rumored in community discussion but no
   Moonshot disclosure as of May 2026.
