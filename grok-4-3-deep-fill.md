# Grok-4.3 deep benchmark fill

Released 2026-04-30. Lab numbers route via 3p coverage of `x.ai/news/grok-4-3`
(blog 403s to fetchers); web.archive.org also unreachable from this environment.

## New numbers for Grok-4.3

### Lab-quoted (via 3p routing of x.ai/news/grok-4-3, dated 2026-04-30)

- GPQA Diamond: 90.1 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04
- HLE (no-tools): 35 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=label "Humanity's Last Exam"; tool config not specified
- SciCode: 47.3 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04
- Terminal-Bench Hard: 37.9 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=matches Vals number; confirms exact
- τ²-Bench Telecom: 97.7 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=AA article gives "98%" (rounded)
- IFBench: 81.3 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=AA article gives "81%" (rounded)
- LCR (AA-LCR Long-Context Reasoning): 64.3 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04
- xAI Intelligence Index (internal composite): 53.2 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=label conflates with AA Index 53; precision suggests rebrand of AAII
- xAI Coding Index: 41 (also 41.0) [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04 note=Kilo lists same 41.0
- xAI Agentic Index: 67.8 [lab] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=xAI-via-DesignForOnline date=2026-04
- CaseLaw v2: 79.3 (#1) [lab] src=https://contracollective.com/blog/gemma-4-vs-grok-4-3-may-2026 publisher=xAI-via-ContraCollective date=2026-04
- CorpFin (rank): #1 [lab] src=https://contracollective.com/blog/gemma-4-vs-grok-4-3-may-2026 publisher=xAI-via-ContraCollective date=2026-04 note=numerical score not surfaced

### Artificial Analysis (AAII v4.0 and AA pages)

- AA Intelligence Index v4.0: 53 (already on file)
- GDPval-AA Elo: 1500 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=+321 vs Grok-4.20 0309 v2 (1179); xAI's single biggest jump
- τ²-Bench Telecom: 98 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=rounded; lab 97.7
- IFBench: 81 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=rounded; lab 81.3
- AA-Omniscience Accuracy: +8 pp vs Grok-4.20 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=directional only; absolute not surfaced
- AA-Omniscience Non-Hallucination Rate: -8 pp vs Grok-4.20 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=regression directional only
- Cost to run Intelligence Index: $395 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=88M output tokens
- AAII rank: #12 of 148 [3p] src=https://artificialanalysis.ai/models/grok-4-3 publisher=ArtificialAnalysis date=2026-04
- Output speed (AA listing): 115.0 tok/s [3p] src=https://artificialanalysis.ai/models/grok-4-3 publisher=ArtificialAnalysis date=2026-04 note=AA rank #32; conflicts with prior 92.3 and Kilo 117 and DesignForOnline 93.9 — see disagreements
- Time to First Token: 18.84s [3p] src=https://artificialanalysis.ai/models/grok-4-3 publisher=ArtificialAnalysis date=2026-04 note=reasoning model TTFT
- Blended price: $0.64 /1M tokens [3p] src=https://artificialanalysis.ai/models/grok-4-3 publisher=ArtificialAnalysis date=2026-04
- Cache hit price: $0.20 /1M tokens (-84% vs input) [3p] src=https://artificialanalysis.ai/models/grok-4-3 publisher=ArtificialAnalysis date=2026-04

### BenchLM (category aggregates + Chatbot Arena)

- BenchLM Coding category avg: 65.8/100 [3p] src=https://benchlm.ai/models/grok-4-3 publisher=BenchLM date=2026-05 note=spans SWE-bench Verified, LiveCodeBench, SWE-bench Pro, SWE-Rebench, SciCode; individual scores hidden behind "source-unverified" gate
- BenchLM Knowledge category avg: 75.4/100 [3p] src=https://benchlm.ai/models/grok-4-3 publisher=BenchLM date=2026-05 note=spans GPQA, SuperGPQA, MMLU-Pro, HLE, FrontierScience, SimpleQA
- BenchLM Multimodal category avg: 72.6/100 [3p] src=https://benchlm.ai/models/grok-4-3 publisher=BenchLM date=2026-05 note=spans MMMU-Pro, OfficeQA Pro, CharXiv, CharXiv w/o tools
- BenchLM Instruction Following: 87.8/100 (#18) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=BenchLM date=2026-05 note=IFEval+IFBench composite
- Chatbot Arena (LMArena via BenchLM) — Text Overall: 1451 Elo (±6.5) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05
- Chatbot Arena — Coding: 1493 (±12.0) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05
- Chatbot Arena — Math: 1434 (±25.8) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05
- Chatbot Arena — Instruction Following: 1428 (±10.9) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05
- Chatbot Arena — Creative Writing: 1440 (±15.7) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05
- Chatbot Arena — Hard Prompts: 1463 (±8.1) [3p] src=https://benchlm.ai/models/grok-4-3 publisher=LMArena date=2026-05

### Vals.ai

- Vals Index: 46.63 ±1.41 [3p] src=https://www.vals.ai/models/grok_grok-4.3 publisher=Vals.ai date=2026-05 note=down significantly from Opus 4.7's 66.10; eval coverage still in progress (most rows still ±zeroed)
- Vals Multimodal Index: 0.0 ±1.28 [3p] src=https://www.vals.ai/models/grok_grok-4.3 publisher=Vals.ai date=2026-05 note=zero indicates eval not yet run; not a true 0% score
- Terminal-Bench 2.0 (Vals): rank 24/61, exact score not surfaced [3p] src=https://www.vals.ai/models/grok_grok-4.3 publisher=Vals.ai date=2026-05 note=±4.41 confidence band visible; matches lab 37.9 on Terminal-Bench Hard. Vals row shows 0.0% — placeholder, not actual score

### Kilo Code / OpenRouter / partner aggregators

- Kilo Output speed: 117 tok/s [3p] src=https://kilo.ai/models/x-ai-grok-4-3 publisher=Kilo date=2026-05 note=median throughput; search-snippet says "94 tok/s" — likely different time window
- DesignForOnline output throughput: 93.9 tok/s [3p] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=DesignForOnline date=2026-04
- DesignForOnline TTFT (best): 784 ms [3p] src=https://designforonline.com/ai-models/xai-grok-4-3/ publisher=DesignForOnline date=2026-04 note=conflicts with AA's 18.84s — different harness; AA times full reasoning trace, DFO times first token
- OpenRouter weekly tokens: 90.8B (week of 2026-05) [3p] src=https://openrouter.ai/x-ai/grok-4.3 publisher=OpenRouter date=2026-05

### Pricing (confirmed)

- Input: $1.25 /1M tokens [lab] src=https://artificialanalysis.ai/models/grok-4-3 publisher=xAI date=2026-04 note=37.5% lower than Grok-4.20
- Output: $2.50 /1M tokens [lab] src=https://artificialanalysis.ai/models/grok-4-3 publisher=xAI date=2026-04 note=58.3% lower than Grok-4.20
- Cache hit: $0.20 /1M tokens [lab] src=https://artificialanalysis.ai/models/grok-4-3 publisher=xAI date=2026-04
- Overall cost-per-intelligence drop: ~20% vs Grok-4.20 0309 v2 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=offset by ~44% more output tokens at same intelligence

### Disagreements >3pp surfaced

- **Output speed**: AA 115.0 / DFO 93.9 / Kilo 117 / prior 92.3 — spread 92-117 tok/s. Reasoning-effort dependent; AA tests at "high", DFO appears to average all configs.
- **τ²-Bench Telecom**: lab 97.7 vs AA 98 (rounding, not real disagreement).
- **Vals SWE/GPQA/AIME**: shown as 0.0% — these are placeholders (eval not run), NOT actual zero scores. Do not propagate as Grok-4.3 failing the benchmark.

## Confirmed unreported (thorough search, no exact number found)

- **SWE-bench Verified exact** — only rank/approximate (~67) and BenchLM coding category avg 65.8 available; xAI did NOT publish a precise lab number for SWE-Verified at launch. Prior research's ~67 stands as best estimate.
- **SWE-bench Pro** — not on any aggregator; Scale SWE-Pro Public board not reachable from this environment. Likely unsubmitted by xAI.
- **LiveCodeBench v6 exact** — Vals shows rank 19/109 with 0.0% placeholder; no exact percentage published.
- **MMLU-Pro exact** — folded into BenchLM Knowledge category (75.4) only; no standalone score surfaced.
- **AIME 2024 / AIME 2025** — no published Grok-4.3 numbers found across AA, Vals, BenchLM, DFO, Kilo, ContraCollective, ProgressiveRobot. xAI evidently chose not to advertise math-olympiad scores at this launch (notable departure from Grok-4 launch posture).
- **MCP-Atlas** — no Grok-4.3 entry.
- **BrowseComp** — no Grok-4.3 entry.
- **OSWorld-Verified** — no Grok-4.3 entry.
- **FrontierMath T1-3 / T4** — no Grok-4.3 entry.
- **Toolathlon** — no Grok-4.3 entry.
- **GDPval** (pass-rate form, not Elo) — only Elo 1500 published.
- **Finance Agent** — Vals placeholder 0.0%; not yet evaluated.
- **CyberGym** — no Grok-4.3 entry.
- **CharXiv** — folded into BenchLM Multimodal category only.
- **MMMLU** — no Grok-4.3 entry.
- **ARC-AGI / ARC-AGI-2** — no Grok-4.3 entry.
- **Vending-Bench exact net worth $** — AndonLabs site 403s to fetcher; prior research's "1.26× Opus 4.7" lab claim stands as the only public datapoint. The derivation ~$13,781 (1.26 × $10,937) is computed, not published — leaving as derivation only per advisor discipline.
- **τ-bench retail / airline** — no Grok-4.3 entry (only τ²-Bench Telecom).
- **CritPt** — listed as evaluated in AAII v4.0 composite but no standalone Grok-4.3 score surfaced.

## Bonus finds

### Grok-4.20 / Grok-4.20 Multi-Agent

- Grok-4.20 Beta 0309 AAII: 48 [3p] src=https://x.com/ArtificialAnlys/status/2032150888530526411 publisher=ArtificialAnalysis date=2026-03 note=+6 over Grok-4 flagship
- Grok-4.20 0309 v2 AAII: 49 [3p] src=https://artificialanalysis.ai/models/grok-4-20 publisher=ArtificialAnalysis date=2026-03
- Grok-4.20 AA-Omniscience non-hallucination: 78% [3p] src=https://artificialanalysis.ai/models/grok-4-20 publisher=ArtificialAnalysis date=2026-03 note=AA describes as "best result seen for this metric"
- Grok-4.20 output speed: 267 tok/s [3p] src=https://artificialanalysis.ai/models/grok-4-20 publisher=ArtificialAnalysis date=2026-03 note=Pareto-frontier speed/intelligence
- Grok-4.20 0309 v2 GDPval-AA Elo: 1179 [3p] src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=baseline for Grok-4.3 "+321" delta
- Grok-4.20 BenchLM rank: #38/115 (overall 65/100) [3p] src=https://benchlm.ai/models/grok-4-20-beta publisher=BenchLM date=2026-05
- Grok-4.20 Multi-Agent context window: 2M tokens [3p] src=https://openrouter.ai/x-ai/grok-4.20-multi-agent publisher=OpenRouter date=2026-03

### Grok Code Fast 1

- SWE-Bench Verified: 70.8 [lab] src=https://x.ai/news/grok-code-fast-1 publisher=xAI-via-search-snippet date=2025 note=xAI internal harness, full subset; xAI itself caveats real-world generalization; no independent replication
- BenchLM specialist tier rank: #102/544 [3p] src=https://benchlm.ai/models/grok-code-fast-1 publisher=BenchLM date=2026-05

### Grok Build 0.1

- BenchLM tracked benchmarks: 0/221 (no published score) [3p] src=https://benchlm.ai/models/grok-build-0-1 publisher=BenchLM date=2026-05 note=released 2026-05-20 per benchable.ai; coding-agent product not a base model
- Speed percentile: 33rd [3p] src=https://benchlm.ai/models/grok-build-0-1 publisher=BenchLM date=2026-05
- Hallucinations: 100 / Ethics: 100 [3p] src=https://benchlm.ai/models/grok-build-0-1 publisher=BenchLM date=2026-05

### Notes on aliasing

- Grok-4.1 / 4.1 Fast: per Vals.ai page metadata, these aliases still resolve in routing tables but are referenced in 3p coverage from a confusing transition window (Grok-4.1 model card was Nov 2025; Grok-4.3 absorbed the alias when 4.20 was deprecated). Any 3p number post-2026-04-30 tagged "Grok-4.1" should be treated as ambiguous (could be Grok-4.3 routed traffic).
- Grok-4 Heavy: HLE 50.7% (with tools), 44.4% (Heavy with tools enabled), 24% (text-only no tools) [3p] src=multiple via search; these are legacy Grok-4 Heavy numbers, NOT Grok-4.3 Heavy (which does not exist as a separate API SKU per prior research's "'Heavy' is a consumer subscription tier" note).

## Methodology notes

- xAI blog (x.ai/news/*) returned 403 throughout; AndonLabs vending-bench page also 403; web.archive.org blocked by harness. All "lab"-tagged numbers above route via 3p (DesignForOnline carries the cleanest set; ContraCollective and ArtificialAnalysis fill in deltas).
- BenchLM individual benchmark scores were intentionally hidden ("source-unverified manual rows … hidden from model pages") — only category aggregates surfaced; this is a structural ceiling on what's recoverable for Grok-4.3 individual coding/knowledge/multimodal subscores from that source.
- Vals.ai Grok-4.3 page renders as 0.0% placeholders for most rows — eval coverage incomplete as of 2026-05. The visible Vals Index 46.63 is therefore composed from very few benchmark rows; treat as preliminary.
- Where lab and 3p disagree by rounding only (lab 97.7 → AA 98), recorded both with note. No >3pp lab-vs-3p disagreements found on numerical benchmarks.
