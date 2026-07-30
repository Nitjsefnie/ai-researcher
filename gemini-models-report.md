# Google Gemini Model Lineage — Complete Reference (May 2026)

Compiled chronologically. Per-model template per coordinator schema:
typed `Sources:` blocks (`announcement`/`model-card`/`pricing`/`deprecation`/`coverage`/`replication`),
and benchmark rows surface both `lab` and `3p` numbers where they disagree by >3pp.

Lifecycle spine sourced from Google's Gemini API deprecation registry and changelog;
per-model release blogs, eval-methodology PDFs, and DeepMind model cards supply benchmarks and pricing.

---

### Gemini 1.0 Ultra

- Release: 2023-12-06 (announced); 2024-02-08 (broad availability via Bard Advanced / "Gemini Advanced")
- Status: retired
- Decommissioned: not formally registered in current deprecations table — Ultra was only ever served via the Gemini app, never via the public Gemini API; Bard Advanced was rebranded into Gemini Advanced and the underlying model moved to 1.5 Pro by mid-2024.
- Context: 32K tokens
- Modality: text + vision + audio + video (natively multimodal)
- Price (in/out per 1M): never offered on the API for direct billing
- Notable: first model to surpass 90% on MMLU (90.0%, ahead of human-expert baseline); 30/32 SOTA on the v1 academic-benchmark suite at launch.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/ai/google-gemini-ai/
    title: "Introducing Gemini: our largest and most capable AI model"
    date: 2023-12-06
  - kind: model-card
    tag: lab
    url: https://arxiv.org/pdf/2312.11805
    title: "Gemini: A Family of Highly Capable Multimodal Models"
    date: 2023-12-19
  - kind: coverage
    tag: 3p
    url: https://en.wikipedia.org/wiki/Gemini_(language_model)
    publisher: Wikipedia
    title: "Gemini (language model)"
    date: 2026-05

Benchmarks (lab from announcement + technical report):
- MMLU (5-shot CoT@32 maj): 90.04 [lab] src=https://blog.google/technology/ai/google-gemini-ai/ date=2023-12-06
- MMMU: 59.4 [lab] src=https://blog.google/technology/ai/google-gemini-ai/ date=2023-12-06
- Big-Bench Hard: 83.6 [lab] src=https://arxiv.org/pdf/2312.11805 date=2023-12
- HumanEval: 74.4 [lab] src=https://arxiv.org/pdf/2312.11805 date=2023-12
- Natural2Code: 74.9 [lab]
- DROP (F1): 82.4 [lab]
- HellaSwag (10-shot): 87.8 [lab]
- MATH: 53.2 [lab]
- GSM8K (maj1@32): 94.4 [lab]

Notes: No SWE-bench / LiveCodeBench published in the v1 era. Ultra never received a public API SKU; Google's deprecation page does not enumerate it.

---

### Gemini 1.0 Pro

- Release: 2023-12-13 (Vertex AI / AI Studio); model ID `gemini-pro` / `gemini-1.0-pro`
- Status: retired
- Decommissioned: 2025-02-15 (sunset announced Aug 2024)
- Context: 32K tokens
- Modality: text (vision split into `gemini-pro-vision`)
- Price (in/out per 1M): historical $0.50 / $1.50 (pre Sept 2024 price cut tiers)
- Notable: first general-purpose Gemini API model; multimodal sibling `gemini-pro-vision` shipped alongside.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/ai/google-gemini-ai/
    title: "Introducing Gemini"
    date: 2023-12-06
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini API model deprecations"
    date: 2024-08

Benchmarks (lab):
- MMLU (5-shot): 71.8 [lab] src=https://arxiv.org/pdf/2312.11805 date=2023-12
- MMMU: 47.9 [lab]
- HumanEval: 67.7 [lab]
- GSM8K (maj1@32): 86.5 [lab]
- MATH: 32.6 [lab]
- Big-Bench Hard: 75.0 [lab]
- DROP: 74.1 [lab]

---

### Gemini 1.0 Nano (Nano-1 / Nano-2)

- Release: 2023-12-06 (with Pixel 8 Pro on-device); two parameter classes: 1.8B (Nano-1) and 3.25B (Nano-2)
- Status: retired (superseded by Gemini Nano v2/v3 on Pixel; on-device only)
- Decommissioned: never had a public API; replaced silently on Pixel firmware updates
- Context: ~8K tokens
- Modality: text (on-device summarization / smart-reply)
- Price (in/out per 1M): not applicable (on-device)
- Notable: first frontier-lab on-device model; quantized 4-bit for mobile NPUs.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/ai/google-gemini-ai/
    title: "Introducing Gemini"
    date: 2023-12-06
  - kind: model-card
    tag: lab
    url: https://arxiv.org/pdf/2312.11805
    title: "Gemini technical report (Nano section)"
    date: 2023-12

