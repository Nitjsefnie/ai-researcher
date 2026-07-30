# Gemini 3.5 Flash deep benchmark fill

Date: 2026-05-23. Model launched 2026-05-19 GA, 4 days old. Sources are sparse and mostly re-report the lab numbers.

## New numbers for Gemini 3.5 Flash

### Google-published (lab)

Source: official evaluation PDF at `https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf` (redirected from `deepmind.google/models/evals-methodology/gemini-3-5-flash`). All numbers pass@1, single attempt, default sampling, May 2026.

**Configuration clarifications for benchmarks I already had:**
- CharXiv Reasoning: **84.2% [No tools]** — confirmed no-tools config; with-tools NOT published src=evaluation PDF
- MMMU-Pro: **83.6% [No tools]** — averaged across Standard (10 options) and Vision settings src=evaluation PDF
- Humanity's Last Exam: **40.2% [full set, text + MM]** — single combined number; no with-tools / no-tools split published src=evaluation PDF
- MRCR v2 128k: **77.3% [8-needle, average]** — config detail src=evaluation PDF
- Terminal-Bench 2.1: **76.2% [Terminus-2 harness only]** src=evaluation PDF
- SWE-Bench Pro (Public): **53.9% [single attempt, 5-run average, Antigravity-internal harness]** src=evaluation PDF
  - **DISCREPANCY ALERT**: the deepmind.google/models/gemini/flash/ landing page and ~all 3p re-reports list 55.1%. The official evaluation PDF (more authoritative, dated "as of May 2026") gives 53.9%. Both are Google numbers from the same week — likely 55.1 is pre-finalization and 53.9 is the 5-run-averaged final. Prefer 53.9% with 55.1% as an alt.

**New numbers not previously in the registry:**
- OSWorld-Verified: **78.4% [default, 5-run avg, 1080p, max 100 steps, pyautogui]** src=evaluation PDF date=2026-05 note=self-computed
- Blueprint-Bench 2 (normalized): **33.6%** src=evaluation PDF publisher=Google date=2026-05 note=Andon Labs leaderboard, 0-100 normalized

### 3p / aggregator

- **Chatbot Arena Text Overall: 1480 Elo (rank 9)** [3p] src=https://arena.ai/leaderboard publisher=LMArena date=2026-05 note=added 2026-05-19
- **Chatbot Arena WebDev: 1507 Elo (rank 9)** [3p] src=https://arena.ai/leaderboard publisher=LMArena date=2026-05
- **Chatbot Arena Math: rank 1 (BenchLM gives 1521 Elo)** [3p] src=https://benchlm.ai/models/gemini-3-5-flash publisher=BenchLM/LMArena date=2026-05
- **Chatbot Arena Instruction Following: 1471 Elo (rank 14)** [3p] src=https://benchlm.ai/models/gemini-3-5-flash publisher=BenchLM/LMArena date=2026-05
- Chatbot Arena category ranks: Expert 14, Hard Prompts 16, Coding 31, Creative Writing 9, Longer Query 20 [3p] src=https://arena.ai/leaderboard date=2026-05
- **Artificial Analysis Intelligence Index v4.0: 55** [3p] src=https://artificialanalysis.ai/models/gemini-3-5-flash publisher=Artificial Analysis date=2026-05 note=rank #7 of 147; "high" reasoning variant
- **AAII v4.0 (Gemini 3.5 Flash minimal variant): 43** [3p] src=https://artificialanalysis.ai/models/gemini-3-5-flash-minimal publisher=Artificial Analysis date=2026-05 note=NEW VARIANT — minimal-reasoning SKU exists, separate AAII score
- **GPQA Diamond: 92.2%** [3p] src=https://pricepertoken.com/leaderboards/benchmark/gpqa publisher=PricePerToken date=2026-05-23 note=99th pctile, rank 2 overall
- **PPT Coding composite: 45.0 (96th pctile)** [3p] src=https://pricepertoken.com/pricing-page/model/google-gemini-3.5-flash date=2026-05
- **Appwrite Arena (with Skills): 96.20% overall** [3p] src=https://appwrite.io/blog/post/gemini-3-5-flash-deep-dive date=2026-05
- **Appwrite Arena (without Skills): 90.70% overall** [3p] src=https://appwrite.io/blog/post/gemini-3-5-flash-deep-dive date=2026-05
- **Hallucination rate: 61%** [3p] src=https://appwrite.io/blog/post/gemini-3-5-flash-deep-dive publisher=Appwrite/AA date=2026-05
- BenchLM category indices: Agentic 97.3 (rank 3), Coding 78.3 (rank 22), Reasoning 80.8 (rank 16), Knowledge 83.8, Multimodal 80.6 (rank 17), Instruction Following 79.3 (rank 37) [3p] src=https://benchlm.ai/models/gemini-3-5-flash date=2026-05

