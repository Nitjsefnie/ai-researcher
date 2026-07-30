# GPT-5.5 deep-fill (April 2026 launch)

Date: 2026-05-23. Released 2026-04-23. Codename "Spud". Three SKUs: GPT-5.5 (standard), GPT-5.5 Thinking, GPT-5.5 Pro. Variants on Artificial Analysis: xhigh / high / low.

## NEW lab numbers (OpenAI-reported, not in prior brief)

### Coding / agentic
- **SWE-bench Verified: 88.7** [marc0.dev leaderboard / tokenmix / o-mega](https://www.marc0.dev/en/leaderboard) — OpenAI-reported. Top of leaderboard; Opus 4.7 second at 87.6.
- **Expert-SWE (OpenAI internal, ~20hr tasks): 73.1** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) / [kingy 9 numbers](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/)

### Knowledge / reasoning
- **MMLU: 92.4** [tokenmix](https://tokenmix.ai/blog/gpt-5-5-spud-review-88-swe-bench-2026) / [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026) — OpenAI headline number.
- **GPQA Diamond: 93.6** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) (OpenAI lab); **AA 3p: 93.5 (xhigh) / 93.2 (high)** [Artificial Analysis GPQA leaderboard](https://artificialanalysis.ai/evaluations/gpqa-diamond) — within noise of lab.
- **HLE with tools: 52.2** [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026) (we already had no-tools 41.4).
- **ARC-AGI-1: 95.0** [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026) — we already had ARC-AGI-2 85.0.

### Long context
- **MRCR v2 512K–1M: 74.0** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) (vs GPT-5.4 36.6).
- **MRCR v2 256K–512K: 81.5** [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026).
- **MRCR v2 128K–256K: 87.5** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) (vs Claude 59.2). (Google cross-tab "MRCR 128k: 94.8" appears to be a different cut — leaving prior figure flagged.)
- **Graphwalks BFS @ 1M tokens: 45.4** [Vending search](https://www.google.com/search?q=%22GPT-5.5%22+%22Graphwalks%22) (vs GPT-5.4 9.4). BFS/Parents split not separately published.

### Multimodal
- **MMMU-Pro no-tools: 81.2** [kingy](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/) (matches Google cross-tab).
- **MMMU-Pro with-tools: 83.2** [kingy](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/) — new split.

### Domain agents
- **τ²-bench Telecom: 98.0** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) — confirms prior 3p figure as lab-side too.
- **FinanceAgent v1.1: 60.0** [kingy](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/) (we had v2 51.8 from Google).
- **Investment-banking internal modeling: 88.5** [kingy showdown](https://kingy.ai/ai/claude-mythos-preview-vs-gpt-5-5-a-benchmark-by-benchmark-showdown-between-the-two-most-important-frontier-models-of-april-2026/)
- **OfficeQA Pro: 54.1** [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026)
- **Harvey BigLaw Bench: 91.7** [Harvey blog](https://www.harvey.ai/blog/gpt-5-5-research-preview-results) — 43% perfect, 87% above 0.80, zero below 0.50. GPT-5.4 was 91.0.
- **BrowseComp Pro: 90.1** [kingy](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/) — distinct from non-Pro BrowseComp 84.4 already on file.

### Science
- **BixBench: 80.5** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) (vs GPT-5.4 74.0)
- **GeneBench: 25.0** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5); **GPT-5.5 Pro: 33.2** [kingy](https://kingy.ai/ai/gpt-5-5-benchmarks-revealed-the-9-numbers-that-prove-chatgpt-5-5-just-changed-the-ai-race/)

### Cyber
- **Cyber Range combined: 93.33** (14/15 scenarios) [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5) (vs GPT-5.4-thinking 73.33)
- **UK AISI cyber tasks pass@5: 90.5** [Vellum](https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5)
- **Expanded CTF: 88.1** [o-mega](https://o-mega.ai/articles/gpt-5-5-the-complete-guide-2026)
- **CTF Professional: 96.3** [Medium system-card review](https://medium.com/@polyglot_factotum/gpt-5-5-system-card-review-133161a1f2e7) vs GPT-5.4-thinking 88.2.

### Health (from system card)
- **HealthBench (length-adjusted): 56.5** [deploymentsafety.openai.com](https://deploymentsafety.openai.com/gpt-5-5)
- **HealthBench Hard: 31.5**
- **HealthBench Professional: 51.8**
- Factuality claim: "23% more likely to be factually correct than GPT-5.4."

### AI self-improvement / safety
- **Monorepo-Bench: 60.0** (GPT-5.4-thinking 59.3) [Medium review](https://medium.com/@polyglot_factotum/gpt-5-5-system-card-review-133161a1f2e7)
- **OPQA: 1.7** (GPT-5.3-Codex 5.8) [Medium review](https://medium.com/@polyglot_factotum/gpt-5-5-system-card-review-133161a1f2e7) (note: Vellum reports OPQA at 5.8 — appears to be a different table; surfacing both, lab dual-report)
- **Sandbagging QA: 100.0** | **Strategic Deception (incentivized <50%): 99.6** [deploymentsafety](https://deploymentsafety.openai.com/gpt-5-5) (Apollo Research)
- **Hard-Negative Protein Binding: 0** (GPT-5.4-thinking 3.46) [Medium review](https://medium.com/@polyglot_factotum/gpt-5-5-system-card-review-133161a1f2e7)
- **Internal Debugging median: 50.5**

## NEW 3p numbers

### Artificial Analysis (xhigh unless noted)
- **AAII v4.0 (xhigh): 60** — #1/148 [AA model page](https://artificialanalysis.ai/models/gpt-5-5)
- **AAII v4.0 (high): 59** — #2/148 [AA high page](https://artificialanalysis.ai/models/gpt-5-5-high)
- **AA-Omniscience accuracy: 57.0** (record), hallucination rate 86% [officechai](https://officechai.com/ai/gpt-5-5-tops-artificial-analysis-with-score-of-60-goes-clear-of-gemini-3-1-pro-and-claude-opus-4-7/) — +14pp over GPT-5.4.
- **GDPval-AA Elo: 1785** [officechai](https://officechai.com/ai/gpt-5-5-tops-artificial-analysis-with-score-of-60-goes-clear-of-gemini-3-1-pro-and-claude-opus-4-7/) — Google cross-tab had 1773; AA's later cut shows 1785 (within 12pp).
- **Output speed (xhigh): 71.7 tok/s** | **TTFT: 112.17s** [AA xhigh](https://artificialanalysis.ai/models/gpt-5-5)
- **Output speed (high): 69.1 tok/s** | **TTFT: 27.45s** [AA high](https://artificialanalysis.ai/models/gpt-5-5-high)
- **Context window: 922K tokens** [AA xhigh](https://artificialanalysis.ai/models/gpt-5-5) — 1M nominal; 922K reflects AA's measured usable window.

### BenchLM category aggregates
- Agentic: **98.3** (11 benches) | Coding: **84.3** (8) | Reasoning: **96.8** (5) | Knowledge: **98.1** (10) | Math: **97.4** (1) | Multimodal: **57.2** (4) — [BenchLM](https://benchlm.ai/models/gpt-5-5)

### Chatbot Arena Elo (BenchLM aggregated cuts)
- **Text Overall: 1478** | Coding: **1509** | Math: **1503** | Instruction Following: **1479** | Creative Writing: **1439** | Multi-turn: **1481** | Hard Prompts: **1496** | Hard Prompts (EN): **1493** | Longer Query: **1481** — [BenchLM](https://benchlm.ai/models/gpt-5-5)
- Cross-check: trendingtopics reports GPT-5.5 sits **below** Opus 4.7, Opus 4.6, Gemini 3.1 Pro, **and Meta Muse Spark** on LMArena — [trendingtopics](https://www.trendingtopics.eu/gpt-5-5-tops-academic-benchmarks-but-loses-to-rivals-in-real-user-tests/). Opus 4.7 thinking Elo 1504 quoted as Arena leader.

### Andon Labs
- **Vending-Bench 2 (single-player, mean net worth): $7,500** [search result citing Andon Labs](https://andonlabs.com/blog/openai-gpt-5-5-vending-bench) — beats GPT-5.4 (~$6k), trails Opus 4.6 ($8k) and Opus 4.7 ($11k).
- **Vending-Bench Arena: $7,980 won** — beats Opus 4.7 ($5,838) and GPT-5.4 ($2,158). And does so without misconduct (notable behavioral finding).

## Pricing (corroborating)

- GPT-5.5 (high): **$5 in / $30 out / $0.50 cache** per M tokens [AA high](https://artificialanalysis.ai/models/gpt-5-5-high)
- GPT-5.5 Pro: $30/$180 per M (per brief).

## GPT-5.5 Pro deltas (separately reported)

- **AAII v4.0 (xhigh): 60** leads index (the headline 60 is GPT-5.5 Pro-tier xhigh).
- **GDPval: 82.3** (vs std 84.9) [kingy showdown](https://kingy.ai/ai/claude-mythos-preview-vs-gpt-5-5-a-benchmark-by-benchmark-showdown-between-the-two-most-important-frontier-models-of-april-2026/)
- **FrontierMath T1-3: 52.4** (vs std 51.7); **T4: 39.6** (vs std 35.4) [kingy showdown](https://kingy.ai/ai/claude-mythos-preview-vs-gpt-5-5-a-benchmark-by-benchmark-showdown-between-the-two-most-important-frontier-models-of-april-2026/)
- **GeneBench: 33.2** (vs std 25.0)
- **BrowseComp Pro: 90.1** attributed to Pro variant by kingy.
- **SWE-bench Verified Pro: 82.6** (per BenchLM Pro page — only 4 published scores so far) [BenchLM Pro](https://benchlm.ai/models/gpt-5-5-pro)

## Lab vs 3p disagreements (>3pp surfaced)

- **Terminal-Bench 2.0**: lab 82.7 vs Vals 73.20 (~9.5pp gap) — already known; confirmed.
- **OPQA**: Vellum 5.8 vs Medium review 1.7. Looks like two different cuts/protocols — leaving both visible.
- **GDPval-AA Elo**: Google cross-tab 1773 vs AA officechai 1785 (~12pp). Different snapshot dates.
- **MRCR 128k**: Google cross-tab 94.8 vs OpenAI MRCR v2 128–256K bucket 87.5. Different test variant (Google's appears to be a 128K needle subset; lab is the v2 128–256K range bucket).
- **HLE**: launch page no-tools 41.4 → with-tools 52.2 (confirmed split). One outlier search hit claimed 56.8/64.7 but is not corroborated by Vellum/launch/system card — disregarding.

## Confirmed unreported (after 25 web ops)

These were specifically searched and not found in lab or 3p sources at time of writing:

- **LiveCodeBench v6 pass@1** — not published. Codesota leaderboard explicitly lacks GPT-5.5 entry; OpenAI launch materials don't include it.
- **LiveCodeBench Pro Elo** — not published.
- **AIME 2024 / AIME 2025** — OpenAI launch page does not report these for GPT-5.5 (a break from prior GPT-5.x patterns). Search returns no third-party measurement either.
- **MATH-500** — not in launch materials; no 3p eval found.
- **USAMO 2026** — Kingy "Mythos vs GPT-5.5" showdown gives Mythos 97.6 and GPT-5.4 95.2, but does NOT cite a GPT-5.5 number. Likely OpenAI declined to publish.
- **MMMLU** — not reported.
- **MMLU-Pro lab number** — OpenAI cites MMLU 92.4 only. AA includes MMLU-Pro in AAII but doesn't surface the standalone score on the model page. PricePerToken's MMLU-Pro leaderboard does not list GPT-5.5 yet.
- **DualEntry Accounting** — GPT-5.4 = 77.3 is the most recent; DualEntry has not yet published a GPT-5.5 run.
- **IFBench / SciCode / CritPt / AA-LCR individual scores** — AA reports only the composite AAII (60) and surfaces gain deltas qualitatively. Individual benchmark scores aren't on the model page.
- **τ-bench Retail / Airline** (1-shot original tau-bench) — only τ² Telecom is lab-reported.
- **MCP-Atlas lab number** — Google cross-tab gave 75.3; not found as an OpenAI lab number, only via Google's cross-tab reporting. Confirmed by Vellum/medium as the figure but origin remains Google's eval reporting.
- **τ³-Bench / MCP-Atlas (OpenAI primary)** — neither in launch nor system card visible sections.
- **CharXiv lab no-tools / with-tools split** — Google cross-tab gave no-tools 84.1; OpenAI did not publish either variant.

## Bonus finds

### GPT-5.5 Pro (separate SKU)
- AAII v4.0 (xhigh tier) = 60 — Pro is the variant that hits the index leader number.
- GDPval 82.3 / FrontierMath T1-3 52.4 / T4 39.6 / GeneBench 33.2 / BrowseComp Pro 90.1 / SWE-Verified 82.6 (only 4 BenchLM-published scores so far).

### GPT-5.4 (predecessor) — new numbers found incidentally
- Terminal-Bench 2.0: **75.1** ; SWE-bench Pro: **57.7** ; SWE-bench Verified: **82.1** ; MMLU: **89.8** ; GDPval: **83.0** ; MRCR v2 512K-1M: **36.6** ; MRCR v2 128K-256K: **59.2** (Claude figure quoted but appears mis-labeled in source — flag) ; Graphwalks BFS @ 1M: **9.4** ; BixBench: **74.0** ; Cyber Range: **73.33** ; CTF Professional: **88.2** ; BigLaw: **91.0** ; DualEntry Accounting: **77.3** ; USAMO 2026: **95.2** ; LMArena Elo (high): **1482** (April 2026).

### Claude Mythos Preview (Anthropic, April 2026)
- SWE-bench: **93.9** ; USAMO 2026: **97.6** — both per [getpassionfruit](https://www.getpassionfruit.com/blog/what-anthropic-s-most-powerful-ai-model-means-for-marketing-teams-claude-mythos-preview) / [nxcode](https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026).

### Meta Muse Spark
- Sits above GPT-5.5 on LMArena per trendingtopics — exact Elo not surfaced.

## Note on the GPT-5.5 launch page (`openai.com/index/gpt-5-5/`)

Direct WebFetch returns 403 (Cloudflare-protected). All "OpenAI-reported" numbers above were re-extracted via Vellum/o-mega/kingy/tokenmix/datacamp/buildfastwithai, all of which quote the launch page or the [system card PDF](https://deploymentsafety.openai.com/gpt-5-5/gpt-5-5.pdf) (also CDN-protected; binary not parseable directly). System card landing page at [openai.com/index/gpt-5-5-system-card/](https://openai.com/index/gpt-5-5-system-card/) also 403s. Numbers cross-verified across ≥2 independent reporters where possible.
