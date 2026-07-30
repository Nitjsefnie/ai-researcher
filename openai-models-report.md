# OpenAI Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Same schema as the prior Anthropic and Google passes:
typed `Sources:` blocks (`announcement`/`model-card`/`pricing`/`deprecation`/`coverage`/`replication`),
and benchmark rows surface both `lab` and `3p` numbers where they disagree by >3pp.

Lifecycle spine sourced from OpenAI's deprecations page; per-model launch blogs and
system cards supply benchmarks and pricing.

**Scope note**: Per task scope, audio-specialty models (gpt-4o-audio-preview,
gpt-4o-realtime-preview, gpt-realtime, gpt-audio-mini), image-out models
(gpt-image-1), and embedding/Whisper/Sora/DALL-E lines are excluded. They appear
in OpenAI's deprecation table but are not in this benchmark-comparison scope.
Computer-Use Agent (CUA, the Operator backbone) IS included — it's the first
agentic-LLM SKU. Codex agent models are included where they have their own
model card.

**O-series clarification**: The user-supplied checklist says "o3 (late Jan 2025)" —
that's actually **o3-mini** (Jan 31 2025 GA). The full **o3** model didn't ship
until **April 16 2025**, alongside o4-mini. The Dec 20 2024 "o3" event was an
announcement of high-compute eval results (ARC-AGI 87.5%), not a public model
release. Report treats these as three distinct lineage events.

---

### text-davinci-003 (and earlier GPT-3 / InstructGPT lineage)

- Release: 2022-11-28
- Status: decommissioned
- Decommissioned: 2024-01-04
- Context: 4,097 tokens
- Modality: text (completion API)
- Price (in/out per 1M): historical $20.00 / $20.00 (single rate, completion API)
- Notable: instruction-tuned GPT-3.5 base; powered early ChatGPT before gpt-3.5-turbo;
  the "modern" InstructGPT line that fed everything that came after.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://news.ycombinator.com/item?id=33780720
    publisher: Hacker News
    title: "New GPT-3 model: text-davinci-003"
    date: 2022-11-28
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2022/12/01/while-anticipation-builds-for-gpt-4-openai-quietly-releases-gpt-3-5/
    publisher: TechCrunch
    title: "While anticipation builds for GPT-4, OpenAI quietly releases GPT-3.5"
    date: 2022-12-01
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2023-07-06

Benchmarks: No modern-suite numbers (the SWE-bench/MMLU-Pro era postdates this
model). Numbers absent.

Notes: text-davinci-002 was retired the same date (2024-01-04). Replacement
recommendation in deprecation table: gpt-3.5-turbo-instruct. The completion-API
shape is gone — Chat Completions replaced it.

---

### ChatGPT (the consumer product, GPT-3.5-powered initial launch)

- Release: 2022-11-30 (consumer launch)
- Status: current (product; backing model has rotated through 3.5-turbo → 4 → 4o → 5 → 5.x → 5.5)
- Notable: not a separate model SKU. Initial release ran on a GPT-3.5 variant
  Sam Altman called "gpt-3.5"; behind the API this maps to the
  `gpt-3.5-turbo-0301` family.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://www.searchenginejournal.com/history-of-chatgpt-timeline/488370/
    publisher: Search Engine Journal
    title: "Timeline of ChatGPT Updates & Key Events"
    date: 2024

Notes: included as a lineage anchor only — the product is not a benchmarkable
model. Current backing on consumer ChatGPT (May 2026) is GPT-5.5 for Plus/Pro
tiers after the Feb 13 2026 retirement of GPT-4o/4.1/4.1-mini/o4-mini from
ChatGPT.

---

### gpt-3.5-turbo (0301 / 0613 / 16k-0613 / 1106 / 0125)

- Release: 2023-03-01 (gpt-3.5-turbo-0301); subsequent dated snapshots 2023-06-13,
  2023-11-06, 2024-01-25
- Status: deprecated (full family in shutdown wave through 2026)
- Decommissioned (per ID):
  - gpt-3.5-turbo-0301: 2024-09-13
  - gpt-3.5-turbo-0613: 2024-09-13
  - gpt-3.5-turbo-16k-0613: 2024-09-13
  - gpt-3.5-turbo-1106: 2026-09-28
  - gpt-3.5-turbo-0125 / gpt-3.5-turbo alias: 2026-10-23
- Context: 4K (0301), 16K (16k-0613), 16K (1106 / 0125)
- Modality: text
- Price (in/out per 1M): final pricing for `gpt-3.5-turbo-0125` $0.50 / $1.50
- Notable: budget chat workhorse that defined the ChatGPT-API era 2023–2024;
  superseded by gpt-4o-mini in 2024.
- Sources:
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2023-06-13
  - kind: announcement
    tag: lab
    url: https://openai.com/index/new-models-and-developer-products-announced-at-devday/
    title: "New models and developer products announced at DevDay"
    date: 2023-11-06

Benchmarks: HumanEval 73% (0613), MMLU 70% range — historical context only.
Comprehensive lab benchmark tables absent for individual snapshots.

Notes: `gpt-3.5-turbo-instruct` (the completion-shape successor to text-davinci-003)
shut down 2026-09-28 alongside `babbage-002` and `davinci-002` (the
base-completion legacy IDs).

---

### GPT-4 (gpt-4-0314 / gpt-4-0613 / gpt-4-32k)

- Release: 2023-03-14
- Status: deprecated; mostly decommissioned
- Decommissioned:
  - gpt-4-0314: 2026-03-26
  - gpt-4-0613 / gpt-4 alias: 2026-10-23
  - gpt-4-32k / 32k-0314 / 32k-0613: 2025-06-06
- Context: 8K (default), 32K (32k variant)
- Modality: text
- Price (in/out per 1M): $30 / $60 (8K); $60 / $120 (32K) — historical
- Notable: first GPT-4-class general API; benchmark-leader in early 2023.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/gpt-4-research/
    title: "GPT-4"
    date: 2023-03-14
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2024-06-06
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/GPT-4
    publisher: Wikipedia
    title: "GPT-4"
    date: 2026-05

