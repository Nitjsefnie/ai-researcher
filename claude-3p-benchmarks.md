# Claude 3p Benchmark Replication Scan

Scan date: 2026-05-23. Skip rule applied: 3p numbers within 3pp of a known lab number on the same bench/model are omitted. Where a 3p source's number lies within 3pp of Anthropic's published value, it's dropped per the user's AGENTS.md sourcing discipline.

Notes on coverage:
- Artificial Analysis dropped MMLU-Pro, AIME 2025, and LiveCodeBench from its Intelligence Index v4.0 (Jan 2026) because frontier models saturated them. AA's per-model pages now publish only the new index components (GDPval-AA, AA-LCR, AA-Omniscience, SciCode, IFBench, Terminal-Bench Hard, HLE, GPQA Diamond, CritPt, τ²-Bench Telecom). 3p LCB/MMLU-Pro/AIME data therefore comes from pricepertoken.com, codesota.com, vals.ai, demandsphere, and per-model reviewer blogs.
- pricepertoken.com is the single most complete 3p source for LCB and MMLU-Pro across the Claude generation. Treated as primary 3p replicator below; corroborated by codesota.com and vals.ai where overlapping.
- "LiveCodeBench" on pricepertoken is the latest version (v6 window) per their methodology page; date-suffix versions not split out per row.

---

