# AI call cost, speed and usage reporting — 2026-09-06

A second pass over the same path, this time measuring where the tokens and the
seconds actually go and making both visible per run. Raw stored evidence is
still byte-identical; every reduction happens while building a prompt.

## Changes

- `engine/prompts.py` projects each packet for its task. Control fields that are
  empty, false or an empty list are dropped and boxes are rounded to whole CSS
  pixels; successful same-method HTTP responses collapse into counts by resource
  type while every failed or non-GET response is kept in full; action prompts
  drop metrics, structured data, accessibility results and timestamps; review and
  critic prompts drop only artifact paths, timestamps and the metric support
  notes. Each omission is explained once in the instruction text, so nothing is
  silently missing. A numeric zero is evidence and is never dropped.
- `engine/ai.py` replaces the Claude Code system prompt with a short task system
  prompt, and captures per-call usage for both workers. Codex runs with `--json`
  so its `turn.completed` usage is read from the event stream.
- `engine/pricing.py` (new) holds the model catalogue and estimates a cost from
  the reported token counts at published API list prices. Runs still go through
  the subscription CLIs; no API key is used and nothing is billed per call.
- `engine/runner.py` records every attempted call, including a primary worker
  that failed before the automatic fallback, and emits a per-call event. The two
  critic calls now run concurrently, and the screenshot and DOM snapshot in
  `observe()` are taken concurrently.
- The console, the Markdown report and `scripts/cli.py` show the models used,
  token counts and the estimate. The mission form offers a model list per worker
  with a price beside each entry and an escape hatch for any other id.

## Measured results

### Prompt size, reconstructed from three saved runs

`.venv/bin/python -m tests.prompt_sizes` rebuilds each prompt from a stored
`run.json` and compares the old encoding with the new one. No browser and no AI
call is involved.

| Saved run | Prompts compared | Before | After | Reduction |
| --- | --- | ---: | ---: | ---: |
| 7703fe… journey, 6 steps | 6 action, 1 review, 2 critic | 185,281 chars | 99,724 chars | 46.2% |
| bdbe4b… explore, 4 steps | 4 action, 1 review, 2 critic | 241,575 chars | 119,982 chars | 50.3% |
| b421c6… audit fixture | 1 review, 2 critic | 16,816 chars | 11,030 chars | 34.4% |

The largest single packet, the review call in bdbe4b…, fell from 105,540 to
50,395 characters. These are characters, not tokens, and they exclude the fixed
instructions, the schema and the screenshot. The comparison uses an empty replay
issue catalogue and counts only deterministic findings as known findings, on
both sides.

### Fixed overhead per Claude call

Four short probe calls on Claude Haiku 4.5, comparing command-line flags:

| Setup | Fixed input tokens | Call duration |
| --- | ---: | ---: |
| Default Claude Code system prompt, cold | 4,643 | 9.1 s |
| Default Claude Code system prompt, warm | 9,736 | 15.7 s |
| Short task system prompt via `--system-prompt` | 1,033 | ~4 s |

The warm default run also returned no structured output, so replacing the system
prompt fixed a correctness problem as well as a cost one. `--setting-sources ''`
and `--restricted` were not adopted: `--safe-mode` already suppresses settings,
CLAUDE.md, skills and plugins.

### Live runs on a fair baseline

Both commits were rerun on 2026-09-06 on isolated SQLite servers, `claude` worker,
`claude-sonnet-5` asked for explicitly on both sides, low effort, three-call budget,
against each server's own `/demo?bug=true` fixture. The earlier 40.7 s baseline is
withdrawn: that mission asked for the `sonnet` alias, which this Claude command line
answers with Opus 5, so it measured a different model.

| Audit run | AI calls | Findings | Duration |
| --- | ---: | ---: | ---: |
| Baseline d33537b… #1 | 2 | 9 | 19.8 s |
| Baseline d33537b… #2 | 2 | 9 | 21.0 s |
| After #1 | 3 | 12 | 39.5 s |
| After #2 | 3 | 12 | 29.7 s |

At the same model, the shorter prompts did not make the run faster. Duration tracks
the number of calls and the output tokens, not the prompt size: the current prompts
draw more findings out of the same fixture, which costs one extra verify call. Per
call the two sides are comparable, roughly 10 s against 10-13 s. The prompt saving
is real and is measured deterministically by `tests/prompt_sizes.py` (34-50% fewer
characters); the earlier claim of a matching wall-clock saving was a model artifact.

### One live journey run

The journey path had never run against a real model since the prompt rewrite. Run
5779e72b3de14a29b66fc40bc0ac7b88 on the same isolated server, `claude-sonnet-5`,
low effort, goal "Open the featured movie page and play its trailer", success text
"Playback ready", three-step and four-call budget:

| Call | Purpose | Input | Output | Wall | Estimate |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | action step 1 | 3,420 | 161 | 4.6 s | $0.0153 |
| 2 | action step 2 | 3,529 | 153 | 5.2 s | $0.0156 |
| 3 | review | 5,987 | 1,249 | 17.3 s | $0.0364 |
| 4 | verify | 4,659 | 893 | 14.6 s | $0.0300 |

Two clicks, then the configured success text matched: outcome `success` with basis
"Configured visible text matched", 12 findings, playable video, 49.4 s total,
$0.0974 estimated. Every call reported `claude-sonnet-5`, and no token count came
back `[REDACTED]`. This is the first live exercise of `prompt_observation(obs,'action')`
and `prompt_actions`, including the second step, where `recent_actions` is non-empty.