Benchmarks (lab, from GPT-4 technical report):
- MMLU (5-shot): 86.4 [lab] src=https://openai.com/index/gpt-4-research/ date=2023-03
- HumanEval: 67.0 [lab] src=https://openai.com/index/gpt-4-research/ date=2023-03
- MATH: 42.5 [lab] src=https://openai.com/index/gpt-4-research/ date=2023-03
- GSM8K: 92.0 [lab] src=https://openai.com/index/gpt-4-research/ date=2023-03

Notes: legacy MMLU-only era. SWE-bench / GPQA-Diamond / FrontierMath had not
been established as standard suites; the comparable-numbers era starts with
GPT-4 Turbo / Claude 3 / Gemini 1.

---

### GPT-4-Vision (gpt-4-vision-preview)

- Release: 2023-09-25 (ChatGPT rollout); 2023-11-06 (API as `gpt-4-vision-preview`)
- Status: decommissioned
- Decommissioned: 2024-12-06
- Context: 128K (folded into GPT-4 Turbo branch by GA)
- Modality: text + vision
- Price (in/out per 1M): $10 / $30 (rolled into gpt-4-turbo-2024-04-09)
- Notable: first multimodal GPT-4 SKU; folded into gpt-4-turbo when GA went out
  in April 2024.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/openai-makes-gpt-4-turbo-with-vision-generally-available-through-its-api
    publisher: VentureBeat
    title: "OpenAI makes GPT-4 Turbo with Vision generally available through its API"
    date: 2024-04-09
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2024-06-06

---

### GPT-4 Turbo (gpt-4-1106-preview / 0125-preview / turbo-2024-04-09)

- Release: 2023-11-06 (1106-preview at DevDay); 2024-01-25 (0125-preview);
  2024-04-09 (gpt-4-turbo-2024-04-09 GA)
- Status: deprecated; in shutdown queue
- Decommissioned:
  - gpt-4-1106-preview: announced 2025-09-26, original 2026-03-26;
    re-announced 2026-04-22 with new shutdown 2026-10-23
  - gpt-4-0125-preview / gpt-4-turbo-preview: 2026-03-26
  - gpt-4-turbo / gpt-4-turbo-2024-04-09: 2026-10-23
- Context: 128K tokens
- Modality: text + vision (from April 2024 GA)
- Price (in/out per 1M): $10 / $30
- Notable: 3x cheaper input than original GPT-4; the first 128K-context OpenAI
  model; bridge to the GPT-4o omnimodal era.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/new-models-and-developer-products-announced-at-devday/
    title: "New models and developer products announced at DevDay"
    date: 2023-11-06
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2023/11/06/openai-launches-gpt-4-turbo-and-launches-fine-tuning-program-for-gpt-4/
    publisher: TechCrunch
    title: "OpenAI debuts GPT-4 Turbo and fine-tuning program for GPT-4"
    date: 2023-11-06
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2025-09-26

Benchmarks: OpenAI did not publish a separate GPT-4 Turbo MMLU score at DevDay;
the inheritance from base GPT-4 (86.4 5-shot) was assumed but not re-evaluated
in the launch communication. No standalone Turbo benchmark table in OpenAI
sources.

Notes: training data cutoff April 2023 (1106), December 2023 (0125), December
2023 (turbo-2024-04-09). The gpt-4-1106-preview entry appears TWICE on the
deprecation table — the original Mar 2026 shutdown was extended into the
April 2026 deprecation wave.

---

### GPT-4o ("omni") — gpt-4o-2024-05-13 / 2024-08-06 / 2024-11-20

- Release: 2024-05-13 (May 2024 omnimodel launch)
- Status: deprecated (retired from ChatGPT 2026-02-13); API in shutdown wave
- Decommissioned:
  - gpt-4o-2024-05-13: 2026-10-23
  - ChatGPT GPT-4o: 2026-02-13
- Context: 128K tokens
- Modality: text + image + audio (true omnimodel — though audio for API came
  via separate gpt-4o-audio-preview / realtime-preview SKUs in Oct 2024)
- Price (in/out per 1M): $2.50 / $10.00 (then $5/$15 at launch; cut Aug 2024)
- Notable: "omni" — text/vision/audio in one model; 2× faster + 50% cheaper than
  GPT-4 Turbo; the default ChatGPT model 2024-mid through 2025-mid.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/hello-gpt-4o/
    title: "Hello GPT-4o"
    date: 2024-05-13
  - kind: announcement
    tag: lab
    url: https://openai.com/index/retiring-gpt-4o-and-older-models/
    title: "Retiring GPT-4o, GPT-4.1, GPT-4.1 mini, and OpenAI o4-mini in ChatGPT"
    date: 2026-02-13
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2026-04-22

Benchmarks (lab, from Hello GPT-4o):
- MMLU (0-shot CoT): 88.7 [lab] src=https://openai.com/index/hello-gpt-4o/ date=2024-05
- HumanEval: 90.2 [lab] src=https://openai.com/index/hello-gpt-4o/ date=2024-05
- GPQA: 53.6 [lab] src=https://openai.com/index/hello-gpt-4o/ date=2024-05
- MATH: 76.6 [lab] src=https://openai.com/index/hello-gpt-4o/ date=2024-05

Notes: the Aug 6 and Nov 20 snapshots increased max output tokens (4K → 16K)
and improved instruction following but kept the same headline benchmarks. The
ChatGPT-version drift from API-version led to the persistence of GPT-4o as a
ChatGPT brand long after GPT-5 shipped — only fully retired Feb 2026.

---

### GPT-4o-mini

- Release: 2024-07-18
- Status: legacy / deprecated (announced retirement from ChatGPT 2026-02-13;
  no explicit API shutdown date yet but in the same wave)
