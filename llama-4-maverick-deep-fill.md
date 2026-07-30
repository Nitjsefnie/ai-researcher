# Llama 4 Maverick — deep-fill benchmarks

Model: `meta-llama/Llama-4-Maverick-17B-128E-Instruct` · released 2025-04-05 · 17B active / 400B total / 128 experts · 1M context.
Date of compilation: 2026-05-23. Numbers below are new vs. the prior dossier.

## New numbers (lab — Meta)

| Benchmark | Score | Source |
|---|---|---|
| Multilingual MMLU (Global MMLU) | **84.6** | [llama.com/models/llama-4](https://www.llama.com/models/llama-4/), [analyticsvidhya](https://www.analyticsvidhya.com/blog/2025/04/meta-llama-4/) |
| MTOB (half book) eng→kgv / kgv→eng, chrF | **54.0 / 46.4** | [HF model card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) |
| MTOB (full book) eng→kgv / kgv→eng, chrF | **50.8 / 46.7** | [HF model card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) |
| ChartQA (pretrained, relaxed_acc) | 85.3 | [HF model card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) |
| DocVQA (pretrained, anls) | 91.6 | [HF model card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) |
| TydiQA (pretrained, multilingual avg F1) | **31.7** | [HF model card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) |

MTOB is the long-context translation eval Meta ships in lieu of RULER/MRCR. It's a half/full-book Kalamang translation chrF, not a generic retrieval probe.

## New numbers (3p)

| Benchmark | Score | Source |
|---|---|---|
| LMArena Elo (Llama-4-Maverick-03-26-Experimental) | **1417** | [lmarena.ai tweet](https://x.com/lmarena_ai/status/1908601011989782976), [Meta announcement](https://ai.meta.com/blog/llama-4-multimodal-intelligence/) |
| SWE-bench Pro Public (Scale, rank 23) | **5.24 ± 1.24** | [labs.scale.com/leaderboard/swe_bench_pro_public](https://labs.scale.com/leaderboard/swe_bench_pro_public) |
| Fiction.live long-context @ 120K tokens | **28.1%** | [the-decoder coverage](https://the-decoder.com/metas-llama-4-models-show-promise-on-standard-tests-but-struggle-with-long-context-tasks/) |
| Phare — Avg Safety | **70.84%** | [phare.giskard.ai](https://phare.giskard.ai/models/llama-4-maverick/) |
| Phare — Hallucination resistance | 71.47% | [phare.giskard.ai](https://phare.giskard.ai/models/llama-4-maverick/) |
| Phare — Harm resistance | 89.25% | [phare.giskard.ai](https://phare.giskard.ai/models/llama-4-maverick/) |
| Phare — Bias resistance | 73.65% | [phare.giskard.ai](https://phare.giskard.ai/models/llama-4-maverick/) |
| Phare — Jailbreak resistance | 48.99% | [phare.giskard.ai](https://phare.giskard.ai/models/llama-4-maverick/) |
| Epoch Capabilities Index (ECI) | **133** (rank 81/172, 90% CI 126–135) | [epoch.ai/models/llama-4-maverick](https://epoch.ai/models/llama-4-maverick) |
| AA Intelligence Index — launch (v?, Apr 2025) | **49** | [AA blog via LinkedIn](https://www.linkedin.com/pulse/llama-4-independent-benchmarks-maverick-402b-total-b4bmc) |

Important caveats:

- **LMArena 1417 is the experimental `Llama-4-Maverick-03-26-Experimental` checkpoint**, not the released weights. Meta confirmed (and TechCrunch / LeCun) that the LMArena submission was tuned for chat-preference voting (verbose, emoji-heavy). Don't read it as the public model's Elo. The publicly released Maverick ranks "below rivals" on LMArena per TechCrunch's Apr 11 follow-up.
- **AA Intelligence Index: 49 at launch (Apr 2025) → 18 on v4.0 (May 2026)**. Same model, different composite scale and eval mix. Both numbers are AA, just different vintages — the v4.0=18 you already have is the current one; 49 is the historical Apr-2025 figure for cross-time reading.
- **AA itself notes Maverick's MMLU-Pro and GPQA Diamond come in materially lower** when AA runs them vs. Meta's reported numbers. AA did not publish the divergent raw numbers in the LinkedIn write-up, only the qualitative note.
- **Phare jailbreak 48.99%** is the only sub-50 metric — Maverick's jailbreak robustness is its weakest safety axis per Phare.

## Confirmed unreported

Searched across Meta's announcement + model card, AA per-eval pages, llm-stats, BenchLM, OpenRouter, NVIDIA NIM, Phare, Vellum leaderboard, Vals.ai (404), Epoch, Oracle, the-decoder, TechCrunch coverage, and the LinkedIn AA writeup. The following are not published for Maverick anywhere I could find:

- **SWE-bench Verified** (Meta did not publish; only SWE-Pro Public via Scale exists)
- **AIME 2024**, **AIME 2025** (Maverick does NOT appear on AA's AIME-2025 leaderboard — it's a non-reasoning model and AA dropped it from the eval set)
- **HLE no-tools / with-tools** (Maverick not on AA HLE leaderboard)
- **Terminal-Bench 1.0 / 2.0 / Hard** (not on AA's TB-Hard leaderboard)
- **MCP-Atlas**, **Toolathlon**, **GDPval pass-rate / Elo**, **CritPt**, **AA-LCR**, **AA-Omniscience**, **IFBench**, **SciCode**, **τ²-Bench Telecom** — all AA composite components, but Maverick is below display cutoff on the per-eval pages I checked (HLE, Terminal-Bench-Hard, IFBench, SciCode all top-15 displays do not include Maverick; AA may have aggregated scores internally but does not surface them per-eval)
- **FrontierMath T1-3 / T4**
- **ARC-AGI**, **ARC-AGI-2**
- **BrowseComp**
- **OSWorld** / **OSWorld-Verified**
- **Finance Agent v1.1 / v2**
- **CyberGym**
- **CharXiv Reasoning** (no-tools / with-tools)
- **MMMLU** (Meta reports Multilingual MMLU = 84.6 on their card; there is no separate MMMLU number)
- **τ-bench retail / airline** (the τ-bench llm-stats leaderboard doesn't list Maverick)
- **MRCR**, **Graphwalks**, **RULER** (Meta substituted MTOB for long-context; no RULER/MRCR/Graphwalks numbers exist)
- **HumanEval+**, **MATH-500**, **GSM8K**, **MBPP** for the **Instruct** variant (Meta published MBPP=77.6 and MATH=61.2 for pretrained only; instruct numbers for these legacy benches are unpublished)
- **Vending-Bench**

This is unusually thin for a flagship — partly because Maverick launched April 2025, before many 2025-2026 frontier benches were standardized; partly because Meta's eval philosophy with Llama 4 was "win on Arena and a small curated set," which became the LMArena controversy.

## Disputed / unverifiable

`tokenmix.ai/blog/llama-4-maverick-review` is the only source attributing instruct-side numbers for SWE-bench Verified (74.2), HumanEval (91.5), MBPP (89.5), MATH-500 (85.3), GSM8K (95.2), MMLU (91.8), MMLU-Pro (77.1), GPQA Diamond (65.8), IFEval (86), ARC-Challenge (97.0), HellaSwag (96.1). These conflict with Meta's own model card (MMLU 85.5 pretrained, MMLU-Pro 80.5 instruct, GPQA Diamond 69.8). Pattern (round numbers, ~5-7pp inflated in one direction vs. the official card, undated 2026 "review" of an April-2025 model, no citations to underlying eval runs) reads as SEO-generated content, not primary measurement. **Do not adopt these as Maverick numbers.**

## Bonus finds

### Llama 4 Scout (`Llama-4-Scout-17B-16E-Instruct`, 17B active / 109B total / 10M context)

From [llama.com/models/llama-4](https://www.llama.com/models/llama-4/) + [HF Maverick card](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct) (sibling table):

| Benchmark | Scout |
|---|---|
| MMMU | 69.4 |
| MathVista | 70.7 |
| ChartQA | 88.8 |
| DocVQA (test) | 94.4 |
| LiveCodeBench (10/24–02/25, pass@1) | 32.8 |
| MMLU Pro | 74.3 |
| GPQA Diamond | 57.2 |
| MTOB half-book eng→kgv / kgv→eng | 42.2 / 36.6 |
| MTOB full-book eng→kgv / kgv→eng | 39.7 / 36.3 |

AA independent Intelligence Index at launch: **36** ([AA tweet](https://x.com/ArtificialAnlys/status/1908890796415414430)).

### Llama 4 Behemoth (288B active / ~2T total — never publicly released)

Meta's announcement claims Behemoth "outperforms GPT-4.5, Claude Sonnet 3.7, and Gemini 2.0 Pro on several STEM benchmarks" specifically calling out **MATH-500** and **GPQA Diamond** — but published no numbers. Behemoth has remained unreleased as of May 2026 ([Meta announcement](https://ai.meta.com/blog/llama-4-multimodal-intelligence/)).

### Llama 3.3 70B context

Fiction.live @ 120K: Maverick **28.1%** — Fiction.live notes "Maverick showed no improvement over Llama 3.3 70B" at long context ([the-decoder](https://the-decoder.com/metas-llama-4-models-show-promise-on-standard-tests-but-struggle-with-long-context-tasks/)). Implies Llama 3.3 70B ~28% at 120K (not directly stated).

### LMArena controversy summary

The 1417 Elo (#2 overall, #1 open-weight) was the `03-26-Experimental` checkpoint — confirmed by Meta to be tuned for Arena voter preferences, not the released model. After LMArena disclosure of the divergence (Apr 11, 2025), the released Maverick re-tested and ranked **below GPT-4o, Gemini 1.5 Pro, Claude 3.5 Sonnet** ([TechCrunch](https://techcrunch.com/2025/04/11/metas-vanilla-maverick-ai-model-ranks-below-rivals-on-a-popular-chat-benchmark/)). LMArena subsequently updated their policy on benchmark gaming. This is the canonical "benchmark manipulation" episode for Llama 4 and the reason AA's independently-measured numbers diverge downward from Meta's.
