# OpenAI non-flagship frontier-18 fill (May 2026)

Flagship (GPT-5.5) already deep-filled separately. This document covers
GPT-5.4 / 5.4 Pro / 5.4 mini / 5.4 nano, o3, o3-pro, o4-mini, codex-1,
gpt-oss-120b, gpt-oss-20b. Per-model sections list fills + confirmed
unreported. Numbers without `[3p:…]` are lab-reported (OpenAI) or
sourced via secondary aggregations of lab numbers.

## GPT-5.4 (Mar 5 2026)

Inputs to reconcile: prior fill said `swebPro 57.7` (3p Scale alt 59.10),
`tb 75.1`, `browseComp 89.3 Pro`, `hleNoTools 42.7 Pro`,
`hleWithTools 58.7 Pro`, `mcpAtlas 68.1`, `osworldV 75.0`,
`financeAgent 61.5 v1.1 Pro`, `cyberGym 66.3`, `gpqa 94.4 Pro`,
`frontierMathT13 50.0 Pro`, `frontierMathT4 38.0 Pro`. These are
GPT-5.4 Pro figures. GPT-5.4 base figures below.

- swebVer: 78.20 [3p:Vals.ai] src=https://www.vals.ai/benchmarks/swebench date=2026-04 — base model. Note: secondary "approximately 80%" appears in multiple aggregators.
- swebPro: 57.7 (lab, "Public" cut, base) / 59.10 ±3.56 [3p:Scale, base+xHigh] src=https://labs.scale.com/leaderboard/swe_bench_pro_public — disagreement ~1.4pp, within MoE.
- tb: 75.1 src=https://llm-stats.com/benchmarks/terminal-bench-2 date=2026-03
- gdpval: 83.0 src=https://x.com/OpenAIDevs/status/2029620996962242663 date=2026-03 (OpenAI Devs tweet; corroborated by datacamp/digitalapplied)
- gpqa: 92.8 (base) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- hleNoTools: confirmed unreported for base GPT-5.4 (only Pro variant 42.7 reported)
- hleWithTools: 52.1 (base) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- frontierMathT13: 47.6 (base) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- frontierMathT4: 27.1 (base) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- mcpAtlas: 67.2 (base; Pro 68.1) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- browseComp: 82.7 (base; Pro 89.3) src=https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing
- toolathlon: 54.6 src=https://x.com/OpenAIDevs/status/2029620996962242663 date=2026-03
- osworldV: 75.0 src=https://x.com/OpenAIDevs/status/2029620996962242663
- financeAgent: 61.5 (v1.1, Pro figure; base unreported separately)
- cyberGym: 66.3 (carry from prior fill)
- charXivNoTools / charXivWithTools / mmmlu: confirmed unreported in any GPT-5.4 source surveyed (Anthropic's cross-tab includes these for Opus 4.7 but does not include GPT-5.4 columns for CharXiv/MMMLU).

## GPT-5.4 mini (Mar 17 2026)

- swebVer: confirmed unreported (Vals.ai leaderboard lists model but no aggregate visible)
- swebPro: 54.4 src=https://www.datacamp.com/blog/gpt-5-4-mini-nano
- tb: 60.0 src=https://llm-stats.com/benchmarks/terminal-bench-2
- gdpval: confirmed unreported
- gpqa: 88.0 src=https://tech-insider.org/openai-gpt-5-4-mini-nano-subagent-models-2026/ (via search summary; OpenAI launch page primary)
- hleNoTools / hleWithTools: confirmed unreported
- frontierMathT13 / frontierMathT4: confirmed unreported
- mcpAtlas: confirmed unreported
- browseComp: confirmed unreported
- toolathlon: confirmed unreported
- osworldV: 72.1 src=https://www.datacamp.com/blog/gpt-5-4-mini-nano
- financeAgent / cyberGym: confirmed unreported
- charXivNoTools / charXivWithTools / mmmlu: confirmed unreported

## GPT-5.4 nano (Mar 17 2026)

- swebPro: 52.4 src=https://www.datacamp.com/blog/gpt-5-4-mini-nano
- tb: 46.3 src=https://llm-stats.com/benchmarks/terminal-bench-2
- gpqa: 82.8 src=https://tech-insider.org/openai-gpt-5-4-mini-nano-subagent-models-2026/
- osworldV: 39.0 src=https://www.datacamp.com/blog/gpt-5-4-mini-nano
- All other frontier-18 cells: confirmed unreported in surveyed sources.

## o3 (Apr 16 2025 GA)

- swebVer: 69.1 src=https://www.datacamp.com/blog/o4-mini (cf. 71.7 cited by Wikipedia/aibusinessweekly; both lab — likely same release, different versioning — surface both: 69.1 launch, 71.7 later)
- swebPro: confirmed unreported (does not appear on Scale public leaderboard)
- tb: confirmed unreported (does not appear on Terminal-Bench 2.0 leaderboard surveyed)
- gpqa: 83.3 src=https://www.datacamp.com/blog/o4-mini (datacamp o3-vs-o4-mini); 87.7 also widely cited (Wikipedia) — disagreement >3pp, surface both: launch table 83.3, headline 87.7.
- hleNoTools: confirmed unreported separately
- hleWithTools: 24.90 src=https://www.datacamp.com/blog/o4-mini
- frontierMathT13: ~25.2 (with no tools) src=https://www.techrepublic.com/article/news-openai-generative-ai-models-frontiermath-score/ — note: T1-3 specifically not split out separately in lab disclosure.
- frontierMathT4: confirmed unreported
- charXivNoTools: 78.6 src=https://www.datacamp.com/blog/o4-mini (split no-tools/with-tools not given; treat as headline)
- charXivWithTools: confirmed unreported
- AIME 2024: 91.6; AIME 2025: 88.9 (context only — not part of frontier-18)
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / mmmlu / gdpval: confirmed unreported

## o3-pro (Jun 10 2025)

- swebVer: confirmed unreported in any source surveyed
- swebPro: confirmed unreported
- tb: confirmed unreported
- gpqa: 84 src=https://binaryverseai.com/chatgpt-o3-pro-review-benchmarks-hacks/ date=2025-08 (3p aggregation; OpenAI's o3-pro page returns 403 to WebFetch)
- AIME 2024: 93 (context only)
- All other frontier-18 cells: confirmed unreported. o3-pro launch communication emphasized reliability ("think longer") over a published benchmark table.

## o4-mini (Apr 16 2025)

- swebVer: 68.1 src=https://www.datacamp.com/blog/o4-mini
- swebPro: confirmed unreported (not on Scale leaderboard surveyed)
- tb: confirmed unreported (not on Terminal-Bench 2.0 leaderboard surveyed)
- gpqa: 81.4 src=https://www.datacamp.com/blog/o4-mini
- hleWithTools: 17.70 src=https://www.datacamp.com/blog/o4-mini
- hleNoTools: confirmed unreported separately
- charXivNoTools: 72.0 src=https://www.datacamp.com/blog/o4-mini
- charXivWithTools: confirmed unreported
- AIME 2024: 93.4; AIME 2025: 92.7 (context only)
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / mmmlu / gdpval / frontierMathT13 / frontierMathT4: confirmed unreported

## codex-1 (May 2025, agentic coding backbone)

OpenAI's "Introducing Codex" launch page returned 403 on direct
fetch. Secondary aggregators surface only fragmented numbers and
disagree.

- swebVer: 72.1 [3p aggregator] src=https://www.allaboutai.com/ai-agents/codex/ (also seen: ~69.1 per other aggregators — disagreement >3pp, surface both). OpenAI's own footnote on the launch page confirms codex-1 was evaluated at 192k context / medium reasoning effort with 23 SWE-V samples excluded as non-runnable on internal infra.
- swebPro: confirmed unreported
- tb: confirmed unreported
- All other frontier-18 cells: confirmed unreported. The codex-1 launch positioned the model as a product backbone, not a benchmark contender; OpenAI declined to publish a broader benchmark table.

## gpt-oss-120b (Aug 5 2025, open-weights)

Source: OpenAI gpt-oss model card (arxiv 2508.10925) — high-reasoning mode.

- swebVer: 62.4 src=https://arxiv.org/html/2508.10925v1
- swebPro: 16.20 ±2.67 [3p:Scale] src=https://labs.scale.com/leaderboard/swe_bench_pro_public
- tb: confirmed unreported on Terminal-Bench 2.0 leaderboard with non-zero value (Vals.ai shows "0.0% ±4.19" which is a placeholder)
- gpqa: 80.1 src=https://arxiv.org/html/2508.10925v1 (OpenAI lab; cf. 80.9 in some aggregators — within MoE)
- hleNoTools: 14.9 src=https://arxiv.org/html/2508.10925v1
- hleWithTools: 19.0 src=https://arxiv.org/html/2508.10925v1
- mmmlu: 81.3 src=https://arxiv.org/html/2508.10925v1
- All other frontier-18 cells (gdpval, frontierMath T1-3/T4, mcpAtlas, browseComp, toolathlon, osworldV, financeAgent, cyberGym, charXiv*): confirmed unreported in model card.

## gpt-oss-20b (Aug 5 2025, open-weights)

Source: same model card.

- swebVer: 60.7 src=https://arxiv.org/html/2508.10925v1
- gpqa: 71.5 src=https://arxiv.org/html/2508.10925v1
- hleNoTools: 10.9 src=https://arxiv.org/html/2508.10925v1
- hleWithTools: 17.3 src=https://arxiv.org/html/2508.10925v1
- mmmlu: 75.7 src=https://arxiv.org/html/2508.10925v1
- All other frontier-18 cells: confirmed unreported.

## Confirmed unreported (global summary)

- **GDPval**: never reported for any o-series (o3, o3-pro, o4-mini), codex-1, gpt-oss, or for GPT-5.4 mini/nano. GDPval is a new (2026-era) benchmark; only GPT-5.4/5.5 and a few competitors have lab numbers.
- **Toolathlon**: never reported for any o-series, codex-1, gpt-oss, GPT-5.4 mini/nano. Only GPT-5.4 base (54.6) and GPT-5.5 published.
- **MCP-Atlas**: only GPT-5.4 (base 67.2, Pro 68.1) and GPT-5.5 published.
- **CharXiv (no tools / with tools split)**: o3 (78.6) and o4-mini (72.0) carry single CharXiv numbers from the launch table; the no-tools/with-tools split that Anthropic's launch table uses is not separately reported for any non-flagship OpenAI model.
- **MMMLU**: only the gpt-oss pair (81.3 / 75.7) and GPT-5.5 published; GPT-5.4 family, o3, o3-pro, o4-mini, codex-1 all unreported.
- **FrontierMath T4 split**: GPT-5.4 base (27.1), GPT-5.4 Pro (38.0) only. T4 split for o-series, codex-1, gpt-oss not published.
- **FinanceAgent v1.1, CyberGym**: only GPT-5.4 (Pro) family and GPT-5.5 published.
- **OSWorld-Verified**: only GPT-5.4 base/mini/nano and GPT-5.5 published; o-series, codex-1, gpt-oss not published.
- **o3-pro**: published table is extremely sparse — only AIME (93), GPQA (~84), Codeforces Elo. Treat as a deliberate "no full table" launch.
- **codex-1**: same — product launch, not a benchmark launch. Only SWE-V fragments published.

## Sources cited

- https://openai.com/index/introducing-gpt-5-4-mini-and-nano/ (403 to WebFetch — referenced via aggregators)
- https://openai.com/index/introducing-o3-and-o4-mini/ (403 to WebFetch)
- https://openai.com/index/o3-pro/ (403 to WebFetch)
- https://openai.com/index/introducing-codex/ (403 to WebFetch)
- https://arxiv.org/html/2508.10925v1 — gpt-oss model card (primary)
- https://x.com/OpenAIDevs/status/2029620996962242663 — GPT-5.4 launch tweet (GDPval/OSWorld/SWE-Pro/Toolathlon)
- https://www.digitalapplied.com/blog/gpt-5-4-computer-use-tool-search-benchmarks-pricing — GPT-5.4 base/Pro table
- https://www.datacamp.com/blog/gpt-5-4-mini-nano — mini/nano SWE-Pro/TB/OSWorld
- https://www.datacamp.com/blog/o4-mini — o3 vs o4-mini full table (SWE-V, GPQA, HLE, CharXiv, AIME)
- https://en.wikipedia.org/wiki/OpenAI_o3 — o3 SWE-V 71.7, GPQA 87.7 alternative
- https://www.vals.ai/benchmarks/swebench — GPT-5.4 78.2 SWE-V (3p)
- https://labs.scale.com/leaderboard/swe_bench_pro_public — SWE-Pro 3p (GPT-5.4 59.10, gpt-oss-120b 16.20)
- https://llm-stats.com/benchmarks/terminal-bench-2 — Terminal-Bench 2.0 leaderboard
- https://binaryverseai.com/chatgpt-o3-pro-review-benchmarks-hacks/ — o3-pro AIME/GPQA/Codeforces
- https://tech-insider.org/openai-gpt-5-4-mini-nano-subagent-models-2026/ — GPT-5.4 mini/nano GPQA
- https://www.allaboutai.com/ai-agents/codex/ — codex-1 SWE-V 72.1
- https://www.techrepublic.com/article/news-openai-generative-ai-models-frontiermath-score/ — o3 FrontierMath 25.2