- Context: 128K tokens
- Modality: text + vision
- Price (in/out per 1M): $0.15 / $0.60
- Notable: replaced gpt-3.5-turbo as the budget tier; 60%+ cheaper.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/
    title: "GPT-4o mini: advancing cost-efficient intelligence"
    date: 2024-07-18

Benchmarks (lab):
- MMLU: 82.0 [lab] src=https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/ date=2024-07
- MGSM: 87.0 [lab] src=https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/ date=2024-07
- HumanEval: 87.2 [lab] src=https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/ date=2024-07
- MMMU: 59.4 [lab] src=https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/ date=2024-07

---

### o1-preview & o1-mini (Sept 2024 reasoning preview)

- Release: 2024-09-12 (both — preview models)
- Status: decommissioned
- Decommissioned: o1-preview 2025-07-28; o1-mini 2025-10-27
- Context: 128K tokens
- Modality: text
- Price (in/out per 1M): o1-preview $15.00 / $60.00; o1-mini $3.00 / $12.00
- Notable: first OpenAI test-time-compute reasoning models. Substantial step on
  math/coding eval suites versus GPT-4o.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/learning-to-reason-with-llms/
    title: "Learning to reason with LLMs"
    date: 2024-09-12
  - kind: announcement
    tag: lab
    url: https://openai.com/index/openai-o1-mini-advancing-cost-efficient-reasoning/
    title: "OpenAI o1-mini"
    date: 2024-09-12
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2025-04-28

Benchmarks (lab, o1-preview):
- AIME 2024 (single sample): 74% [lab] src=https://openai.com/index/learning-to-reason-with-llms/ date=2024-09
- AIME 2024 (cons@64): 83% [lab] src=https://openai.com/index/learning-to-reason-with-llms/ date=2024-09
- Codeforces Elo: 1673 (89th pctile) [lab] src=https://openai.com/index/learning-to-reason-with-llms/ date=2024-09
- GPQA Diamond: 78% [lab] src=https://openai.com/index/learning-to-reason-with-llms/ date=2024-09

---

### o1 (GA) & o1-pro (Dec 5 2024)

- Release: 2024-12-05 (o1 GA + ChatGPT Pro launch; o1-pro = ChatGPT Pro mode);
  o1-pro API as `o1-pro-2025-03-19` shipped March 2025
- Status: deprecated; in shutdown wave
- Decommissioned:
  - o1 / o1-2024-12-17: 2026-10-23
  - o1-pro / o1-pro-2025-03-19: 2026-10-23
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): o1 $15.00 / $60.00; o1-pro $150.00 / $600.00
- Notable: first reasoning-model GA. o1-pro is **BOTH** (a) the ChatGPT Pro
  "o1 pro mode" reasoning-effort variant ($200/mo plan) AND (b) a separate API
  SKU (`o1-pro-2025-03-19`) priced 10× the standard o1 — they run the same
  weights at different reasoning-effort budgets.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-chatgpt-pro/
    title: "Introducing ChatGPT Pro"
    date: 2024-12-05
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2026-04-22

Benchmarks (lab, o1):
- AIME 2024: 78% [lab] (single sample), 86% [lab] (pro mode) src=https://openai.com/index/introducing-chatgpt-pro/ date=2024-12
- Codeforces Elo: 1891 [lab] src=https://openai.com/index/openai-o1/ date=2024-12
- GPQA Diamond (Physics): 92.8 [lab] src=https://openai.com/index/openai-o1/ date=2024-12

---

### o3 (announcement, Dec 20 2024) — not a public release

- Announcement: 2024-12-20 (final day of "12 Days of OpenAI" / "Shipmas")
- Public access at the time: none — only eval results disclosed
- Notable: ARC-AGI Semi-Private high-compute score 87.5%; SWE-bench Verified
  71.7%; FrontierMath 25.2% — disclosed by Sam Altman and Mark Chen at the
  ARC Prize offices. No model artifact shipped; access was deferred to o3-mini
  (Jan 2025) and full o3 (April 2025).
- Sources:
  - kind: coverage
    tag: 3p
    url: https://arcprize.org/blog/oai-o3-pub-breakthrough
    publisher: ARC Prize
    title: "OpenAI o3 Breakthrough High Score on ARC-AGI-Pub"
    date: 2024-12-20
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2024/12/20/openai-announces-new-o3-model/
    publisher: TechCrunch
    title: "OpenAI announces new o3 models"
    date: 2024-12-20

Notes: this entry exists for lineage clarity. The "o3-preview" naming in the
user's checklist refers to this announcement; OpenAI itself never shipped a
model called o3-preview. The Dec 2024 disclosure was followed by o3-mini
(Jan 31 2025) and then full o3 (April 16 2025).

---

### o3-mini (Jan 31 2025)

- Release: 2025-01-31
- Status: deprecated; in shutdown wave
- Decommissioned: o3-mini / o3-mini-2025-01-31: 2026-10-23
- Context: 200K tokens
- Modality: text
- Price (in/out per 1M): $1.10 / $4.40
- Notable: first non-preview reasoning model with three reasoning-effort levels
  (low/medium/high); cheaper than o1-mini with better performance.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/openai-o3-mini/
    title: "OpenAI o3-mini"
    date: 2025-01-31
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2026-04-22

Benchmarks (lab):
- GPQA Diamond (high effort): 77 [lab] src=https://openai.com/index/openai-o3-mini/ date=2025-01
- Codeforces Elo (high effort): 2073 [lab] src=https://openai.com/index/openai-o3-mini/ date=2025-01
- AIME 2024 (high effort): 87.3 [lab] src=https://openai.com/index/openai-o3-mini/ date=2025-01
- SWE-bench Verified (high effort): 49.3 [lab] src=https://openai.com/index/openai-o3-mini/ date=2025-01

---

### GPT-4.5 ("Orion") — research preview

