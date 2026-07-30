## Opus 4.6
- gdpval: 1606 Elo [lab] src=https://www-cdn.anthropic.com/0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf publisher=Anthropic date=2026-02 (NOTE: Anthropic only publishes GDPval-AA as Elo, not as a pass-rate. A 3p source [digitalapplied.com] cites "GDPval: 78.0%" but this appears to be unsourced — Anthropic's primary methodology is Elo, and OpenAI's GDPval evaluates via pairwise ratings → Elo, not pass-rate. Treat the 78.0% as unverified.)
- gdpval (alt, 3p): 78.0% [3p] src=https://www.digitalapplied.com/blog/gpt-5-4-vs-opus-4-6-vs-gemini-3-1-pro-best-frontier-model publisher=DigitalApplied date=2026 (unverified, no upstream cite)
- toolathlon: confirmed unreported — not in Opus 4.6 system card, not in any 3p source. Google's Gemini 3.5 Flash eval PDF lists Toolathlon column for Sonnet 4.6 / Opus 4.7 / Gemini family but omits Opus 4.6 entirely from that table.
- frontierMathT13: confirmed unreported — not in Opus 4.6 system card; Anthropic did not run FrontierMath for 4.6. No 3p replication found.
- frontierMathT4: confirmed unreported — same as above.

## Sonnet 4.6
- tb (Terminal-Bench 2.0): 59.1% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Table 2.1.A + Section 2.3)
- gdpval: 1633 Elo [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Section 2.8 / Table 2.1.A — Elo only, no pass-rate)
- gdpval (alt, 3p): 1674 Elo [3p] src=https://deepmind.google/models/evals-methodology/gemini-3-5-flash/ publisher=Google date=2026-05 (Google sources from Artificial Analysis leaderboard; >3pp difference vs lab Elo — likely later snapshot)
- gpqa (GPQA Diamond): 89.9% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Table 2.1.A. NOTE: widespread 3p reports of "74.1%" are WRONG — that number appears nowhere in the system card.)
- hleNoTools: 33.2% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Table 2.1.A row "HLE")
- hleWithTools: 49.0% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Table 2.1.A row "With tools")
- frontierMathT13: confirmed unreported — not in Sonnet 4.6 system card (grep confirmed). No 3p replication.
- frontierMathT4: confirmed unreported — same.
- browseComp: 74.01% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Section 2.20.1.1, single-agent, thinking disabled. Multi-agent variant: 82.07% per Section 2.20.1.3.)
- toolathlon: confirmed unreported — not in Sonnet 4.6 system card (grep confirmed absent). Google's Gemini 3.5 Flash eval PDF shows "—" (dash) in the Toolathlon column for Claude Sonnet 4.6. arxiv:2510.25726 (Tool Decathlon paper) lists "Claude-4.5-Sonnet at 38.6%" but no Sonnet 4.6.
- cyberGym: 65.2% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Section 2.15, pass@1 on 1,507 tasks)
- charXivWithTools: 77.4% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Section 2.17.3, CharXiv Reasoning with image-cropping tool)
- charXivNoTools: 72.4% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Section 2.17.3, CharXiv Reasoning no tools — supersedes the 70.5% on the merge list)
- mmmlu: 89.3% [lab] src=https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf publisher=Anthropic date=2026-02 (Table 2.1.A)

## Opus 4.7
- toolathlon: confirmed unreported — Vellum, BuildFastWithAI, Lushbinary, Kingy.ai, DataCamp checks all turn up no Toolathlon score. Google's Gemini 3.5 Flash eval PDF (May 2026) explicitly shows "—" (dash) in the Toolathlon column for Claude Opus 4.7. Anthropic did not run it; no 3p replication exists.
- financeAgentV2 (newer than v1.1): 51.5% [3p] src=https://deepmind.google/models/evals-methodology/gemini-3-5-flash/ publisher=Google date=2026-05 (sourced from vals.ai public leaderboard per Google's methodology note; substantially lower than v1.1's 64.4% — Vals AI's v2 is a harder/redesigned eval, not directly comparable)

## Confirmed unreported
- toolathlon for Opus 4.6: not in any 3p source.
- toolathlon for Sonnet 4.6: explicit "—" in Google 3p table; absent from system card.
- toolathlon for Opus 4.7: explicit "—" in Google 3p table; absent from Vellum / Lushbinary / BuildFastWithAI / Kingy / DataCamp.
- frontierMathT13 for Opus 4.6: not in any 3p source.
- frontierMathT4 for Opus 4.6: not in any 3p source.
- frontierMathT13 for Sonnet 4.6: not in system card; not in 3p sources.
- frontierMathT4 for Sonnet 4.6: not in system card; not in 3p sources.
- GDPval pass-rate (any model): GDPval-AA is Elo-only by methodology. The 78.0% Opus 4.6 number on digitalapplied.com is unverified.

## Caveats / corrections to existing registry
- Sonnet 4.6 GPQA Diamond: registry / merge list should NOT use 74.1% — system card Table 2.1.A says **89.9%**. The 74.1% figure is widespread 3p but contradicted by primary source.
- Sonnet 4.6 HLE (no tools): system card says **33.2%**, matches the merge list note. HLE (with tools) is **49.0%**, not 53.0%.
- Sonnet 4.6 CharXiv (no tools): system card says **72.4%** (adaptive thinking, max effort); the 70.5% on the merge list is the lower-effort variant.
- Sonnet 4.6 MCP-Atlas: system card says **61.3%** (max effort); the 69.5% on the merge list appears WRONG — no source supports 69.5% for Sonnet 4.6 on MCP-Atlas.
- Opus 4.7 Terminal-Bench: registry has 69.4% (lab, TB 2.0). Google's 3p table reports 66.1% but that's TB **2.1** (different benchmark version) — surface as TB 2.1 = 66.1% [3p Google], distinct from TB 2.0 = 69.4% [lab].

## Sources cited
- Claude Sonnet 4.6 System Card PDF: https://www-cdn.anthropic.com/bbd8ef16d70b7a1665f14f306ee88b53f686aa75.pdf
- Claude Opus 4.6 System Card PDF: https://www-cdn.anthropic.com/0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf
- Claude Opus 4.6 announcement: https://www.anthropic.com/news/claude-opus-4-6
- Google Gemini 3.5 Flash eval methodology + results PDF (3p comparison table): https://deepmind.google/models/evals-methodology/gemini-3-5-flash/
- Vellum Opus 4.7 benchmarks: https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained
- Vellum Opus 4.6 vs 4.5 benchmarks: https://www.vellum.ai/blog/claude-opus-4-6-benchmarks
- BuildFastWithAI Opus 4.7 review: https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026
- DigitalApplied Opus 4.6 comparison: https://www.digitalapplied.com/blog/gpt-5-4-vs-opus-4-6-vs-gemini-3-1-pro-best-frontier-model
- DigitalApplied Sonnet 4.6 guide: https://www.digitalapplied.com/blog/claude-sonnet-4-6-benchmarks-pricing-guide
- MorphLLM claude-benchmarks: https://www.morphllm.com/claude-benchmarks
- NxCode Sonnet 4.6 guide: https://www.nxcode.io/resources/news/claude-sonnet-4-6-complete-guide-benchmarks-pricing-2026
- Tool Decathlon paper (arxiv 2510.25726): https://arxiv.org/pdf/2510.25726
- Kingy.ai Mythos vs GPT-5.5: https://kingy.ai/ai/claude-mythos-preview-vs-gpt-5-5-a-benchmark-by-benchmark-showdown-between-the-two-most-important-frontier-models-of-april-2026/
