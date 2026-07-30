## Gemini 3.1 Pro
- osworldV: 76.2 [lab] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf publisher=Google date=2026-05 (cross-tab from 3.5 Flash eval PDF)
- cyberGym: 38.8 [3p] src=https://huggingface.co/zai-org/GLM-5.1/commit/bef021499129c8734c071411f980c5c718874da3 publisher=Z.ai (GLM-5.1 README) date=2026-05
- charXivNoTools: 83.3 [lab] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf publisher=Google date=2026-05
- charXivWithTools: unreported (Google's CharXiv Reasoning row has no "+python"/"+code" annotation for Gemini 3.1 Pro; the only "with tools" CharXiv cell in the table is GPT-5 mini at 75.5% +python)
- financeAgent (v2): 43.0 [lab, vals-sourced] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf publisher=Google (sourced from Vals.ai per methodology footnote) date=2026-05 — NOTE: registry already has 59.7 (v1.1, 3p Anthropic); v2 = 43.0 is a different bench version
- mcpAtlas confirm: 78.2 [lab, ScaleAI-sourced] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf publisher=Google date=2026-05 (Google's revised cross-tab; original 3.1 Pro eval PDF showed 69.2, but Google's own 3.5 Flash PDF supersedes it with 78.2 from ScaleAI leaderboard)

## Gemini 3.1 Pro Deep Think
- swebVer: unreported
- swebPro: unreported
- tb: unreported
- gdpval: unreported
- gpqa: unreported (Deep Think page only lists HLE, ARC-AGI-2, MMMU-Pro, IMO/IPhO/IChO, Codeforces, CMT — see https://deepmind.google/models/gemini/deep-think/)
- frontierMathT13: unreported
- frontierMathT4: unreported
- mcpAtlas: unreported
- browseComp: unreported
- toolathlon: unreported
- osworldV: unreported
- financeAgent: unreported
- cyberGym: unreported
- charXivNoTools: unreported
- charXivWithTools: unreported
- mmmlu: unreported
(Google bundles all agentic/coding benches into the base 3.1 Pro model card; only academic/reasoning benches are reported separately for Deep Think. No 3p source has filled this in as of 2026-05-23.)

## Gemini 3.1 Flash-Lite
- swebVer: 0.8 [3p] src=https://www.buildfastwithai.com/blogs/gemini-3-1-flash-lite-vs-2-5-flash-speed-cost-benchmarks-2026 publisher=BuildFastWithAI date=2026-05 — flagged as suspiciously low / likely degenerate run; treat as alt only
- swebPro: unreported
- tb (2.0): unreported (Google reports only LiveCodeBench 72.0 for coding; AA's "Terminal-Bench Hard" is a different variant and individual cell not exposed)
- gdpval: unreported (only AA Intelligence Index aggregate = 34)
- hleNoTools: 16.0 [lab] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-1_flash-lite_model_evaluation.pdf publisher=Google date=2026-05 (also 16.0% reported by https://deepmind.google/models/model-cards/gemini-3-1-flash-lite/)
- hleWithTools: unreported
- frontierMathT13: unreported
- frontierMathT4: unreported
- mcpAtlas: unreported
- browseComp: unreported
- toolathlon: unreported
- osworldV: unreported
- financeAgent: unreported
- cyberGym: unreported
- charXivNoTools: 73.2 [lab] src=https://storage.googleapis.com/deepmind-media/gemini/gemini_3-1_flash-lite_model_evaluation.pdf publisher=Google date=2026-05 (column header "CharXiv Reasoning / no tools"; GPT-5 mini cell carries "+python" annotation, Flash-Lite cell does not)
- charXivWithTools: unreported

## Gemini 3.5 Flash
- gdpval (pass-rate): unreported. Only GDPval-AA **Elo = 1656** is published (Google PDF + AA leaderboard). No pass-rate accuracy variant exists for GDPval-AA — it is an Elo-only benchmark. AA confirms: "GDPval-AA result is especially notable, achieving an Elo of 1656". src=https://artificialanalysis.ai/articles/gemini-3-5-flash-everything-you-need-to-know
- hleWithTools: unreported (Google PDF only reports HLE "no tools" = 40.2 for 3.5 Flash; no search+code variant published as of 2026-05-23, 4 days post-launch)
- charXivWithTools: unreported (Google PDF row "CharXiv Reasoning / no tools" = 84.2 for 3.5 Flash; no "+python"/"with tools" variant published)

## Confirmed unreported
- charXivWithTools for Gemini 3.1 Pro: not in any 3p source
- All 14 non-academic frontier benches for Gemini 3.1 Pro Deep Think (swebVer, swebPro, tb, gdpval, gpqa, frontierMathT13, frontierMathT4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXivNoTools, charXivWithTools, mmmlu): Google does not publish, no 3p has re-run
- swebPro, tb 2.0, gdpval, hleWithTools, frontierMathT13, frontierMathT4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXivWithTools for Gemini 3.1 Flash-Lite: not in any 3p source
- gdpval (pass-rate), hleWithTools, charXivWithTools for Gemini 3.5 Flash: not in any 3p source

## Sources cited
- https://storage.googleapis.com/deepmind-media/gemini/gemini_3-5_flash_model_evaluation.pdf (Google, 2026-05) — primary source for 3.1 Pro OSWorld-V/CharXiv/FinanceAgent-v2/MCP-Atlas-revised and all 3.5 Flash agentic cross-tab values
- https://storage.googleapis.com/deepmind-media/gemini/gemini_3-1_flash-lite_model_evaluation.pdf (Google, 2026-05) — primary source for all Flash-Lite values
- https://storage.googleapis.com/deepmind-media/gemini/gemini_3-1_pro_model_evaluation.pdf (Google, 2026-02) — confirms 3.1 Pro original numbers (MCP Atlas 69.2 before revision, TB 2.0 = 68.5)
- https://deepmind.google/models/model-cards/gemini-3-1-pro/ (Google) — 3.1 Pro headline benches
- https://deepmind.google/models/model-cards/gemini-3-1-flash-lite/ (Google) — Flash-Lite headline benches
- https://deepmind.google/models/gemini/deep-think/ (Google) — confirms Deep Think bench list is limited to academic
- https://huggingface.co/zai-org/GLM-5.1/commit/bef021499129c8734c071411f980c5c718874da3 (Z.ai GLM-5.1 README) — 3p CyberGym 38.8 for 3.1 Pro
- https://epochai.substack.com/p/gemini-31-pro-comparable-to-gemini (Epoch AI, 2026-02) — confirms 3.1 Pro FrontierMath ≈ Gemini 3 Pro (38%/19% range, with the 36.9/16.7 OpenAI 3p numbers in registry consistent)
- https://artificialanalysis.ai/articles/gemini-3-5-flash-everything-you-need-to-know (Artificial Analysis, 2026-05) — confirms 3.5 Flash GDPval-AA is Elo-only (1656), no pass-rate variant
- https://www.buildfastwithai.com/blogs/gemini-3-1-flash-lite-vs-2-5-flash-speed-cost-benchmarks-2026 (BuildFastWithAI) — only 3p Flash-Lite SWE-Verified mention (0.8%, likely degenerate)
