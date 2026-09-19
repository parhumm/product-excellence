# Reference

Everything Product Excellence can do, in detail. Start at the
[README](../README.md) to install it and the
[user manual](USER_MANUAL.md) to use it.

A local web and Android testing console for goal-driven journeys, five-pillar reviews, replay and evidence-backed findings. A workspace contains targets with separate missions, runs and findings. Uses a signed-in Codex or Claude CLI, without API keys.

New here? Read the [short, plain-language user manual](USER_MANUAL.md).

## Open the app

Open **http://127.0.0.1:8741**. If the service is stopped, double-click **start.command** in the project folder. Leave its terminal open while using the app. The same command works from a shell:

```bash
./start.command
```

Codex workers use `~/.codex` by default, even when Product Excellence is started
from another Codex installation with a different inherited `CODEX_HOME`. If the
same OS user has extra signed-in profiles named `~/.codex-NAME`, Settings lists
them by email. Choose a default for each workspace, then optionally override it
on a mission. The resolved profile is recorded in each run snapshot. A new
replay resolves the mission choice and current workspace default again.
`PEX_CODEX_HOME` changes the standard default profile only. See the
[account selection guide](USER_MANUAL.md#choose-a-codex-account).

The app keeps its database, screenshots, traces, video and account sessions under `data/`. Source archives omit these private runtime files. AI-enabled runs send selected evidence to the chosen provider, and a connected team server receives shared results. See [privacy and data handling](PRIVACY.md).

## First real run

1. Choose the website in the sidebar **Workspace** selector.
2. Open **Missions**.
3. Choose a mission and press **Run**, or edit its goal first. On the mission form, write what you want to learn in your own words and press **Suggest two better goals**: the signed-in worker returns two goals aimed at different business questions, each with what you learn from it and the mode and pillars it needs. **Use this goal** fills the form; nothing is saved until you press **Save mission**. Every workspace starts with ten ready missions covering the home page, registration, sign-in, search, the core features, pricing and checkout, the mobile app, SEO and AEO, accessibility, and a slow phone. The sign-in missions need an account: open one and fill in **Sign-in identifier** and **Sign-in password**.
4. Follow the live timeline. Choose an observation to inspect its screenshot and measured signals.
5. Read the executive summary and the pillar scores at the head of the finished run, then open findings, inspect evidence, and use **Replay** to gather a second run. The recorded journey plays at 2x by default; the selector beside it offers 0.5x to 10x.
6. Download the Markdown report or complete JSON. Compare runs in **Compare releases**.

**Benchmark** answers one question on this website and then on each competitor listed on the mission, and the finished run compares the sites side by side: outcome, measurements, and what the review found strong and weak on each. Findings stay about your own site; competitor pages are evidence for the comparison.

The **5 networks** button queues the same mission under five browser profiles. For a targeted audit, select **Page / pillar audit** and choose the evaluation pillars. **No AI** runs deterministic checks only; CRO and visual judgment require an AI worker.

## Workspaces and targets

A workspace is one product and may hold multiple website and Android targets. Existing workspace URLs become deterministic default web targets; migration adds JSON records only, writes `data/backups/records-before-targets-*.json` before its first change, and does not rewrite missions, runs, schedules, secrets or evidence. An app-only workspace may have a blank URL.

Android build metadata contains SHA-256, version name/code, SDK requirements, launcher, ABIs and size. APK bytes remain mode `0600` under `data/apps` on each execution console and are never sent to the hub. Queueing resolves "latest" once and pins the SHA. Archiving removes a build from new latest selection; removing local bytes preserves history and requires that exact SHA before replay.

`PEX_ANDROID_SDK`, then `ANDROID_HOME`, `ANDROID_SDK_ROOT`, Homebrew's command-line tools root and `~/Library/Android/sdk` are checked in order. `PEX_ANDROID_AVD` names the only disposable AVD allowed for execution; `PEX_ANDROID_WINDOW=1` shows its window. `PEX_ANDROID_PROBE_URL` is an operator-supplied HTTPS endpoint used only to verify offline restoration. APK runs need platform-tools, emulator, build-tools, a system image and an AVD. AVD creation additionally needs command-line tools and a JDK; fixture compilation needs platform android-34, javac, d8, zipalign, apksigner and keytool.

The measured fixture ran on API 34 arm64 with usable hierarchy, safe text input, sensitive-field recognition, seekable MP4, PSS and attributable Java crash/ANR logs. Gfx/jank was unavailable. Without an operator probe URL, Android is baseline-only; shaping and periodic disconnects are rejected. Launch is `am start -W TotalTime`, PSS is KiB, touch targets use 48 dp, and unavailable measurements remain null. This is not full mobile accessibility, playback QoE, physical-device coverage or field performance.

Mission fields `target_id`, `build`, `device`, `visibility` and resolved `platform` bind these facts. Android permits an optional HTTPS deep link only on the target's hosts and rejects benchmark, competitors, SEO/AEO, personas and sign-in; it may name a proxy route, and its emulator is launched against the relay that serves it. Raw MP4 cannot be masked; logs are attributable, bounded and best-effort redacted. Continue is web-only; Android replay requires the same SHA.

In a connected workspace, `visibility=local` keeps a target, mission or run on one Mac. Sharing is explicit and ordered: target, mission, terminal run. Run sharing uploads finalized ordinary evidence but not browser traces; local records remain authoritative until acknowledgement. Published items cannot be made local.

## Scores and the executive summary

Every finished run is rated 0–100 for each evaluated pillar and carries an executive summary.

A score is arithmetic over the run's own findings, not a benchmark or a field measurement. A pillar starts at 100 and loses 40 points for each open P0 or P1, 15 for a P2 and 5 for a P3, counting an unconfirmed AI finding at half weight; functionality loses a further 30 when the journey did not reach its goal. Every tile lists the deductions that produced it, and dismissing or rejecting a finding recomputes the score. A pillar the run did not evaluate reads "not scored" with its reason rather than zero, and the overall figure averages only the scored pillars, alongside how many of the five those were.

The summary is deterministic by default: status, gate, open findings by severity, coverage gaps, the most serious findings and next steps, all read from the record. When an AI worker ran the review it also writes the headline, the prose and the next steps within the same call, and the run states which of the two you are reading. The AI is never asked for a number.

## Subscription access

Open Settings to check each provider. Authentication uses the provider's installed CLI, not automated ChatGPT/Claude web pages. API-key environment variables are removed from worker processes to respect subscription-only operation.

```bash
codex login
codex login status
claude auth login
claude auth status
```

Workers run bounded: the Claude client is started with `--safe-mode`, an empty tool set, an empty MCP configuration, no session persistence and a short task-only system prompt; Codex with `--ephemeral --ignore-user-config --sandbox read-only` and its shell tool disabled. Neither worker can touch this machine; it answers with a schema-validated action or evaluation. CLI versions must support the flags shown in `../engine/ai.py`. This installation was verified with its installed clients. Provider `auto` can use the first authenticated client and fall back on execution failure within the mission's call budget. Subscription usage and quotas still apply.

### Choosing the worker, model and reasoning effort

Every mission carries three independent settings, editable in the mission form and in exported YAML:

- **AI worker**: Codex on the ChatGPT subscription, Claude on the Claude Code subscription, the first available worker, or no AI for a deterministic audit.
- **AI model**: pick from the catalogue the mission form lists for the selected worker, or leave it on **CLI default**. Each entry is a full model id with a price hint; **Custom model id…** accepts any other id the client takes. Prefer full ids: probing the installed Claude CLI on 2026-09-06 showed its short aliases answer as a different family (`--model sonnet` replied as `claude-opus-5`, `--model opus` as `claude-fable-5-1`), while every full id answered as itself.
- **Reasoning effort**: `low`, `medium`, `high` or `xhigh`. Dynamic sets this per call, so the form hides it and shows the ceiling instead.

**Dynamic** is the default model choice, designed to balance accepted-result quality, cost and speed. Instead of one model for the whole run, it picks a model and an effort for each call: the smallest model on the list plans each browser action, the next one up judges the outcome and challenges a finding, and the evidence review runs on Opus 5 / GPT-5.6 Sol at high effort, capped by the highest model allowed; P1 finding critics use Opus/Sol at medium effort. **Highest model allowed** is that ceiling; left empty it means the strongest model this console lists. When an action is refused by the safety policy or changes nothing on the page, the next action is planned one model and one effort higher, up to the ceiling. A mission that falls back to the other worker keeps the same tier, because the two ladders line up.

Higher effort is slower and spends more subscription quota, so give a high-effort journey a longer run time limit. Missions saved before 2026-09-06 may still hold a short alias; reselect the model to pin the family you want.

### AI usage and cost

Each AI call records the model the client actually reported, the reasoning effort, input, cached and output tokens, its wall time and an estimated cost at published standard API prices. Runs use your subscription and nothing is billed per call, so the estimate exists to compare runs with each other, not as an invoice. Totals appear in the runs table and run header, the per-call table sits under **AI usage** in the run detail, and both the Markdown export and `cli.py run --wait` print them. A model with no published price shows `n/a` and marks the run total partial. See the [price table and caveats](USER_MANUAL.md#token-use-and-cost-estimates).

## Test accounts

Run the helper, sign into a **test account** in the browser it opens, then import the saved file under **Settings → Test personas**:

```bash
.venv/bin/python scripts/capture-persona.py --url https://example.com
```

For a site whose login the assistant should exercise itself, fill **Sign-in identifier** and **Sign-in password** on the mission instead. The identifier is typed literally; the password is kept in `data/secrets` and filled by the engine, and exact reflected password text is scrubbed from structured page evidence. Password inputs are masked in screenshots, but other page content, video and traces can still contain secrets. Redaction is not a guarantee; see [privacy and data handling](PRIVACY.md). Setting an identifier also lets that website send its own mutating requests to the mission's allowed domains, which a phone-and-password login needs. Payment, deletion and publishing controls stay refused, and logins that require a one-time code are not supported.

The AI does not type passwords or OTPs. Account sessions are stored locally with restricted file permissions. Screenshots, video, traces and DOM snapshots can contain personal page content; keep them private. Image masks cover common password/email/phone inputs, but they are not a comprehensive PII detector.

## Network testing

Local Chromium profiles support browser-level latency, download/upload caps, offline and periodic disconnects. Firefox and WebKit support baseline/offline locally. Unsupported combinations fail explicitly.

For packet-level loss and jitter, start the isolated Linux browser:

```bash
./scripts/start-netem.sh
```

Docker is required. It runs on this laptop, uses no extra hardware, and shapes only its own container network. The **Linux loss and jitter** profile then uses this browser. The profile records the actual Linux queue configuration in the run.

Network scope is explicit: Linux netem shapes container **egress**, including control traffic. Chromium additionally applies the download cap at browser level. This is not a symmetric physical-link simulation. Delay, jitter, packet loss, reordering and duplication are egress effects; incoming packet loss is not separately emulated. Reordering needs nonzero latency. Browser profile latency is a browser setting, not measured end-to-end RTT.

Use **Network & routes → Add a proxy route** for a real remote egress. Supply an HTTP(S) or SOCKS5 endpoint and credentials you control. Labels do not prove ISP/ASN identity; verify the provider and route independently. No ISP endpoints or credentials are bundled.

### Changing the route mid-journey

A mission whose scenario contains a `route` step runs through a relay this run owns. The relay listens on loopback on an ephemeral port for the length of the run, and the browser or the emulator is pointed at that one local address. Upstream credentials stay in the relay: they never reach the browser, the page, the device or the run record, and inbound proxy credentials are stripped. Only HTTP(S) upstreams can be switched to; a SOCKS5 route is refused with its name rather than silently skipped, though a SOCKS5 route still works as a mission's fixed route, which is passed to the browser directly.

A switch is a deliberate interruption. Every connection opened on the previous route is terminated so the next request takes the new way out, which means in-flight requests can fail — that is the point of the step, and a scenario that switches mid-download should expect it. Nothing is retried and nothing falls back to a direct connection: a route that cannot be established stops the run.

What a switch proves is bounded. The relay probes itself through the new route with two independent public echoes and records the address they report; that address, and the per-generation connection counts, are the evidence. DNS is resolved on this machine, so a CDN may still answer from the host resolver's country rather than the exit IP's, and UDP/QUIC is never proxied at all. Two routes reporting the same exit IP is a valid result, not a failure.

On Android the way out is fixed when the emulator launches, so the run starts the relay first and launches the designated AVD against it with `-http-proxy`. The guest keeps no proxy setting of its own and no app can opt out of it. An emulator that is already running was not launched against this relay, so a routed Android mission refuses to start until the designated AVD is stopped.

## Scenarios

An Android or website mission may carry an ordered scenario of at most 40 steps. Without one, the mission runs as a single AI journey exactly as before. One vocabulary, one interpreter and one journey library serve both; the target decides what each step acts on.

Build it in the mission form's **Scenario** section, or start from the gallery at **Missions → Start from a journey**, which opens the form with a journey's target, name, goal, time limit and steps already set. Twelve shipped journeys fill the rows, **Draft the steps** asks the signed-in AI worker for a first draft from a sentence (or from the goal, when no sentence is given), and the advanced view shows the same steps as YAML. The rows and the YAML are one model: text that does not parse stays in the editor and never replaces working rows.

A journey carries no platform and leaves two to four blanks where a real value belongs. The console lists every distinct blank above the step list, fills each occurrence across the name, goal and steps at once, and keeps both submit buttons disabled — saying how many are left — until none remain. The server refuses a mission that still holds one, which is the check that counts.

Each step is exactly one of five keys, plus an optional `name` used only as a label:

```yaml
- goal: "Open '<Movie title>' and start playback"
- check: {playing: true, within: 15}
- event: {network: cellular}
- hold: {playing: true, for: 20, policy: unknown}
- manual: "Sign in as <Account B>"
```

- `goal` gives the AI worker one instruction, with an optional `until: {text: "…"}` early stop. Reaching it proves navigation, nothing later.
- `check` requires a fact to become true once inside `within` seconds, default 10.
- `hold` requires it to stay true across `for` seconds, sampled about every two seconds. The result reports how many samples were taken over how long, and gaps are recorded rather than smoothed over.
- `event` acts on the device or the page: `route`, `network`, `speed` with an optional `delay_ms`, a standalone `delay_ms`, `wait`, `home`, `back`, `kill`, `relaunch`, `deep_link` and `open_notification`. A `route` may carry the `speed` and `delay_ms` it is to be measured under; that is one operation, not two.
- `manual` hands the run to a person. On Android recording is stopped and confirmed stopped before the notice appears, so credentials are never recorded or sent to the AI worker; on the web it means acting outside the page, and the per-context video is not cut. The run page offers **Continue**; the wait counts against the run's own budget and is shown as the shorter of the two.

A check or hold states exactly one fact: `text`, `text_absent`, `screen` (`contains` or `equals`, the focused activity on Android and the page address on the web), `playing`, `notification`, or `no_crash`. Three modifiers apply to any of them. `policy: unknown` marks a behaviour nobody has confirmed: it is recorded as an observation with severity `info`, deducts nothing, blocks nothing, and can never be required. `severity` defaults to P2. `required` defaults to true under confirmed policy; a required failure or a required measurement that could not be established stops the steps that depend on it.

Evidence that cannot be read is never read as a negative. An unreachable hierarchy, an unknown foreground package or a parser error makes a step **unavailable**, which is a coverage gap, not a defect. The run page lists those separately from findings, alongside the questions raised by unknown-policy steps.

### What a step means in a browser

`screen` is the page address. `notification` is a notification the page itself created through the Notification API, and `open_notification` fires that notification's own click handler. `playing` reads the first `<video>` or `<audio>` element that has loaded anything. `no_crash` means no uncaught page error since the last goal or event — not that nothing failed. `kill` drops the document to `about:blank`, so in-memory state is gone while cookies and storage stay; `home` brings another tab in front so the page goes hidden; `relaunch` brings the page back and reloads it; `back` is the browser's own back; `deep_link` opens a URL only on a host the mission is already allowed to visit.

Two caveats, both refused at save time rather than discovered mid-run. Link shaping — `speed`, `delay_ms` and `network: wifi | cellular` — throttles the browser through Chromium's own emulation and is refused on any other browser; `offline` and `restore` work everywhere. A saved device state cannot be loaded into a browser: a website mission carries its signed-in session through a persona instead, and `Keep previous app data` reuses the session storage the mission's last run wrote.

### Start state and saved device states

Fresh app data clears the package before the run. That is `pm clear`, not a reinstall, and it changes nothing on any server. Keep leaves whatever the last run left behind, which is useful for exploring and useless for confirming a reproduction. Load restores a device state saved on this Mac.

Manage those states under **Settings → Android device**. A state is saved under a generated id, is never overwritten, and is validated against what is actually on disk before it loads: changed or missing files fail the load instead of quietly using the current device. Saving and deleting share the lock a run holds, so both wait while a mission is in progress. A saved state restores the local emulator only; an account, a paid entitlement and an expired session are still the scenario's job to check.

Manual steps need an emulator with a visible window. Start the console with `PEX_ANDROID_WINDOW=1`, and restart an emulator that is already running without one; the environment variable alone does not give a window to a process that started without it.

### Replay and reproduction

**Compare releases** answers two separate questions and says so. Whether the conditions match is one: the scenario digest, requested and actual start state, fault settings, package, device properties and network settings all take part. Whether a finding seen in both runs may be called **reproduced** is another: that needs the same APK, a start state that was established rather than inherited, no operator attestation in the middle, and no required step left without evidence. When it cannot be called a reproduction the console says which of those is missing, and a matching finding counts as a second observation instead.

## Fresh installation

```bash
./scripts/setup.sh
./start.command
```

`setup.sh` installs `uv` when it is missing, then the locked Python dependencies
and the three Playwright browsers. `uv` downloads its own Python 3.11+, so
nothing else has to be installed first. axe-core is vendored in
`static/vendor/axe-core`, so there is no Node or npm step. For autonomous runs,
sign in to at least one AI CLI.

A fresh installation keeps its records in SQLite at `data/records.db`. Three
environment variables change where things live and which port is used:
`DATABASE_URL` selects the database, `PEX_DATA` moves the data directory and
`PEX_PORT` moves the service off 8741. Together they start a second, isolated
service beside the running one, which is how the measurements in
`OPTIMIZATION.md` were taken:

```bash
DATABASE_URL=sqlite:///$PWD/tmp/pex.db PEX_DATA=$PWD/tmp/data .venv/bin/uvicorn app:app --port 8742
```

For PostgreSQL, set `DATABASE_URL` before starting. An installation that already
holds a project-local cluster in `data/postgres` keeps using it: the launcher
starts that cluster on 127.0.0.1:55439 and never silently moves its records to
SQLite. The local cluster trusts local connections and is intended for a single
trusted user. It does not replace a system database.

On Linux, install Playwright's browser dependencies with
`.venv/bin/playwright install --with-deps`. Keep the console bound to loopback:
it is a single-user tool. To share results with other people, publish them to
the team server below.

## Team server

Your configured team server exposes a public landing page at its root URL. `/console` asks for a workspace username and password and then shows that workspace's missions, runs, evidence, findings and comparisons, read only.

Playwright traces (`trace.zip`) stay on the machine that ran the mission; every other piece of evidence is shared. The server stores and shows results. It never opens a browser and never calls an AI, so Run, Replay, the network matrix and the mission forms are disabled there and read "Coming soon". Everyone runs missions on their own machine with their own Claude and ChatGPT subscription: `./scripts/setup.sh`, `./start.command`, then Settings → Team server → `https://team.example.com` and the workspace login. A finished run publishes itself, evidence included, and the whole team sees it.

Sign-in is HTTP Basic. **Sign out** is in the console sidebar and in the admin page header; Safari may show its sign-in prompt once, and Cancel completes it. One login per workspace, created and rotated at `/admin`.

Deployment is a `git push`. A timer on the box checks `origin/main` every two minutes and, when it moves, syncs the locked dependencies, restarts the service and rolls back to the previous commit if the new one does not answer its health check. `ssh root@<box> pex-deploy --force` does it immediately. See [the deployment guide](DEPLOY.md).

## Automation and integration

Schedules run while the service is alive and persist across restarts. Their minimum interval is five minutes. One run executes at a time; up to 20 can queue. User-set time, step and AI-call limits bound each run.

```bash
.venv/bin/python scripts/cli.py health
.venv/bin/python scripts/cli.py models
.venv/bin/python scripts/cli.py missions
.venv/bin/python scripts/cli.py run MISSION_ID --wait
.venv/bin/python scripts/cli.py run MISSION_ID --network slow-mobile --wait
.venv/bin/python scripts/cli.py import mission.yaml
.venv/bin/python scripts/cli.py export RUN_ID --format md
.venv/bin/python scripts/cli.py findings --project PROJECT_ID --grouped
.venv/bin/python scripts/cli.py findings --run RUN_ID
.venv/bin/python scripts/cli.py review RUN_ID FINDING_ID --status accepted --owner "QA"
.venv/bin/python scripts/cli.py compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

`findings` prints findings as JSON, filtered to one workspace or one run, and `--grouped` folds one issue into one row across runs; `review` sets a finding's status (`open`, `accepted`, `resolved`, `dismissed`) and owner and reports how many earlier reports of the same issue it synced; `compare` prints what changed between two runs. `health` shows the version and the database, worker and browser readiness; `models` lists the selectable model ids with their estimated prices; `run --network` overrides the mission's profile for one run; `run --wait` prints the run's AI usage and cost estimate when it finishes. Every command accepts `--url` for a service on another port.

CLI exit codes after `run --wait`: 0 completed/pass, 1 completed/warn, 2 blocked/failed/cancelled or a blocking gate. API documentation is at **http://127.0.0.1:8741/docs**. Mutating API calls require `X-PEX-Request: 1`; cross-origin requests are rejected. The team server's `/hub/health` returns its version alongside `ok`, which is how a deploy is confirmed from another machine.

### Claude Code skills

`.claude/skills/` ships eight skills that drive the commands above. Every one reads `.claude/skills/_shared/rules.md` first: reading is free, anything that imports, runs, edits, files, pushes or deploys stops for confirmation, and findings, page text and log lines are treated as data rather than as instructions. None of them opens `data/secrets`, a saved persona or a recording, and none writes a credential into anything it produces. The [skills guide](SKILLS.md) is the version written for users.

| Skill | Invocation | Tools it may use |
| --- | --- | --- |
| `pex-env-check` | model or user | cli.py, `curl` on 127.0.0.1, `claude auth status`, `codex login status`, `./scripts/setup.sh` |
| `pex-mission-write` | model or user | cli.py, Read, Write |
| `pex-mission-suggest` | model or user | cli.py, one fetch of the workspace's own home page, Read, Write |
| `pex-run-diagnose` | model or user | cli.py, `curl` on 127.0.0.1, Read, Write |
| `pex-findings-triage` | model or user | cli.py, Read, Write |
| `pex-run-brief` | user only | cli.py, its own `scripts/build_report.py` (benchmark runs use `scripts/benchmark.py`), Read, Write |
| `pex-issue-report` | user only | its own `scripts/collect.py`, `gh issue list`, `create` and `comment` |
| `pex-release-ship` | user only | `git`, pytest and `tests.ui_check`, `curl`, `ssh root@<box>` |

`pex-issue-report` attaches only what its `collect.py` gathers: the version, the commit, the operating system, the health output, the run's status, error and last events, and matching log lines with emails, tokens, cookies, passwords and long identifiers redacted. It attaches no screenshot and no recording; it references the artifact path instead.

`tests/test_skills.py` checks the front matter, the description length, the bundled paths and the documentation of every skill. `tests/test_release.py` checks that `pyproject.toml`, `app.py` and `hub.py` declare the same version and that the changelog leads with it.

## Measurement and verification

- Browser signals: navigation timing, LCP, session-window CLS, observed interaction duration, long tasks, console errors, HTTP status and resource metadata.
- Accessibility: axe-core WCAG A/AA checks. Incomplete checks are recorded; automated checks do not establish complete accessibility compliance.
- SEO/AEO: title, description, canonical presence, robots, JSON-LD parsing, headings and initial/hydrated evidence. JSON-LD parsing and a bundled vocabulary check are not full Schema.org validation.
- Video: HTML video play/startup, waiting/stalls, dimensions, errors and dropped-frame counters when actual playback occurs. ABR bitrate needs player instrumentation.
- JavaScript errors: every page error and console error keeps its name, message, source location (file, line and column), page URL, observation step and stack trace. The finding carries the same detail; the review prompt receives only the source location, so prompt size does not grow with stack depth.
- Scores: derived from the recorded findings and coverage by the fixed rule above, never measured or estimated quality. An unevaluated pillar is not scored rather than zero.
- CRO and visual judgment: evidence-referenced AI hypotheses; no invented conversion uplift or causal claims.
- Verification: deterministic findings are confirmed observations. AI findings begin unconfirmed; a critic reviews up to two within the call budget. AI findings carry an issue key independent of their title; replays receive the earlier issue catalog. Replay uses the original network snapshot and is a separate run; matching findings under compatible conditions are marked reproduced.
- Automatic replay: when enabled, an open or accepted, non-rejected P0–P2 finding queues one child run using its own mission budget. P3/info findings do not trigger it. Children never trigger another automatic replay. This does not raise severity or relax the release gate: blocking still requires a confirmed, reproduced P0/P1.
- Review state: a finding's status and owner belong to the issue, not to one report. Editing either writes it to every finished run of the workspace that recorded the same finding identity, and a compatible replay that no longer detects an earlier finding marks it resolved everywhere. Runs still queued or running are left alone, and a later run that detects the issue again records it as open.
- Comparison: identifies new, persisting and not-seen-again findings and lab metric changes. It flags incompatible conditions. A missing finding in one replay does not prove resolution. Incompatible conditions, incomplete coverage, evaluation failures and policy-blocked requests suppress the not-seen-again claim. Historical AI records without issue keys remain intact; their old fingerprints are provided as legacy keys to new replays. Two old runs with differently worded AI findings cannot be reliably reconciled without review; unmatched legacy AI findings are flagged as uncertain rather than new or resolved.

To expose proprietary player events, the tested page can dispatch:

```javascript
window.dispatchEvent(new CustomEvent('pex:player', {
  detail: { type: 'quality_change', bitrate_kbps: 2400, resolution: '1280x720' }
}));
```

## Scope and limits

This is an internal engineering release. The full PRD's statistical quality targets are not certified by the smoke tests. It does not include payment authorization, automated account mutation, a device lab, native mobile/TV execution, multi-user access, commercial-scale concurrency, a full Schema.org validator, or verified ISP endpoints.

Keyboard input is restricted to navigation: Tab, Escape, the arrow keys, Home and End, plus Enter when the focused element is a live search input, because some search pages expose no submit control. Any other key is refused rather than risking an unintended form submission; the worker is told why and can choose a different action, and two consecutive refused or malformed actions end the run. The default network policy blocks POST/PUT/PATCH/DELETE to prevent account or financial changes; sites using POST for read-only search/data may need a reviewed adapter. Blocked requests are reported so resulting failures are not silently attributed to the product. An unavailable measurement is not a zero; a blocked capability is not a pass.

## Tests and delivery record

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m tests.ui_check
```

The default pytest suite is offline and consumes no AI quota. While iterating,
run the relevant test file; run the full suite before delivery. The UI check waits
for each destination heading instead of fixed delays, and accepts `PEX_BASE_URL`
and `PEX_UI_ARTIFACTS` for an isolated server and screenshot directory.

AI prompts use compact JSON. The review pass references identical fields from
earlier observations when that saves space, with an explicit decoding note.
No evidence is truncated by this compaction; screenshots, measurements, action
history, worker/model/effort settings, critics and saved artifacts are preserved.
Provider readiness checks run concurrently without caching authentication state.
See [optimization measurements](OPTIMIZATION.md) for results and limits; the prompt-size saving is measured, while the earlier claim that the shorter prompts run faster was withdrawn after a fair same-model rerun.

The smoke and acceptance scripts create test missions and consume subscription usage when AI is selected. Run them intentionally. See `DELIVERY_PLAN.md` and `VERIFICATION.md` for delivery scope and observed results.

## Usage modes

| Mode | Workspace data | Browser and AI | Selection |
| --- | --- | --- | --- |
| Local | Local database and `data/artifacts` | This machine's browser and signed-in CLI | No workspace logins |
| Hybrid | HTTPS team server | Each teammate's machine and subscription | Settings → Team server → workspace sign-in |
| Fully server | Planned separately | Not implemented | Not available |

An admin-only sign-in does not change data mode. Signing out of the last workspace returns to the existing local records. A disconnected team server never silently switches the app to local data. Settings remains accessible when the server is unreachable or a password was changed.

When the server stops answering, a page the browser reads falls back to the last copy this console received for that read, and the console shows a warning naming when it was synced; a browser read gives up after 20 seconds instead of the 60 second publication timeout, and once one read in a page has timed out the rest of that page skips the server instead of waiting again. A read with no earlier copy answers with an empty list rather than an error, so the console still opens on a machine that has never reached the server, with the warning saying no copy is held. Saving and starting runs still require the server and fail with the unreachable message, so a stale copy is never written back. Those copies live in `data/hub-cache/reads`, separated by server, sign-in and query, and are only served while the connection is failing. Background publication, recovery and reconciliation always read the server itself.

### Team server deployment

The hub serves shared records and evidence, not browser execution or AI. Start with one process and SQLite on persistent storage. PostgreSQL also remains supported. Use a dedicated service account; the paths below assume the repository is installed at `/opt/product-excellence` and its dependencies were installed there with `uv sync --frozen`.

Create `/var/lib/product-excellence-hub`, owned by that service account, with mode `0700`. Create `/etc/product-excellence-hub.env`, readable only by the service account/root (`0600`):

```dotenv
PEX_DATA=/var/lib/product-excellence-hub
DATABASE_URL=sqlite:////var/lib/product-excellence-hub/records.db
PEX_HUB_ADMIN_PASSWORD=replace-with-a-long-unique-admin-passphrase
```

Install `/etc/systemd/system/product-excellence-hub.service`:

```ini
[Unit]
Description=Product Excellence workspace hub
After=network.target

[Service]
Type=simple
User=pex
Group=pex
WorkingDirectory=/opt/product-excellence
EnvironmentFile=/etc/product-excellence-hub.env
ExecStart=/opt/product-excellence/.venv/bin/uvicorn hub:app --host 127.0.0.1 --port 8750 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/product-excellence-hub

[Install]
WantedBy=multi-user.target
```

Replace `pex` with the account you created. Enable the service with `sudo systemctl daemon-reload` and `sudo systemctl enable --now product-excellence-hub`. Configure DNS and Caddy for your actual hostname:

```caddyfile
team.example.com {
    reverse_proxy 127.0.0.1:8750
}
```

Only expose HTTPS through the reverse proxy; the hub port stays on loopback. Trust forwarded headers only from the actual proxy address, never `*`. The app rejects cross-origin browser mutations, requires `X-PEX-Request: 1` for writes, limits JSON to 8 MiB and individual evidence files to 512 MiB, and throttles failed authentication in bounded process-local buckets. Use one hub worker with this limiter; add an edge limiter before scaling workers. Monitor available disk space because evidence accumulates.

Open the HTTPS server URL and sign in as `admin`. Create a workspace with its own username and a 15–256 character password. Starter missions are enabled by default; leave them off for an import. In each local app, open Settings → Team server and enter the same server URL plus that workspace's credentials. You can also sign in as `admin` locally to create workspaces or rotate their sign-ins. Credentials are stored atomically in a `0600` local `data/hub.json`; they are never returned by status endpoints. Changing credentials requires teammates to update their sign-in.

For development, HTTP is accepted only for loopback server URLs. Use separate data directories/databases for the hub and local apps. Do not point the hub at an actively used local database.

### Execution, evidence and recovery

Workspaces share missions, versions, runs, schedules and evidence. Custom network definitions, proxy credentials, mission passwords and test-persona sessions remain local. A teammate must configure any referenced local resource before starting a mission that needs it. Evidence already captured inside runs is shared and may include account information; use test accounts.

Each schedule runs on the machine that created it, while that app is open. Imported schedules start paused. Shared credentials give everyone in that workspace the same access; machine IDs coordinate execution and do not identify individual users securely. Remote cancellation works only while a run is queued. After it starts, cancel it on its owning machine. A schedule paused after a run was accepted does not stop that run.

Concurrent edits are rejected with a conflict rather than overwriting someone else's changes. Reload the affected record, review the retained form draft and reapply the change. The local app holds one execution lock per data directory; run one app process per directory.

Screenshots upload as a run progresses. Final status is published after the referenced evidence has been uploaded and its checksums verified. Failed transfers leave the local evidence and latest run snapshot in `data/pending-publication`; Settings shows pending uploads and a Retry uploads button. Recovery retries after reconnect/restart and does not overwrite a conflicting newer revision. Keep the source files until upload succeeds. Signing out or changing servers is blocked while runs or pending publication need that connection. Artifact caches are separated by server and workspace under `data/hub-cache`; authentication is checked before cached evidence is served. Signing out is not secure erasure of evidence already downloaded to a machine.

The hub generates `run.json` from the current canonical record, so later finding review is reflected in that export. Original local raw evidence remains complete. List views return bounded run summaries; full evidence is fetched for run detail and findings. This is a small-team design, not a distributed job system or an offline editing system.

### Import a workspace

First back up the source and hub as described below. Create an empty target workspace with **Add starter missions** unchecked, then sign into that workspace in the local app. Stop the local app before running the import (the importer checks its execution lock).

```bash
.venv/bin/python scripts/push-workspace.py LOCAL_PROJECT_ID HUB_WORKSPACE_ID
.venv/bin/python scripts/push-workspace.py LOCAL_PROJECT_ID HUB_WORKSPACE_ID --apply
```

Replace `LOCAL_PROJECT_ID` with the source workspace's local project ID. Without `--apply`, the tool reports counts and validates the source/target without uploading records. The apply step saves a source-record/empty-target backup and resumable manifest in `data/imports`. It preserves record IDs, timestamps, historical snapshots, evidence links and replay references, changes only workspace ownership fields, pauses schedules and marks unfinished history interrupted. Password/persona directories are never imported. Unresolved ownership, missing evidence, unrelated ID collisions or teammate edits stop the import with an error. Fix the stated issue and rerun the same command; matching uploaded data is verified and reused. Only a completely verified import reports success.

Afterward, compare mission/version/run/schedule counts and inspect a screenshot, trace/video and replay pair where present. Configure local execution resources and deliberately enable the schedules you want. Keep the source data and backups until these checks are complete.

### Backup and restore

Back up the database **and** artifact directory together. For a consistent SQLite snapshot, stop the hub, archive its whole persistent data directory with restricted permissions, and restart it:

```bash
sudo systemctl stop product-excellence-hub
sudo tar -C /var/lib -czf /root/product-excellence-hub-backup.tar.gz product-excellence-hub
sudo chmod 600 /root/product-excellence-hub-backup.tar.gz
sudo systemctl start product-excellence-hub
```

Store a separate protected backup of the environment file. For PostgreSQL, stop the hub, use `pg_dump --format=custom` against its database and archive `PEX_DATA/artifacts` in the same stopped interval; restart after both complete. Back up local data with the local app stopped, including local secrets/personas if those must be recoverable.

Before upgrading, stop submissions, drain queued/running runs and every console's `data/pending-publication`, then checkpoint database and artifacts together. Version 1.5 adds no database schema: it creates default target JSON records and writes `records-before-targets-*.json` before the first such write. This export is supplementary, not the restore source. Upgrade the hub first, then every console in a workspace before using targets, Android or private items. The first such shared mutation stamps server-owned `min_console=1.5.0`; older, missing or malformed `X-PEX-Console` headers then receive HTTP 426, while health, auth and the read-only team page remain reachable.

For rollback after new-format writes, stop all processes, preserve the current database/artifacts/APKs, quarantine all pending-publication JSON, new share journals and affected hub read caches, then restore the coordinated checkpoint databases including `min_console`. Do not copy the old outbox back blindly; retain it for explicit reconciliation after a later upgrade and record which machines were restored. A code-only rollback is safe only if no target, Android or visibility-stamped record was written.

Test restoration into a separate directory/database and loopback hub: extract the archive there, set `PEX_DATA`/`DATABASE_URL` to the restored paths and launch `uvicorn hub:app` on a spare port. Verify workspace authentication, record counts, historical versions, one artifact checksum and a video range request before replacing a live installation. Restore PostgreSQL dumps into an empty disposable database using `pg_restore`, with matching artifacts. Integration tests exercise a source-record backup restore into a fresh SQLite database; operational archive/production restoration still needs the deployment's own rehearsal.

### Team-server verification

`.venv/bin/python -m pytest -q` includes isolated API tests plus one loopback cluster with a hub and two local apps. It needs permission to bind local ports. Tests do not call AI providers or production websites. Existing UI verification remains `.venv/bin/python -m tests.ui_check` with `PEX_BASE_URL`/`PEX_UI_ARTIFACTS` pointed at an isolated local app. `tests/hub_smoke.py` separately exercises real browsers against the local demo only, without AI.

Fully server-side browser execution is future work. It requires a separate review of worker ownership, API-key authentication, secrets and authenticated application routes; disabling the local boundary is not sufficient.
