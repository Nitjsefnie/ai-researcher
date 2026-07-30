# Opus 4.7 deep benchmark fill

## New numbers for Opus 4.7

### Anthropic-published (system card / blog, lab)

- ARC-AGI-1: 92.0 [lab] src=https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh publisher=Anthropic-SystemCard date=2026-04 note=down from 4.6's 93.0
- ARC-AGI-2 Verified: 75.83 [lab] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Anthropic-SystemCard date=2026-04
- MRCR v2 8-needle @ 256k: 59.2 [lab] src=https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh publisher=Anthropic-SystemCard date=2026-04 note=regression vs 4.6's 91.9
- MRCR v2 8-needle @ 1M: 32.2 [lab] src=https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh publisher=Anthropic-SystemCard date=2026-04 note=regression vs 4.6's 78.3
- Graphwalks BFS 256K-1M: 58.6 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04 note=up from 4.6's 38.7; Anthropic-preferred long-context metric
- Graphwalks parents 256K-1M: 76.5 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- USAMO 2026: 69.3 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- DRACO: 77.7 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- LAB-Bench FigQA (with tools): 78.6 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04 note=up from 74.0
- LAB-Bench FigQA (without tools): 86.4 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- ScreenSpot-Pro: 79.5 [lab] src=https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh publisher=Anthropic-SystemCard date=2026-04 note=up from 69.0
- OSWorld (non-Verified): 77.9 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- VendingBench (mean net worth): $10,937 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- VendingBench (high-effort only): $7,971 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- BioPipelineBench: 83.6 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- BioMysteryBench: 78.9 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- Structural biology (system card sub-eval): 74 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- Organic chemistry (system card sub-eval): 77 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- Phylogenetics (system card sub-eval): 80 [lab] src=https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions publisher=Anthropic-SystemCard date=2026-04
- BigLaw Bench: 90.9 [lab] src=https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026 publisher=Anthropic-blog date=2026-04 note=at high effort
- DeepSearchQA F1: 89.1 [lab] src=https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh publisher=Anthropic-SystemCard date=2026-04 note=regression vs 4.6's 91.3
- SWE-bench Multilingual: 80.5 [lab] src=https://help.apiyi.com/en/claude-opus-4-7-benchmark-review-2026-en.html publisher=Anthropic-SystemCard date=2026-04
- HLE effort-scaling — Low: 43.0, Medium: 48.4, High: 53.2, XHigh: 55.4, Max: 54.7 [lab] src=https://allthings.how/claude-opus-4-7-system-card-key-findings-and-benchmarks/ publisher=Anthropic-SystemCard date=2026-04 note=XHigh > Max; "no tools" track of HLE 46.9 is a separate config
- Reward-hacking cheat rate: 45.0 default / 12.5 with anti-hack prompt [lab] src=https://allthings.how/claude-opus-4-7-system-card-key-findings-and-benchmarks/ publisher=Anthropic-SystemCard date=2026-04
- LlamaIndex ParseBench — Charts: 55.8, Formatting: 69.4, Content: 90.3, Tables: 87.2, Layout: 14.0 [3p] src=https://www.latent.space/p/ainews-anthropic-claude-opus-47-literally publisher=LlamaIndex date=2026-04 note=Layout regressed from 16.5; Charts huge jump from 13.5
- RULER @ 128k: ~85 [3p] src=https://blog.wentuo.ai/en/claude-opus-4-7-long-context-regression-en.html publisher=Wentuo date=2026-04 note=approximate
- Needle-in-haystack @ 1M: ~95 [3p] src=https://blog.wentuo.ai/en/claude-opus-4-7-long-context-regression-en.html publisher=Wentuo date=2026-04 note=approximate
- XBOW visual-acuity: 98.5 [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=XBOW-via-Anthropic date=2026-04 note=vs 4.6's 54.5

### AAII v4.0 components & 3p indices

- AA Intelligence Index v4.0: 57 (precise 57.3), rank #3 of 148 [3p] src=https://artificialanalysis.ai/models/claude-opus-4-7 publisher=ArtificialAnalysis date=2026-04 note=Adaptive Reasoning, Max Effort; composite of GDPval-AA, τ²-Telecom, Terminal-Bench Hard, SciCode, AA-LCR, AA-Omniscience, IFBench, HLE, GPQA Diamond, CritPt
- AA-Omniscience: 26 [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04 note=up from 4.6's 14
- AA-Omniscience hallucination rate: 36% [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04 note=down from 61% on 4.6
- AA-Omniscience attempt rate: 70% [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04
- Terminal-Bench Hard: 68.54 [3p] src=https://www.vals.ai/benchmarks/terminal-bench-2 publisher=Vals/ArtificialAnalysis date=2026-04 note=this is "Terminal-Bench 2.0" in AA's naming
- GDPval-AA Elo: 1753 [3p] src=https://artificialanalysis.ai/models/claude-opus-4-7 publisher=ArtificialAnalysis date=2026-04 note=ranked #1; this is the Elo form of the 80.3 GDPval pass-rate already collected
- IFBench: directional "+5.5 p.p. vs 4.6" — no absolute published [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04
- SciCode: directional "+2.6 p.p. vs 4.6" — no absolute published [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04
- AA-LCR: directional "equivalent to 4.6" [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04
- CritPt: directional "equivalent to 4.6" [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04
- τ²-Bench Telecom: directional "-3.5 p.p. vs 4.6" (regression); 4.6 was 99.3, so Opus 4.7 ~95.8 [3p] src=https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know publisher=ArtificialAnalysis date=2026-04 note=derived; AA leaderboard now headed by JT-35B-Flash 99.1 / GLM-4.7-Flash 98.8

### Vals.ai third-party leaderboard

- Vals Index: 66.10 ±1.36 [3p] src=https://www.vals.ai/models/anthropic_claude-opus-4-7 publisher=Vals.ai date=2026-04 note=rank 2/19; temp 1, max effort, 128k output. Kingy AI reported 71.47 — likely a prior snapshot or different aggregation
- LiveCodeBench (Vals): 84.69 [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Vals.ai date=2026-04 note=version not specified; Vals does not specify v5/v6
- GPQA (Vals): 89.90 [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Vals.ai date=2026-04 note=lower than Anthropic's 94.2 — different harness/sampling
- MMMU (Vals): 85.55 [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Vals.ai date=2026-04

### Other 3p / partner / domain

- MMMU (MindStudio): 84.1 [3p] src=https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown publisher=MindStudio date=2026-04
- MathVista: 79.3 [3p] src=https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown publisher=MindStudio date=2026-04
- DocVQA: 93.8 [3p] src=https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown publisher=MindStudio date=2026-04
- ChartQA: 88.2 [3p] src=https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown publisher=MindStudio date=2026-04
- FinanceBench: 82.7 [3p] src=https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown publisher=MindStudio date=2026-04
- OfficeQA Pro: 43.6 [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Databricks-via-Kingy date=2026-04 note=Databricks reports "21% fewer errors than 4.6"
- DualEntry Accounting AI Benchmark: 79.2 overall (Transactions/Journal 92, Month-End Close 50, Financial Reporting 62) [3p] src=https://www.dualentry.com/blog/claude-opus-4-7-accounting-ai-benchmark-results publisher=DualEntry date=2026-04 note=rank #1
- OTIS Mock AIME 2024-25: 97.8 ±2.2 (xhigh) [3p] src=https://lmcouncil.ai/benchmarks publisher=LMCouncil date=2026-04
- Vibe Code Benchmark: 71 [3p] src=https://www.latent.space/p/ainews-anthropic-claude-opus-47-literally publisher=Vibe-Code-Bench date=2026-04
- Sonar functional pass rate: 82.52 [3p] src=https://www.sonarsource.com/blog/claude-opus-4-7-evaluation publisher=Sonar date=2026-04 note=4,444 tasks; bug density 0.80/kLOC; cognitive complexity 171.22/kLOC
- Chatbot Arena Text Overall: 1492 Elo [3p] src=https://benchlm.ai/models/claude-opus-4-7 publisher=LMArena date=2026-05 note=13,571 votes; Coding 1552, Math 1499, IF 1495, Creative 1479, Multi-turn 1511, Hard 1518, Hard-EN 1522, Long-query 1513
- MCP-Atlas (Kingy table variant): 79.1 [3p] src=https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/ publisher=Kingy date=2026-04 note=conflicts with Anthropic blog's 77.3; possibly retest

### Partner-reported deltas (directional only)

- CodeRabbit: recall +>10% vs 4.6 [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=CodeRabbit date=2026-04
- Roadhouse Robotics: +13% on 93-task coding bench [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=Roadhouse date=2026-04
- Rakuten-SWE-Bench: 3x more production tasks resolved vs 4.6; double-digit gains in Code+Test Quality [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=Rakuten date=2026-04
- Notion Agent: +14% on complex workflows vs 4.6, 1/3 fewer tool errors [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=Notion date=2026-04
- Databricks OfficeQA Pro: 21% fewer errors vs 4.6 [3p] src=https://www.anthropic.com/news/claude-opus-4-7 publisher=Databricks date=2026-04

### Benchmarks confirmed unreported / no number found

- **LiveCodeBench v6 pass@1**: no Anthropic or PricePerToken number; only Vals composite "LiveCodeBench 84.69" available
- **LiveCodeBench Pro Elo**: not in any source seen
- **AIME 2024**: not reported (AIME 2025 96.2 and OTIS Mock 97.8 already in hand)
- **Toolathlon**: explicit "not reported by Anthropic"; GPT-5.5 holds at 55.6
- **τ-bench retail/airline**: no Opus 4.7 number found on any leaderboard
- **MATH-500 / GSM8K / HumanEval+ / IFEval**: not reported in any source
- **METR Time Horizons**: Opus 4.7 not in LMCouncil top-5 (table shows "Show all 10" exists; not surfaced)
- **WeirdML v2**: not in LMCouncil top-5
- **GSO / WebDev Arena**: Opus 4.7 not in LMCouncil top-5
- **SciCode / IFBench / AA-LCR / CritPt absolute %**: AA publishes only directional p.p. deltas in the launch article; PNG leaderboard charts on AA pages are JS-rendered and not extractable via WebFetch
- **MMLU-Pro on PricePerToken**: PricePerToken's LCB leaderboard does not include 4.7

## Bonus finds

### Claude Mythos Preview (Anthropic gated)

- SWE-bench Verified: 93.9 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- SWE-bench Pro: 77.8 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- SWE-bench Multilingual: 87.3 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- SWE-bench Multimodal: 59.0 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- Terminal-Bench 2.0: 82.0 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- Terminal-Bench 2.1 (4-hour timeout): 92.1 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- USAMO 2026: 97.6 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- GPQA Diamond: 94.5 (also reported as 94.6 elsewhere) [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- MMMLU: 92.7 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- HLE (no tools): 56.8 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- HLE (with tools): 64.7 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- CharXiv Reasoning (no tools): 86.1 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- CharXiv Reasoning (with tools): 93.2 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- Graphwalks BFS 256K-1M: 80.0 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- OSWorld: 79.6 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026
- BrowseComp: 86.9 [lab] src=https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026 publisher=Anthropic date=2026 note=4.9x fewer tokens than 4.6
- MCP-Atlas: not scored (Anthropic skipped per source)

### GPT-5.5

- Terminal-Bench Hard (AA leaderboard top): 60.6 [3p] src=https://artificialanalysis.ai/evaluations/terminalbench-hard publisher=ArtificialAnalysis date=2026-04 note=xhigh effort
- Terminal-Bench 2.0 (Vals): 73.20 [3p] src=https://www.vals.ai/benchmarks/terminal-bench-2 publisher=Vals date=2026-04 note=#1 on leaderboard
- Toolathlon: 55.6 [3p] src=search-result-aggregation publisher=OpenAI date=2026-04
- τ²-Bench Telecom: 98.0 [3p] src=https://www.analyticsvidhya.com/blog/2026/04/gpt-5-5-vs-opus-4-7/ publisher=Sierra-via-OpenAI date=2026-04
- ARC-AGI: 95.0 [3p] src=https://www.analyticsvidhya.com/blog/2026/04/gpt-5-5-vs-opus-4-7/ publisher=OpenAI date=2026-04
- MMLU-Pro: 88.14 [3p] src=https://llm-stats.com/blog/research/gpt-5-5-vs-claude-opus-4-7 publisher=llm-stats date=2026-04
- SWE-bench Pro (Scale leaderboard, GPT-5.4 entry): 59.10 ±3.56 [3p] src=https://labs.scale.com/leaderboard/swe_bench_pro_public publisher=Scale date=2026-04
- DualEntry Accounting (GPT-5.4): 77.3 [3p] src=https://www.dualentry.com/blog/claude-opus-4-7-accounting-ai-benchmark-results publisher=DualEntry date=2026-04

### Gemini 3.1 Pro

- LiveCodeBench Pro Elo: 2887 [3p] src=search-result-aggregation publisher=LiveCodeBench-Pro date=2026-04 note=leader
- SWE-bench Verified: 80.6 [3p] src=https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained publisher=Anthropic-comparison date=2026-04
- Terminal-Bench 2.0 (Vals): 67.42 [3p] src=https://www.vals.ai/benchmarks/terminal-bench-2 publisher=Vals date=2026-04
- SWE-bench Pro Public (Scale): 46.10 ±3.60 [3p] src=https://labs.scale.com/leaderboard/swe_bench_pro_public publisher=Scale date=2026-04
- MCP-Atlas: 69.2 [3p] src=mythos-comparison publisher=Anthropic date=2026-04
- BrowseComp: 85.9 [3p] src=mythos-comparison publisher=Anthropic date=2026-04
- GPQA Diamond: 94.3 [3p] src=https://www.analyticsvidhya.com/blog/2026/04/gpt-5-5-vs-opus-4-7/ publisher=Google date=2026-03

### Opus 4.6 (updated numbers vs prior recordings)

- CyberGym (restated in 4.7 launch): 73.8 [lab] src=https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026 publisher=Anthropic date=2026-04 note=revision

## Sources cited

- https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
- https://artificialanalysis.ai/articles/opus-4-7-everything-you-need-to-know
- https://artificialanalysis.ai/models/claude-opus-4-7
- https://artificialanalysis.ai/evaluations/terminalbench-hard
- https://artificialanalysis.ai/evaluations/tau2-bench
- https://artificialanalysis.ai/evaluations/ifbench
- https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained
- https://lmcouncil.ai/benchmarks
- https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026
- https://www.mindstudio.ai/blog/claude-opus-47-benchmark-breakdown
- https://www.vals.ai/benchmarks/terminal-bench-2
- https://www.vals.ai/models/anthropic_claude-opus-4-7
- https://www.codesota.com/llm
- https://kingy.ai/uncategorized/gpt-5-5-vs-claude-opus-4-7-a-benchmark-by-benchmark-field-guide-to-the-new-frontier/
- https://benchlm.ai/models/claude-opus-4-7
- https://pricepertoken.com/leaderboards/benchmark/livecodebench
- https://labs.scale.com/leaderboard/swe_bench_pro_public
- https://www.swebench.com/
- https://dev.to/ji_ai/i-read-all-232-pages-of-the-opus-47-system-card-28mh
- https://allthings.how/claude-opus-4-7-system-card-key-findings-and-benchmarks/
- https://www.latent.space/p/ainews-anthropic-claude-opus-47-literally
- https://blog.wentuo.ai/en/claude-opus-4-7-long-context-regression-en.html
- https://www.anthropic.com/news/claude-opus-4-7
- https://thezvi.substack.com/p/opus-47-part-2-capabilities-and-reactions
- https://help.apiyi.com/en/claude-opus-4-7-benchmark-review-2026-en.html
- https://www.datacamp.com/tutorial/opus-4-7-project
- https://www.dualentry.com/blog/claude-opus-4-7-accounting-ai-benchmark-results
- https://www.sonarsource.com/blog/claude-opus-4-7-evaluation
- https://www.stampr-ai.com/data/models/cards/claude-opus-4-7/claude-opus-4-7_20260416_153246_a7729a0e_stamped.pdf
- https://www.nxcode.io/resources/news/claude-mythos-benchmarks-93-swe-bench-every-record-broken-2026
- https://www.analyticsvidhya.com/blog/2026/04/gpt-5-5-vs-opus-4-7/
- https://llm-stats.com/blog/research/gpt-5-5-vs-claude-opus-4-7
- https://mindwiredai.com/2026/04/24/gpt-5-5-is-here-benchmarks-pricing-and-who-should-actually-upgrade-april-2026/
