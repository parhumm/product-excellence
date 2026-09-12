# Phase 1 web delivery plan

Target: usable local internal product for authorized websites. Delivery target is today; completion is determined by recorded acceptance results, not time elapsed. The workspace begins with a PRD and no application code.

## Implementation order

| Stage | Build | Acceptance |
| --- | --- | --- |
| 1 Foundation | FastAPI service, PostgreSQL persistence, setup scripts, health checks | Start, restart and retain projects, missions, runs and findings |
| 2 Browser and evidence | Chromium/Firefox/WebKit, viewports, personas, screenshots, DOM, console, HTTP, trace | Real run produces timestamped evidence; cancel closes browser |
| 3 AI journeys | Codex subscription adapter, Claude alternative, structured decisions, bounded action loop | Logged-in provider chooses and executes actions; invalid results and timeouts fail visibly |
| 4 Evaluation | Functionality, CRO hypotheses, SEO/AEO, accessibility/visual review, performance/video | Each pillar reports coverage and evidence; no invented metrics |
| 5 Networks | Browser throttling, five profiles, Linux netem runner, per-run proxy routes | Applied settings recorded; synthetic impairment and actual egress reported separately |
| 6 Verification | Replays, finding fingerprints, baseline comparison, deterministic release gate | Replay creates separate evidence and comparison uses compatible runs |
| 7 Console and automation | Missions, live timelines, findings, configuration, schedules, CLI, export | A user starts and reviews a run without coding |
| 8 Release verification | Fixture bugs, policy tests, persistence/recovery, smoke run, installation guide | Test report lists passed checks and any unverified functionality |

## Delivery contract

Deliver source, locked dependencies, one-command startup, local console, generic mission presets, JSON/YAML mission import and export, Markdown/JSON reports, and a reproducible test record. Do not claim the PRD's statistical targets from a handful of runs. They require a representative labelled benchmark and human review.

## External prerequisites

Codex is installed and reports ChatGPT login on this Mac. Claude is installed but initially reports no login. Authenticated journeys need a user-supplied test session; no credentials are bundled. Real ISP switching needs actual proxy/VPN endpoints. Linux netem needs a Linux host and isolated network privileges. Network access, geo restrictions, anti-bot screens, DRM and login challenges may limit what can be verified from this location.

## Runtime choices

FastAPI and SQLAlchemy with PostgreSQL; local evidence files; one active run to bound subscription usage and host load. Playwright runs the browser. The AI proposes bounded actions; the engine validates and executes them. A deterministic audit mode remains useful when AI login/quota is unavailable and is explicitly identified as non-autonomous. The console is served locally by the same service. No public SaaS deployment or API keys are required.

## Reference checks

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): structured output and saved CLI authentication.
- [Codex authentication](https://learn.chatgpt.com/docs/auth): ChatGPT subscription sign-in for local work.
- [Claude programmatic mode](https://code.claude.com/docs/en/headless): structured print output.
- [Playwright network](https://playwright.dev/docs/network): browser-scoped proxy routing.
- [Linux netem](https://man7.org/linux/man-pages/man8/tc-netem.8.html): Linux network impairments.