Benchmarks (Nano-2, lab from technical report):
- BoolQ: 79.3 [lab]
- TydiQA (GoldP): 68.9 [lab]
- NaturalQuestions (retrieved): 38.6 [lab]
- BIG-Bench Hard: 45.9 [lab]
- MBPP: 27.2 [lab]
- MATH: 22.8 [lab]
- MMLU (5-shot): 45.9 [lab]

Notes: Nano-1 figures are lower across the board (e.g. MMLU 32.6). Not benchmarked against modern SWE-bench / LiveCodeBench / GPQA Diamond.

---

### Gemini 1.5 Pro (Feb-2024 preview)

- Release: 2024-02-15 (limited preview); broader API GA 2024-04-09
- Status: retired
- Decommissioned: 2025-09-29 (entire 1.5 family shut down)
- Context: 1M tokens public; 10M tokens demonstrated in research (text-only / code), 2M tokens via Vertex AI request later
- Modality: text + image + audio + video (natively multimodal)
- Price (in/out per 1M): $7.00 / $21.00 at launch for >128K context; $3.50 / $10.50 ≤128K (Sept 2024 dropped to $1.25 / $5.00 ≤128K, $2.50 / $10.00 >128K)
- Notable: first 1M-token production context window; sparse MoE architecture; near-perfect Needle-in-a-Haystack recall up to 1M tokens.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/
    title: "Our next-generation model: Gemini 1.5"
    date: 2024-02-15
  - kind: model-card
    tag: lab
    url: https://arxiv.org/pdf/2403.05530
    title: "Gemini 1.5: Unlocking multimodal understanding across millions of tokens of context"
    date: 2024-03
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini 1.5 shutdown"
    date: 2025-09-29

Benchmarks (lab from 1.5 tech report; Feb-2024 build):
- MMLU (5-shot): 81.9 [lab] src=https://arxiv.org/pdf/2403.05530 date=2024-03
- MATH (4-shot): 58.5 [lab]
- HumanEval: 71.9 [lab]
- GSM8K (11-shot): 91.7 [lab]
- MMMU: 58.5 [lab]
- Big-Bench Hard: 84.0 [lab]
- Needle-in-Haystack @ 1M: ~99% recall (text), ~99.7% (video), ~100% (audio) [lab]
- Needle-in-Haystack @ 10M (research): >99% recall [lab]

Notes: Sept 2024 002 refresh (see next entry) reported ~7% MMLU-Pro gain and ~20% gain on MATH/HiddenMath versus this build.

---

### Gemini 1.5 Pro 002 / Flash 002 (Sept-2024 stable refresh)

- Release: 2024-09-24
- Status: retired
- Decommissioned: 2025-09-29
- Context: 2M tokens (Pro) / 1M tokens (Flash)
- Modality: text + image + audio + video
- Price (in/out per 1M, Pro): $1.25 / $5.00 ≤128K; $2.50 / $10.00 >128K (~50% reduction vs Feb build)
- Notable: stable production IDs `gemini-1.5-pro-002` and `gemini-1.5-flash-002`; Google-reported ~7% MMLU-Pro lift and ~20% MATH/HiddenMath lift over Feb-2024 builds; 2× output rate limits.
- Sources:
  - kind: announcement
    tag: lab
    url: https://developers.googleblog.com/en/updated-gemini-models-reduced-15-pro-pricing-increased-rate-limits-and-more/
    title: "Updated production-ready Gemini models, reduced 1.5 Pro pricing"
    date: 2024-09-24
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini Developer API pricing"
    date: 2024-09

Benchmarks (lab, deltas vs Feb-2024 baseline; absolute numbers in 002 build not always re-published per benchmark):
- MMLU-Pro: ~+7% vs Feb build [lab] src=https://developers.googleblog.com/en/updated-gemini-models-reduced-15-pro-pricing-increased-rate-limits-and-more/ date=2024-09-24
- MATH: ~+20% vs Feb build [lab]
- HiddenMath: ~+20% vs Feb build [lab]

Notes: Google framed 002 as production-stabilized, not a re-benched release. 3p sites (Artificial Analysis) re-benched and reported MMLU-Pro 75.8 on Pro-002.

---

### Gemini 1.5 Flash

- Release: 2024-05-14 (Google I/O preview); GA 2024-06-27
- Status: retired
- Decommissioned: 2025-09-29
- Context: 1M tokens (8K output)
- Modality: text + image + audio + video
- Price (in/out per 1M): $0.075 / $0.30 ≤128K; $0.15 / $0.60 >128K (Sept 2024 tier)
- Notable: distilled from 1.5 Pro; same 1M context at ~10× lower price; tuned for high-frequency, low-latency tasks.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/ai/google-io-2024-gemini-1-5-flash-pro-update/
    title: "Gemini 1.5 Flash announcement"
    date: 2024-05-14
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (Flash tier)"
    date: 2024-09
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini 1.5 shutdown"
    date: 2025-09-29