- Release: 2025-02-27 (research preview)
- Status: decommissioned
- Decommissioned: 2025-07-14 (only 4.5 months of API availability)
- Context: 128K tokens
- Modality: text + vision
- Price (in/out per 1M): $75.00 / $150.00 — by far the most expensive OpenAI
  API SKU ever shipped
- Notable: largest pretrained OpenAI model to date; ChatGPT Pro ($200/mo)
  exclusive at launch; underperformed reasoning models on math/coding,
  outperformed on SimpleQA factual accuracy. Replaced by GPT-4.1 three months
  after launch.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2025/02/27/openai-unveils-gpt-4-5-orion-its-largest-ai-model-yet/
    publisher: TechCrunch
    title: "OpenAI unveils GPT-4.5 'Orion,' its largest AI model yet"
    date: 2025-02-27
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/GPT-4.5
    publisher: Wikipedia
    title: "GPT-4.5"
    date: 2026-05
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2025-04-14

Benchmarks: SimpleQA (factual) leading among non-reasoning OpenAI models at
launch; underperformed o1/o3-mini on AIME 2024 and Codeforces.

Notes: shortest-lived flagship-class SKU in OpenAI history. Estimated 4–5
trillion parameters per outside analysts. Pricing made it a poor cost-per-token
deal; lab pivoted to the GPT-4.1 distillation series immediately after.

---

### GPT-4.1 / 4.1-mini / 4.1-nano

- Release: 2025-04-14 (all three SKUs simultaneously)
- Status: deprecated (4.1-nano in shutdown wave; 4.1 itself retired from ChatGPT
  2026-02-13)
- Decommissioned:
  - gpt-4.1-nano / -2025-04-14: 2026-10-23
  - GPT-4.1 in ChatGPT: 2026-02-13
- Context: 1,047,576 tokens (≈1M) — first OpenAI 1M-context SKU
- Modality: text + vision
- Price (in/out per 1M): GPT-4.1 $2.00 / $8.00; 4.1-mini $0.40 / $1.60;
  4.1-nano $0.10 / $0.40
- Notable: first 1M-context OpenAI model; explicit cost/perf upgrade over GPT-4o;
  succeeded GPT-4.5 Orion which was retired the same week.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/gpt-4-1/
    title: "Introducing GPT-4.1 in the API"
    date: 2025-04-14
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2026-04-22

Benchmarks (lab):
- SWE-bench Verified: 54.6 [lab] src=https://openai.com/index/gpt-4-1/ date=2025-04
- Scale MultiChallenge: 38.3 [lab] src=https://openai.com/index/gpt-4-1/ date=2025-04
- Video-MME (long, no subtitles): 72.0 [lab] src=https://openai.com/index/gpt-4-1/ date=2025-04

Notes: SWE-bench Verified jumped 21.4 points over GPT-4o and 26.6 over GPT-4.5.
4.1-nano was OpenAI's smallest/cheapest production model until gpt-5-nano.

---

### o3 (GA) and o4-mini

- Release: 2025-04-16
- Status: deprecated; in shutdown wave
- Decommissioned:
  - o4-mini / -2025-04-16: 2026-10-23 (API); 2026-02-13 (ChatGPT)
  - o3 itself: no specific shutdown date — Aug 2025 "GPT-5 retires o3" lifecycle
    indicates phasing; not on October 2026 wave but path forward unclear
- Context: 200K tokens
- Modality: text + vision (multimodal reasoning)
- Price (in/out per 1M): o3 $2.00 / $8.00 (after June 2025 80% price cut from
  original $10/$40); o4-mini $1.10 / $4.40
- Notable: first OpenAI models that reason *with* images (chain-of-thought
  includes image manipulation). o3 hit SWE-bench Verified 69.1% at launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-o3-and-o4-mini/
    title: "Introducing OpenAI o3 and o4-mini"
    date: 2025-04-16
  - kind: model-card
    tag: lab
    url: https://cdn.openai.com/pdf/2221c875-02dc-4789-800b-e7758f3722c1/o3-and-o4-mini-system-card.pdf
    title: "OpenAI o3 and o4-mini System Card"
    date: 2025-04-16
  - kind: coverage
    tag: 3p
    url: https://techcrunch.com/2025/04/16/openai-launches-a-pair-of-ai-reasoning-models-o3-and-o4-mini/
    publisher: TechCrunch
    title: "OpenAI launches a pair of AI reasoning models, o3 and o4-mini"
    date: 2025-04-16

Benchmarks (lab, o3 unless noted):
- SWE-bench Verified: 69.1 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04
- AIME 2025: 88.9 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04
- ARC-AGI-1 (high compute): 87.5 [lab] src=https://arcprize.org/blog/oai-o3-pub-breakthrough date=2024-12
- ARC-AGI-2 (medium): 2.9 [3p:ARC Prize] src=https://arcprize.org/blog/analyzing-o3-with-arc-agi date=2025-04
- Codeforces Elo: 2706 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04

Benchmarks (lab, o4-mini):
- AIME 2024 (no tools): 93.4 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04
- AIME 2025: 92.7 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04
- SWE-bench Verified: 68.1 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04
- Codeforces Elo (with terminal): 2719 [lab] src=https://openai.com/index/introducing-o3-and-o4-mini/ date=2025-04

Notes: o4-mini beat o3 on Codeforces and AIME 2024 — first time a "mini"
variant exceeded its full counterpart in OpenAI's lineup.

---

### Computer-Using Agent (CUA) — Operator backbone

- Release: 2025-01-23 (research preview as Operator at operator.chatgpt.com)
- Status: superseded — folded into o3-Operator addendum (Apr 2025) and then into
  agentic capabilities of GPT-5/GPT-5.4 mainline (computer use native)