### Confirmed unreported (after thorough search)

Google did NOT publish any of these for 3.5 Flash. They are either entirely absent from the lab eval card or replaced by a sibling benchmark (e.g. SWE-Bench Pro replaces SWE-bench Verified; tau-bench replaced by tau2-Bench Telecom inside AAII; MMLU-Pro / AIME / LCB silently dropped):

- **SWE-bench Verified**: not in lab card. 3p search returned "78%" but verified that's Gemini 3 Flash, NOT 3.5 Flash. No 3.5 Flash SWE-V published anywhere.
- **SWE-bench Multilingual / Multimodal**: not published
- **LiveCodeBench v6 pass@1**: not in lab card. PricePerToken LCB leaderboard does NOT list 3.5 Flash (only Gemini 3 Pro Preview 91.7% and Gemini 3 Flash Preview 90.8%, both different models). 3.5 Flash absent.
- **LiveCodeBench Pro Elo**: not published
- **Terminal-Bench 2.0**: superseded by 2.1; only 2.1 published
- **AIME 2024**: not published
- **AIME 2025**: not in lab card. BenchLM shows AIME 2025 as 0.0 (no data tracked) for this model.
- **MMLU-Pro**: not published. (BenchLM "80.6" was multimodal-category index, not MMLU-Pro)
- **MMMLU**: not published
- **BrowseComp**: not published
- **OSWorld (non-Verified)**: only OSWorld-Verified published
- **CyberGym**: not published
- **USAMO 2026, MATH-500, GSM8K**: not published (saturated/deprecated)
- **FrontierMath T1-3 / T4**: not published for 3.5 Flash
- **Graphwalks BFS/Parents**: not published
- **Vending-Bench (mean net worth)**: not published
- **GDPval (base, not -AA)**: only GDPval-AA (1656 Elo) published
- **MMMU (base, not Pro)**: not published
- **MathVista, DocVQA, ChartQA**: not published
- **FinanceBench, BigLaw Bench (Vals.ai)**: Vals.ai model page returned 404 — Gemini 3.5 Flash not yet indexed there as of 2026-05-23
- **τ-bench retail / airline**: not published (subsumed by τ²-Bench Telecom inside AAII, component score not separately disclosed)
- **τ²-Bench Telecom (standalone)**: only as AAII component; individual number behind interactive chart, not extractable from text content
- **AAII components (AA-Omniscience, AA-LCR, SciCode, IFBench, Terminal-Bench Hard, CritPt, APEX-Agents-AA absolute scores)**: only composite 55 / 43 published in text; individual component values gated behind AA interactive charts
- **PricePerToken LCB / MMLU-Pro / AIME**: all marked "—" (no data) for 3.5 Flash; only GPQA and Coding composite populated
- **ScreenSpot-Pro**: not published
- **Sonar functional pass rate** and other partner numbers: no partner published reviews surfaced

### Already had (no change)

Terminal-Bench 2.1 76.2, MCP-Atlas 83.6, Toolathlon 56.5, Finance Agent v2 57.9, ARC-AGI-2 72.1, MRCR v2 1M pointwise 26.6, GDPval-AA Elo 1656.

## Bonus finds

### Gemini 3.5 Flash — variant disclosure

There is a "minimal" reasoning-effort variant on Artificial Analysis with its own SKU and lower AAII (43 vs 55 for "high"). The lab card and model card show only one model; AA splits it by reasoning-budget setting. Worth treating as a separate row in any registry.

### Cross-model numbers extracted from the same Google evaluation PDF (table is canonical; useful for 3p-corroborating other model rows)

All numbers below are Google's self-computed comparison column from the same PDF table, dated 2026-05. They differ from each lab's own reporting and should be tagged "3p, Google-reported".

**Gemini 3 Flash** (older Flash, comparison column):
- Terminal-Bench 2.1: 58.0%, SWE-Bench Pro Public: 48.4%, MCP Atlas: 62.0%, Toolathlon: 49.4%, OSWorld-Verified: 65.1%, Finance Agent v2: 42.6%, GDPval-AA: 1204 Elo, CharXiv (no-tools): 80.3%, MMMU-Pro (no-tools): 81.2%, Blueprint-Bench 2: 0.0%, MRCR 128k: 67.2%, MRCR 1M: 22.1%, HLE: 33.7%, ARC-AGI-2: 33.6%

