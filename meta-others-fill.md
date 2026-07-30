# Meta Llama (non-Maverick) — Frontier-18 Fill

Research conducted 2026-05-23. Source taxonomy: `lab` = Meta-published (HF model card / llama.com / Llama paper). `3p:<publisher>` = third-party evaluator (Artificial Analysis, Vellum, Scale, Designforonline, etc.).

Note on the Artificial Analysis (AA) mirror: `designforonline.com` reproduces AA's disaggregated component scores per-model. AA's Intelligence-Index v4.0 uses these benchmarks: GDPval-AA, τ²-Bench Telecom, Terminal-Bench Hard, SciCode, AA-LCR, AA-Omniscience, IFBench, HLE, GPQA Diamond, CritPt. Where AA publishes a number for one of those, it counts as `3p:AA`.

---

## Llama 4 Scout (17B active / 109B total / 16 experts; released 2025-04-05)

- **swebVer**: confirmed unreported. Meta did NOT publish SWE-bench Verified. Web folklore quotes "68%" or "54.6%" but both fail to source — 54.6 is GPT-4.1's score; 68 has no primary citation. [lab silence: HF card, llama.com both report only LiveCodeBench for coding]
- **swebPro**: confirmed unreported (not on Scale public leaderboard; only Maverick "Llama4-maverick-17b-instruct" entry exists at 5.24±1.24). src=https://labs.scale.com/leaderboard/swe_bench_pro_public date=2026-05
- **tb**: 1.5% [3p:AA, Terminal-Bench Hard] src=https://designforonline.com/ai-models/meta-llama-4-scout/ date=2026-05
- **gdpval**: confirmed unreported as a specific percentage (AA includes GDPval-AA in Index but the disaggregated row for Scout is not exposed via designforonline or the AA model page); the Intelligence Index composite = 14. src=https://artificialanalysis.ai/models/llama-4-scout date=2026-05
- **gpqa**: 57.2% [lab, 0-shot accuracy, GPQA-Diamond] src=https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct date=2025-04 — AA's independent re-measurement gives 58.7% [3p:AA] src=https://designforonline.com/ai-models/meta-llama-4-scout/ date=2026-05
- **hleNoTools**: 4.3% [3p:AA] src=https://designforonline.com/ai-models/meta-llama-4-scout/ date=2026-05
- **hleWithTools**: confirmed unreported
- **frontierMathT13**: confirmed unreported (no Llama entries on the FrontierMath leaderboard, which only lists 13 OpenAI models). src=https://llm-stats.com/benchmarks/frontiermath date=2026-05
- **frontierMathT4**: confirmed unreported
- **mcpAtlas**: confirmed unreported
- **browseComp**: confirmed unreported
- **toolathlon**: confirmed unreported
- **osworldV**: confirmed unreported
- **financeAgent**: confirmed unreported
- **cyberGym**: confirmed unreported
- **charXivNoTools**: confirmed unreported (Scout reports ChartQA 88.8%, DocVQA 94.4%, MMMU 69.4% — visual-reasoning suite, but not CharXiv)
- **charXivWithTools**: confirmed unreported
- **mmmlu**: confirmed unreported. Meta's own card reports plain MMLU (79.6, 5-shot) and MMLU-Pro (74.3, 0-shot instruct) but no Multilingual MMLU; the multilingual eval Meta provides is MGSM = 90.6.

---

## Llama 3.3 70B Instruct (dense 70B; released 2024-12-06)

- **swebVer**: confirmed unreported. Not on Meta card; not on Vellum (Vellum reports SWE-bench Verified for 3.1 405B but blank for 3.3 70B).
- **swebPro**: confirmed unreported (not on Scale leaderboard). src=https://labs.scale.com/leaderboard/swe_bench_pro_public date=2026-05
- **tb**: confirmed unreported. AA Index 4.0 includes Terminal-Bench Hard as a component, but the Scout-style disaggregated row is not published for 3.3 70B (composite Intelligence Index = 14). src=https://artificialanalysis.ai/models/llama-3-3-instruct-70b date=2026-05
- **gdpval**: confirmed unreported (same as above; Index components for 3.3 70B not disaggregated publicly).
- **gpqa**: 50.5% [lab, GPQA-Diamond, 0-shot, CoT] src=https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct date=2024-12
- **hleNoTools**: confirmed unreported
- **hleWithTools**: confirmed unreported
- **frontierMathT13**: confirmed unreported
- **frontierMathT4**: confirmed unreported
- **mcpAtlas**: confirmed unreported
- **browseComp**: confirmed unreported
- **toolathlon**: confirmed unreported
- **osworldV**: confirmed unreported
- **financeAgent**: confirmed unreported
- **cyberGym**: confirmed unreported
- **charXivNoTools**: confirmed unreported (Llama 3.3 is text-only; no visual-reasoning suite at all)
- **charXivWithTools**: confirmed unreported
- **mmmlu**: confirmed unreported. Meta reports MGSM 91.1 (multilingual math, not MMMLU); standard MMLU 86.0, MMLU-Pro 68.9.

---

## Llama 3.1 405B Instruct (dense 405B; released 2024-07-23)