### Claude Opus 4.7
- LiveCodeBench Pro: ~2,687 Elo (~200 below Gemini 3.1 Pro's 2,887) [3p] src=https://www.morphllm.com/best-ai-model-for-coding publisher=Morph date=2026-05
- MMLU-Pro: 89.87% [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Kingy AI date=2026-04
- AIME 2025 (64K thinking): 96.2% [3p] src=https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026 publisher=BuildFastWithAI date=2026-04
- SWE-bench Verified (LM Council, max effort): 83.5% ±1.7 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05 (note: lower than Anthropic's published 87.6 — independent run, different scaffold)
- OTIS Mock AIME 2024-25 (xhigh): 97.8% ±2.2 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- CursorBench: 70% [3p] src=https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026 publisher=BuildFastWithAI date=2026-04
- BigLaw Bench: 90.9% [3p] src=https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026 publisher=BuildFastWithAI date=2026-04
- GDPval-AA Elo: 1,753 [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=Artificial Analysis date=2026-04
- AAII (Intelligence Index v4.0): 57 [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=Artificial Analysis date=2026-04
- AA-Omniscience Index: 26 (hallucination rate 36%, attempt rate 70%) [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=Artificial Analysis date=2026-04

### Claude Mythos Preview / "Capybara"
- SWE-bench Verified: 93.9% [3p] src=https://llm-stats.com/benchmarks/swe-bench-verified publisher=llm-stats date=2026-05
- GPQA Diamond: 94.6% [3p] src=https://wavespeed.ai/blog/posts/what-is-claude-mythos/ publisher=WaveSpeed date=2026-04
- (No other 3p numbers located — model is preview-only with limited eval coverage.)

### Claude Sonnet 4.6
- LiveCodeBench: 80% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- MMLU-Pro: 79.2% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- AIME 2025: 94% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- MATH-500: 97.8% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- HumanEval: 98% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- IFEval: 95% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- HLE: 51% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03
- ARC-AGI: 58.3% [3p] src=https://automatio.ai/models/claude-sonnet-4-6 publisher=Automatio date=2026-03

### Claude Opus 4.6
- LiveCodeBench: ~73-74% (back-computed: Opus 4.5 = 73.8%, Opus 4.6 ≈ similar per AA's "no LCB regression" note) [3p, indirect] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05 — INSUFFICIENT, no direct row found
- MMLU-Pro: 89.0% [3p] src=https://www.demandsphere.com/research/demandsphere-radar/ai-frontier-model-tracker/benchmarks/mmlu-pro/ publisher=DemandSphere date=2026-04
- MMLU-Pro: 88.9% [3p corroboration] src=https://medium.com/@reliabledataengineering/claude-opus-4-6-vs-4-5-what-actually-changed-and-whether-you-should-upgrade-ff46550e8a75 publisher=Medium/Reliable Data Engineering date=2026-02
- AIME 2025 (no tools, avg 5 trials, adaptive thinking max effort): 99.79% [3p] src=https://www.codesota.com/llm publisher=CodeSOTA date=2026-05 (matches Anthropic's launch number — borderline skip; kept because Anthropic stopped publishing AIME as primary)
- SWE-bench Verified (high effort, LM Council): 78.7% ±1.9 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- FrontierMath (max effort): 40.7% ±2.9 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- WeirdML v2 (no thinking): 65.9% [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- HLE: 19% [3p] src=https://www.codesota.com/llm publisher=CodeSOTA date=2026-05
- AAII v4.0: 46 [3p] src=https://artificialanalysis.ai/models/claude-opus-4-6 publisher=Artificial Analysis date=2026-02

### Claude Opus 4.5
- LiveCodeBench (Thinking): 87.1% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 73.8% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench: 89.4% (alt scaffold) [3p] src=https://vertu.com/lifestyle/claude-opus-4-5-vs-gpt-5-2-codex-head-to-head-coding-benchmark-comparison publisher=Vertu date=2026-01
- MMLU-Pro (Thinking): 89.5% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (non-reasoning): 88.9% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro: 90% (Thinking, AA-reported) [3p corroboration] src=https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis publisher=Artificial Analysis date=2025-11
- AIME 2025: 80% [3p] src=https://www.codesota.com/llm publisher=CodeSOTA date=2026-05
- AAII v4.0 (Reasoning): 70 [3p] src=https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis publisher=Artificial Analysis date=2025-11
- AAII v4.0 (Non-Reasoning): 60 [3p] src=https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis publisher=Artificial Analysis date=2025-11
- CritPt: 5% [3p] src=https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis publisher=Artificial Analysis date=2025-11
- METR Time Horizons: 293.0 ±239.0 min [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- GSO: 26.5% [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- WebDev Arena (no thinking): 1479 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- WebDev Arena (32k thinking): 1512 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05
- SWE-bench Verified (no thinking, LM Council): 76.7% ±1.9 [3p] src=https://lmcouncil.ai/benchmarks publisher=LM Council date=2026-05

### Claude Haiku 4.5
- LiveCodeBench (Thinking): 61.5% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 51.1% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- MMLU-Pro: 80.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2025: 63.4 (out of 100, BenchLM scale) [3p] src=https://benchlm.ai/models/claude-haiku-4-5 publisher=BenchLM date=2026-04

### Claude Sonnet 4.5
- LiveCodeBench (Thinking): 71.4% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 59.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (Thinking, alt): 78.8% [3p] src=https://vertu.com/lifestyle/claude-opus-4-5-vs-gpt-5-2-codex-head-to-head-coding-benchmark-comparison publisher=Vertu date=2026-01
- MMLU-Pro (Thinking): 87.5% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (non-reasoning): 86.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2025: 87.0% [3p] src=https://llm-stats.com/blog/research/gpt-5-2-vs-claude-opus-4-5 publisher=llm-stats date=2025-11

### Claude Opus 4.1
- LiveCodeBench (Thinking): 65.4% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- MMLU-Pro (Thinking): 88.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05

### Claude Opus 4
- LiveCodeBench (Thinking): 63.6% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 54.2% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (codesota/Berkeley merge): 57.8% [3p corroboration] src=https://www.codesota.com/benchmark/livecodebench publisher=CodeSOTA date=2026-05
- MMLU-Pro (Thinking): 87.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (non-reasoning): 86.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2024 (Thinking): 75.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- AIME 2024 (non-reasoning): 56.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05

### Claude Sonnet 4
- LiveCodeBench (Thinking): 65.5% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 44.9% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (codesota/Berkeley merge): 52.8% [3p corroboration] src=https://www.codesota.com/llm publisher=CodeSOTA date=2026-05
- MMLU-Pro (Thinking): 84.2% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (non-reasoning): 83.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2024 (Thinking): 77.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- AIME 2024 (non-reasoning): 40.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- SWE-bench Verified (vals/llm-stats retro): 72.7% [3p] src=https://llm-stats.com/benchmarks/swe-bench-verified publisher=llm-stats date=2026-05

### Claude 3.7 Sonnet
- LiveCodeBench (Thinking): 47.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (non-reasoning): 39.4% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- LiveCodeBench (alt eval): 56.7% [3p] src=https://www.vellum.ai/llm-leaderboard publisher=Vellum date=2026-04
- LiveCodeBench (alt eval): 65.4% [3p] src=https://www.datacamp.com/blog/claude-3-7-sonnet publisher=DataCamp date=2025-04
- MMLU-Pro (Thinking): 83.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (non-reasoning): 80.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- MMLU-Pro (alt eval): 78.4% [3p] src=https://www.vellum.ai/llm-leaderboard publisher=Vellum date=2025-03
- AIME 2024 (Thinking): 48.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- AIME 2024 (non-reasoning): 22.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- SWE-bench Verified (vals/llm-stats retro): 70.3% [3p] src=https://llm-stats.com/benchmarks/swe-bench-verified publisher=llm-stats date=2026-05
- AA SciCode + LiveCodeBench: "best non-reasoning coding model" [3p directional] src=https://x.com/ArtificialAnlys/status/1894437867914682764 publisher=Artificial Analysis date=2025-02

### Claude 3.5 Haiku
- MMLU-Pro: 63.4% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2024: 3.3% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05

### Claude 3.5 Sonnet v2 ("new", Oct 2024)
(pricepertoken's "Claude 3.5 Sonnet" row most likely refers to v2 / "new" — the model that achieved 49% SWE-V per Anthropic. Treated as v2 below.)
- LiveCodeBench: 38.1% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- MMLU-Pro: 77.2% [3p] src=https://pricepertoken.com/leaderboards/benchmark/mmlu-pro publisher=PricePerToken date=2026-05
- AIME 2024: 15.7% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05
- LiveCodeBench (pass@1, academic): 41.4% [3p] src=https://x.com/rohanpaul_ai/status/1833875823868145769 publisher=Rohan Paul / PLANSEARCH paper date=2024-09

### Claude 3.5 Sonnet (Jun 2024 original)
- (No discrete 3p row separating original from v2 located in budget. PricePerToken's "Claude 3.5 Sonnet" almost certainly maps to v2 given the Oct 2024 column dates. Treat original 3.5 Sonnet as having only Anthropic's June 2024 numbers — SWE-V 33.4% per lab; no 3p replication of the original within budget.)
- (none located in budget)

### Claude 3 Opus
- LiveCodeBench: "best across different scenarios" but no single discrete pass@1 in 3p tables [3p directional] src=https://livecodebench.github.io/ publisher=LiveCodeBench paper date=2024
- (No 3p row on pricepertoken LCB or MMLU-Pro tables — the model has aged out of the active rotation. Vals/llm-stats SWE-V leaderboard does not include 3 Opus retroactively.)
- (No additional 3p numbers located in budget.)

### Claude 3 Sonnet
- (none located in budget — model retired from all active 3p leaderboards.)

### Claude 3 Haiku
- LiveCodeBench: 15.4% [3p] src=https://pricepertoken.com/leaderboards/benchmark/livecodebench publisher=PricePerToken date=2026-05
- AIME 2024: 1.0% [3p] src=https://pricepertoken.com/leaderboards/benchmark/aime publisher=PricePerToken date=2026-05

---

## Cross-cutting observations

- **PricePerToken LCB column appears to be LCB v5 / v6 unified (post-Aug-2024 problems).** Their methodology page describes "rolling window, latest version." Their numbers for 3.7 Sonnet (47.3% Thinking) align with Anthropic's contemporaneous "extended thinking ~50%" range, suggesting reliable methodology.
- **LCB "Thinking" vs "non-reasoning" split** is consistent with Anthropic's adaptive-reasoning toggle; the table above preserves both where present so the consumer can pick the variant that matches their context.
- **AIME 2025 vs AIME 2024 split is sharp on pricepertoken.** They only carry AIME (2024) on their AIME leaderboard. AIME 2025 numbers for Claude 4.x+ come from individual review blogs (BuildFastWithAI, Automatio, CodeSOTA, llm-stats).
- **No 3p replication located for original Jun-2024 Claude 3.5 Sonnet, Claude 3 Sonnet, or Claude 3 Opus on MMLU-Pro or LCB.** These models have aged off active rotation. Stick with Anthropic-published numbers for them.

---

## Sources

- https://livecodebench.github.io/
- https://livecodebench.github.io/leaderboard.html
- https://artificialanalysis.ai/models/claude-opus-4-7
- https://artificialanalysis.ai/models/claude-opus-4-6
- https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know
- https://artificialanalysis.ai/articles/claude-opus-4-5-benchmarks-and-analysis
- https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained
- https://www.vellum.ai/blog/claude-opus-4-6-benchmarks
- https://www.vellum.ai/blog/claude-opus-4-5-benchmarks
- https://www.vellum.ai/llm-leaderboard
- https://pricepertoken.com/leaderboards/benchmark/mmlu-pro
- https://pricepertoken.com/leaderboards/benchmark/livecodebench
- https://pricepertoken.com/leaderboards/benchmark/aime
- https://www.codesota.com/llm
- https://www.codesota.com/benchmark/livecodebench
- https://www.morphllm.com/best-ai-model-for-coding
- https://www.morphllm.com/claude-benchmarks
- https://llm-stats.com/benchmarks/swe-bench-verified
- https://llm-stats.com/blog/research/gpt-5-2-vs-claude-opus-4-5
- https://llm-stats.com/models/claude-opus-4-7
- https://www.vals.ai/benchmarks/swebench
- https://www.vals.ai/benchmarks/mmlu_pro
- https://www.vals.ai/models/anthropic_claude-3-7-sonnet-20250219
- https://lmcouncil.ai/benchmarks
- https://automatio.ai/models/claude-sonnet-4-6
- https://www.demandsphere.com/research/demandsphere-radar/ai-frontier-model-tracker/benchmarks/mmlu-pro/
- https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026
- https://benchlm.ai/models/claude-haiku-4-5
- https://benchlm.ai/models/claude-opus-4-6
- https://benchlm.ai/models/claude-opus-4-7
- https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/
- https://vertu.com/lifestyle/claude-opus-4-5-vs-gpt-5-2-codex-head-to-head-coding-benchmark-comparison
- https://medium.com/@reliabledataengineering/claude-opus-4-6-vs-4-5-what-actually-changed-and-whether-you-should-upgrade-ff46550e8a75
- https://www.datacamp.com/blog/claude-3-7-sonnet
- https://x.com/ArtificialAnlys/status/1894437867914682764
- https://x.com/rohanpaul_ai/status/1833875823868145769
- https://wavespeed.ai/blog/posts/what-is-claude-mythos/
