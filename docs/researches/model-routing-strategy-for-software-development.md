# Model Routing Strategy for Software Development — AI Context Document

**Scope:** Software development only. Providers: Anthropic (Claude) + OpenAI. Optimizes for cost per *accepted* result, not per-token sticker price. Pricing baseline: September 7, 2026.

**Governing principle:** Optimize for **cost per accepted result** = (token cost + latency cost of a step) ÷ (probability the output is accepted on that attempt). A cheap model redone twice is more expensive and slower than one correct answer from a mid-tier model. This drives every default below. Verifiability is the gate: if you cannot cheaply check a step's output, do not cheap out on the model for it.

---

## Routing rules

1. **Default to Claude Sonnet 5** ($2/$10, model ID `claude-sonnet-5`) for all interactive coding: implementation, scaffolding, refactors, test generation, in-repo edits. Best quality-per-dollar for software work; 1M-token context at flat pricing (no long-context surcharge).
2. **De-escalate to Claude Haiku 4.5** ($1/$5) or **GPT-5.6 Luna** ($0.20/$1.20) when the task is mechanical and output is machine-verifiable: boilerplate, CRUD, config, commit messages, autocomplete, subagent search, high-volume classification/extraction. Luna is cheaper and carries a 1.05M context; Haiku has the lower time-to-first-token for interactive UX.
3. **Escalate to Claude Opus 5** ($5/$25) when: (a) Sonnet fails the same step twice, (b) tests are still red after one fix cycle, (c) the change spans ≥3 files or needs cross-file/architectural reasoning, (d) the code is security-sensitive, or (e) you are launching a long-running autonomous agent loop.
4. **Escalate to a max-reasoning frontier model — Claude Fable 5.1 ($10/$50) or GPT-6 Astra ($10/$50)** — only for the hardest long-horizon autonomous work, novel algorithm/scientific design, or a deep multi-file root-cause Opus 5 could not close. Prefer **Fable 5.1** for long agent runs (its cache reads are $0.25/M, 4× cheaper than Astra's $1/M); prefer **Opus 5** when you need a published SWE-bench figure at half the price.
5. **For deep reasoning at moderate cost, use GPT-5.6 Sol** at high/max effort, or **Opus 5**. Both lead current agentic-coding leaderboards — Sol leads Terminal-Bench; Opus 5 leads the harder Terminal-Bench 3.0/4.0 and novel-reasoning tasks.
6. **Set reasoning effort explicitly.** Use `minimal`/`low` for mechanical steps and `high`/`max` only where a wrong answer is expensive. On GPT-5-class models, high effort can burn ~4–5× the tokens for only a 2–5 point accuracy gain — do not pay it by default.
7. **Cache aggressively.** Put stable content (system prompt, tool definitions, repo context) first and mark it cacheable. Cache reads are 10% of input on both vendors (2.5% on Fable 5.1/Mythos 5.1). Use 1-hour TTL for agent steps spaced >5 min apart.
8. **Batch anything non-interactive** (test generation over a suite, bulk refactors, doc generation, eval runs): 50% off both vendors.
9. **Never route architecture, ambiguous debugging, or security review to a nano/Luna-class model.**

---

## Routing table

| Step | Primary model | Why | Fallback / escalate to | Escalate when |
|---|---|---|---|---|
| Requirements clarification & spec writing | Claude Sonnet 5 | Strong instruction-following + writing at low cost; 1M context ingests existing docs | GPT-5.6 Sol (high) or Opus 5 | Ambiguous/large domain; conflicting stakeholder inputs; needs deep reasoning |
| Architecture & system design | Claude Opus 5 | Leads novel-reasoning/agentic evals (ARC-AGI-3, Frontier-Bench, OSWorld 2.0 at 70.57%); edge on open-ended problem solving | Claude Fable 5.1 or GPT-6 Astra | Greenfield at scale; irreversible/high-blast-radius decisions; security-critical |
| Task decomposition / planning an agent run | Claude Opus 5 | Plan quality determines whole-run cost; reasoning depth pays off here | GPT-5.6 Sol (`pro` mode) | Very long horizon (hours), many tools |
| Scaffolding & boilerplate (CRUD, config, glue) | GPT-5.6 Luna or Claude Haiku 4.5 | Mechanical, verifiable, high-volume; cheapest correct answer | Claude Sonnet 5 | Non-obvious framework wiring; generated code fails to compile once |
| Core implementation (complex/novel logic) | Claude Sonnet 5 | Best quality-per-dollar for real coding; SWE-bench Verified ~85% class | Claude Opus 5 → Fable 5.1 | Two failed attempts; cross-file/algorithmic; perf-critical |
| Debugging — shallow (single-file) | Claude Sonnet 5 | Fast, cheap, usually sufficient | Claude Opus 5 | Fix doesn't turn tests green in one cycle |
| Debugging — deep multi-file root-cause | Claude Opus 5 | Cross-file reasoning; targets root causes not symptoms | Claude Fable 5.1 (high/max) | Still red after Opus attempt; spans subsystems |
| Refactoring & migration | Claude Sonnet 5 | Reliable structured edits at scale; batchable | Claude Opus 5 → Fable 5.1 | Semantics-changing; large repo-wide migration; weak test coverage |
| Code review / PR feedback | Claude Haiku 4.5 (first pass) → Claude Opus 5 (deep) | Haiku triages cheaply; escalate only flagged/risky diffs | Claude Opus 5 or GPT-5.6 Sol | Security-sensitive, concurrency, or public-API change |
| Test generation | Claude Sonnet 5 (Batch) | Output is self-verifying (tests run); batch halves cost | Claude Opus 5 | Property/fuzz tests; tricky mocking; coverage gaps on critical paths |
| Documentation, commit messages, PR descriptions | GPT-5.6 Luna or Claude Haiku 4.5 | Low-stakes, high-volume, human-verifiable | Claude Sonnet 5 | Public API docs / external-facing spec |
| Inline autocomplete / rapid iteration | GPT-5.6 Luna | ~157 tok/s, ~100 ms TTFT, cheapest; latency is the feature | Claude Haiku 4.5 | Multi-line semantic completion needed |
| Long-running autonomous agent loops | Claude Opus 5 (default) | Purpose-built for long-horizon agentic; near-frontier at half Fable's price | Claude Fable 5.1 or GPT-6 Astra | Hours-long, scientific/novel, or highest reliability required |

---

## Model profiles

- **Claude Fable 5.1** ($10/$50; cache read $0.25, 5-min write $12.50, 1-hr write $20) — *Best for:* hardest long-horizon autonomous agents, novel/scientific problem-solving, deep root-cause. Leads SWE-bench Verified (~95%) and tops Terminal-Bench 4.0 (57.9% ±3.8, tbench.ai). *Avoid for:* routine coding, latency-sensitive work. *Speed:* slow — ~66–70 tok/s at max effort; thinks heavily by default (adaptive thinking always on), pushing end-to-end latency to minutes at max (Artificial Analysis TTFT ~265–291 s at max; ~5.9 s at low effort). *Cost:* highest, but cache reads are 4× cheaper than Astra's, so warm-context agent runs undercut expectations (Anthropic estimates typical Fable workloads ~25% cheaper vs Fable 5, up to ~45% for highly agentic work).
- **Claude Opus 5** ($5/$25; cache read $0.50) — *Best for:* architecture, deep multi-file debugging, planning, long-running agents; "close to Fable 5 frontier intelligence at half the price." SWE-bench Verified 96.0% (Vals.ai harness), SWE-bench Pro 79.2%, Terminal-Bench 2.1 89.1%, OSWorld 2.0 70.57%. *Avoid for:* bulk mechanical work, autocomplete. *Speed:* moderate (~51–57 tok/s, Artificial Analysis); Fast mode $10/$50 for up to ~2.5× speed. Thinking on by default (400 error if disabled above high effort).
- **Claude Sonnet 5** ($2/$10; cache read $0.20) — *Best for:* the default coding workhorse — implementation, refactor, tests, in-repo agents. 1M context, flat pricing. SWE-bench Verified ~85.2%, SWE-bench Pro 63.2%. *Avoid for:* the hardest novel reasoning (use Opus). *Speed:* good (~72–86 tok/s; non-reasoning TTFT ~1 s). *Cost:* best quality-per-dollar in software; $2/$10 is now the permanent standard rate.
- **Claude Haiku 4.5** ($1/$5; cache read $0.10) — *Best for:* fast interactive work, review triage, parallel subagents, classification. Per Anthropic's launch post, "We report 73.3% [SWE-bench Verified], averaged over 50 trials, no test-time compute, 128K thinking budget… on the full 500-problem dataset" — Sonnet-4-class at one-third the cost. *Avoid for:* deep reasoning, architecture. *Speed:* fast — Artificial Analysis measures the non-reasoning variant at 94.9 tok/s output with 0.69 s TTFT (fastest Anthropic model at 95.6 tok/s on its provider page). *Cost:* cheap; barbell partner to Sonnet/Opus.
- **GPT-6 Astra** ($10/$50; cached $1, write $12.50; 1.05M context) — *Best for:* hardest end-to-end reasoning/agentic work and computer use; OpenAI flagship (released Sep 3–4, 2026, knowledge cutoff Apr 2026). *Avoid for:* single-turn chat/classification (pays premium for nothing). *Speed:* no independent throughput published yet. *Cost:* highest OpenAI tier; Batch/Flex halve to $5/$25, Fast mode doubles to $20/$100; any prompt >272K input tokens reprices the whole request to $20/$75.
- **GPT-5.6 Sol** ($4/$20 promotional through ≥Nov 21 2026; list $5/$30; cached 10%) — *Best for:* deep reasoning at high/max effort and agentic coding. Per OpenAI's GA launch post, Sol posts 88.8% on Terminal-Bench 2.1 (91.9% ultra mode) and 64.6% on SWE-bench Pro, and set SOTA at 80 on the Artificial Analysis Coding Agent Index "using less than half the output tokens and taking less than half the time." *Avoid for:* high-volume cheap work. *Speed:* ~72–80 tok/s; TTFT scales sharply with effort (2.6 s low → ~130 s max, Artificial Analysis). *Cost:* mid-high; `pro` reasoning mode for the hardest tasks. Fast mode $8/$40 (2× standard).
- **GPT-5.6 Terra** ($2/$12; cached $0.20; 1.05M context) — *Best for:* balanced OpenAI production default; undercuts prior GPT-5.4 ($2.50/$15). *Avoid for:* frontier reasoning. *Speed:* ~2.7× faster than Sol in Artificial Analysis testing. *Cost:* mid; the OpenAI analog to Sonnet 5.
- **GPT-5.6 Luna** ($0.20/$1.20; cached $0.02; 1.05M context) — *Best for:* autocomplete, boilerplate, mechanical refactors, whole-repo reads, high-volume steps. Artificial Analysis: ~157 tok/s, ~100 ms TTFT; $0.05 per Intelligence-Index task (cheapest on board). *Avoid for:* architecture, ambiguous debugging, visual work. *Cost:* cheapest current-gen with large context (80% cut from launch $1/$6).
- **o-series reasoning models** — per CloudZero's 2026 OpenAI pricing guide: "o4-mini at $1.10/$4.40 per million tokens, o3 at $2.00/$8.00, and o3-pro at $20.00/$80.00… o-series models bill internal reasoning tokens at output rates, so effective costs run 3× to 10× the base rate." *Best for:* legacy reasoning workloads; reserve o3-pro for tasks where evals prove the lift. Superseded for most coding by GPT-5.6/Astra.

---

## Cost & speed trade-offs

**Where spending more buys real quality:** architecture/design, deep multi-file root-cause debugging, agent-run planning, and security-sensitive code. A wrong answer here has high blast radius and is expensive to verify, so Opus 5 / Fable 5.1 / Astra earn their premium by raising first-attempt acceptance and cutting retries.

**Where premium spend is wasted:** boilerplate, CRUD, config, commit messages, autocomplete, doc drafts, and test scaffolding. These are cheaply verifiable (compiler/tests/human glance), so a Luna/Haiku answer that is occasionally redone is still cheaper and faster. Do NOT run these on a frontier model.

**Worked example 1 — implement + debug a feature end-to-end.** Assumptions: spec (5K in / 2K out), implementation (30K in / 8K out), 2 debug cycles (20K in / 4K out each), tests (15K in / 5K out), PR description (8K in / 1K out).
- **All-Opus-5:** input ≈ 98K × $5/M = $0.49; output ≈ 24K × $25/M = $0.60 → **≈ $1.09** per clean pass, moderate latency.
- **Routed (recommended):** spec on Sonnet (~$0.03) + implementation on Sonnet (~$0.14) + debug cycle 1 on Sonnet (~$0.06) + debug cycle 2 escalated to Opus (~$0.20) + tests on Sonnet-Batch (~$0.04) + PR on Luna (~$0.003) → **≈ $0.47** — a ~57% saving at equal-or-better acceptance, because the one genuinely hard debug step still gets Opus.
- **All-Luna (naïve cheap):** ~$0.11 sticker, but if the complex logic and debug fail and must be redone on Opus anyway, effective cost exceeds $1.20 and wall-clock is worse. This is the trap the governing principle warns against.

**Worked example 2 — 500-file dependency migration (mechanical, well-tested repo).** Batch Sonnet 5 across files: input 500 × 4K × $1/M (batch) = $2.00; output 500 × 1.5K × $5/M (batch) = $3.75 → **≈ $5.75** for the whole migration, with the test suite as the acceptance gate. Escalate only the handful of files that fail tests to Opus 5. The same job on Opus 5 non-batch would cost roughly 4× with no quality gain on mechanical edits.

**Latency classes (Artificial Analysis, Sept 2026, first-party APIs):** Luna ~157 tok/s / ~100 ms TTFT (fastest) → Haiku 4.5 ~95 tok/s / 0.69 s TTFT → Sonnet 5 ~72–86 tok/s → Sol ~72–80 tok/s → Opus 5 ~51–57 tok/s → Fable 5.1 ~66–70 tok/s but heavy default thinking pushes end-to-end latency to minutes at max effort. For anything user-facing, **effort tier matters more than model choice**.

---

## Decision flow

```
Incoming step
│
├─ Is output cheaply machine-verifiable AND mechanical
│  (boilerplate, config, commit msg, autocomplete)?
│    └─ YES → GPT-5.6 Luna (or Haiku 4.5 if you need lowest TTFT). Batch if non-interactive.
│
├─ Is it a review/triage pass over a diff?
│    └─ YES → Haiku 4.5 first pass → escalate flagged/security/concurrency diffs to Opus 5.
│
├─ Is it architecture, agent-run planning, deep multi-file root-cause, or security-sensitive?
│    └─ YES → Opus 5 (high effort).
│         └─ Still failing OR novel/long-horizon/scientific? → Fable 5.1 or GPT-6 Astra.
│
├─ Is it "normal" coding (implement / refactor / shallow debug / tests / spec)?
│    └─ YES → Sonnet 5 (default).
│         ├─ Failed same step twice OR tests still red OR spans ≥3 files? → Opus 5.
│         └─ Non-interactive batch of many files? → Sonnet 5 via Batch API.
│
└─ Need deep reasoning but cost-sensitive / OpenAI-shop?
     └─ GPT-5.6 Sol (high or `pro`) ; drop to Terra ($2/$12) for balanced production traffic.
```

---

## Assumptions & caveats

- **Pricing date:** September 7, 2026. Claude prices verified against the platform.claude.com docs pricing page. OpenAI prices verified against OpenAI developer docs plus corroborating trackers (CloudZero, BenchLM, Morph, Artificial Analysis).
- **Pricing deltas from the user's supplied table (flagged):**
  - **GPT-5.6 Sol:** the brief lists $4/$20; OpenAI's current *list* price is **$5/$30**, and **$4/$20 is promotional** pricing. OpenAI's Fast-mode doc bills Sol at exactly 2× standard = $8/$40, consistent with a $4/$20 standard promo rate available "at least through November 21, 2026." Treat $4/$20 as promo and **budget for reversion to $5/$30**, which narrows Sol's cost edge over Opus 5.
  - **GPT-6 Astra confirmed** at $10/$50 (cached $1, write $12.50), released Sep 3–4 2026, 1.05M context — matches the brief. The brief's note is right that Astra and Fable 5.1 share the frontier tier and cache-write ($12.50) but differ on cache read ($1 vs $0.25); the internal inconsistency the user flagged resolves in favor of the differing-cache-read reading.
  - **Claude table matches the primary source exactly:** Fable 5.1 $10/$50 (cache read $0.25); Opus 5 $5/$25; Sonnet 5 $2/$10; Haiku 4.5 $1/$5. **Correction:** the user's note that Sonnet 5's intro rate lapses Sep 1 is WRONG — Anthropic cancelled the scheduled increase; $2/$10 is now the permanent standard price.
  - **Long-context:** Claude has **no** long-context surcharge (full 1M at flat rate from 4.6 onward). OpenAI reprices the entire request past 272K input tokens to ~2× input / ~1.5× output — factor into large-repo work.
- **Benchmark sources & harness caveat:** SWE-bench Verified (Anthropic system cards, Vals.ai, llm-stats), SWE-bench Pro (Scale SEAL), Terminal-Bench 2.1/3.0/4.0 (Artificial Analysis, tbench.ai, CodingFleet), Aider Polyglot. **Scores are NOT comparable across harnesses/scaffolds or benchmark versions.** SWE-bench Verified is near-saturation (top models cluster within ~1 pt) with known contamination/flawed-test caveats. OpenAI's July 8 2026 audit *"Separating signal from noise in coding evaluations"* states: "we find widespread task issues in SWE-Bench Pro and estimate that ~30% of the tasks are broken" — its automated pipeline flagged 200 tasks (27.4%) and five human engineers flagged 249 (34.1%), overly-strict hidden tests being the top failure mode. Use scores for within-benchmark ranking only, and always re-validate on your own codebase.
- **Reasoning-effort controls materially change cost & quality:** GPT-5.6 supports `none`→`max` effort plus `standard`/`pro` modes (independent controls); Claude current-gen uses adaptive thinking (Opus 5 and Fable 5.1 default thinking on; Fable 5.1 defaults to High effort in Claude Code, Medium elsewhere). High effort improves hard-task accuracy but can cost 4–5× tokens for small gains — **route effort, not just model**.
- **Caching mechanics:** Claude 5-min TTL (write 1.25×) or 1-hr TTL (write 2×), read 0.1× base (0.025× on Fable/Mythos 5.1); minimum cacheable prefix 512 tokens on current models (Opus 5, Fable/Mythos 5, Fable 5), 2,048 on others; cache reads are excluded from ITPM rate limits (a free throughput multiplier). Break-even: ~2 reads (5-min) or ~6 reads (1-hr). OpenAI cached input 10% of standard, cache writes 1.25×, cache persists ≥30 min.
- **Batch / Flex / Fast:** Both vendors' Batch = 50% off, for non-interactive jobs (Claude 24-hr window; OpenAI 24-hr). OpenAI Flex = Batch rates, synchronous, best-effort (429s not charged). OpenAI Fast mode (renamed from Priority Jul 30 2026) = 2× cost, up to 2.5× speed on Sol. Claude Fast mode = $10/$50, Opus 5 / Opus 4.8 only, not batch-compatible.
- **What would change the recommendation:** (1) Sol promo reverting to $5/$30 narrows its edge over Opus 5; (2) a measured Astra $/task advantage — OpenAI claims Astra's best config completes DeepSWE tasks at ~57% lower cost/task than Sol (Sol scores 80 vs DeepSWE-style baselines on the Artificial Analysis Coding Agent Index; the per-task claim is vendor-reported and not independently verified) — could promote Astra for agent loops if it holds; (3) new Haiku/Sonnet generations closing the gap upward; (4) **your own evaluation on your codebase always overrides public benchmarks.** Re-run this routing table quarterly given the active price war.