Benchmarks (lab from 1.5 tech report):
- MMLU (5-shot): 78.9 [lab] src=https://arxiv.org/pdf/2403.05530 date=2024-05
- HellaSwag: 86.5 [lab]
- GSM8K (11-shot): 86.2 [lab]
- MATH (4-shot): 54.9 [lab]
- BIG-Bench Hard: 85.5 [lab]
- MGSM: 82.6 [lab]
- HumanEval: 74.3 [lab]
- MMMU: 56.1 [lab]

---

### Gemini 1.5 Flash-8B

- Release: 2024-10-03 (production GA); previewed 2024-08-27 as `gemini-1.5-flash-8b-exp-0827`
- Status: retired
- Decommissioned: 2025-09-29
- Context: 1M tokens
- Modality: text + image + audio + video
- Price (in/out per 1M): $0.0375 / $0.15 ≤128K — Google's "lowest cost per intelligence" Gemini at the time
- Notable: 8B-class Flash distillation; near-parity with May-2024 Flash on many benchmarks; introduced 4 000 RPM rate limit (2× over 1.5 Flash).
- Sources:
  - kind: announcement
    tag: lab
    url: https://developers.googleblog.com/en/gemini-15-flash-8b-is-now-generally-available-for-use/
    title: "Gemini 1.5 Flash-8B is now production ready"
    date: 2024-10-03
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini 1.5 shutdown"
    date: 2025-09-29

Benchmarks: Google did not publish a standalone bench table for Flash-8B at GA; positioning was "matches 1.5 Flash on chat, transcription, long-context translation while ~2× cheaper." 3p replication (llm-stats) reports MMLU 69.0, GPQA 38.4, MATH 55.3.

Notes: 3p numbers are not original-lab; included with explicit `3p` tag if used.

---

### Gemini 2.0 Flash (Experimental → GA)

- Release: 2024-12-11 (experimental `gemini-2.0-flash-exp`); GA 2025-02-05 as `gemini-2.0-flash-001`
- Status: deprecated (announced 2026-02-18)
- Decommissioned: 2026-06-01 (scheduled)
- Context: 1M tokens (8K output)
- Modality: text + image + audio + video input; text + native image-gen + steerable multilingual TTS output
- Price (in/out per 1M): $0.10 / $0.40 (text/image/video); $0.70 input for audio
- Notable: first Gemini with native image generation and native multilingual TTS; native tool use (Search, code-exec, third-party functions); >2× speed of 1.5 Pro at sub-1.5-Pro pricing.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/google-gemini-ai-update-december-2024/
    title: "Introducing Gemini 2.0"
    date: 2024-12-11
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/
    title: "Gemini 2.0 family updates (GA)"
    date: 2025-02-05
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini 2.0 Flash deprecation (shutdown 2026-06-01)"
    date: 2026-02-18

Benchmarks (lab, Feb 2025 GA):
- MMLU-Pro: 76.4 [lab] src=https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/ date=2025-02-05
- GPQA Diamond (0-shot): 62.1 [lab]
- LiveCodeBench (v5): 34.5 [lab]
- Bird-SQL: 51.8 [lab]
- MATH: 89.7 [lab]
- MRCR (1M): 73.1 [lab]
- HiddenMath: 63.5 [lab]
- FACTS Grounding: 84.6 [lab]

Notes: Lab GPQA / MMLU-Pro consistent with Artificial Analysis replication within 1-2pp.

---

### Gemini 2.0 Flash-Lite

- Release: 2025-02-05 (public preview); GA shortly after under `gemini-2.0-flash-lite-001`
- Status: deprecated (announced 2026-02-18)
- Decommissioned: 2026-06-01 (scheduled)
- Context: 1M tokens
- Modality: text + image + video input
- Price (in/out per 1M): $0.075 / $0.30
- Notable: cheapest 2.0 tier; "better than 1.5 Flash at same speed and cost"; can caption 40 000 photos for <$1.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/
    title: "Gemini 2.0 Flash-Lite preview"
    date: 2025-02-05
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "Gemini 2.0 Flash-Lite shutdown (2026-06-01)"
    date: 2026-02-18

Benchmarks: Google did not publish a per-benchmark Flash-Lite table at launch; framing was relative ("better than 1.5 Flash at same cost"). No standalone lab figures.

---

### Gemini 2.0 Flash Thinking Experimental

- Release: 2024-12-19 (`gemini-2.0-flash-thinking-exp-1219`); updated 2025-01-21 as `gemini-2.0-flash-thinking-exp-01-21`
- Status: experimental (rolled into 2.5 Pro / 2.5 Flash reasoning capability)
- Decommissioned: superseded April 2025
- Context: 1M tokens
- Modality: text
- Price (in/out per 1M): free during experimental tier
- Notable: first public Gemini reasoning/CoT model; introduced visible "thinking" tokens.
- Sources:
  - kind: announcement
    tag: 3p
    url: https://x.com/demishassabis/status/1881844417746632910
    publisher: Demis Hassabis (Google DeepMind)
    title: "Gemini 2.0 Flash Thinking update"
    date: 2025-01-21
  - kind: coverage
    tag: 3p
    url: https://www.marktechpost.com/2025/01/21/google-ai-releases-gemini-2-0-flash-thinking-model-gemini-2-0-flash-thinking-exp-01-21-scoring-73-3-on-aime-math-and-74-2-on-gpqa-diamond-science-benchmarks/
    publisher: MarkTechPost
    title: "Gemini 2.0 Flash Thinking 01-21 benchmarks"
    date: 2025-01-21

