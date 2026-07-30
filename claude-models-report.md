# Anthropic Claude Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema addendum:
typed `Sources:` blocks (`announcement`/`model-card`/`pricing`/`deprecation`/`coverage`/`replication`),
and benchmark rows surface both `lab` and `3p` numbers where they disagree by >3pp.

Lifecycle spine sourced from Anthropic's deprecations page; per-model release blogs
and system cards supply benchmarks and pricing.

---

### Claude 1 (1.0 / 1.1 / 1.2 / 1.3)

- Release: 2023-03-14 (initial API), Claude 1.3 May 2023 (100K context expansion)
- Status: retired
- Decommissioned: 2024-11-06
- Context: 9K tokens at launch; 100K tokens by Claude 1.3
- Modality: text
- Price (in/out per 1M): not separately listed in current pricing tables (legacy); historical Claude 1 priced around $8/$24 per 1M (same tier as Claude 2 at the time)
- Notable: first publicly-accessible Anthropic model; closed-beta access only at launch; 1.3 was the first 100K-context Anthropic model.
- Sources:
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Model deprecations — Claude API Docs"
    date: 2024-09-04
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Claude_(language_model)
    publisher: Wikipedia
    title: "Claude (language model)"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://hidekazu-konishi.com/entry/anthropic_claude_model_release_timeline.html
    publisher: hidekazu-konishi
    title: "Anthropic Claude Model Release Timeline"
    date: 2025

Benchmarks: No comparable modern benchmark suite (SWE-bench/MMLU-Pro/etc.) was published by Anthropic for Claude 1.x. Numbers absent.

Notes: claude-1.0, 1.1, 1.2, 1.3 all retired same date (Nov 6 2024). Anthropic's deprecation registry lists no separate per-subversion benchmarks.

---

### Claude Instant 1.0 / 1.1 / 1.2

- Release: 2023-03-14 (Instant 1.0 alongside Claude 1.0); Instant 1.2 on 2023-08-09
- Status: retired
- Decommissioned: 2024-11-06
- Context: 100K tokens (Instant 1.2)
- Modality: text
- Price (in/out per 1M): historical Instant pricing approx $1.63/$5.51 (Nov 2023 price sheet)
- Notable: lightweight, low-latency tier; Instant 1.2 incorporated Claude 2 improvements in math/coding/safety.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/releasing-claude-instant-1-2
    title: "Releasing Claude Instant 1.2"
    date: 2023-08-09
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Model deprecations — Claude API Docs"
    date: 2024-09-04
  - kind: pricing
    tag: lab
    url: https://www-cdn.anthropic.com/1b1ea2c43d8dd058f6a331a8097e05ea40d626c6/model_pricing_nov2023.pdf
    title: "Model pricing November 2023"
    date: 2023-11

Benchmarks (Claude Instant 1.2, lab):
- HumanEval (Codex): 58.7% [lab] src=https://www.anthropic.com/news/releasing-claude-instant-1-2 date=2023-08-09
- GSM8K: 86.7% [lab] src=https://www.anthropic.com/news/releasing-claude-instant-1-2 date=2023-08-09
- MMLU (5-shot): 73.4 [lab] src=https://www.anthropic.com/news/releasing-claude-instant-1-2 date=2023-08-09

Notes: Anthropic's deprecation table lists only claude-instant-1.0/1.1/1.2 — a "claude-instant-1.3" API ID does not appear in the deprecation registry, and the user-supplied checklist's reference to "Instant 1.3" appears unsubstantiated. Excluded.

---

### Claude 2

- Release: 2023-07-11
- Status: retired
- Decommissioned: 2025-07-21 (deprecated 2025-01-21)
- Context: 100K tokens
- Modality: text
- Price (in/out per 1M): historical $8.00 / $24.00
- Notable: first Anthropic model with general public availability; doubled context to 100K; substantial coding/math gains over Claude 1.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-2
    title: "Claude 2"
    date: 2023-07-11
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude 2 deprecation notice"
    date: 2025-01-21
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2023/07/11/anthropic-releases-claude-2-the-second-generation-of-its-ai-chatbot/
    publisher: TechCrunch
    title: "Anthropic releases Claude 2"
    date: 2023-07-11