- **swebVer**: 49 [3p:Vellum] src=https://www.vellum.ai/open-llm-leaderboard date=2026-05 — note: low confidence on the exact number; Vellum cited it in summary but the disaggregated table is not visible in the fetched content. Treat as "approximately 49%".
- **swebPro**: 11.18 ± 2.15 [3p:Scale] src=https://labs.scale.com/leaderboard/swe_bench_pro_public date=2026-05 — Scale's public leaderboard. This is the ONLY Llama 3.1 family entry on the SWE-bench Pro Public leaderboard.
- **tb**: 6.8% [3p:AA, Terminal-Bench Hard] src=https://designforonline.com/ai-models/meta-llama-3-1-405b/ date=2026-05
- **gdpval**: confirmed unreported as disaggregated percentage (Intelligence Index = 17.4 composite, GDPval-AA is a component but not exposed individually for 3.1 405B).
- **gpqa**: 50.7% [lab, plain GPQA, not Diamond] src=https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct date=2024-07 — AA's independent measurement of GPQA-Diamond gives 51.5% [3p:AA] src=https://designforonline.com/ai-models/meta-llama-3-1-405b/ date=2026-05
- **hleNoTools**: 4.2% [3p:AA] src=https://designforonline.com/ai-models/meta-llama-3-1-405b/ date=2026-05
- **hleWithTools**: confirmed unreported
- **frontierMathT13**: confirmed unreported (no Llama entries on FrontierMath leaderboard). src=https://llm-stats.com/benchmarks/frontiermath date=2026-05
- **frontierMathT4**: confirmed unreported
- **mcpAtlas**: confirmed unreported
- **browseComp**: confirmed unreported
- **toolathlon**: confirmed unreported
- **osworldV**: confirmed unreported
- **financeAgent**: confirmed unreported
- **cyberGym**: confirmed unreported
- **charXivNoTools**: confirmed unreported (Llama 3.1 is text-only at the 405B Instruct release; no CharXiv)
- **charXivWithTools**: confirmed unreported
- **mmmlu**: confirmed unreported as a single composite number. Meta's card publishes per-language MMLU breakdowns and Multilingual MGSM = 91.6, but not the canonical MMMLU aggregate.

---

## Cross-cutting observations

- All three models PRE-DATE the frontier-18 reporting convention. Meta's coding eval choice across releases is consistently HumanEval / MBPP / LiveCodeBench, with no SWE-bench numbers in their own cards. The single hard 3p number we surfaced is **Llama 3.1 405B Instruct on SWE-bench Pro = 11.18%** (Scale's own evaluation). Notably the only other Llama on Scale's public board is Maverick at 5.24%, so 3.1 405B actually beats Maverick on SWE-bench Pro despite being 21 months older — consistent with Maverick's release-time critique that it underperformed expectations on coding/reasoning.
- Artificial Analysis is the only consistent disaggregated source for these three Meta models and only for **Terminal-Bench Hard, GPQA Diamond, HLE, MMLU-Pro, MATH 500, AIME, AIME 2025, LiveCodeBench, IFBench, SciCode, τ²-Bench, LCR**. They do NOT publish (or have not yet measured) FrontierMath, BrowseComp, OSWorld, MCP-AtlAS, Toolathlon, FinanceAgent, CyberGym, CharXiv, MMMLU for any of these three models.
- AA's disaggregated tables are only visible on `designforonline.com`'s AA-mirror pages for **Scout** and **Llama 3.1 405B** in our fetches. The Llama 3.3 70B equivalent designforonline page does NOT have the AA component values rendered (states "no benchmark data is available in this listing") — only the Intelligence Index composite of 14 from AA itself. This is a publication gap, not a measurement absence: AA has the numbers (since Index = 14 requires them), they simply aren't surfaced on a per-component basis for 3.3 70B in the channels we can reach without API access.

## Confirmed unreported summary (whole frontier-18 minus the explicit hits above)

- **Llama 4 Scout**: swebVer, swebPro, gdpval, hleWithTools, frontierMathT13, frontierMathT4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXivNoTools, charXivWithTools, mmmlu — 15/18 unreported.
- **Llama 3.3 70B**: swebVer, swebPro, tb, gdpval, hleNoTools, hleWithTools, frontierMathT13, frontierMathT4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXivNoTools, charXivWithTools, mmmlu — 17/18 unreported (only GPQA-Diamond is reported).
- **Llama 3.1 405B**: gdpval, hleWithTools, frontierMathT13, frontierMathT4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXivNoTools, charXivWithTools, mmmlu — 13/18 unreported.

## Sources cited

- https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct (Meta lab card)
- https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct (Meta lab card)
- https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct (Meta lab card)
- https://www.llama.com/models/llama-4/ (Meta's Llama 4 announcement page)
- https://artificialanalysis.ai/models/llama-4-scout (AA model page)
- https://artificialanalysis.ai/models/llama-3-3-instruct-70b (AA model page)
- https://artificialanalysis.ai/models/llama-3-1-instruct-405b (AA model page)
- https://artificialanalysis.ai/leaderboards/models (AA composite leaderboard)
- https://designforonline.com/ai-models/meta-llama-4-scout/ (AA-mirror, disaggregated Scout)
- https://designforonline.com/ai-models/meta-llama-3-1-405b/ (AA-mirror, disaggregated 3.1 405B)
- https://designforonline.com/ai-models/meta-llama-3-3-70b-instruct/ (AA-mirror, 3.3 70B — no disaggregation rendered)
- https://www.vellum.ai/open-llm-leaderboard (Vellum open-weight leaderboard)
- https://www.vellum.ai/llm-leaderboard (Vellum general leaderboard)
- https://labs.scale.com/leaderboard/swe_bench_pro_public (Scale SWE-bench Pro Public)
- https://llm-stats.com/benchmarks/terminal-bench (Terminal-Bench leaderboard)
- https://llm-stats.com/benchmarks/frontiermath (FrontierMath leaderboard)
- https://docsbot.ai/models/compare/gpt-4-1/llama-4-scout (3p comparison page)
- https://tokenmix.ai/blog/llama-4-vs-llama-3-3 (3p blog — numbers unreliable/uncited; treat as folklore not lab-grade)
