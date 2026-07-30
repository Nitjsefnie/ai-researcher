# xAI non-flagship models — frontier-18 fill

Scope: Grok-3 / Grok-3 mini, Grok-4 / Grok-4 Fast, Grok-4 Heavy, Grok-4.1 / Grok-4.1 Fast,
Grok-4.20 / Grok-4.20 Multi-Agent, Grok Build 0.1, Grok Code Fast 1.

Frontier-18 = `swebVer`, `swebPro`, `tb` (Terminal-Bench 2.0), `gdpval`,
`gpqa` (Diamond), `hleNoTools`, `hleWithTools`, `frontierMathT13`,
`frontierMathT4`, `mcpAtlas`, `browseComp`, `toolathlon`, `osworldV`,
`financeAgent`, `cyberGym`, `charXivNoTools`, `charXivWithTools`, `mmmlu`.

Methodology note: `x.ai/news/*`, `data.x.ai/*`, `docs.x.ai/*` all 403
to non-browser fetchers. The Grok-4.1 model card PDF *was* directly
fetchable via WebFetch (binary stream → `pdftotext`), but it is a
**safety-only model card** — capability benches absent. All other
lab numbers route via AA / DataCamp / DesignForOnline / SciAm / Vals
mirrors of the lab assertions. xAI launch tweets supply Heavy claims.

Standing observation: Vals.ai pages for Grok-4-Fast and Grok-4.1-Fast
display benchmark rows but all values render as "0.0% ±band, rank x/y"
— eval is queued but not run as of May 2026 (consistent with the
Grok-4.3 Vals row noted in prior fill). Treat Vals scores as
"queued/unreported" until non-zero values appear.

---

## Grok-3
(Release 2025-02-17; legacy alias → Grok-4.3 May 2026; Think + DeepSearch are runtime toggles, not separate SKUs)