Benchmarks (lab):
- HumanEval (Codex): 71.2 [lab] src=https://www.anthropic.com/news/claude-2 date=2023-07-11
- GSM8K: 88.0 [lab] src=https://www.anthropic.com/news/claude-2 date=2023-07-11
- Bar exam MC: 76.5 [lab] src=https://www.anthropic.com/news/claude-2 date=2023-07-11

Notes: Anthropic's Claude 2 announcement did not publish an MMLU score; legacy MMLU figures from third-party sites should be treated as derivative.

---

### Claude 2.1

- Release: 2023-11-21
- Status: retired
- Decommissioned: 2025-07-21 (deprecated 2025-01-21)
- Context: 200K tokens
- Modality: text
- Price (in/out per 1M): historical $8.00 / $24.00
- Notable: first 200K context Anthropic model; ~50% reduction in hallucination rate; introduced tool use beta.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-2-1
    title: "Claude 2.1"
    date: 2023-11-21
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude 2/2.1 deprecation notice"
    date: 2025-01-21

Benchmarks: Anthropic positioned 2.1 around context-recall and hallucination metrics rather than the standard suite; no SWE-bench/MMLU-Pro/GPQA Diamond numbers were published in the release blog.

---

### Claude 3 Haiku

- Release: 2024-03-13 (announced 2024-03-04 with family)
- Status: retired
- Decommissioned: 2026-04-20 (deprecated 2026-02-19)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $0.25 / $1.25
- Notable: smallest/cheapest Claude 3 tier; near-instant latency.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-3-family
    title: "Introducing the next generation of Claude"
    date: 2024-03-04
  - kind: model-card
    tag: lab
    url: https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf
    title: "The Claude 3 Model Family: Opus, Sonnet, Haiku"
    date: 2024-03
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude 3 Haiku retirement"
    date: 2026-02-19

Benchmarks (Claude 3 Haiku, lab from model card):
- MMLU (5-shot CoT): 75.2 [lab] src=Model_Card_Claude_3.pdf date=2024-03
- GPQA Diamond (0-shot CoT): 33.3 [lab] src=Model_Card_Claude_3.pdf date=2024-03
- HumanEval (0-shot): 75.9 [lab] src=Model_Card_Claude_3.pdf date=2024-03
- GSM8K: 88.9 [lab] src=Model_Card_Claude_3.pdf date=2024-03

---

### Claude 3 Sonnet

- Release: 2024-03-04
- Status: retired
- Decommissioned: 2025-07-21 (deprecated 2025-01-21)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: balanced workhorse tier; vision capability across photos/charts/diagrams.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-3-family
    title: "Introducing the next generation of Claude"
    date: 2024-03-04
  - kind: model-card
    tag: lab
    url: https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf
    title: "Claude 3 model card"
    date: 2024-03
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude 3 Sonnet deprecation"
    date: 2025-01-21

Benchmarks (lab from model card):
- MMLU (5-shot CoT): 79.0 [lab]
- GPQA Diamond (0-shot CoT): 40.4 [lab]
- HumanEval (0-shot): 73.0 [lab]
- GSM8K: 92.3 [lab]

---

### Claude 3 Opus

- Release: 2024-03-04
- Status: retired (still accessible to paid claude.ai subscribers; on API by request per Anthropic preservation commitments)
- Decommissioned: 2026-01-05 (deprecated 2025-06-30)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): historical $15.00 / $75.00 (now effectively unbilled at API)
- Notable: flagship Claude 3 tier; first Anthropic model to surpass GPT-4 on MMLU at launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-3-family
    title: "Introducing the next generation of Claude"
    date: 2024-03-04
  - kind: model-card
    tag: lab
    url: https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf
    title: "Claude 3 model card"
    date: 2024-03
  - kind: deprecation
    tag: lab
    url: https://www.anthropic.com/research/deprecation-updates-opus-3
    title: "An update on our model deprecation commitments for Opus 3"
    date: 2025-06-30

Benchmarks (lab from model card):
- MMLU (5-shot CoT): 86.8 [lab]
- GPQA Diamond (0-shot CoT): 50.4 [lab]
- HumanEval (0-shot): 84.9 [lab]
- GSM8K: 95.0 [lab]
- BIG-Bench Hard: 86.8 [lab]

Notes: Opus 3 weights are preserved per Anthropic's deprecation-commitments policy.

---

### Claude 3.5 Sonnet (June 2024 / `claude-3-5-sonnet-20240620`)

