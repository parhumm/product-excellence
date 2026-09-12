# Phase 1 review fixes

## Correctness and reliability

- Fixed fresh installation seeding: auxiliary Linux/disconnect profiles previously caused baseline profiles to be skipped entirely.
- Validate AI budgets, selected pillars, observation duration and network/browser combinations before execution.
- Snapshot network configuration on each queued run, preserving reproducibility when profiles are edited later.
- Persist cancelled queued runs and align timeout JSON artifacts with database status.
- Enforce configured success text when AI claims success. Check final observations after the last allowed action.
- Preserve unavailable browser metrics as null. WebKit's unsupported CLS no longer appears as zero.
- Attach HTTP and console evidence only to the observation interval in which it was collected.
- Use the finding's own screenshot for verification, and review candidates by severity within the available budget.
- Report incomplete AI evaluation and failed accessibility coverage. Release gates exclude rejected/dismissed findings and cannot pass incomplete coverage.
- A failed candidate run cannot falsely mark previous findings resolved.
- Bound trace, browser-context and video cleanup. Record playable journey video.
- Publish a terminal run status only after video, trace and timings are attached, so pollers never read a finished run without its evidence.
- Give completion actions an explicit status, matching every other recorded action.
- Send screenshots to the Claude Code worker over the streaming input and output pair the CLI requires, instead of mixing streaming input with buffered output.
- Find the Codex and Claude clients in their usual install locations, so the verification scripts behave the same as the service even when a plain shell PATH does not list them.
- Report a worker that has run out of subscription credit as an unverified adapter with the client's own message, instead of an unexplained crash.

## Choosing the AI worker, model and reasoning effort

- Missions carry `provider`, `model` and `effort`. Each can be switched independently in the console, in exported YAML and through the API.
- The Codex worker receives the model as `--model` and the effort as `model_reasoning_effort`; the Claude Code worker receives `--model` and `--effort`.
- Model names are validated as plain aliases so they cannot smuggle extra command-line arguments.
- High and extra-high effort get a longer per-call deadline and, for seeded journeys, a longer wall clock, because a single Opus call with a screenshot can take minutes.
- Both workers authenticate only through their subscription; API-key variables stay stripped from the worker process.

## Added and completed controls

- Schedule pause/resume, persistent next-run times and prevention of overlapping scheduled copies.
- Project creation and mission assignment, mission version history, ownership and duplicate grouping.
- Proxy public-IP verification through an actual HTTP CONNECT connection.
- Local Schema.org vocabulary validation across known types, properties and their domains.
- Playback observation duration, fresh frame counters, active-stall duration, stall ratio and custom player events.
- Focus/select/forward browser actions and select-option observations.
- Unique form IDs and preservation of expanded evidence panels during live refresh.

## Remaining external requirements

Authenticated playback needs a valid test session and content entitlement. A named real ISP needs an actual endpoint from that ISP, not merely a label or a loopback proxy. Production payments remain blocked. Native mobile/TV devices are outside Phase 1. Statistical recall, precision and UI-resilience targets require the PRD's labelled benchmark and human adjudication; smoke tests do not establish those targets.

## Phase 1 readiness review, 2026-09-06

- Added schema-required AI issue keys, normalized page identity and previous-run issue catalogs. Titles can change without changing an issue identity. Domain and content query parameters distinguish different pages; tracking parameters and fragments do not. Legacy deterministic identities are recalculated for comparison/grouping without rewriting historical evidence. New replays can reuse legacy AI keys.
- Enabled one bounded automatic replay for non-rejected, non-dismissed/non-resolved P0–P2 findings when the mission opts in. No severity inflation; the release-blocking rule stays unchanged.
- Manual and automatic replays preserve the original network snapshot. Comparison checks actual network settings, target URL and worker conditions. Incompatible or incomplete candidates cannot claim missing findings were resolved.
- Replay queue/configuration errors no longer turn a completed parent into a failed run. Manual replay errors return a usable validation/capacity response.
- Blocked unscoped Space-key activation, which could otherwise activate a destructive button reached by Tab without the normal click-policy check.
- Limited critic review to the documented two findings; bounded browser and Playwright shutdown; cancellation publishes its terminal state after artifacts finish.
- Reject nonexistent project assignments on mission edits before storing a version. Markdown reports now include screenshot references and owner/triage status.

Historical AI-to-AI comparisons between two records lacking issue keys still need human reconciliation. No old findings or severities were rewritten.

## After readiness, 2026-09-06

- Compacted every AI prompt in `engine/prompts.py`: fields the model cannot act on are dropped and a repeated observation is encoded as a reference to an earlier one with a decoding note. No screenshot, measurement, action or finding is removed.
- Hardened the workers: Claude runs with `--safe-mode`, an empty tool set, an empty MCP configuration, no session persistence and a short task-only system prompt; Codex with `--ephemeral --ignore-user-config --sandbox read-only` and no shell tool.
- Redaction keeps its counts, so a prompt shows that content was withheld rather than silently shrinking.
- Fixed model identity: the reported model is read from the client's own usage record for that call, instead of assuming the requested id. Only full model ids are offered, after a probe showed `--model sonnet` answering as `claude-opus-5` and `--model opus` as `claude-fable-5-1`.
- Added per-call token, wall-time and list-price cost estimates to the run record, the console, the Markdown report and `cli.py run --wait`, with a `models` command listing the priced catalogue. Unpriced models show `n/a` and mark the run total partial.
- Allowed Enter on a live search input, rechecked against the element immediately before the key lands. All other form-submitting keys stay refused.
- A refused or malformed action no longer ends the run on its own: the reason is recorded, handed back to the model, and only two consecutive rejections stop the run. Not yet exercised on a live run.
- Treat a URL the standard parser rejects, such as an unparseable port, as disallowed instead of raising.
- Withdrew the earlier 40.7 s to 26.5 s speed claim. Rerun at one model, the shorter prompts are not faster; only the prompt-size saving is established. See `docs/OPTIMIZATION.md`.
- Changed the seeded Claude preset from the `opus` alias to `claude-opus-5`. Existing missions keep whatever model they were saved with.