- Decommissioned: `computer-use-preview-2025-03-11` API SKU: 2026-07-23
- Context: 128K tokens (built on GPT-4o vision base)
- Modality: text + vision (screenshot-based GUI interaction)
- Price (in/out per 1M): $3.00 / $12.00 (computer-use-preview)
- Notable: first OpenAI agentic-LLM SKU; OSWorld 38.1%, WebArena 58.1%,
  WebVoyager 87% at launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/computer-using-agent/
    title: "Computer-Using Agent"
    date: 2025-01-23
  - kind: model-card
    tag: lab
    url: https://openai.com/index/operator-system-card/
    title: "Operator System Card"
    date: 2025-01-23
  - kind: deprecation
    tag: lab
    url: https://community.openai.com/t/deprecation-notice-upcoming-model-shutdowns-in-2026/1379553
    title: "Deprecation notice: upcoming model shutdowns in 2026"
    date: 2026-04-22

Benchmarks (lab):
- OSWorld: 38.1 [lab] src=https://openai.com/index/computer-using-agent/ date=2025-01
- WebArena: 58.1 [lab] src=https://openai.com/index/computer-using-agent/ date=2025-01
- WebVoyager: 87.0 [lab] src=https://openai.com/index/computer-using-agent/ date=2025-01

Notes: succeeded by `o3-operator` addendum April 2025; computer-use is now
native in GPT-5.4 (75% OSWorld) and GPT-5.5 (78.7% OSWorld-Verified).

---

### o3-pro

- Release: 2025-06-10 (API + ChatGPT Pro tier)
- Status: deprecated; in shutdown wave
- Decommissioned: o3-pro is being phased toward gpt-5.5-pro replacements; no
  explicit shutdown date currently listed (the related o3-deep-research /
  o4-mini-deep-research shut down 2026-07-23)
- Context: 200K tokens
- Modality: text + vision
- Price (in/out per 1M): $20.00 / $80.00 — 10× the standard o3 after the June
  2025 80% price cut on standard o3
- Notable: **separate API SKU** with its own pricing, NOT just a reasoning-effort
  variant. Bundles real-time web search, file analysis, visual reasoning,
  Python execution, and memory access.
- Sources:
  - kind: announcement
    tag: lab
    url: https://community.openai.com/t/o3-is-80-cheaper-and-introducing-o3-pro/1284925
    title: "O3 is 80% cheaper and introducing o3-pro"
    date: 2025-06-10
  - kind: pricing
    tag: 3p
    url: https://www.cometapi.com/openais-o3%E2%80%91pro-benchmarks-pricing-and-access/
    publisher: CometAPI
    title: "OpenAI's o3-pro: Benchmarks, Pricing & Access"
    date: 2025-06

---

### Codex (May 2025 agentic coding launch — codex-1)

- Release: 2025-05-16 (research preview as "Codex Cloud"); Codex CLI launched
  2025-04-16 alongside o3/o4-mini
- Status: superseded — codex-1 replaced by gpt-5-codex (Sep 2025), then
  gpt-5.1-codex / gpt-5.2-codex / gpt-5.3-codex
- Context: 200K (o3 base)
- Modality: text + code
- Price (in/out per 1M): metered via ChatGPT Pro subscription at launch; API
  via o3 base pricing
- Notable: codex-1 = o3 finetune for software engineering; cloud sandboxes per
  task, multi-file edits, PR proposals.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-codex/
    title: "Introducing Codex"
    date: 2025-05-16
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/OpenAI_Codex_(AI_agent)
    publisher: Wikipedia
    title: "Codex (AI agent)"
    date: 2026

---

### gpt-oss-120b and gpt-oss-20b (open-weights)

- Release: 2025-08-05
- Status: current (Apache 2.0 open-weights — no shutdown applicable)
- Context: 128K tokens
- Modality: text (reasoning, with tool-use)
- Price (in/out per 1M): N/A — weights only; OpenAI lists no first-party API
  pricing
- Notable: first OpenAI open-weights since GPT-2 (2019). MoE architecture:
  gpt-oss-120b activates 5.1B params/token; gpt-oss-20b activates 3.6B.
  Three reasoning-effort levels (low/medium/high). gpt-oss-20b runs on 16GB
  consumer hardware.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-oss/
    title: "Introducing gpt-oss"
    date: 2025-08-05
  - kind: model-card
    tag: lab
    url: https://openai.com/index/gpt-oss-model-card/
    title: "gpt-oss-120b & gpt-oss-20b Model Card"
    date: 2025-08-05
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2025/Aug/5/gpt-oss/
    publisher: Simon Willison
    title: "OpenAI's new open weight (Apache 2) models are really good"
    date: 2025-08-05

Benchmarks (lab):
- gpt-oss-120b matches/exceeds o4-mini on Codeforces, MMLU, HLE, TauBench [lab]
  src=https://openai.com/index/introducing-gpt-oss/ date=2025-08
- gpt-oss-120b exceeds o4-mini on HealthBench, AIME 2024, AIME 2025 [lab]
  src=https://openai.com/index/introducing-gpt-oss/ date=2025-08
- gpt-oss-20b matches o3-mini on standard suites [lab]
  src=https://openai.com/index/introducing-gpt-oss/ date=2025-08

Notes: only OpenAI open-weights releases in scope; no follow-up gpt-oss generation
has shipped as of May 2026.

---

### GPT-5 (gpt-5 / gpt-5-mini / gpt-5-nano / gpt-5-chat-latest / gpt-5-codex)

- Release: 2025-08-07
- Status: deprecated; in shutdown wave
- Decommissioned:
  - gpt-5-chat-latest: 2026-07-23
  - gpt-5-codex: 2026-07-23
  - GPT-5 (Instant / Thinking / Pro in ChatGPT): retired 2026-02-13
- Context: 272K input + 128K output ≈ 400K total
- Modality: text + vision
- Price (in/out per 1M): GPT-5 $1.25 / $10.00; GPT-5-mini $0.25 / $2.00;
  GPT-5-nano $0.05 / $0.40