Benchmarks (lab via Hassabis announcement):
- AIME 2024: 73.3 [lab] src=https://x.com/demishassabis/status/1881844417746632910 date=2025-01-21
- GPQA Diamond: 74.2 [lab]
- MMMU: 75.4 [lab]

Notes: Replaced by 2.5 Pro's built-in thinking April 2025; never had a standalone GA release.

---

### Gemini 2.0 Pro Experimental

- Release: 2025-02-05 (`gemini-2.0-pro-experimental`)
- Status: experimental (never went GA; effectively succeeded by 2.5 Pro)
- Decommissioned: superseded March 2025
- Context: 2M tokens (largest at the time)
- Modality: text + image + video + audio
- Price (in/out per 1M): not separately priced (experimental access via AI Studio / Vertex)
- Notable: Google's strongest-coding model in the 2.0 generation; introduced 2M token context for general API users.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/
    title: "Gemini 2.0 Pro Experimental"
    date: 2025-02-05

Benchmarks: Google's Feb 2025 comparison chart referenced relative wins on coding and complex prompts but did not publish a discrete bench table for 2.0 Pro Experimental. No standalone lab numbers.

---

### gemini-exp-1206 (named experimental preview)

- Release: 2024-12-06
- Status: experimental (sunset; widely believed to be the 2.0 Pro precursor)
- Decommissioned: rolled into 2.0 Pro Experimental Feb 2025
- Context: 2M tokens
- Modality: text + vision
- Price (in/out per 1M): free during experimental period
- Notable: first publicly accessible "2.0 Experimental Advanced"; topped Chatbot Arena leaderboard at launch (Elo > 1380); served via AI Studio and Gemini Advanced.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/feed/gemini-exp-1206/
    title: "Gemini Exp-1206 now available as a preview in Gemini Advanced"
    date: 2024-12-06
  - kind: coverage
    tag: 3p
    url: https://simonwillison.net/2024/Dec/6/gemini-exp-1206/
    publisher: Simon Willison
    title: "New Gemini model: gemini-exp-1206"
    date: 2024-12-06

Benchmarks: Google did not publish discrete lab numbers for `gemini-exp-1206` (it was an experimental snapshot). LMArena #1 Elo at launch was the headline. 3p coverage (Helicone, VentureBeat) reported strong coding/math/reasoning lifts vs GPT-4o and o1 but without standardized scores.

---

### Gemini 2.5 Pro Experimental → Preview → GA

- Release: 2025-03-25 (`gemini-2.5-pro-exp-03-25`, experimental); preview tier with billing 2025-04-04; GA 2025-06-17 as `gemini-2.5-pro`
- Status: current
- Decommissioned: still active as of May 2026 (legacy tier; 3.1 Pro is flagship)
- Context: 1M tokens (2M flagged but never broadly enabled)
- Modality: text + image + audio + video + code repositories
- Price (in/out per 1M): $1.25 / $10.00 ≤200K; $2.50 / $15.00 >200K
- Notable: first Gemini with always-on reasoning ("thinking"); industry-leading LMArena Elo at launch; introduced 2.5 family.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/
    title: "Gemini 2.5: Our newest Gemini model with thinking"
    date: 2025-03-25
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/google-gemini-updates-io-2025/
    title: "Gemini 2.5 updates at I/O 2025"
    date: 2025-05-20
  - kind: announcement
    tag: lab
    url: https://cloud.google.com/blog/products/ai-machine-learning/gemini-2-5-flash-lite-flash-pro-ga-vertex-ai
    title: "Gemini 2.5 Pro / Flash GA"
    date: 2025-06-17
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (2.5 Pro)"
    date: 2026-05

Benchmarks (lab, March 2025 launch numbers from Google):
- Humanity's Last Exam (no tools): 18.8 [lab] src=https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/ date=2025-03-25
- GPQA Diamond: 84.0 [lab]
- AIME 2025: 86.7 [lab]
- SWE-bench Verified: 63.8 [lab] (Google custom agent harness)
- MMMU: 81.7 [lab]
- LMArena Elo: #1 at launch
- LiveCodeBench v5: 70.4 [lab]
- WebDev Arena Elo: 1415 [lab] (May 2025 update)

Notes: 3p (Artificial Analysis) replications place SWE-bench Verified within 2-3pp of lab figure; LiveCodeBench v6 (later, harder split) at 75.6 per Vellum replication.