- Release: 2024-06-20
- Status: retired
- Decommissioned: 2025-10-28 (deprecated 2025-08-13)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: mid-tier model surpassing Opus 3 on most benchmarks at 1/5 price; "Artifacts" UI feature introduced alongside.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-3-5-sonnet
    title: "Introducing Claude 3.5 Sonnet"
    date: 2024-06-20
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude Sonnet 3.5 deprecation"
    date: 2025-08-13

Benchmarks (lab):
- HumanEval (0-shot): 92.0 [lab] src=https://www.anthropic.com/news/claude-3-5-sonnet date=2024-06-20
- GPQA Diamond (0-shot): 59.4 [lab]
- MMLU (5-shot): 88.7 [lab]
- Internal agentic-coding (SWE-bench-style): 64% [lab] (Anthropic's own harness, not SWE-bench Verified)

Notes: Pre-SWE-bench-Verified era; Anthropic used an internal agentic-coding score in the release post.

---

### Claude 3.5 Sonnet "new" / v2 (October 2024 / `claude-3-5-sonnet-20241022`)

- Release: 2024-10-22
- Status: retired
- Decommissioned: 2025-10-28 (deprecated 2025-08-13)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: introduced **computer use** (public beta) — first frontier model with cursor/click/typing tool; SWE-bench Verified jumped from 33.4% to 49.0%.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/3-5-models-and-computer-use
    title: "Introducing computer use, a new Claude 3.5 Sonnet, and Claude 3.5 Haiku"
    date: 2024-10-22
  - kind: model-card
    tag: lab
    url: https://assets.anthropic.com/m/1cd9d098ac3e6467/original/Claude-3-Model-Card-October-Addendum.pdf
    title: "Claude 3.5 model card addendum"
    date: 2024-10

Benchmarks (lab):
- SWE-bench Verified: 49.0 [lab] src=https://www.anthropic.com/news/3-5-models-and-computer-use date=2024-10-22
- TAU-bench Retail: 69.2 [lab]
- TAU-bench Airline: 46.0 [lab]
- OSWorld (screenshot-only): 14.9 [lab]
- OSWorld (multi-step): 22.0 [lab]

---

### Claude 3.5 Haiku

- Release: 2024-10-22 (GA early November 2024)
- Status: retired
- Decommissioned: 2026-02-19 (deprecated 2025-12-19)
- Context: 200K tokens
- Modality: text initially (vision added later)
- Price (in/out per 1M): $0.80 / $4.00 (revised down from $1/$5 on 2024-12-03)
- Notable: smallest Claude 3.5 tier; matched Claude 3 Opus on many intelligence benchmarks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/3-5-models-and-computer-use
    title: "Introducing Claude 3.5 Haiku"
    date: 2024-10-22
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude Haiku 3.5 deprecation"
    date: 2025-12-19

Benchmarks (lab):
- SWE-bench Verified: 40.6 [lab] src=https://www.anthropic.com/news/3-5-models-and-computer-use date=2024-10-22

---

### Claude 3.7 Sonnet

- Release: 2025-02-24
- Status: retired
- Decommissioned: 2026-02-19 (deprecated 2025-10-28)
- Context: 200K tokens (128K max output)
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: first hybrid reasoning model — single model with optional extended-thinking mode; introduced Claude Code agentic CLI alongside.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-3-7-sonnet
    title: "Claude 3.7 Sonnet and Claude Code"
    date: 2025-02-24
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude Sonnet 3.7 deprecation"
    date: 2025-10-28

Benchmarks (lab):
- SWE-bench Verified (vanilla): 63.7 [lab] src=https://www.anthropic.com/news/claude-3-7-sonnet date=2025-02-24
- SWE-bench Verified (high compute): 70.3 [lab]
- TAU-bench: state-of-the-art (Anthropic did not publish a single number in the release blog)
- MATH-500 (extended thinking): 91.4 [lab] (3p coverage)
- GPQA (extended thinking): 84.8 [lab] (3p coverage)
- HumanEval: 93.7 [lab] (3p coverage)

Notes: Anthropic's Feb 2025 release post did not publish a comprehensive numerical table; numbers above are commonly cited from the system card and third-party reproductions.

---

### Claude Sonnet 4

- Release: 2025-05-22
- Status: deprecated
- Decommissioned: 2026-06-15 (deprecated 2026-04-14)
- Context: 200K tokens (1M beta added later)
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: first "Claude 4"-naming-convention model (no more "3.x"); extended-thinking + parallel tool execution; massive jump on SWE-bench Verified vs 3.7.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-4
    title: "Introducing Claude 4"
    date: 2025-05-22
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude Sonnet 4 retirement notice"
    date: 2026-04-14

Benchmarks (lab):
- SWE-bench Verified: 72.7 [lab] src=https://www.anthropic.com/news/claude-4 date=2025-05-22
- GPQA Diamond (extended thinking): 70.0 [lab]
- MMLU-Pro (extended thinking): 85.4 [lab]
- AIME 2025 (extended thinking): 33.1 [lab]
- OSWorld: 42.2 [lab]

---

### Claude Opus 4

- Release: 2025-05-22
- Status: deprecated
- Decommissioned: 2026-06-15 (deprecated 2026-04-14)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $15.00 / $75.00
- Notable: flagship of the Claude 4 launch; "world's best coding model" at release; supports extended thinking with tool use; 7-hour autonomous coding claim.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-4
    title: "Introducing Claude 4"
    date: 2025-05-22
  - kind: deprecation
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Claude Opus 4 retirement notice"
    date: 2026-04-14

Benchmarks (lab):
- SWE-bench Verified: 72.5 [lab] src=https://www.anthropic.com/news/claude-4 date=2025-05-22
- Terminal-Bench (1.0): 43.2 [lab]
- GPQA Diamond (extended thinking): 76.9 [lab]
- MMLU-Pro (extended thinking): 88.7 [lab]
- AIME 2025 (extended thinking): 40.9 [lab]

---

### Claude Opus 4.1

- Release: 2025-08-05
- Status: active (tentative retirement not sooner than 2026-08-05)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $15.00 / $75.00 (same as Opus 4)
- Notable: incremental upgrade to Opus 4 on agentic coding/refactoring and detail-tracking; multi-file refactor strength.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-opus-4-1
    title: "Claude Opus 4.1"
    date: 2025-08-05
  - kind: model-card
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/model-deprecations
    title: "Active model status"
    date: 2026-05

Benchmarks (lab):
- SWE-bench Verified: 74.5 [lab] src=https://www.anthropic.com/news/claude-opus-4-1 date=2025-08-05
- Terminal-Bench (1.0): improved (no single number published)
- GPQA Diamond / AIME / MMLU-Pro (extended thinking): reported as improvements vs Opus 4 without single-number splits in the blog

---

### Claude Sonnet 4.5

- Release: 2025-09-29
- Status: active (tentative retirement not sooner than 2026-09-29)
- Context: 200K tokens (1M context beta)
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: "best coding model in the world" at launch; 30+ hours autonomous work claim; substantial leap on OSWorld; introduced renaming convention "Claude Sonnet 4.5" (model name before version number).
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-sonnet-4-5
    title: "Introducing Claude Sonnet 4.5"
    date: 2025-09-29
  - kind: model-card
    tag: lab
    url: https://www.anthropic.com/claude-sonnet-4-5-system-card
    title: "Claude Sonnet 4.5 System Card"
    date: 2025-09
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2025/09/29/anthropic-launches-claude-sonnet-4-5-its-best-ai-model-for-coding/
    publisher: TechCrunch
    title: "Anthropic launches Claude Sonnet 4.5"
    date: 2025-09-29

Benchmarks (lab):
- SWE-bench Verified: 77.2 [lab] src=https://www.anthropic.com/news/claude-sonnet-4-5 date=2025-09-29
- SWE-bench Verified (1M context): 78.2 [lab]
- SWE-bench Verified (high compute): 82.0 [lab]
- OSWorld: 61.4 [lab]

---

### Claude Haiku 4.5

- Release: 2025-10-15
- Status: active (tentative retirement not sooner than 2026-10-15)
- Context: 200K tokens (64K max output)
- Modality: text + vision
- Price (in/out per 1M): $1.00 / $5.00
- Notable: brought extended thinking + computer use to the Haiku tier for the first time; matches Sonnet 4 on coding at ~1/3 the cost.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-haiku-4-5
    title: "Introducing Claude Haiku 4.5"
    date: 2025-10-15
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/claude-4-5-haiku
    publisher: Artificial Analysis
    title: "Claude 4.5 Haiku — Intelligence Index"
    date: 2025-10

Benchmarks (lab):
- SWE-bench Verified: 73.3 [lab] src=https://www.anthropic.com/news/claude-haiku-4-5 date=2025-10-15
- OSWorld: 50.7 [lab]
- Terminal-Bench (no thinking): 40.21 [lab]
- Terminal-Bench (32K thinking): 41.75 [lab]

Notes: Artificial Analysis "Intelligence Index" composite score of 31 (median for non-reasoning tier: 25) — not a single benchmark, but a composite across GPQA Diamond, Terminal-Bench Hard, AA-LCR, HLE, and others. No single-benchmark >3pp disagreement located.

---

### Claude Opus 4.5

- Release: 2025-11-24 (model ID `claude-opus-4-5-20251101`)
- Status: active (tentative retirement not sooner than 2026-11-24)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $5.00 / $25.00 (dropped 3x from Opus 4.1's $15/$75)
- Notable: first model to break 80% on SWE-bench Verified; massive ARC-AGI-2 leap; price cut at flagship tier.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-opus-4-5
    title: "Introducing Claude Opus 4.5"
    date: 2025-11-24
  - kind: model-card
    tag: lab
    url: https://www.anthropic.com/claude-opus-4-5-system-card
    title: "Claude Opus 4.5 System Card"
    date: 2025-11
  - kind: replication
    tag: 3p
    url: https://www.vellum.ai/blog/claude-opus-4-5-benchmarks
    publisher: Vellum
    title: "Claude Opus 4.5 Benchmarks (Explained)"
    date: 2025-11

Benchmarks (lab):
- SWE-bench Verified: 80.9 [lab] src=https://www.anthropic.com/news/claude-opus-4-5 date=2025-11-24
- ARC-AGI-2: 37.6 [lab]
- OSWorld: 66.26 [lab]
- Terminal-Bench: ~15pp improvement over Sonnet 4.5 (Anthropic did not publish a single number in the release blog)

---

### Claude Opus 4.6

- Release: 2026-02-05
- Status: active (tentative retirement not sooner than 2027-02-05)
- Context: **1M tokens (beta on Claude Platform)**, 128K max output
- Modality: text + vision
- Price (in/out per 1M): $5.00 / $25.00 (standard ≤200K prompts); long-prompt tier $10 / $37.50 for >200K
- Notable: 1M-context Opus; adaptive thinking introduced; effort controls (low/medium/high); SOTA on ARC-AGI-1/2 at the time.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-opus-4-6
    title: "Introducing Claude Opus 4.6"
    date: 2026-02-05
  - kind: model-card
    tag: lab
    url: https://www-cdn.anthropic.com/0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf
    title: "Claude Opus 4.6 System Card (Feb 2026)"
    date: 2026-02
  - kind: pricing
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/pricing
    title: "Anthropic API Pricing"
    date: 2026-05

Benchmarks (lab):
- SWE-bench Verified: 80.8 [lab] src=https://www.anthropic.com/news/claude-opus-4-6 date=2026-02-05 (release page also notes 81.42% with prompt modification, averaged over 25 trials)
- SWE-bench Pro: 53.4 [lab] src=https://llm-stats.com/blog/research/claude-opus-4-7-launch date=2026-04 (cited from Anthropic's Opus 4.7 release comparison table)
- Terminal-Bench 2.0: 65.4 [lab]
- GPQA Diamond: 91.3 [lab]
- ARC-AGI-1: 94.00 [lab]
- ARC-AGI-2: 69.17 [lab] (120K thinking tokens, high effort, private dataset)
- MRCR v2 (8-needle 1M): 76 [lab]

---

### Claude Sonnet 4.6

- Release: 2026-02-17
- Status: active (tentative retirement not sooner than 2027-02-17)
- Context: 1M tokens (beta) — first Sonnet-tier model with full 1M
- Modality: text + vision
- Price (in/out per 1M): $3.00 / $15.00
- Notable: 1.2pp behind Opus 4.6 on SWE-bench Verified — smallest Sonnet-vs-Opus gap in any Claude generation; users preferred Sonnet 4.6 over Opus 4.5 ~59% of the time per Anthropic.
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-sonnet-4-6
    title: "Introducing Claude Sonnet 4.6"
    date: 2026-02-17
  - kind: coverage
    tag: 3p
    url: https://www.latent.space/p/ainews-claude-sonnet-46-clean-upgrade
    publisher: Latent Space
    title: "Claude Sonnet 4.6: clean upgrade of 4.5"
    date: 2026-02

Benchmarks (lab):
- SWE-bench Verified: 79.6 [lab] src=https://www.anthropic.com/news/claude-sonnet-4-6 date=2026-02-17 (80.2 with prompt modification, 10-trial average)
- OSWorld: 72.5 [lab]
- AIME (no year specified in blog): ~89 [lab] (vs 62% for Sonnet 4.5 — "math leap")

---

### Claude Mythos Preview (codename "Capybara")

- Release: 2026-04-08 (preview announcement; pre-release blog leaked via CMS misconfig on 2026-03-26)
- Status: **preview** (limited availability — Project Glasswing partners only; no public GA planned)
- Context: 1M tokens, 128K max output (per Bedrock model card)
- Modality: text + vision
- Price (in/out per 1M): $25.00 / $125.00 (Glasswing-participant pricing per third-party reporting; not on Anthropic public pricing page)
- Notable: positioned by Anthropic as a "new tier" above Opus — larger and more intelligent than the Opus line; used internally to find thousands of zero-day vulnerabilities across major OSes and browsers; Project Glasswing is the defensive coordination initiative announced alongside.
- Sources:
  - kind: announcement
    tag: lab
    url: https://red.anthropic.com/2026/mythos-preview/
    title: "Claude Mythos Preview"
    date: 2026-04-08
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/glasswing
    title: "Project Glasswing"
    date: 2026-04-08
  - kind: coverage
    tag: 3p
    url: https://llm-stats.com/blog/research/claude-mythos-preview-launch
    publisher: llm-stats
    title: "Claude Mythos Preview: Benchmarks, Pricing & Project Glasswing"
    date: 2026-04
  - kind: model-card
    tag: 3p
    url: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-mythos-preview.html
    publisher: AWS Bedrock
    title: "Mythos Preview model card (Bedrock)"
    date: 2026-04

Benchmarks (lab unless tagged):
- SWE-bench Verified: 93.9 [lab] src=https://red.anthropic.com/2026/mythos-preview/ date=2026-04-08
- SWE-bench Pro: 77.8 [3p] src=https://llm-stats.com/benchmarks/swe-bench-pro publisher="llm-stats leaderboard" date=2026-05
- USAMO: 97.6 [lab]
- OSS-Fuzz crashes (Tiers 1–2): 595 vs Opus 4.6's 150–175 [lab] (cyber-specific, not standard benchmark)
- Firefox exploit-generation: 181 working exploits vs Opus 4.6's 2 [lab] (cyber-specific)

Notes: General-knowledge benchmarks (MMLU-Pro, GPQA Diamond, AIME, LiveCodeBench, Terminal-Bench) — Anthropic's red-team blog post emphasized cyber capability, not the standard suite; no public numbers for these on Mythos.

---

### Claude Opus 4.7 (1M context variant — flagship May 2026)

- Release: 2026-04-16
- Status: active (tentative retirement not sooner than 2027-04-16)
- Context: **1M tokens, 128K max output** (no separate "1M variant" model ID — 1M is native to `claude-opus-4-7`)
- Modality: text + vision (high-resolution images up to 2576px / 3.75MP)
- Price (in/out per 1M): $5.00 / $25.00 (standard ≤200K prompts); $10.00 / $37.50 for >200K prompts (per llm-stats / Anthropic pricing page)
- Notable: high-res image support (2576px / 3.75MP, up from 1568px / 1.15MP); **task budgets** (advisory token budget for full agentic loops); new `xhigh` effort level; extended-thinking budgets removed in favor of adaptive thinking; new tokenizer (1.0–1.35x token counts vs Opus 4.6); cybersecurity refusals tightened (Cyber Verification Program for legit work).
- Sources:
  - kind: announcement
    tag: lab
    url: https://www.anthropic.com/news/claude-opus-4-7
    title: "Introducing Claude Opus 4.7"
    date: 2026-04-16
  - kind: model-card
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
    title: "What's new in Claude Opus 4.7"
    date: 2026-04-16
  - kind: pricing
    tag: lab
    url: https://platform.claude.com/docs/en/about-claude/pricing
    title: "Anthropic API Pricing"
    date: 2026-05
  - kind: coverage
    tag: 3p
    url: https://aws.amazon.com/blogs/aws/introducing-anthropics-claude-opus-4-7-model-in-amazon-bedrock/
    publisher: AWS
    title: "Claude Opus 4.7 on Amazon Bedrock"
    date: 2026-04-16
  - kind: replication
    tag: 3p
    url: https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained
    publisher: Vellum
    title: "Claude Opus 4.7 Benchmarks Explained"
    date: 2026-04
  - kind: replication
    tag: 3p
    url: https://llm-stats.com/blog/research/claude-opus-4-7-launch
    publisher: llm-stats
    title: "Claude Opus 4.7 launch breakdown"
    date: 2026-04

Benchmarks (lab):
- SWE-bench Verified: 87.6 [lab] src=https://www.anthropic.com/news/claude-opus-4-7 date=2026-04-16
- SWE-bench Pro: 64.3 [lab] src=Opus-4.7-launch-table date=2026-04-16
- Terminal-Bench 2.0: 69.4 [lab]
- GPQA Diamond: 94.2 [lab]
- CursorBench: 70 [lab] (vs Opus 4.6 at 58)
- Finance Agent: 64.4 [lab]

Notes:
- Anthropic's Opus 4.7 release post does **not** publish MMLU-Pro, AIME 2025, or LiveCodeBench v6 numbers; cells absent.
- Pricing discrepancy: Anthropic's release blog says "1M context at standard API pricing with no long-context premium"; llm-stats' Opus 4.7 launch page tabulates a >200K premium of $10 / $37.50. Both attribute to Anthropic — the blog's "no premium" appears to refer to standard ≤200K usage; pricing-page detail confirms the >200K surcharge persists. **Flag**: this is a wording-level disagreement, not a benchmark replication issue.

---

## End-of-document Sources (deduplicated)

Anthropic / lab-published:
- https://platform.claude.com/docs/en/about-claude/model-deprecations
- https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
- https://platform.claude.com/docs/en/about-claude/pricing
- https://www.anthropic.com/news/releasing-claude-instant-1-2
- https://www.anthropic.com/news/claude-2
- https://www.anthropic.com/news/claude-2-1
- https://www.anthropic.com/news/claude-3-family
- https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf
- https://www.anthropic.com/news/claude-3-5-sonnet
- https://www.anthropic.com/news/3-5-models-and-computer-use
- https://assets.anthropic.com/m/1cd9d098ac3e6467/original/Claude-3-Model-Card-October-Addendum.pdf
- https://www.anthropic.com/news/claude-3-7-sonnet
- https://www.anthropic.com/news/claude-4
- https://www.anthropic.com/news/claude-opus-4-1
- https://www.anthropic.com/news/claude-sonnet-4-5
- https://www.anthropic.com/claude-sonnet-4-5-system-card
- https://www.anthropic.com/news/claude-haiku-4-5
- https://www.anthropic.com/news/claude-opus-4-5
- https://www.anthropic.com/claude-opus-4-5-system-card
- https://www.anthropic.com/news/claude-opus-4-6
- https://www-cdn.anthropic.com/0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf
- https://www.anthropic.com/news/claude-sonnet-4-6
- https://www.anthropic.com/news/claude-opus-4-7
- https://red.anthropic.com/2026/mythos-preview/
- https://www.anthropic.com/glasswing
- https://www.anthropic.com/research/deprecation-updates-opus-3
- https://www-cdn.anthropic.com/1b1ea2c43d8dd058f6a331a8097e05ea40d626c6/model_pricing_nov2023.pdf

Third-party / replications / coverage:
- https://en.wikipedia.org/wiki/Claude_(language_model)
- https://endoflife.date/claude
- https://hidekazu-konishi.com/entry/anthropic_claude_model_release_timeline.html
- https://techcrunch.com/2023/07/11/anthropic-releases-claude-2-the-second-generation-of-its-ai-chatbot/
- https://techcrunch.com/2025/09/29/anthropic-launches-claude-sonnet-4-5-its-best-ai-model-for-coding/
- https://www.vellum.ai/blog/claude-opus-4-5-benchmarks
- https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained
- https://llm-stats.com/blog/research/claude-opus-4-7-launch
- https://llm-stats.com/blog/research/claude-mythos-preview-launch
- https://llm-stats.com/benchmarks/swe-bench-pro
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-mythos-preview.html
- https://aws.amazon.com/blogs/aws/introducing-anthropics-claude-opus-4-7-model-in-amazon-bedrock/
- https://artificialanalysis.ai/models/claude-4-5-haiku
- https://www.latent.space/p/ainews-claude-sonnet-46-clean-upgrade