- Notable: unified "reasoning + chat" routing — minimal/low/medium/high
  reasoning effort; first OpenAI model called a "GPT" since 4.5 (the o-series
  ran parallel). Launch SKUs: `gpt-5-main`, `gpt-5-main-mini`,
  `gpt-5-thinking-pro` (ChatGPT Pro exclusive). Codex variant
  (`gpt-5-codex`) shipped Sept 15 2025 — first GPT-5 optimized for agentic
  coding, runs autonomously >7 hours on long-horizon tasks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-5/
    title: "Introducing GPT-5"
    date: 2025-08-07
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2025/Aug/7/gpt-5/
    publisher: Simon Willison
    title: "GPT-5: Key characteristics, pricing and model card"
    date: 2025-08-07
  - kind: coverage
    tag: 3p
    url: https://venturebeat.com/ai/openai-unveils-new-model-gpt-5-codex-optimized-for-agentic-coding
    publisher: VentureBeat
    title: "OpenAI unveils new model GPT-5-Codex"
    date: 2025-09-15

Benchmarks (3p, GPT-5 high effort):
- GPQA Diamond: 84.2 [3p:artificialanalysis.ai] src=https://artificialanalysis.ai/models/gpt-5 date=2025-08
- MMLU-Pro: 86.7 [3p:artificialanalysis.ai] src=https://artificialanalysis.ai/models/gpt-5 date=2025-08
- MATH 500: 99.1 [3p:artificialanalysis.ai] src=https://artificialanalysis.ai/models/gpt-5 date=2025-08
- AIME: 91.7 [3p:artificialanalysis.ai] src=https://artificialanalysis.ai/models/gpt-5 date=2025-08

Notes: Sam Altman publicly stated the launch was "botched" — colder persona
forced reinstatement of GPT-4o for free-tier users. By Feb 2026 the entire
GPT-5 ChatGPT family (Instant/Thinking/Pro) was retired in favor of GPT-5.4.

---

### GPT-5.1 (gpt-5.1 / gpt-5.1-codex / gpt-5.1-codex-max / gpt-5.1-codex-mini)

- Release: 2025-11-13
- Status: deprecated; in shutdown wave
- Decommissioned:
  - gpt-5.1-chat-latest / gpt-5.1-codex / gpt-5.1-codex-max / gpt-5.1-codex-mini:
    2026-07-23
  - GPT-5.1 in ChatGPT: 2026-03-11
- Context: 410K tokens (input) + 128K output
- Modality: text + vision
- Price (in/out per 1M): $1.25 / $10.00 (same as GPT-5)
- Notable: first dynamic-thinking-time model — adapts reasoning depth to task
  complexity rather than fixed effort levels.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://cloudprice.net/models/openai-gpt-5-1
    publisher: CloudPrice
    title: "GPT-5.1 pricing & specs"
    date: 2025-11-13
  - kind: coverage
    tag: 3p
    url: https://claude5.com/news/gpt-5-1-performance-review-benchmarks-november-2025
    publisher: Claude5 Hub
    title: "GPT-5.1 Review: OpenAI's Benchmark Champion with 76.3% SWE-bench Score"
    date: 2025-11
  - kind: deprecation
    tag: lab
    url: https://developers.openai.com/api/docs/deprecations
    title: "OpenAI API model deprecations"
    date: 2026-04-22

Benchmarks (lab/3p):
- SWE-bench Verified: 76.3 [3p:artificialanalysis.ai] src=https://artificialanalysis.ai/ date=2025-11
- AIME 2025: 94 [3p:artificialanalysis.ai] date=2025-11
- SWE-bench Verified (500 real GitHub issues): 381/500 [3p] date=2025-11

---

### GPT-5.2 (gpt-5.2 / gpt-5.2-codex / gpt-5.2-chat-latest)

- Release: 2025-12-10
- Status: deprecated; in shutdown wave
- Decommissioned:
  - gpt-5.2-codex: 2026-10-23
  - gpt-5.2-chat-latest: 2026-08-10
- Context: 400K tokens
- Modality: text + vision
- Price (in/out per 1M): $0.875 / $7.00 — first OpenAI mainline price cut
  since GPT-4o
- Notable: first OpenAI model to cross 90% on ARC-AGI-1; three ChatGPT variants
  (Instant, Thinking, Pro). gpt-5.2-codex (Dec 18 2025) advanced secure-coding
  agentic workflows.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-5-2/
    title: "Introducing GPT-5.2"
    date: 2025-12-10
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-5-2-codex/
    title: "Introducing GPT-5.2-Codex"
    date: 2025-12-18
  - kind: pricing
    tag: 3p
    url: https://pricepertoken.com/pricing-page/model/openai-gpt-5.2
    publisher: PricePerToken
    title: "GPT-5.2 API Pricing 2026"
    date: 2026

Benchmarks (lab):
- ARC-AGI-1: ≥90 [lab] src=https://openai.com/index/introducing-gpt-5-2/ date=2025-12
- GPQA Diamond: 93.2 [lab] src=https://openai.com/index/introducing-gpt-5-2/ date=2025-12

---

### GPT-5.3 (gpt-5.3 / gpt-5.3-codex)

- Release: 2026-02-24
- Status: deprecated (chat-latest in shutdown wave)
- Decommissioned: gpt-5.3-chat-latest: 2026-08-10
- Context: 400K tokens
- Modality: text + vision
- Price (in/out per 1M): $1.75 / $14.00
- Notable: 26.8% fewer hallucinations than GPT-5.2 at same pricing
  (5.3-Instant); gpt-5.3-codex was the inflection point for "production-reliable
  autonomous coding agents" per OpenAI Developer community posts.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-5-3-codex/
    title: "Introducing GPT-5.3-Codex"
    date: 2026-02-24
  - kind: pricing
    tag: 3p
    url: https://pricepertoken.com/pricing-page/model/openai-gpt-5.3-codex
    publisher: PricePerToken
    title: "GPT-5.3 Codex API Pricing 2026"
    date: 2026