---

### Gemini 2.5 Flash

- Release: 2025-04-09 (preview); 2025-06-17 GA as `gemini-2.5-flash`
- Status: current (legacy tier vs 3.5 Flash)
- Decommissioned: still active
- Context: 1M tokens (64K output)
- Modality: text + image + audio + video
- Price (in/out per 1M): $0.30 input (text/image/video), $1.00 (audio) / $2.50 output
- Notable: first Flash with controllable thinking budget; introduced agentic-tool-use defaults.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/google-gemini-updates-io-2025/
    title: "Gemini 2.5 Flash announcement"
    date: 2025-05-20
  - kind: announcement
    tag: lab
    url: https://cloud.google.com/blog/products/ai-machine-learning/gemini-2-5-flash-lite-flash-pro-ga-vertex-ai
    title: "Gemini 2.5 Flash GA"
    date: 2025-06-17
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (2.5 Flash)"
    date: 2026-05

Benchmarks (lab, I/O 2025 + GA):
- Humanity's Last Exam: 11.1 [lab] src=https://deepmind.google/technologies/gemini/flash/ date=2025-06
- GPQA Diamond: 79.0 [lab]
- AIME 2025: 73.3 [lab]
- LiveCodeBench v5: 69.5 [lab]
- MMLU-Pro: 83.2 [lab]
- MATH-500: 98.1 [lab]
- SWE-bench Verified: 60.4 [lab]

Notes: 3p replication (Artificial Analysis) lands GPQA at 76.5 — within 3pp; not flagged as disagreement.

---

### Gemini 2.5 Flash-Lite

- Release: 2025-07-22 (GA); preview windows earlier in 2025
- Status: current (active legacy tier)
- Decommissioned: still active
- Context: 1M tokens
- Modality: text + image + audio + video
- Price (in/out per 1M): $0.10 (text/image/video) / $0.30 (audio) input; $0.40 output
- Notable: at launch, fastest proprietary frontier-lab model on tokens/s (per Google + VentureBeat); native Search Grounding / code-exec / URL Context.
- Sources:
  - kind: announcement
    tag: lab
    url: https://developers.googleblog.com/en/gemini-25-flash-lite-is-now-stable-and-generally-available/
    title: "Gemini 2.5 Flash-Lite is now stable and generally available"
    date: 2025-07-22
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (2.5 Flash-Lite)"
    date: 2026-05

Benchmarks (lab, vs Flash-Lite GA + Flash-Lite v 3.1 comparison table):
- GPQA Diamond: 66.7 [lab] src=https://deepmind.google/models/gemini/flash-lite/ date=2026-05
- MMMU-Pro: 51.0 [lab]
- SimpleQA: 11.5 [lab]
- MMMLU: 84.5 [lab]
- LiveCodeBench: 34.3 [lab]

---

### Gemini 2.5 Pro Deep Think

- Release: 2025-05-20 (announced at I/O); rolled to AI Ultra subscribers 2025-08-01
- Status: superseded by 3 / 3.1 Deep Think (still listed as accessible Aug 2025–Nov 2025)
- Decommissioned: rolled forward into 3 Pro Deep Think on Nov 2025
- Context: 1M tokens
- Modality: text + image + audio + video
- Price (in/out per 1M): bundled into Google AI Ultra subscription (~$249.99/mo), not API-priced
- Notable: first Gemini "Deep Think" reasoning mode (multi-hypothesis parallel inference); bronze-medal on IMO 2025; "fixed set of prompts per day" cap.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/technology/google-deepmind/google-gemini-updates-io-2025/
    title: "Gemini 2.5 Pro Deep Think (I/O)"
    date: 2025-05-20
  - kind: announcement
    tag: lab
    url: https://blog.google/products/gemini/gemini-2-5-deep-think/
    title: "Gemini 2.5 Deep Think to Google AI Ultra"
    date: 2025-08-01

Benchmarks (lab from I/O and Aug 2025 launch):
- USAMO 2025: "bronze-level / impressive" (Google did not disclose exact %) [lab]
- IMO 2025: bronze-medal performance [lab]
- LiveCodeBench v6: SOTA at announcement (no exact figure) [lab]
- MMMU: 84.0 [lab] src=https://blog.google/technology/google-deepmind/google-gemini-updates-io-2025/ date=2025-05-20

Notes: Google did not consistently publish numeric Deep Think scores beyond MMMU; framing was relative leaderboard claims.

---

### Gemini 3 Pro (`gemini-3-pro-preview`)

