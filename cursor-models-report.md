# Cursor / Anysphere — Model Lineage Report

Status as of **May 2026**. Anysphere (parent company; "Cursor" is the IDE
brand) has shipped a small but rapidly expanding stable of in-house
models, all closed-weight. They are tier-leader of the "product company
with its own trained model" cohort — Composer 2.5 (May 18, 2026) is the
current flagship, claimed at Opus 4.7 / GPT-5.5 parity on coding at
roughly one-tenth the per-token cost.

A central caveat runs through this report: **Cursor does not train base
models from scratch (yet)**. Composer 2 and 2.5 are continued-pretraining +
RL on top of Moonshot's open-weight **Kimi K2.5**; Composer 1 / 1.5 were
community-asserted to be based on Qwen but Cursor never confirmed that
specifically. Cursor was publicly criticized in March 2026 for not
disclosing the Kimi base in their Composer 2 announcement; co-founder
Aman Sanger admitted the omission was a mistake and corrected it in
later publications. ([TechCrunch][tc], [VentureBeat][vb1])

A separate, future-tense effort is also announced: a **from-scratch
model trained with SpaceXAI on Colossus 2** (~10× the compute used for
Composer 2.5). No release date, no name, no benchmarks. ([Cursor][spx])

---

## Per-model entries

### cursor-small / cursor-small-v3 / "cursor-fast"

- **Name:** `cursor-small` (later iterations referenced as
  `cursor-small-v3`); a sibling "`cursor-fast`" appeared in the model
  picker.
- **Release:** Exists from at least mid-2024; no first-party launch
  blog post identifiable. Distilled small model for low-latency tasks
  (chat, simple completions in the chat sidebar, not Tab autocomplete).
- **Status (May 2026):** Effectively **legacy / quietly retired**.
  Not listed on the current `cursor.com/docs/models-and-pricing`
  page. Community threads in late 2025 asked whether `cursor-fast` was
  "abandoned or updated" without an official response. ([forum][csmall])
- **Base model:** Not disclosed. Described in third-party coverage as
  one of Cursor's "proprietary distilled models" but Cursor never
  published source or training details.
- **Context window / parameters / pricing:** Not disclosed.
- **Selectability:** Was selectable from the model picker; in
  Cursor 2.0+ the model dropdown was overhauled and these older names
  disappeared. ([changelog][cl30])
- **Benchmarks:** None published — Cursor never ran the small model
  on standard benches. Don't fabricate; nothing exists.

### Cursor Tab (autocomplete model)

- **Name:** Cursor Tab. Iterations have been called "Next Tab Model"
  (Jan 2025), "A new Tab model" (mid-2025), then the September 2025
  online-RL update.
- **Release timeline:** First Tab model trained / shipped March 2024
  ([Pragmatic Engineer coverage][pe]). Major update September 12, 2025
  via online RL. Continuous retraining cycles thereafter — "1.5–2
  hours from data collection to checkpoint rollout." ([Cursor][tabrl])
- **Status:** Current; default Tab completion across all plans
  including free Hobby tier.