---

### GPT-5.4 / GPT-5.4 Pro / GPT-5.4-mini / GPT-5.4-nano

- Release: 2026-03-05 (5.4 mainline + Pro); 2026-03-17 (mini, nano)
- Status: current (recent flagship before GPT-5.5)
- Context: 1M tokens
- Modality: text + vision (native computer-use built in)
- Price (in/out per 1M): GPT-5.4 $2.50 / $15.00; GPT-5.4 Pro $30.00 / $180.00;
  5.4-mini ~$0.40 / $1.60; 5.4-nano (~$0.10 / $0.40 — successor to gpt-4.1-nano)
- Notable: first OpenAI model with **native computer-use** built into the base
  model (not a separate Operator SKU); 75% OSWorld — first model above the
  72.4% human-expert baseline. Introduces tool-search mechanism cutting tool
  token cost by 47%. **GPT-5.4 Pro is a separate API SKU** with distinct
  pricing, not just higher reasoning effort.
- Sources:
  - kind: coverage
    tag: 3p
    url: https://almcorp.com/blog/gpt-5-4/
    publisher: ALM Corp
    title: "OpenAI GPT-5.4: Features, Benchmarks, Pricing & Computer Use (2026)"
    date: 2026-03-05
  - kind: coverage
    tag: 3p
    url: https://www.nxcode.io/resources/news/gpt-5-4-release-date-features-pricing-2026
    publisher: NxCode
    title: "GPT-5.4 (March 2026): 75% Computer Use, 1M Context, $2.50/MTok"
    date: 2026-03-05
  - kind: pricing
    tag: 3p
    url: https://pricepertoken.com/pricing-page/model/openai-gpt-5.4
    publisher: PricePerToken
    title: "GPT-5.4 API Pricing 2026"
    date: 2026

Benchmarks (3p Anthropic-cross-lab and lab):
- SWE-Bench Pro: 57.7 [3p:Anthropic-cross] (in Opus 4.7 launch comparison)
- Terminal-Bench 2.0: 75.1 [lab]
- BrowseComp (Pro variant): 89.3 [lab]
- HLE no-tools (Pro): 42.7 [lab]
- HLE with-tools (Pro): 58.7 [lab]
- MCP-Atlas: 68.1 [lab]
- OSWorld-V: 75.0 [lab]
- Finance v1.1 (Pro): 61.5 [lab]
- CyberGym: 66.3 [lab]
- GPQA Diamond (Pro): 94.4 [lab]
- SWE-Pro Scale Public: 59.10 ±3.56 [3p:Scale]
- DualEntry: 77.3 [3p]
- FrontierMath T1-3 (Pro): 50.0 [3p:Anthropic-cross]
- FrontierMath T4 (Pro): 38.0 [3p:Anthropic-cross]

Notes: GPT-5.4 Pro pricing ($30/$180) is identical to GPT-5.5 Pro pricing,
reflecting OpenAI's Pro tier ceiling.

---

### GPT-5.5 / GPT-5.5 Pro (current flagship, May 2026)

- Release: 2026-04-23 (ChatGPT); 2026-04-24 (API)
- Status: current
- Context: 1M tokens
- Modality: text + vision + omnimodal (audio/video unified architecture per
  launch claims)
- Price (in/out per 1M): GPT-5.5 $5.00 / $30.00 (doubled from GPT-5.4);
  GPT-5.5 Pro $30.00 / $180.00; Codex variant (gpt-5.5-codex) included with
  subscription tier, 400K context, 2.5× faster execution
- Notable: 40% fewer output tokens for equivalent tasks vs GPT-5.4; MRCR v2 at
  1M tokens doubled (36.6% → 74.0%). Hardware co-designed with NVIDIA
  GB200/GB300 NVL72. Codenamed "Spud" internally. **GPT-5.5 Pro is a separate
  API SKU** with distinct pricing, not just a reasoning-effort variant.
- Sources:
  - kind: announcement
    tag: lab
    url: https://openai.com/index/introducing-gpt-5-5/
    title: "Introducing GPT-5.5"
    date: 2026-04-23
  - kind: announcement
    tag: lab
    url: https://openai.com/index/gpt-5-5/
    title: "GPT-5.5"
    date: 2026-04-23
  - kind: coverage
    tag: 3p
    url: https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5
    publisher: Vellum
    title: "Everything You Need to Know About GPT-5.5"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://llm-stats.com/models/gpt-5.5
    publisher: llm-stats
    title: "GPT-5.5 Benchmarks, Pricing & Context Window"
    date: 2026-04

Benchmarks (lab unless tagged 3p):
- Terminal-Bench 2.0: 82.7 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- Terminal-Bench 2.0: 73.20 [3p:Vals.ai] date=2026-04
- Terminal-Bench 2.1: 78.2 [3p:Google-cross-lab] (Gemini 3.5 Flash eval PDF)
- Terminal-Bench Hard (AA): 60.6 [lab] date=2026-04
- GDPval (pass-rate): 84.9 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- GDPval-AA Elo: 1773 [3p:Google-cross-lab]
- OSWorld-Verified: 78.7 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- Toolathlon: 55.6 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- BrowseComp: 84.4 [lab] (GPT-5.5); 90.1 [lab] (GPT-5.5 Pro)
- FrontierMath T1-3: 51.7 [lab] (GPT-5.5); 52.4 [lab] (Pro)
- FrontierMath T4: 35.4 [lab] (GPT-5.5); 39.6 [lab] (Pro)
- CyberGym: 81.8 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- τ²-Bench Telecom: 98.0 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- ARC-AGI: 95.0 [lab] src=https://openai.com/index/gpt-5-5/ date=2026-04
- ARC-AGI-2: 85.0 [3p:Google-cross-lab]
- MMLU-Pro: 88.14 [3p:llm-stats] src=https://llm-stats.com/models/gpt-5.5 date=2026-04
- SWE-Bench Pro: 58.6 [3p:Google-cross-lab]
- MCP-Atlas: 75.3 [3p:Google-cross-lab]
- Finance Agent v2: 51.8 [3p:Google-cross-lab]
- CharXiv Reasoning: 84.1 [3p:Google-cross-lab]
- MMMU-Pro: 81.2 [3p:Google-cross-lab]
- MRCR 128k: 94.8 [3p:Google-cross-lab]
- MRCR v2 (512K–1M): 74.0 [lab] src=https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5 date=2026-04
- HLE no-tools: 41.4 [lab/3p] date=2026-04
- HLE no-tools (Pro): 43.1 [lab] date=2026-04
- GPQA Diamond: 93.6 [lab] date=2026-04