- swebVer: Confirmed unreported (no Grok-3 SWE-bench Verified number located in lab blog or 3p coverage — Grok-3 launch focused on AIME, GPQA, LCB, MMLU-Pro, HLE)
- swebPro: Confirmed unreported (SWE-bench Pro postdates Grok-3 launch)
- tb (Terminal-Bench 2.0): Confirmed unreported (TB 2.0 released ~Sept 2025, after Grok-3)
- gdpval: Confirmed unreported (GDPval postdates Grok-3)
- gpqa: 84.6 [lab src=https://x.ai/news/grok-3 via report=grok-models-report.md date=2025-02 note=Grok-3 Think mode, max compute config]
- hleNoTools: Confirmed unreported (xAI only published "Think+DeepSearch" HLE figure; no plain no-tools figure)
- hleWithTools: 25.8 [lab src=https://x.ai/news/grok-3 via report=grok-models-report.md date=2025-02 note=Think + DeepSearch runtime, max compute; xAI's own description; treat as "with-tools" since DeepSearch is browsing tool]
- frontierMathT13: Confirmed unreported
- frontierMathT4: Confirmed unreported
- mcpAtlas: Confirmed unreported (MCP-Atlas postdates Grok-3)
- browseComp: Confirmed unreported
- toolathlon: Confirmed unreported
- osworldV: Confirmed unreported
- financeAgent: Confirmed unreported
- cyberGym: Confirmed unreported (CyberGym postdates Grok-3; only Grok-4.1+ has dual-use cyber bench numbers — CyBench, different test)
- charXivNoTools: Confirmed unreported
- charXivWithTools: Confirmed unreported
- mmmlu: Confirmed unreported (Grok-3 reported MMLU-Pro 79.9 only)
- AA Intelligence Index (context): 25 [3p src=https://artificialanalysis.ai/models/grok-3 publisher=ArtificialAnalysis date=2025-02 note=AA rank #35 of 71 in class at that time]

## Grok-3 mini
(Release 2025-02-17; cheapest reasoning-mini at launch; legacy alias → Grok-4.3 May 2026)

- swebVer: Confirmed unreported
- swebPro: Confirmed unreported
- tb: Confirmed unreported
- gdpval: Confirmed unreported
- gpqa: 78.9 [lab src=https://x.ai/news/grok-3 via report=grok-models-report.md date=2025-02 note=Think mode]
- hleNoTools: Confirmed unreported
- hleWithTools: Confirmed unreported
- frontierMathT13: Confirmed unreported
- frontierMathT4: Confirmed unreported
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported (all postdate Grok-3 mini's launch or were not in xAI's reporting set)

## Grok-4
(Release 2025-07-09; legacy alias → Grok-4.3 as of May 2026)

- swebVer: 72-75 [lab src=https://x.ai/news/grok-4 via https://medium.com/@leucopsis/grok-4-independent-reviews-and-benchmarks-6c22b3beb18c date=2025-07 note=xAI quoted range; specific subset / scaffold not disclosed]
  - swebVer (3p replication): 58.6 [3p src=https://www.vals.ai/models/grok_grok-4 publisher=Vals.ai date=2025-08 note=Vals SWE-agent scaffold; ~14-16pp below lab — flag >3pp disagreement]
- swebPro: Confirmed unreported (SWE-bench Pro postdates Grok-4 launch; not re-reported when Pro shipped)
- tb (Terminal-Bench 2.0): 38.8 [3p src=https://www.vals.ai/benchmarks/terminal-bench-2 publisher=Vals.ai date=2025-09 note=$7.31/test, 902s latency per row]
- gdpval: Confirmed unreported (GDPval ~Sept 2025; xAI didn't refresh Grok-4 against it before Grok-4.20 replacement)
- gpqa (Diamond): 87.5 [lab src=https://x.ai/news/grok-4 via https://www.datacamp.com/blog/grok-4 date=2025-07]
- hleNoTools: 25.4 [lab src=https://x.ai/news/grok-4 via https://www.scientificamerican.com/article/elon-musks-new-grok-4-takes-on-humanitys-last-exam-as-the-ai-race-heats-up/ date=2025-07 note=text-only subset]
  - hleNoTools (alt lab figure): 26.9 [lab src=https://x.ai/news/grok-4 via https://www.datacamp.com/blog/grok-4 date=2025-07 note=DataCamp summary; 1.5pp delta likely reflects subset/sampling window difference within same lab run]
- hleWithTools: 38.6 [lab src=https://x.ai/news/grok-4 via SciAm + grok-models-report.md date=2025-07 note=text-only subset, tools enabled]
  - hleWithTools (alt lab figure): 41.0 [lab src=https://x.ai/news/grok-4 via https://www.datacamp.com/blog/grok-4 date=2025-07 note=2.4pp delta — same caveat as hleNoTools alt]
- frontierMathT13: Confirmed unreported
- frontierMathT4: Confirmed unreported
- mcpAtlas: Confirmed unreported
- browseComp: Confirmed unreported (Grok-4 didn't publish; AA's BrowseComp coverage of competing models doesn't cite a Grok-4 score)
- toolathlon: Confirmed unreported
- osworldV: Confirmed unreported
- financeAgent: Confirmed unreported (CorpFin v2 ranks visible on Vals but values all 0.0 — eval not run)
- cyberGym: Confirmed unreported (Grok-4 launch did not publish; Grok-4.1 published CyBench 0.43 which is different bench)
- charXivNoTools / charXivWithTools: Confirmed unreported
- mmmlu: Confirmed unreported (Grok-4 launch reported MMLU-Pro ~87 only)
- AA Intelligence Index (context): 73 [3p src=https://x.com/ArtificialAnlys/status/1943166841150644622 publisher=ArtificialAnalysis date=2025-07-10 note=launch-day AA harness] / 42 [3p src=https://artificialanalysis.ai/models/grok-4 publisher=ArtificialAnalysis date=2026-05 note=AA re-eval; harness updated, NOT comparable to 73]

## Grok-4 Heavy
(Release 2025-07-09 alongside Grok-4; SuperGrok Heavy $300/mo consumer subscription; multi-agent inference scheduler; no per-token API SKU at launch)

- swebVer: Confirmed unreported (xAI's launch comms emphasized HLE, AIME, USAMO; SWE-Bench Heavy number never surfaced)
- swebPro: Confirmed unreported
- tb: Confirmed unreported
- gdpval: Confirmed unreported
- gpqa (Diamond): 88.9 [lab src=https://x.ai/news/grok-4 via https://www.datacamp.com/blog/grok-4 date=2025-07]
- hleNoTools: 44.4 [lab src=https://x.ai/news/grok-4 via https://www.scientificamerican.com/article/elon-musks-new-grok-4-takes-on-humanitys-last-exam-as-the-ai-race-heats-up/ date=2025-07 note=text-only, multi-agent, no external tools]
- hleWithTools: 50.7 [lab src=https://x.ai/news/grok-4 via https://x.com/MarioNawfal/status/1943165339438637097 + SciAm date=2025-07 note=text-only subset, tools enabled; first AI past 50% on HLE-with-tools text]
  - hleWithTools (3p reproducibility): "yet to appear on the leaderboard — pending review" [3p src=SciAm date=2025-07 note=SciAm explicitly flagged no independent reproduction at the time]
  - hleWithTools (3p concern): Scale/METR independent runs reportedly placed Grok-4 Heavy 3-6pp behind xAI's marketing numbers on coding tasks per grok-models-report.md notes; specific Heavy-on-HLE rerun not located in current ops. Flag for >3pp disagreement risk; absolute 3p number not surfaced.
- frontierMathT13 / frontierMathT4: Confirmed unreported (Grok-4 Heavy USAMO 61.9 published, but FrontierMath split not reported)
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported
- AIME 2025 (context, not frontier-18): 100.0 [lab src=https://x.ai/news/grok-4 via DataCamp + UCStrategies date=2025-07 note=xAI claim, max test-time compute; NOT pass@1 — separate-runtime configuration; UCStrategies 2026 still cites figure unchallenged; independent reproduction not surfaced. Flag 3p reproducibility concern per prior grok-models-report.md notes (Scale, METR)]

## Grok-4 Fast
(Release 2025-09-19; unified reasoning toggle; 2M context; legacy alias → Grok-4.3 as of May 2026)

- swebVer: Confirmed unreported (xAI's Grok-4 Fast blog emphasized AIME / HMMT / LCB / GPQA / HLE; no SWE-Bench)
  - swebVer (3p, queued): row exists on https://www.vals.ai/models/grok_grok-4-fast-reasoning rank 44/48 but score 0.0% ±2.23 — eval not run
- swebPro: Confirmed unreported
- tb (Terminal-Bench 2.0): row queued on Vals.ai (rank 43/64, score 0.0% ±4.85, eval not run) [3p src=https://www.vals.ai/models/grok_grok-4-fast-reasoning publisher=Vals.ai date=2026-05]
- gdpval: Confirmed unreported
- gpqa (Diamond): 85.7 [lab src=https://x.ai/news/grok-4-fast via report=grok-models-report.md date=2025-09]
  - gpqa (3p): rank 23/106 on Vals.ai but score 0.0% — eval not run
- hleNoTools: 19.3 [lab src=https://x.ai/news/grok-4-fast via report=grok-models-report.md date=2025-09]
- hleWithTools: Confirmed unreported (xAI only published Grok-4 Fast with-tools as a delta vs no-tools narratively, no numeric)
- frontierMathT13 / frontierMathT4: Confirmed unreported
- mcpAtlas / browseComp / toolathlon / osworldV: Confirmed unreported
- financeAgent (CorpFin v2): rank 6/107 on Vals.ai but score 0.0% — eval not run [3p src=https://www.vals.ai/models/grok_grok-4-fast-reasoning date=2026-05 note=rank-without-score signals queue position only]
- cyberGym / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported
- AA Intelligence Index (context): 23 [3p src=https://artificialanalysis.ai/models/grok-4-fast publisher=ArtificialAnalysis date=2025-09]

## Grok-4.1 + Grok-4.1 Fast
(Grok-4.1 2025-11-17 chatbot; Grok-4.1 Fast 2025-11-19 API GA; legacy alias → Grok-4.3 as of May 2026)

- The **Grok-4.1 model card** (https://data.x.ai/2025-11-17-grok-4-1-model-card.pdf — directly fetchable via WebFetch + pdftotext) is a **safety-only document** — no frontier-18 capability benches. It publishes: MASK dishonesty 0.49 (T) / 0.46 (NT) vs Grok-4 0.43; Sycophancy 0.19 (T) / 0.23 (NT) vs Grok-4 0.07; WMDP-Bio 0.87, VCT 0.61, BioLP 0.37, ProtocolQA 0.79, FigQA 0.34, CloningScenarios 0.46, WMDP-Chem 0.84, WMDP-Cyber 0.84, **CyBench 0.39** (success rate, agentic CTF), MakeMeSay 0.00. None map cleanly to frontier-18.
- Grok-4.1 launch blog post (https://x.ai/news/grok-4-1-fast) only published EQ-Bench 1586 Elo (#1) and Agent Tools API tool-calling 93 on t2-Bench.
- swebVer / swebPro: Confirmed unreported; Vals row for Grok-4.1 Fast (Reasoning) rank 45/48 score 0.0% — eval not run
- tb (Terminal-Bench 2.0): row queued on Vals.ai for Grok-4.1 Fast (rank 48/64, score 0.0% ±4.60) [3p src=https://www.vals.ai/models/grok_grok-4-1-fast-reasoning date=2026-05]
- gdpval: Confirmed unreported
- gpqa (Diamond): Confirmed unreported in 4.1 lab outputs (Vals rank 26/106 score 0.0% — eval not run)
- hleNoTools / hleWithTools: Confirmed unreported (xAI 4.1 deliberately omitted HLE in favor of EQ-Bench narrative)
- frontierMathT13 / frontierMathT4 / mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported
- cyberGym: **CyBench 0.39 unguided success rate** [lab src=https://data.x.ai/2025-11-17-grok-4-1-model-card.pdf publisher=xAI date=2025-11 note=Grok-4.1 T; Grok-4 baseline 0.43 — Grok-4.1 regressed 4pp on cyber-agentic. NOT same benchmark as `cyberGym` in frontier-18 schema, but closest cyber-agentic capability number xAI has published. Flag mapping caveat.]
- AA Intelligence Index (context, 4.1 Fast): 24 [3p src=https://artificialanalysis.ai/models/grok-4-1-fast publisher=ArtificialAnalysis date=2025-11]

## Grok-4.20
(Release 2026-02-17 public beta on X; 2026-03-10 API GA `grok-4.20-0309-*`; still listed on docs.x.ai as of May 2026 alongside Grok-4.3)

- swebVer: Confirmed unreported (DesignForOnline xAI mirror does NOT list a SWE-Bench Verified number for Grok-4.20)
- swebPro: Confirmed unreported
- tb (Terminal-Bench 2.0): Confirmed unreported as a TB-2.0 number; **TerminalBench Hard 16.7** [lab src=https://designforonline.com/ai-models/xai-grok-4-20/ publisher=xAI-via-DesignForOnline date=2026-02 note=TB-Hard is a different benchmark from TB-2.0; included as the closest tool-use number xAI surfaced]
- gdpval: Confirmed unreported as a value; AA-listed in the Intelligence Index breakdown but per-model number not surfaced. (Per prior research GDPval-AA Elo for Grok-4.20 0309 v2 = 1179, but the May-2026 AA page no longer surfaces this — only Grok-4.3's 1500.)
  - gdpval (prior-research carry-forward, low confidence): 1179 Elo [3p src=https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing publisher=ArtificialAnalysis date=2026-04 note=cited as Grok-4.20 0309 v2 baseline when measuring Grok-4.3's +321 GDPval lift]
- gpqa (Diamond): 77.6 [lab src=https://designforonline.com/ai-models/xai-grok-4-20/ publisher=xAI-via-DesignForOnline date=2026-02]
- hleNoTools: 24.2 [lab src=https://designforonline.com/ai-models/xai-grok-4-20/ publisher=xAI-via-DesignForOnline date=2026-02 note=tool config unspecified; label "HLE" presumed no-tools given absence of "with-tools" qualifier]
- hleWithTools: Confirmed unreported
- frontierMathT13 / frontierMathT4: Confirmed unreported
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent: Confirmed unreported
- cyberGym / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported
- AA Intelligence Index (context): 49 [3p src=https://artificialanalysis.ai/models/grok-4-20 publisher=ArtificialAnalysis date=2026-04 note=AA rank #23/148; AAII v4.0 harness]
- Other lab-quoted numbers on the DesignForOnline mirror (for completeness, not in frontier-18): SciCode 32.8, τ²-Bench 59.9, IFBench 49.3, AA-LCR 17.3
- BenchLM rank (context): #42 of 117, overall 64/100 [3p src=https://benchlm.ai/models/grok-4-20-beta publisher=BenchLM date=2026-05 note=Arena Elo 1478]

## Grok-4.20 Multi-Agent
(API SKU `grok-4.20-multi-agent-0309`; first xAI SKU to expose multi-agent inference scheduler directly to developers, March 2026)

- swebVer / swebPro / tb / gdpval / gpqa / hleNoTools / hleWithTools / frontierMathT13 / frontierMathT4 / mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / charXivNoTools / charXivWithTools / mmmlu: **All confirmed unreported.**
- Rationale: AA model pages list only the `grok-4.20-0309 v2 (Reasoning)` SKU; the Multi-Agent SKU is not on AA model index, not on benchlm.ai, not on Vals.ai. xAI did not publish a separate benchmark deck for the Multi-Agent API SKU at launch — the messaging was "Heavy is now developer-accessible," not "here's a new benchmark sweep." Carry-forward (per prior research): AAII 48-49, AA-Omniscience non-hallucination 78%, GDPval-AA 1179, BenchLM #38 — none of which are frontier-18 cells.

## Grok Build 0.1
(Release 2026-05 quiet rollout; early access; `grok-build-0.1` SKU at $1.00/$2.00 per 1M)

- swebVer / swebPro / tb / gdpval / gpqa / hleNoTools / hleWithTools / frontierMathT13 / frontierMathT4 / mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / charXivNoTools / charXivWithTools / mmmlu: **All confirmed unreported.**
- Rationale: xAI explicitly stated no public eval suite at launch (early-access SKU). Kilo's coding-index harness is reportedly the first 3p number circulating per grok-models-report.md, but coverage is not stable enough to cite. No AA model page, no Vals page, no BenchLM page exists as of the current web ops.

## Grok Code Fast 1
(Release 2025-08-28; deprecated on docs.x.ai as of May 2026; superseded by Grok-4 Fast + Grok Build 0.1)

- swebVer: 70.8 [lab src=https://x.ai/news/grok-code-fast-1 via https://medium.com/@leucopsis/grok-code-fast-1-review-a-fast-low-cost-coder-for-agentic-work-6ef638b25c2e + InfoQ date=2025-08 note=xAI's internal harness on full SWE-Bench-Verified subset; harness details not disclosed]
- swebPro: Confirmed unreported
- tb (Terminal-Bench 2.0): Confirmed unreported as a specific TB-2.0 value; xAI's launch text said the model "mastered common tools like grep, terminal, and file editing" — no quantitative TB number
- gdpval: Confirmed unreported
- gpqa (Diamond): Confirmed unreported (Grok Code Fast 1 is code-specialist; xAI did not publish GPQA)
- hleNoTools / hleWithTools: Confirmed unreported
- frontierMathT13 / frontierMathT4: Confirmed unreported
- mcpAtlas / browseComp / toolathlon / osworldV / financeAgent / cyberGym / charXivNoTools / charXivWithTools / mmmlu: Confirmed unreported
- AA Intelligence Index (context): 29 [3p src=https://artificialanalysis.ai/models/grok-code-fast-1 publisher=ArtificialAnalysis date=2025-09 note=AA rank #20/217 in class]

---

## Cross-model summary — `[lab]` numbers harvested

| Model | swebVer | tb | gpqa | hleNoTools | hleWithTools | cyber-cap |
|---|---|---|---|---|---|---|
| Grok-3 | — | — | 84.6 (Think) | — | 25.8 (Think+DeepSearch) | — |
| Grok-3 mini | — | — | 78.9 (Think) | — | — | — |
| Grok-4 | 72-75 (lab) / 58.6 (Vals 3p) | 38.8 (Vals 3p) | 87.5 | 25.4 / 26.9 | 38.6 / 41.0 | — |
| Grok-4 Heavy | — | — | 88.9 | 44.4 | 50.7 (3p concerns) | — |
| Grok-4 Fast | — | — | 85.7 | 19.3 | — | — |
| Grok-4.1 (T) | — | — | — | — | — | CyBench 0.39 (≠cyberGym) |
| Grok-4.20 | — | — | 77.6 | 24.2 | — | — |
| Grok-4.20 MA | — | — | — | — | — | — |
| Grok Build 0.1 | — | — | — | — | — | — |
| Grok Code Fast 1 | 70.8 | — | — | — | — | — |

## Confirmed-unreported observations (per model, key gaps)

- **Grok-3 / Grok-3 mini**: 15 of 18 frontier-18 unreported (benchmarks postdate launch); only gpqa + a partial-mapping hleWithTools surface
- **Grok-4**: 12 of 18 unreported; swebVer has lab-vs-Vals >3pp disagreement (72-75 vs 58.6)
- **Grok-4 Heavy**: 13 of 18 unreported; hleWithTools 50.7 has explicit "pending independent review" 3p concern (SciAm) but no specific 3p rerun number was located
- **Grok-4 Fast**: 14 of 18 unreported; Vals.ai has Fast queued on most benches but all scores 0.0% (eval not run)
- **Grok-4.1 / 4.1 Fast**: 17 of 18 unreported; the lab-published model card is safety-only — frontier-18 capability sweep absent by design. CyBench 0.39 is closest cyber number but ≠ CyberGym schema.
- **Grok-4.20**: 14 of 18 unreported; DesignForOnline mirror surfaces gpqa + hleNoTools only; TerminalBench Hard 16.7 captured as adjacent-not-equal to TB-2.0
- **Grok-4.20 Multi-Agent**: 18 of 18 unreported — no separate benchmark deck published for the API SKU
- **Grok Build 0.1**: 18 of 18 unreported — early-access, no eval suite
- **Grok Code Fast 1**: 17 of 18 unreported; only swebVer 70.8 published (xAI internal harness)

## 3p disagreement flags (>3pp)

- **Grok-4 swebVer**: lab 72-75 vs Vals 58.6 → ~14-16pp gap. Vals uses SWE-agent scaffold; xAI's harness undisclosed. Flagged in grok-models-report.md already.
- **Grok-4 hleNoTools**: SciAm cites 25.4, DataCamp cites 26.9 — both lab routes; 1.5pp delta likely subset/window variation, BELOW 3pp threshold but worth noting.
- **Grok-4 hleWithTools**: SciAm 38.6 vs DataCamp 41.0 — 2.4pp, BELOW threshold; same subset/window caveat.
- **Grok-4 Heavy hleWithTools 50.7**: SciAm explicitly flagged "pending independent review" at launch; grok-models-report.md cites Scale/METR concerns of 3-6pp on coding tasks (different domain). Specific HLE-Heavy 3p rerun not surfaced — flag is qualitative.
- **Grok-4 Heavy AIME 2025 100%**: xAI claim with max test-time compute; not pass@1; widely flagged as not directly comparable to single-pass baselines (UCStrategies 2026 cites unchallenged; per grok-models-report.md, independent runs place Grok-4 Heavy 3-6pp behind marketing on coding tasks).
- **Grok-4.1 cyber regression**: CyBench Grok-4 0.43 → Grok-4.1 0.39 (4pp drop, lab-internal); not 3p disagreement but a notable lab-internal regression.

## Sources cited

- xAI lab pages (404 to fetchers; cited as `via` chain):
  - https://x.ai/news/grok-3
  - https://x.ai/news/grok-4
  - https://x.ai/news/grok-4-fast
  - https://x.ai/news/grok-4-1-fast
  - https://x.ai/news/grok-4-20
  - https://x.ai/news/grok-code-fast-1
- xAI directly-fetched primary (PDF):
  - https://data.x.ai/2025-11-17-grok-4-1-model-card.pdf (safety-only; no frontier-18 capability benches)
- Artificial Analysis:
  - https://artificialanalysis.ai/models/grok-3
  - https://artificialanalysis.ai/models/grok-4
  - https://artificialanalysis.ai/models/grok-4-fast
  - https://artificialanalysis.ai/models/grok-4-1-fast
  - https://artificialanalysis.ai/models/grok-4-20
  - https://artificialanalysis.ai/models/grok-code-fast-1
  - https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing
  - https://x.com/ArtificialAnlys/status/1943166841150644622
- Vals.ai:
  - https://www.vals.ai/models/grok_grok-4-fast-reasoning
  - https://www.vals.ai/models/grok_grok-4-1-fast-reasoning
  - https://www.vals.ai/benchmarks/terminal-bench-2
- Lab-mirror coverage (where x.ai blogs 403):
  - https://designforonline.com/ai-models/xai-grok-4-20/
  - https://www.datacamp.com/blog/grok-4
  - https://www.scientificamerican.com/article/elon-musks-new-grok-4-takes-on-humanitys-last-exam-as-the-ai-race-heats-up/
  - https://x.com/MarioNawfal/status/1943165339438637097
  - https://ucstrategies.com/news/grok-4-heavy-100-aime-score-benchmarks-api-pricing-2026/
  - https://medium.com/@leucopsis/grok-4-independent-reviews-and-benchmarks-6c22b3beb18c
  - https://medium.com/@leucopsis/grok-code-fast-1-review-a-fast-low-cost-coder-for-agentic-work-6ef638b25c2e
  - https://www.infoq.com/news/2025/09/xai-grok-fast1/
- Aggregators:
  - https://benchlm.ai/models/grok-4-20-beta
  - https://lmcouncil.ai/benchmarks
- Internal cross-reference:
  - /root/ai-researcher/grok-models-report.md
  - /root/ai-researcher/grok-4-3-deep-fill.md (sibling deep-fill for context)