- Release: 2025-11-18 (preview only)
- Status: decommissioned (only ever a preview SKU; never went GA — superseded by 3.1 Pro Preview)
- Decommissioned: 2026-03-09 (per Gemini API changelog)
- Context: 1M tokens (64K output)
- Modality: text + image + audio + video + code repositories
- Price (in/out per 1M): preview pricing matched 3.1 Pro tier ($2.00/$12.00 ≤200K; $4.00/$18.00 >200K)
- Notable: first Gemini 3 generation; introduced built-in Deep Think mode on the same model ID; new Antigravity coding-agent surface launched alongside.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/products/gemini/gemini-3/
    title: "A new era of intelligence with Gemini 3"
    date: 2025-11-18
  - kind: model-card
    tag: lab
    url: https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-3-Pro-Model-Card.pdf
    title: "Gemini 3 Pro Model Card"
    date: 2025-11
  - kind: model-card
    tag: lab
    url: https://storage.googleapis.com/deepmind-media/gemini/gemini_3_pro_model_evaluation.pdf
    title: "Gemini 3 Pro Model Evaluation"
    date: 2025-11
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "gemini-3-pro-preview shutdown"
    date: 2026-03-09

Benchmarks (lab, Nov 2025 launch):
- LMArena Elo: 1501 [lab] src=https://blog.google/products/gemini/gemini-3/ date=2025-11-18
- Humanity's Last Exam (no tools): 37.5 [lab]
- GPQA Diamond: 91.9 [lab]
- MathArena Apex: 23.4 [lab]
- MMMU-Pro: 81.0 [lab]
- Video-MMMU: 87.6 [lab]
- SimpleQA Verified: 72.1 [lab]
- SWE-bench Verified: 76.2 [lab]
- Terminal-Bench 2.0: 54.2 [lab]
- WebDev Arena Elo: 1487 [lab]
- LiveCodeBench Pro Elo: 2439 [lab]
- ARC-AGI-2: 31.1 [lab] (estimated from Deep Think delta — 3 Pro non-Deep-Think baseline)
- Vending-Bench 2: leading long-horizon planning score [lab] (Google did not disclose exact $)

Gemini 3 Pro **Deep Think** variant (Nov 2025):
- Humanity's Last Exam: 41.0 [lab]
- GPQA Diamond: 93.8 [lab]
- ARC-AGI-2 (with code execution): 45.1 [lab]

Notes: 3p (Vellum) replications of SWE-bench Verified and LiveCodeBench Pro confirmed within ~2pp of lab. Knowledge cutoff: January 2025.

---

### Gemini 3 Flash (preview)

- Release: late 2025 / early 2026 (preview-only; never received its own standalone blog launch — surfaced via 3.5 Flash comparison tables)
- Status: legacy preview (superseded by 3.5 Flash GA May 2026)
- Decommissioned: scheduled with 3.5 Flash GA cutover
- Context: 1M tokens (64K output)
- Modality: text + image + audio + video input; text output
- Price (in/out per 1M): preview-tier; never had its own price sheet
- Notable: bridge model between 2.5 Flash and 3.5 Flash; ARC-AGI-2 33.6%.
- Sources:
  - kind: coverage
    tag: lab
    url: https://deepmind.google/models/gemini/flash/
    title: "Gemini Flash family comparison (3.5 Flash vs 3 Flash)"
    date: 2026-05

Benchmarks (lab, from 3.5 Flash comparison page):
- Terminal-Bench 2.1: 58.0 [lab] src=https://deepmind.google/models/gemini/flash/ date=2026-05
- SWE-Bench Pro: 49.6 [lab]
- MCP Atlas: 62.0 [lab]
- Toolathlon: 49.4 [lab]
- Finance Agent v2: 42.6 [lab]
- CharXiv: 80.3 [lab]
- MMMU-Pro: 81.2 [lab]
- Humanity's Last Exam: 33.7 [lab]
- ARC-AGI-2: 33.6 [lab]

---

### Gemini 3.1 Pro (`gemini-3.1-pro-preview`)

- Release: 2026-02-19 (preview; current flagship as of May 2026)
- Status: current (preview but production-billable)
- Decommissioned: —
- Context: 1M tokens input / 64K tokens output
- Modality: text + image + audio + video + code repositories
- Price (in/out per 1M): $2.00 / $12.00 ≤200K input; $4.00 / $18.00 >200K input
- Notable: leads 13/16 benchmarks Google measured at launch; 2887 Elo on LiveCodeBench Pro; built-in Deep Think mode toggleable on same ID.
- Sources:
  - kind: announcement
    tag: lab
    url: https://blog.google/products/gemini/gemini-3-1-pro/
    title: "Gemini 3.1 Pro"
    date: 2026-02-19
  - kind: model-card
    tag: lab
    url: https://deepmind.google/models/model-cards/gemini-3-1-pro/
    title: "Gemini 3.1 Pro Model Card"
    date: 2026-02
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (3.1 Pro Preview)"
    date: 2026-05
  - kind: replication
    tag: 3p
    url: https://artificialanalysis.ai/models/gemini-3-1-pro-preview
    publisher: Artificial Analysis
    title: "Gemini 3.1 Pro Preview — Intelligence Index"
    date: 2026-04
  - kind: coverage
    tag: 3p
    url: https://smartchunks.com/gemini-3-1-pro-benchmarks-gpqa-hle-lmsys-frontiermath/
    publisher: SmartChunks
    title: "Gemini 3.1 Pro Benchmarks Decoded"
    date: 2026-02