For one review call in the first optimized audit the recorded usage was 2 fresh input tokens,
4,707 tokens written to the 1-hour cache, no cache hits and 477 output tokens.
Recomputing by hand at Sonnet 5 list prices gives $0.023602, which equals the
stored estimate exactly. The command line reported $0.025896 for the same call;
the $0.0023 difference is its own side call to Haiku, which our usage block does
not include.

## Two defects the live run exposed

- **Token counts were being redacted.** `redact()` blanks any key matching
  `token`, which caught `input_tokens` and `output_tokens` and wrote
  `"[REDACTED]"` into the run record. It now keeps numbers and explicit nulls
  under a sensitive key name, since neither can carry a credential.
- **The wrong model was being reported.** The Claude command line bills a small
  side call to another model and lists both in `modelUsage`, and the first entry
  is not necessarily the one that answered. A run asking for Sonnet was recorded
  as Haiku, and its estimate was five times too low. The reported model is now
  the entry whose counts match the result's own usage block, falling back to the
  largest consumer.

Both were found only by running the thing for real, and both are covered by
tests now.

## Deviations from the plan

- The budget-stop judgment call and the review call were **not** parallelized.
  When `observe_seconds` is set, another observation is taken between them, so
  running them together would change which evidence the reviewer sees.
- In `observe()`, only the screenshot and the DOM snapshot run concurrently. The
  accessibility pass still runs afterwards, because it injects a script tag that
  would otherwise appear in the stored DOM snapshot.
- The model list renders both workers' models at all times rather than only the
  selected worker's, so every model stays reachable, including when the worker
  is set to pick the first available one.

## What was not verified

The Codex path is covered by a JSON-lines fixture test only. The ChatGPT
workspace has no credits, so no Codex run was executed live and its usage
parsing, model reporting and estimate remain unconfirmed against a real call.

Live quality was checked on one audit run of a local fixture. That run produced
its expected deterministic findings and one verified AI finding; it is not
evidence about journey or explore modes, other sites, or other models.


# Token use and test speed — 2026-09-06

## Changes

- Compact JSON in journey, final-outcome, review and critic prompts removes
  formatting overhead. Repeated review observation fields reference earlier
  observations with an explicit `same_as` explanation. The encoder falls back
  to plain compact JSON when references would be larger or IDs are ambiguous.
- Evidence content is preserved, including nulls, zeroes, Unicode, controls,
  metrics, errors and action history. Raw stored observations are unchanged.
  Worker/model/effort settings, screenshot attachments and verification remain.
- Codex and Claude readiness checks run concurrently. Timeout/cancellation uses
  the subprocess cleanup path; killed children are reaped. No auth cache is used.
- UI checks wait for the exact destination heading. This avoids both fixed
  delays and falsely accepting the previous view's heading during hash navigation.
  Video verification waits for playback progress. Deliberate observation,
  network-settling, cancellation and deadline test intervals remain.
- Short root agent instructions guide scoped reads and offline testing.
  The early observation write is retained so cancellation during accessibility
  collection still leaves partial evidence on disk.

## Measured results

| Check | Before | After | Conditions |
| --- | ---: | ---: | --- |
| UI smoke test | 11.343 s | 1.227 s | Same local Chromium, isolated SQLite server, provider discovery disabled; one before/after pair |
| Saved-run review sample 1 | 126,353 chars | 117,323 chars | Latest eligible local saved run, last four observations |
| Saved-run review sample 2 | 109,929 chars | 102,267 chars | Next eligible saved run |
| Saved-run review sample 3 | 48,644 chars | 45,612 chars | Next eligible saved run |
| Repeated synthetic evidence | 30,244 chars | 7,834 chars | Four observations from `tests/test_prompts.py` |

Saved-run comparisons reconstruct the review packet with its goal, observations,
actions, findings and an empty replay issue catalog. They exclude the fixed task
instructions, provider wrapper, schema and screenshot tokens. Synthetic savings
are intentionally a repetition case, not an estimate for typical production use.
Character reductions do not establish billed-token savings or AI latency savings.

The original 41-test suite passed in 1.03 s. The expanded 47-test suite passed
in 1.41 s, including lossless prompt reconstruction, value preservation, provider
concurrency and subprocess output handling. Parallel pytest workers were not
added: the baseline is already short and startup overhead would need justification.
Two existing dependency deprecation warnings remain.

The optimized UI check passed all eight desktop views, screenshots, mobile
overflow and JavaScript-error checks. The full external-site acceptance scripts
were not rerun. Live subscription-worker judgments have since been rerun on
2026-09-06: the audit and journey runs recorded above show the model reading the
rewritten evidence encoding correctly on both the review and the action path.
Those five live runs spent subscription quota; the rest of this verification did
not. This was a focused prompt/test-speed review, not a full security, dependency
or product audit.

## Routine verification

```bash
.venv/bin/python -m pytest -q
# Prompt sizes rebuilt from saved runs; offline, no AI quota:
.venv/bin/python -m tests.prompt_sizes
# Against an already-running isolated server, when browser checks are relevant:
PEX_BASE_URL=http://127.0.0.1:8742 PEX_UI_ARTIFACTS=/tmp/pex-ui .venv/bin/python -m tests.ui_check
# Model catalogue and prices, against a running server:
.venv/bin/python scripts/cli.py --url http://127.0.0.1:8742 models
```

Keep slower live tests for changes that need them. Avoid reducing evidence,
disabling critic checks, lowering model quality or shortening measurement
windows merely to obtain a lower token count or a faster reported test time.