**Gemini 3.1 Pro** (Google-reported in same table):
- Terminal-Bench 2.1: 70.3%, SWE-Bench Pro Public: 54.2%, MCP Atlas: 78.2% (vs 69.2 we had — sizable upward revision), Toolathlon: not reported, OSWorld-Verified: 76.2%, Finance Agent v2: 43.0%, GDPval-AA: 1314 Elo, CharXiv (no-tools): 83.3%, MMMU-Pro (no-tools): 80.5%, Blueprint-Bench 2: 26.5%, MRCR 128k: 84.9%, MRCR 1M: 26.3%, HLE: 44.4%, ARC-AGI-2: 77.1%

**Claude Sonnet 4.6** (Google-reported, "best available reasoning"):
- Terminal-Bench 2.1: not reported, SWE-Bench Pro: 53.0%, MCP Atlas: 69.5%, OSWorld-Verified: 72.5%, Finance Agent v2: 51.0%, GDPval-AA: 1674 Elo, CharXiv: 70.5%, MMMU-Pro: 74.5%, Blueprint-Bench 2: 6.7%, MRCR 128k: 84.9%, HLE: 33.2%, ARC-AGI-2: 58.3%

**Claude Opus 4.7** (Google-reported, "max thinking"):
- Terminal-Bench 2.1: 66.1%, SWE-Bench Pro: 64.3%, MCP Atlas: 79.1%, OSWorld-Verified: 78.0%, Finance Agent v2: 51.5%, GDPval-AA: 1753 Elo, CharXiv: 82.1%, MMMU-Pro: 75.2%, Blueprint-Bench 2: 24.5%, MRCR 128k: 59.3%, HLE: 46.9%, ARC-AGI-2: 75.8%

**GPT-5.5** (Google-reported, max reasoning):
- Terminal-Bench 2.1: 78.2%, SWE-Bench Pro: 58.6%, MCP Atlas: 75.3%, Toolathlon: 55.6%, OSWorld-Verified: 78.7%, Finance Agent v2: 51.8%, GDPval-AA: 1773 Elo, CharXiv: 84.1%, MMMU-Pro: 81.2%, Blueprint-Bench 2: 36.2%, MRCR 128k: 94.8% (not-supported on 1M), HLE: 41.4%, ARC-AGI-2: 85.0%

Note: these Opus 4.7 / Sonnet 4.6 / GPT-5.5 cross-tab numbers are useful as third-party corroborating numbers but should NOT replace each lab's own primary numbers — they are Google's read of competitor self-reports, with Google's choice of which reasoning setting to surface.

## Sources cited

- https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf — official Google evaluation PDF (PRIMARY)
- https://deepmind.google/models/gemini/flash/ — lab family page
- https://deepmind.google/models/model-cards/gemini-3-5-flash/ — model card
- https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/ — launch blog
- https://artificialanalysis.ai/models/gemini-3-5-flash — AAII v4.0 = 55 (high variant)
- https://artificialanalysis.ai/models/gemini-3-5-flash-minimal — AAII = 43 (minimal variant)
- https://artificialanalysis.ai/articles/gemini-3-5-flash-everything-you-need-to-know — launch article
- https://benchlm.ai/models/gemini-3-5-flash — Arena Elo + category indices
- https://arena.ai/leaderboard — LMArena (rank 9 text, rank 1 math)
- https://pricepertoken.com/pricing-page/model/google-gemini-3.5-flash — GPQA 92.2 + composites
- https://pricepertoken.com/leaderboards/benchmark/gpqa — GPQA leaderboard
- https://pricepertoken.com/leaderboards/benchmark/livecodebench — confirms LCB unreported for 3.5 Flash
- https://appwrite.io/blog/post/gemini-3-5-flash-deep-dive — Appwrite arena, hallucination rate
- https://www.nxcode.io/resources/news/gemini-3-5-flash-complete-guide-benchmarks-pricing-api-2026 — re-report
- https://wavespeed.ai/blog/posts/gemini-3-5-flash-shipped-leads-agent-benchmarks/ — re-report
- https://www.buildfastwithai.com/blogs/gemini-3-5-flash-review-benchmarks-price-api — re-report
- https://www.digitalapplied.com/blog/gemini-3-5-flash-benchmarks-api-guide — re-report
- https://www.datacamp.com/blog/gemini-3-5-flash — re-report
- https://handyai.substack.com/p/model-drop-gemini-35-flash — re-report
- https://www.aimadetools.com/blog/gemini-3-5-flash-complete-guide/ — re-report
- https://www.marktechpost.com/2026/05/20/google-introduces-gemini-3-5-flash-at-i-o-2026-a-faster-and-cheaper-model-for-ai-agents-and-coding/ — launch coverage
- https://llm-stats.com/blog/research/gemini-3.5-flash-launch — re-report
- https://llm-stats.com/models/gemini-3.5-flash — no scored fields populated
- https://www.codesota.com/llm — does not yet list 3.5 Flash