Benchmarks (per coordinator schema; user pre-supplied 3p figures from Anthropic Opus 4.7 + OpenAI GPT-5.5 cross-lab tables — kept verbatim):
- SWE-bench Verified: 80.6 [3p:Anthropic-published] src=https://deepmind.google/models/model-cards/gemini-3-1-pro/ date=2026-02
- SWE-bench Pro: 54.2 [3p:Anthropic-published]
- Terminal-Bench 2.0: 68.5 [3p:Anthropic-published]
- Humanity's Last Exam (no tools): 44.4 [3p:Anthropic-published]
- Humanity's Last Exam (with tools): 51.4 [3p:Anthropic-published]
- BrowseComp: 85.9 [3p:Anthropic-published]
- MCP-Atlas: 73.9 [3p:Anthropic-published]
- GDPval: 67.3 [3p:Anthropic-published]
- Toolathlon: 48.8 [3p:Anthropic-published]
- FrontierMath T1-3: 36.9 [3p:Anthropic-published]
- FrontierMath T4: 16.7 [3p:Anthropic-published]
- Finance Agent v1.1: 59.7 [3p:Anthropic-published]
- GPQA Diamond: 94.3 [3p:Anthropic-published]
- MMMLU: 92.6 [3p:Anthropic-published]

Lab benchmarks from Google 3.1 Pro model card:
- LiveCodeBench Pro Elo: 2887 [lab] src=https://deepmind.google/models/model-cards/gemini-3-1-pro/ date=2026-02
- MMMU-Pro: 80.5 [lab]
- ARC-AGI-2: 77.1 [lab]
- MCP-Atlas: 69.2 [lab] (Google's number; 3p Anthropic table reports 73.9)
- MRCR v2 (8-needle): 84.9 @ 128K; 26.3 @ 1M [lab]

Notes: Lab vs 3p MCP-Atlas disagreement is >3pp (69.2 lab vs 73.9 Anthropic-published 3p) — surfaced both. ARC-AGI-2 77.1% is more than 2× Gemini 3 Pro's 31.1% in same eval. Knowledge cutoff: January 2025.

---

### Gemini 3.1 Pro Deep Think

- Release: 2026-02-19 (toggleable on `gemini-3.1-pro-preview` for Gemini app users; AI Ultra-tier limits)
- Status: current
- Decommissioned: —
- Context: 1M tokens
- Modality: text + image + audio + video
- Price (in/out per 1M): bundled in Gemini app / AI Ultra tier; not separately API-priced as of May 2026
- Notable: highest scores ever recorded on ARC-AGI-2 (84.6%); IMO 2025 gold-medal territory (81.5%); ICO 2025 gold-medal (82.8%).
- Sources:
  - kind: announcement
    tag: lab
    url: https://deepmind.google/models/gemini/deep-think/
    title: "Gemini 3.1 Deep Think"
    date: 2026-02

Benchmarks (lab):
- Humanity's Last Exam (no tools): 48.4 [lab] src=https://deepmind.google/models/gemini/deep-think/ date=2026-02
- Humanity's Last Exam (search + code): 53.4 [lab]
- ARC-AGI-2: 84.6 [lab]
- International Math Olympiad 2025: 81.5 [lab]
- International Chemistry Olympiad 2025: 82.8 [lab]

Notes: Google did not publish standalone Deep Think numbers for SWE-bench, LiveCodeBench, or GPQA — model-card numbers fold both into the base 3.1 Pro row.

---

### Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`)

- Release: 2026-05-07 (GA); preview phase ran from late 2025
- Status: current
- Decommissioned: — (the *preview* SKU `gemini-3.1-flash-lite-preview` is deprecated, shutdown 2026-05-25)
- Context: 1M tokens input / 64K output
- Modality: text + image + audio + video + PDF input; text output
- Price (in/out per 1M): $0.25 (text/image/video), $0.50 (audio) / $1.50 output
- Notable: substantial lifts over 2.5 Flash-Lite (GPQA 86.9 vs 66.7, LiveCodeBench 72.0 vs 34.3); positioning is high-volume + high-throughput tier.
- Sources:
  - kind: announcement
    tag: lab
    url: https://deepmind.google/models/gemini/flash-lite/
    title: "Gemini 3.1 Flash-Lite"
    date: 2026-05
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing"
    date: 2026-05
  - kind: deprecation
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/changelog
    title: "gemini-3.1-flash-lite-preview shutdown 2026-05-25"
    date: 2026-05-07

Benchmarks (lab):
- GPQA Diamond: 86.9 [lab] src=https://deepmind.google/models/gemini/flash-lite/ date=2026-05
- MMMU-Pro: 76.8 [lab]
- SimpleQA: 43.3 [lab]
- MMMLU: 88.9 [lab]
- LiveCodeBench: 72.0 [lab]

---

### Gemini 3.5 Flash (`gemini-3.5-flash`)

- Release: 2026-05-19 (GA)
- Status: current
- Decommissioned: —
- Context: 1M tokens input / 64K output
- Modality: text + image + video + audio + PDF input; text output
- Price (in/out per 1M): $1.50 / $9.00 standard tier; ~50% off batch / Flex
- Notable: surpasses 3.1 Pro on several agentic/coding benches (Terminal-Bench 2.1 76.2, MCP-Atlas 83.6, SWE-Bench Pro 55.1, CharXiv 84.2) while costing ~1/2 of Pro; positioned as new agentic / coding workhorse.
- Sources:
  - kind: announcement
    tag: lab
    url: https://deepmind.google/models/gemini/flash/
    title: "Gemini 3.5 Flash"
    date: 2026-05-19
  - kind: pricing
    tag: lab
    url: https://ai.google.dev/gemini-api/docs/pricing
    title: "Gemini API pricing (3.5 Flash)"
    date: 2026-05

Benchmarks (lab from Flash comparison page):
- Terminal-Bench 2.1: 76.2 [lab] src=https://deepmind.google/models/gemini/flash/ date=2026-05
- SWE-Bench Pro: 55.1 [lab]
- MCP Atlas: 83.6 [lab]
- Toolathlon: 56.5 [lab]
- Finance Agent v2: 57.9 [lab]
- CharXiv: 84.2 [lab]
- MMMU-Pro: 83.6 [lab]
- Humanity's Last Exam: 40.2 [lab]
- ARC-AGI-2: 72.1 [lab]

Notes: 3.5 Flash beats 3.1 Pro on Terminal-Bench 2.1, MCP-Atlas, SWE-Bench Pro, CharXiv, and MMMU-Pro — explicit Google framing positions it as the new flagship for agentic + coding work, with 3.1 Pro retained for general-purpose reasoning + long-context. "3.5 Pro coming soon" per deepmind.google.

---

## Excluded / not-shipped

- **Gemini 3 Ultra** — no public announcement, no API SKU, no model card; rumors only. Excluded.
- **Gemini Robotics-ER 1.5** — appears in Gemini API deprecation registry but is a robotics-specific embedding/reasoning model, out of scope for this comparison.
- **Veo / Imagen / text-embedding-004** entries in the deprecation registry are non-Gemini media / embedding models — excluded.

---

## Sources

- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/changelog
- https://ai.google.dev/gemini-api/docs/pricing
- https://blog.google/technology/ai/google-gemini-ai/
- https://arxiv.org/pdf/2312.11805
- https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/
- https://arxiv.org/pdf/2403.05530
- https://blog.google/technology/ai/google-io-2024-gemini-1-5-flash-pro-update/
- https://developers.googleblog.com/en/updated-gemini-models-reduced-15-pro-pricing-increased-rate-limits-and-more/
- https://developers.googleblog.com/en/gemini-15-flash-8b-is-now-generally-available-for-use/
- https://blog.google/technology/google-deepmind/google-gemini-ai-update-december-2024/
- https://blog.google/feed/gemini-exp-1206/
- https://simonwillison.net/2024/Dec/6/gemini-exp-1206/
- https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/
- https://x.com/demishassabis/status/1881844417746632910
- https://www.marktechpost.com/2025/01/21/google-ai-releases-gemini-2-0-flash-thinking-model-gemini-2-0-flash-thinking-exp-01-21-scoring-73-3-on-aime-math-and-74-2-on-gpqa-diamond-science-benchmarks/
- https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/
- https://blog.google/technology/google-deepmind/google-gemini-updates-io-2025/
- https://cloud.google.com/blog/products/ai-machine-learning/gemini-2-5-flash-lite-flash-pro-ga-vertex-ai
- https://developers.googleblog.com/en/gemini-25-flash-lite-is-now-stable-and-generally-available/
- https://blog.google/products/gemini/gemini-2-5-deep-think/
- https://deepmind.google/technologies/gemini/flash/
- https://blog.google/products/gemini/gemini-3/
- https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-3-Pro-Model-Card.pdf
- https://storage.googleapis.com/deepmind-media/gemini/gemini_3_pro_model_evaluation.pdf
- https://blog.google/products/gemini/gemini-3-1-pro/
- https://deepmind.google/models/model-cards/gemini-3-1-pro/
- https://deepmind.google/models/gemini/
- https://deepmind.google/models/gemini/flash/
- https://deepmind.google/models/gemini/flash-lite/
- https://deepmind.google/models/gemini/deep-think/
- https://artificialanalysis.ai/models/gemini-3-1-pro-preview
- https://smartchunks.com/gemini-3-1-pro-benchmarks-gpqa-hle-lmsys-frontiermath/
- https://en.wikipedia.org/wiki/Gemini_(language_model)