Notes: On GDPval, Pro (82.3) scored *below* standard GPT-5.5 (84.9) — an
unusual Pro/standard inversion within the same family on a single benchmark.
HLE shows GPT-5.5 below Opus 4.7 (46.9) — first major benchmark where OpenAI
lost the top spot since GPT-5.

---

## Sources (deduplicated)

### OpenAI (lab — announcements, model cards, deprecation)
- https://openai.com/index/gpt-4-research/
- https://openai.com/index/new-models-and-developer-products-announced-at-devday/
- https://openai.com/index/hello-gpt-4o/
- https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/
- https://openai.com/index/learning-to-reason-with-llms/
- https://openai.com/index/openai-o1-mini-advancing-cost-efficient-reasoning/
- https://openai.com/index/introducing-chatgpt-pro/
- https://openai.com/index/openai-o3-mini/
- https://openai.com/index/gpt-4-1/
- https://openai.com/index/introducing-o3-and-o4-mini/
- https://cdn.openai.com/pdf/2221c875-02dc-4789-800b-e7758f3722c1/o3-and-o4-mini-system-card.pdf
- https://openai.com/index/computer-using-agent/
- https://openai.com/index/operator-system-card/
- https://openai.com/index/o3-o4-mini-system-card-addendum-operator-o3/
- https://openai.com/index/introducing-codex/
- https://openai.com/index/introducing-gpt-oss/
- https://openai.com/index/gpt-oss-model-card/
- https://openai.com/index/introducing-gpt-5/
- https://openai.com/index/introducing-gpt-5-2/
- https://openai.com/index/introducing-gpt-5-2-codex/
- https://openai.com/index/introducing-gpt-5-3-codex/
- https://openai.com/index/introducing-gpt-5-5/
- https://openai.com/index/gpt-5-5/
- https://openai.com/index/retiring-gpt-4o-and-older-models/
- https://developers.openai.com/api/docs/deprecations
- https://developers.openai.com/codex/changelog
- https://developers.openai.com/codex/models
- https://community.openai.com/t/o3-is-80-cheaper-and-introducing-o3-pro/1284925
- https://community.openai.com/t/deprecation-notice-upcoming-model-shutdowns-in-2026/1379553

### Third-party coverage / replication
- https://techcrunch.com/2023/11/06/openai-launches-gpt-4-turbo-and-launches-fine-tuning-program-for-gpt-4/
- https://venturebeat.com/ai/openai-makes-gpt-4-turbo-with-vision-generally-available-through-its-api
- https://techcrunch.com/2024/12/20/openai-announces-new-o3-model/
- https://techcrunch.com/2025/02/27/openai-unveils-gpt-4-5-orion-its-largest-ai-model-yet/
- https://techcrunch.com/2025/04/16/openai-launches-a-pair-of-ai-reasoning-models-o3-and-o4-mini/
- https://techcrunch.com/2024/12/05/openai-confirms-its-new-200-plan-chatgpt-pro-which-includes-reasoning-models-and-more/
- https://venturebeat.com/ai/openai-unveils-new-model-gpt-5-codex-optimized-for-agentic-coding
- https://arcprize.org/blog/oai-o3-pub-breakthrough
- https://arcprize.org/blog/analyzing-o3-with-arc-agi
- https://simonwillison.net/2025/Aug/5/gpt-oss/
- https://simonwillison.net/2025/Aug/7/gpt-5/
- https://www.vellum.ai/blog/everything-you-need-to-know-about-gpt-5-5
- https://llm-stats.com/models/gpt-5.5
- https://artificialanalysis.ai/models/gpt-5
- https://artificialanalysis.ai/models/o3-mini
- https://artificialanalysis.ai/models/gpt-4o
- https://artificialanalysis.ai/models/gpt-4o-mini
- https://pricepertoken.com/pricing-page/model/openai-gpt-5
- https://pricepertoken.com/pricing-page/model/openai-gpt-5.2
- https://pricepertoken.com/pricing-page/model/openai-gpt-5.3-codex
- https://pricepertoken.com/pricing-page/model/openai-gpt-5.4
- https://pricepertoken.com/pricing-page/model/openai-o4-mini
- https://cloudprice.net/models/openai-gpt-5-1
- https://almcorp.com/blog/gpt-5-4/
- https://almcorp.com/blog/openai-gpt-5-5-benchmarks-pricing-api-vs-gpt-5-4/
- https://www.nxcode.io/resources/news/gpt-5-4-release-date-features-pricing-2026
- https://www.cometapi.com/openais-o3%E2%80%91pro-benchmarks-pricing-and-access/
- https://claude5.com/news/gpt-5-1-performance-review-benchmarks-november-2025
- https://en.wikipedia.org/wiki/GPT-4
- https://en.wikipedia.org/wiki/GPT-4.5
- https://en.wikipedia.org/wiki/OpenAI_o3
- https://en.wikipedia.org/wiki/OpenAI_Codex_(AI_agent)
- https://www.searchenginejournal.com/history-of-chatgpt-timeline/488370/
- https://news.ycombinator.com/item?id=33780720
- https://techcrunch.com/2022/12/01/while-anticipation-builds-for-gpt-4-openai-quietly-releases-gpt-3-5/