- **Architecture:** Sparse Mixture-of-Experts (third-party reporting;
  Cursor's tab-rl post deliberately avoids architectural disclosure).
  Optimized for huge inputs / small targeted edit outputs.
- **Training method:** Online reinforcement learning with policy
  gradients. Reward = user accept / reject signal. Cursor explicitly
  contrasts this with "static datasets or paid labelers." Self-trained;
  base model not disclosed. ([Cursor][tabrl])
- **Scale of operation:** > 400 million requests/day as of Sept 2025.
- **Reported deltas (Sept 2025 update):** 21% fewer suggestions, 28%
  higher accept rate vs prior version.
- **Context window / parameters / pricing:** Not disclosed; bundled
  into subscription (Tab completions included in Hobby/Pro/Pro+/Ultra
  without per-call accounting).
- **Modality:** Text-only (code).
- **Benchmarks:** None — Cursor reports internal accept-rate deltas,
  not public benches. Tab is not the kind of model SWE-bench measures.

### Composer 1

- **Name:** Composer (later retroactively "Composer 1").
- **Release:** **October 29, 2025**, alongside Cursor 2.0. ([Cursor][c1])
- **Status (May 2026):** **Legacy**, hidden by default but still
  accessible via API pool. ([docs][docs])
- **Pricing (now, as a legacy API option):** $1.25/M input, $10/M
  output, $0.125/M cache read. ([docs][docs])
- **Base model:** **Undisclosed by Cursor.** Widely asserted on Hacker
  News and elsewhere to be Qwen-based (the HN top comment on the
  Composer-2 thread asserted "Cursor Composer 1 was Qwen and this is
  Kimi"), but no Cursor employee confirmation, no tokenizer-level
  proof published. ([HN][hn]) — flag as **community claim, unverified**.
  The Composer 2 technical report does mention using
  Qwen3-Coder-30B-A3B for ablation studies, which is suggestive but
  not dispositive.
- **Training method:** RL specialization for software-engineering
  agents across diverse development environments. Cursor's own framing.
- **Context window:** Not disclosed in the launch post.
- **Modality:** Text only.
- **Selectability:** Was the default in-IDE agent model at launch.
- **Cursor's claims at launch:**
  - "Generation speed four times faster than similar models" on
    Cursor's internal bench (250 tokens/sec, ~4× GPT-5 / Sonnet 4.5).
  - Positioned in "Fast Frontier" tier — outperformed only by GPT-5
    and Sonnet 4.5 ("Best Frontier"). Compared against Haiku 4.5,
    Gemini Flash 2.5, Qwen Coder, GLM 4.6. ([Cursor][c1])
- **Third-party replication:** Sparse — Cursor declined to publish on
  SWE-bench Verified or LiveCodeBench at launch, drawing criticism for
  cherry-picked internal-only numbers. EPAM's 2026 review revisited
  the model and noted "speed strong, intelligence behind Sonnet 4.5
  on complex tasks." ([EPAM][epam])
- **Open weights:** No. Closed.

### Composer 1.5

- **Release:** **February 9, 2026.** ([Cursor][c15])
- **Status:** **Legacy**, hidden by default, accessible via API pool.
- **Pricing (now):** $3.5/M input, $17.5/M output, $0.35/M cache read.
  ([docs][docs]) (Notably higher than Composer 2/2.5 — reflects
  pre-Kimi-base inference economics.)
- **Base model:** Cursor says "the same pretrained model" as Composer 1.
  By their own Composer 2 paper, Composer 1.5 is the lineage that
  predates the Kimi switch — so base remains undisclosed and the
  community-Qwen assertion is the only candidate. ([Cursor][c15])
- **Training method:** **20× scaled RL** on the Composer-1 base.
  Cursor's headline framing was "post-training compute now exceeds
  the pretrain compute" — i.e. they treat it as RL-dominant. Introduced
  the **self-summarization** mechanism for long-horizon tasks
  (carried forward into Composer 2/2.5). It is described as a "thinking
  model" (generates internal reasoning tokens). ([Cursor][c15])
- **Context window:** Not disclosed; self-summarization is the
  workaround for limited window.
- **Benchmarks:** Cursor's blog showed Terminal-Bench 2.0 deltas vs
  Composer 1 in chart form only — **no specific numbers** in the
  launch post.
- **Third-party:** Adwait X and EPAM both noted the RL-scaling story
  as the headline; benchmark numbers in third-party reviews were
  ranges, not Cursor-published figures. ([EPAM][epam], [AdwaitX][adwait])
- **Open weights:** No.

### Composer 2

- **Release:** **March 19, 2026.** ([Cursor][c2])
- **Status (May 2026):** Available but **hidden by default** in the
  picker; superseded by Composer 2.5 two months after launch. API pool
  access only. ([docs][docs])
- **Pricing:** $0.50/M input, $2.50/M output, $0.20/M cache read
  (Standard tier). Fast variant: $1.50/M input, $7.50/M output, same
  intelligence, faster serving. ([Cursor][c2], [docs][docs])
- **Base model:** **Kimi K2.5** (Moonshot AI, open-weight). This was
  **not disclosed at launch** — added to the Composer 2 technical
  report after the omission was discovered and criticized. The
  technical report formally states: "These evaluations led us to
  select Kimi K2.5, a 1.04T parameter / 32B active parameter
  Mixture-of-Experts model as our base model for Composer 2."
  ([Composer 2 PDF][c2pdf])
- **Training method (from the technical report):**
  - **Phase 1: Continued pretraining** on a code-dominated mix.
    Three stages: 32k-sequence-length bulk, 256k long-context
    extension, then short SFT on targeted coding tasks. Trained in
    MXFP8 on **NVIDIA B300s** with AdamW.
  - **Phase 2: Asynchronous RL** with policy-gradient (single-epoch,
    full-parameter, no length standardization à la Dr. GRPO, k1 KL
    estimator). Replay-MoE-routing trick to mitigate off-policy drift.
  - **Self-summarization** carried forward from Composer 1.5.
  - **MTP layers** trained from scratch with self-distillation for
    speculative decoding at serve time.
- **Cursor admission:** Per Sanger (Mar 22, 2026): *"It was a miss
  to not mention the Kimi base in our blog from the start. We'll fix
  that for the next model."* Lee Robinson (VP Dev Education) framed
  it as "~25% of compute came from the Kimi base, ~75% from Cursor's
  training." ([TechCrunch][tc])
- **Context window:** **200K tokens** (third-party reporting and
  inference from continued-pretraining stage; not headline-stated in
  launch blog but consistent with the 256k-extension training).
  ([VentureBeat][vb2], [Vantage][vantage])
- **Modality:** Text-only (code + tool calls).
- **Benchmarks (Cursor-reported in technical report):**
  - **CursorBench: 61.3** (vs Composer 1.5 and prior — substantial
    jump)
  - **Terminal-Bench 2.0: 61.7**
  - **SWE-bench Multilingual: 73.7** (in their harness)
- **Third-party context:** VentureBeat's headline was "beats Claude
  Opus 4.6 but still trails GPT-5.4" — i.e. Cursor's claim of frontier
  parity holds for some Claude comparisons but not vs the very latest
  OpenAI models at the time of release. ([VentureBeat][vb2]) DataCamp's
  independent review reproduced the cost-per-token gap (86% cheaper
  than Opus 4.6 at the API-equivalent rate) and confirmed CursorBench
  / Terminal-Bench numbers from the technical report. ([DataCamp][dc])
- **Open weights:** No. Closed. (Despite the base being open-weight,
  the post-trained Composer 2 weights are not released.)

### Composer 2.5

- **Release:** **May 18, 2026.** Current default. ([Cursor][c25])
- **Status:** **Current flagship.** Included in Auto + Composer pool
  across Pro / Pro Plus / Ultra plans. Cursor docs label it
  "Cursor's own model, trained to be highly capable for agentic
  coding." ([docs][docs])
- **Pricing:** $0.50/M input, $2.50/M output, $0.20/M cache read
  (Standard). Fast variant ratcheted to $3.00/M input, $15.00/M
  output (significantly higher than Composer 2's Fast tier). ([docs][docs])
- **Base model:** **Kimi K2.5** (same as Composer 2). Cursor's
  Composer 2.5 announcement now explicitly states "built on
  Moonshot's Kimi K2.5 open-source checkpoint" — Sanger's promise
  to "fix that for the next model" was kept. ([Cursor][c25])
- **Training method:** Same two-phase pipeline as Composer 2
  (continued pretraining + asynchronous RL), with **25× more
  synthetic tasks** than Composer 2. Cursor frames 2.5 as
  intelligence-and-behavior improvement, not architecture change.
  Targeted training for textual-feedback handling and longer-running
  task coherence. ([Cursor][c25])
- **Context window:** Not headline-disclosed in the 2.5 announcement;
  consistent with Composer 2's 200K.
- **Modality:** Text-only.
- **Benchmarks (Cursor-claimed):**
  - **SWE-Bench Multilingual: 79.8%** (matches Claude Opus 4.7 per
    Cursor's claim, at ~1/10 the per-token cost)
  - **CursorBench v3.1: 63.2** (delta vs Composer 2's 61.3 — modest
    headline jump; large jump on long-horizon subsets per
    Cursor's chart)
  - Terminal-Bench 2.0: not headline-figured in the blog (charts
    only); third-party reviews place it ~mid-60s.
  Note: Cursor's blog post itself presents benchmarks as **charts
  without numeric tables** for several axes — the numbers above
  come from third-party recaps (Memeburn, BuildFastWithAI,
  Beyond Tomorrow) of Cursor's stated claims. **Independent
  third-party replication is not yet published** (model is six
  days old at time of this report). ([Memeburn][mb], [BuildFast][bfw])
- **Cursor's headline comparison claims:**
  - "Matches Claude Opus 4.7 on SWE-Bench Multilingual"
  - "Costs one-tenth as much per token" as Opus 4.7 / GPT-5.5
  These are **Cursor-published, not yet independently replicated.**
  Cursor's track record on cherry-picked comparisons (the
  Composer 1 launch and the un-disclosed-Kimi-base of Composer 2)
  argues for waiting on third-party numbers before treating these
  as load-bearing. **Surface the disagreement.**
- **Open weights:** No.

### "SpaceXAI partnership model" — announced, not released

- **Status:** Future. Announced in Composer 2.5's launch post as a
  parallel effort: "Together with SpaceXAI, Cursor is training a
  significantly larger model from scratch, using 10x more total
  compute" leveraging Colossus 2's million H100-equivalent cluster.
- **Name:** Not yet named.
- **Release date:** Not announced.
- **Base model:** **None — explicitly from scratch.** Would be
  Cursor's first foundation model rather than a continued-pretrain
  on an open-weight base.
- **Benchmarks:** None — pre-release. Don't include in bench tables.
- **Context (Bloomberg, May 21 2026):** SpaceX reportedly has an
  option to acquire Cursor for $60B post-Cursor-IPO; the model
  partnership and the acquisition option are part of the same deal
  shape. ([Bloomberg][bloom], [InfoWorld][iw])

---

## Benchmarks summary

| Model | CursorBench | SWE-bench Multilingual | Terminal-Bench 2.0 | Source |
|---|---|---|---|---|
| Composer 1 | not published | not published | not published | [Cursor][c1] (charts only, internal speed claim) |
| Composer 1.5 | not published as number | not published | charted vs Composer 1, no number | [Cursor][c15] |
| Composer 2 | **61.3** | **73.7** (Cursor harness) | **61.7** | [Composer 2 tech report PDF][c2pdf] |
| Composer 2.5 | **63.2** (v3.1) | **79.8** | not headline-disclosed | [Cursor][c25], [Memeburn][mb], [BuildFast][bfw] |

For comparison context, Cursor's own footnote in the Composer 2 paper
notes that Haiku 4.5 = 73.3 and GPT-5 = 74.9 on SWE-bench **Verified**
(different benchmark — don't confound) — Cursor uses Multilingual
specifically because they argue Verified is contaminated.
([Composer 2 PDF][c2pdf])

**Notably absent:** Cursor has not published SWE-bench Verified,
LiveCodeBench, or Aider polyglot for any Composer version. They argue
publicly (Composer 2 tech report Section 5) that these benches are
contamination-vulnerable. Whether this is principled or a convenient
dodge is a recurring critique in third-party coverage — surface this
in the benchmark page UI.

---

## Open vs closed weights — definitive

All Cursor models are **closed-weight**. Composer 2 and 2.5 are
fine-tunes of open-weight Kimi K2.5 (Moonshot AI), but the
post-trained Cursor weights are not released. Cursor has not
released any model on HuggingFace. The Kimi K2.5 base itself **is**
open-weight under Moonshot's license, which is what enabled the
Cursor partnership in the first place — and which is why HN
commenters were able to verify the base by tokenizer inspection.

---

## Sources (typed)

- [c1]: <https://cursor.com/blog/composer> — Composer 1 launch (Oct 29, 2025)
- [c15]: <https://cursor.com/blog/composer-1-5> — Composer 1.5 launch (Feb 9, 2026)
- [c2]: <https://cursor.com/blog/composer-2> — Composer 2 launch (Mar 19, 2026)
- [c2pdf]: <https://cursor.com/resources/Composer2.pdf> — Composer 2 technical report (Cursor Research Team)
- [c25]: <https://cursor.com/blog/composer-2-5> — Composer 2.5 launch (May 18, 2026)
- [tabrl]: <https://cursor.com/blog/tab-rl> — "Improving Cursor Tab with online RL" (Sept 12, 2025)
- [docs]: <https://cursor.com/docs/models-and-pricing> — Current model pricing / status table
- [spx]: <https://cursor.com/blog/spacex-model-training> — Cursor × SpaceXAI partnership announcement
- [cl30]: <https://cursor.com/changelog/3-0> — Cursor 3.0 changelog (model picker overhaul)
- [tc]: <https://techcrunch.com/2026/03/22/cursor-admits-its-new-coding-model-was-built-on-top-of-moonshot-ais-kimi/> — Sanger's admission (Mar 22, 2026)
- [vb1]: <https://venturebeat.com/technology/cursors-composer-2-was-secretly-built-on-a-chinese-ai-model-and-it-exposes-a> — VentureBeat: "secretly built on a Chinese AI model" critique
- [vb2]: <https://venturebeat.com/technology/cursors-new-coding-model-composer-2-is-here-it-beats-claude-opus-4-6-but> — Composer 2 vs Opus 4.6 / GPT-5.4
- [hn]: <https://news.ycombinator.com/item?id=47452816> — HN thread "Cursor Composer 1 was Qwen and this is Kimi" (community claim; unverified)
- [epam]: <https://www.epam.com/insights/ai/blogs/cursor-composer-model-review> — EPAM third-party Composer 1 / 1.5 review
- [adwait]: <https://www.adwaitx.com/cursor-composer-1-5-agentic-coding-model/> — Composer 1.5 RL-scaling coverage
- [dc]: <https://www.datacamp.com/blog/composer-2> — DataCamp Composer 2 independent benchmark write-up
- [vantage]: <https://www.vantage.sh/blog/cursor-composer-2> — Vantage cost-economics analysis
- [mb]: <https://memeburn.com/cursor-composer-2-5-officially-launches/> — Memeburn Composer 2.5 numbers
- [bfw]: <https://www.buildfastwithai.com/blogs/cursor-composer-2-5-review-2026> — BuildFastWithAI Composer 2.5 review
- [pe]: <https://newsletter.pragmaticengineer.com/p/cursor> — Pragmatic Engineer "Real-world engineering challenges: building Cursor" (first Tab model in March 2024)
- [csmall]: <https://forum.cursor.com/t/cursor-fast-model-abandoned-or-updated/132195> — Community thread asking whether cursor-fast was abandoned
- [bloom]: <https://www.bloomberg.com/news/articles/2026-05-21/cursor-hits-3-billion-annual-sales-rate-ahead-of-spacex-deal> — Cursor $3B ARR + SpaceX deal
- [iw]: <https://www.infoworld.com/article/4161997/spacex-secures-option-to-acquire-ai-coding-startup-cursor-for-60b.html> — SpaceX $60B acquisition option
