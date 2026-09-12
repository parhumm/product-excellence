# AUTONOMOUS PRODUCT EXCELLENCE ENGINE

**Phase 1 — Full-Feature Web Edition**

Visual AI QA + Product Optimization + Network / ISP Simulation

> **Deployment constraint — **Phase 1 must run on one developer laptop or one VPS. No dedicated device lab, no mobile/TV hardware, and no AI API key are required.

**Purpose: **Define a buildable product architecture, scope, execution model, prompts, success metrics, and phased roadmap for an autonomous product-excellence system. Phase 1 is intentionally device-limited to Web while keeping the full product capability set.

*Status: Development baseline*

## 1. Executive Summary

Build an autonomous product-quality and optimization engine that uses AI to experience a web product like a real user, execute goal-driven journeys, discover defects and friction, measure objective browser/network/video signals, verify findings, and produce evidence-backed product issues. The engine is not a replacement for deterministic telemetry; AI performs perception, exploration and judgment while instrumentation supplies measurable facts.

Phase 1 delivers the complete product loop for the Web interface only. It supports real browser execution, desktop/mobile web viewports, multiple browsers, authenticated and unauthenticated personas, deterministic network impairment profiles, optional real ISP egress through VPN/proxy endpoints, autonomous exploration, five-pillar evaluation, replay, deduplication, regression comparison, evidence capture, and a local dashboard. Later phases add exactly one new device family at a time while reusing the same engine.

> **Core product idea — **Give the system a user goal rather than a selector script. It observes the rendered product, decides what to do, interacts through a browser, collects evidence, evaluates the experience across five pillars, reproduces important findings, and reports only evidence-backed results.

## 2. Phase 1 Scope

| **Area** | **Phase 1 requirement** |
| --- | --- |
| Execution target | React/Web applications in Chromium first; Firefox and WebKit available for compatibility runs. |
| Host | Single macOS/Linux laptop or single Linux VPS. |
| AI access | Codex CLI authenticated with a ChatGPT subscription and/or Claude Code authenticated with a Claude subscription. No API key required for the initial build. |
| Interaction | Visual-first autonomous browser use. Playwright is the deterministic browser control/evidence layer, not a brittle selector-authored test suite. |
| Network | Local network shaping for latency, bandwidth, jitter, loss, reorder/disconnect profiles; optional VPN/proxy routing for true regional/ISP egress. |
| Pillars | Functionality, CRO, SEO/AEO, UX/UI/accessibility, Performance/Video QoE. |
| Modes | Golden journeys, exploratory missions, regression comparison, scheduled/release runs, targeted audits. |
| Storage | Local PostgreSQL + filesystem/object storage. SQLite is acceptable only for the first developer prototype. |
| UI | Local web dashboard to create missions, watch runs, review findings and compare releases. |
| Integrations | CLI/webhook interface first; Jira/GitHub/GitLab issue creation can be optional adapters. |

### 2.1 Explicitly Out of Scope for Phase 1

- Native Android, native iOS, Android TV, Samsung Tizen and LG webOS execution.

- Physical device farms, HDMI capture cards, IR blasters or smart plugs.

- AI provider API integration. The architecture must expose a provider interface so APIs can be added later, but subscriptions/CLI sessions are the first execution path.

- Production payment with uncontrolled real money. Use sandbox/staging accounts or deterministic policy gates.

- Claims that AI can directly measure hard metrics from pixels. Browser/player/network telemetry remains the source of truth.

## 3. How the Product Is Used

The primary interface is mission-oriented. A user creates or selects a mission, chooses personas/environments, starts a run, and receives ranked findings with evidence. No Playwright test authoring is required for normal use.

1. Create a mission: e.g., “As a new user, find a premium movie, subscribe, return to the movie and start playback.”

2. Choose execution matrix: browser, viewport, authentication state, locale, network/ISP profile and release/build URL.

3. Run the mission. The agent observes the page, plans the next user action, executes it, verifies the state change and repeats.

4. Collectors continuously capture screenshots, DOM/accessibility snapshots, HTTP data, console errors, Core Web Vitals, player events and network condition metadata.

5. Five specialist evaluators analyze the same run. Candidate findings are challenged by a verifier and replayed when practical.

6. The dashboard groups duplicates, compares with previous runs/releases, assigns severity/confidence and exposes exact evidence/reproduction steps.

```text
Mission → Environment → Observe → Decide → Act → Verify State
          ↘ Evidence collectors run continuously ↙
      5 Pillar Evaluators → Critic → Replay → Deduplicate → Finding
```

## 4. Phase 1 Technical Architecture

```text
┌──────────────────── Product Excellence Console ────────────────────┐
│ Missions | Runs | Findings | Regressions | Evidence | Settings     │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                     Journey Orchestrator
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   AI Worker Adapter      Browser Runtime       Policy Engine
 Codex CLI / Claude Code   Playwright/CDP      limits & safety
        │                      │
        │            ┌─────────┴──────────────┐
        │            │ Browser + Instrument  │
        │            │ screenshots / DOM     │
        │            │ a11y / HTTP / CWV     │
        │            │ console / player QoE  │
        │            └─────────┬──────────────┘
        │                      │
        └──────────── Evidence Bundle ──────────────┐
                                                    │
   Functionality | CRO | SEO/AEO | UX/UI | Performance/QoE
                                                    │
                          Verifier / Replay / Dedup
                                                    │
                           PostgreSQL + Artifacts
```

### 4.1 Recommended Software Stack

| **Layer** | **Recommended choice** | **Why** |
| --- | --- | --- |
| Backend / orchestrator | Python 3.12 + FastAPI | Simple process control, CV ecosystem, network tooling integration and service APIs. |
| Job execution | Python asyncio + local worker process; Redis queue only when concurrency requires it | Avoid premature distributed complexity on one machine. |
| Database | PostgreSQL | Runs, journeys, findings, evidence metadata, baselines and history. |
| Artifacts | Local filesystem first; MinIO optional | Screenshots, traces, HAR, video clips, DOM and telemetry bundles. |
| Browser automation | Playwright | Browser control, screenshots, tracing, Chromium/Firefox/WebKit, CDP access and agent tooling. |
| Browser telemetry | Chrome DevTools Protocol + PerformanceObserver | Network, performance and browser-level evidence. |
| Accessibility | axe-core + accessibility tree snapshots | Deterministic rule checks plus AI interpretation. |
| Visual state filter | OpenCV + perceptual hash / SSIM | Avoid sending/reasoning over unchanged frames. |
| Video handling | FFmpeg | Capture/trim/compress run evidence and playback samples. |
| Network shaping | Linux tc/netem | Rate, latency, jitter, loss, corruption/reorder/duplicate profiles on Linux. |
| True ISP routing | WireGuard/OpenVPN/SOCKS/HTTP proxy adapters | Routes traffic through actual external egress nodes when available. |
| Dashboard | React/Next.js | Mission builder, live run timeline, findings and comparison UI. |
| Observability | OpenTelemetry + structured JSON logs | Trace every AI decision, action, collector event and verifier result. |

## 5. AI Access Without API Keys

Phase 1 uses installed AI coding-agent clients as local reasoning workers. The application does not automate the ChatGPT or Claude consumer web UI. It launches supported local clients/CLIs that are already authenticated by the developer’s subscription session, passes a bounded task/context packet, and captures the returned structured result.

| **Provider** | **Authentication** | **Phase 1 integration** |
| --- | --- | --- |
| OpenAI | Sign in to Codex using the ChatGPT account/subscription. | Install Codex CLI; create a CodexWorker adapter that invokes the local authenticated client as a subprocess and reads machine-parseable output when supported. |
| Anthropic | Sign in to Claude Code using the user’s eligible Claude account/subscription. | Install Claude Code; create a ClaudeWorker adapter with the same internal request/response schema. |
| Fallback | At least one provider must be configured. | Provider router chooses primary/fallback based on availability, quota, task type and failure state. |

> **Important limitation — **Subscription-backed CLIs are excellent for a PoC and internal tool, but they are not the right assumption for a high-concurrency commercial service. Keep the AIWorker interface provider-independent so official APIs or enterprise endpoints can replace CLI workers later without changing the rest of the engine.

### 5.1 Internal AI Worker Contract

```text
AIRequest {
  task_type,
  system_instructions,
  mission,
  current_state,
  evidence_refs,
  allowed_actions,
  output_schema,
  budget
}

AIResponse {
  decision,
  rationale_summary,
  action,
  observations[],
  candidate_findings[],
  confidence,
  stop_reason
}
```

Do not depend on provider-specific conversation memory. The orchestrator owns state and sends the minimum required context for every decision. This allows provider switching and makes runs auditable.

## 6. Browser Execution Engine

Playwright is used as a low-level actuator and sensor. The normal authoring unit is not a Playwright test; it is a product mission. The AI should prefer user-observable state and semantic/accessibility information and should not depend on fragile CSS/XPath selectors generated by humans.

### 6.1 Observation Packet

- Current screenshot plus optional cropped regions around meaningful state changes.

- URL, title, viewport, scroll position and browser identity.

- Accessibility tree / semantic snapshot of actionable controls.

- Reduced DOM facts for current visible region and important metadata; never dump the full DOM by default.

- Console errors and failed network requests since the previous action.

- Current performance snapshot and player/QoE events.

- Last N actions and observed outcomes.

- Current mission progress and remaining execution budget.

### 6.2 Action Vocabulary

```text
click(target)
focus(target)
type(target, text)
press(key)
select(target, option)
scroll(direction, amount)
open(url)
back() / forward() / reload()
wait_for_state(description, timeout)
capture_evidence(label)
finish(success | blocked | policy_stop | budget_stop)
```

The browser adapter resolves an abstract target through visible text, accessibility role/name, bounding box and current semantic snapshot. DOM/CSS identifiers may be used internally as temporary handles after an element is resolved, but mission definitions never store them as the durable contract.

## 7. Network and ISP Switching

Phase 1 supports two separate capabilities because they solve different problems: reproducible network-condition simulation and real egress/ISP routing. They must not be conflated in reports.

| **Mode** | **What it does** | **Requirements** | **Use** |
| --- | --- | --- | --- |
| Network profile emulation | Applies controlled bandwidth, latency, jitter, packet loss, reorder, duplication or temporary disconnect. | Linux host/network namespace with tc/netem. On macOS, run the browser/runner inside a Linux VM/container or use a platform-specific shaper. | Reproducible QoE and resilience testing. |
| Real ISP / regional egress | Routes browser traffic through a VPN/proxy exit located on the desired ISP/region. | VPN/proxy endpoint and credentials; can be rented/remote, so no local hardware is needed. | Geo/ISP-specific routing, CDN behavior, peering, availability. |
| Combined | Applies an impairment profile on top of a selected egress. | Both above. | Example: ISP-A Tehran egress + 180 ms RTT + 2% loss + 5 Mbps cap. |

### 7.1 Example Profiles

| **Profile** | **Parameters** |
| --- | --- |
| baseline | No artificial impairment. Record actual RTT/throughput. |
| slow-mobile | 5 Mbps down, 1 Mbps up, 90 ms added latency, 20 ms jitter, 0.5% loss. |
| poor-mobile | 1.5 Mbps down, 512 Kbps up, 180 ms latency, 50 ms jitter, 2% loss. |
| unstable | 8 Mbps average, 70 ms latency, variable rate, 1% loss, periodic 2–5 second disconnect. |
| high-latency | 20 Mbps, 300 ms latency, low loss. |
| custom-isp-X | Selected proxy/VPN route + recorded impairment profile based on measurements from ISP X. |

Every finding must record both egress identity and impairment profile so results are reproducible. The engine must never label a synthetic profile as proof of a real ISP problem.

## 8. Full Feature Set — Five Evaluation Pillars

### 8.1 Pillar 0 — Functionality

Goal: determine whether a real user can complete the mission and whether application state is correct. Detect blocked journeys, bad navigation, authentication/session failures, incorrect content, player failures, persistence bugs and broken recovery paths.

| **Metric** | **Phase 1 target** |
| --- | --- |
| Golden journey completion | ≥95% on stable test environments after baseline tuning |
| Seeded critical defect recall | ≥90% |
| High-severity false positive rate | <10% |
| Reproduction success | ≥85% for reproducible P0/P1 candidates |
| UI-change resilience | ≥80% of harmless layout/text/DOM changes require no mission edit |

### 8.2 Pillar 1 — CRO

Goal: identify potential conversion friction without inventing causal impact. The evaluator inspects step count, competing actions, value clarity, pricing comprehension, authentication timing, error recovery, trust signals and cognitive load. CRO findings are hypotheses unless supported by analytics/experiment data.

- Classify as opportunity/risk, not defect, unless functionality is actually broken.

- Every recommendation includes affected funnel step, observed evidence, hypothesis and proposed experiment.

- Track accepted recommendations and expert agreement to measure usefulness.

### 8.3 Pillar 2 — SEO + AEO

Goal: verify discoverability and machine interpretability using HTTP/HTML/DOM evidence, not screenshots alone. Evaluate status/indexability, robots directives, canonical, metadata, server-rendered content, hydration parity, structured data, internal links, semantic headings, media metadata and answer extractability.

- Fetch important URLs both as normal browser navigation and raw HTTP where possible.

- Capture initial HTML and hydrated DOM and compare important content presence.

- Validate JSON-LD/schema syntax and required/recommended properties using deterministic rules.

- Keep “AEO” findings evidence-oriented: entity clarity, concise answerability, semantic structure and content availability; do not claim certification by specific answer engines.

### 8.4 Pillar 3 — UX/UI + Accessibility

Goal: combine deterministic accessibility checks with AI visual judgment. Detect clipping, overlaps, broken responsive layouts, poor hierarchy, inconsistent components, missing/weak focus states, RTL problems, unclear states and accessibility barriers. Objective rule violations and subjective design recommendations must be labeled separately.

### 8.5 Pillar 4 — Performance + Video QoE

Goal: measure real browser performance and playback quality while correlating metrics with visible user experience. Collect LCP, INP, CLS, TTFB, long tasks/resource failures where available, plus video startup time, stalls, stall duration/ratio, bitrate/resolution changes, dropped frames, player errors and abandonment state. Network profile metadata is attached to every result.

## 9. Execution Prompt System

Prompts are versioned product assets. The orchestrator injects mission, current state, evidence references, allowed actions and budgets into a stable prompt template. Prompt versions are stored with every run/finding.

### 9.1 Master Journey Agent Prompt

```text
ROLE
You are an autonomous product-quality agent operating a web application as a real user.

OBJECTIVE
Complete the supplied user mission while observing the experience for meaningful failures and friction.

OPERATING RULES
- Navigate from visible/semantic user-observable state; do not rely on durable CSS/XPath selectors.
- Before each action, identify the current state and the next legitimate user action.
- After each action, verify whether the intended state change actually happened.
- Recover from unexpected states only when a reasonable user could recover.
- Do not claim measurements that are available from telemetry; reference telemetry instead.
- Do not report a defect without observable evidence.
- Distinguish confirmed defect, probable issue, optimization opportunity and subjective observation.
- Respect the allowed-action policy and execution budget.
- Stop on mission success, irrecoverable block, policy stop or budget exhaustion.

OUTPUT
Return the requested structured decision/action object only.
```

### 9.2 Edge-Case Generator Prompt

```text
Generate realistic variations of this mission that are most likely to expose product failures. Rank by business impact × probability × state-transition complexity × historical risk. Prefer plausible user behavior. Do not generate destructive or arbitrary chaos. Return only variations that fit the supplied exploration budget.
```

### 9.3 Finding Verifier Prompt

```text
Challenge the candidate finding. Determine whether the evidence actually proves the claim, identify alternative explanations, and decide whether replay is necessary. Return one status: CONFIRMED, PROBABLE, UNCONFIRMED or REJECTED. Never increase severity without evidence.
```

## 10. Execution Modes

| **Mode** | **Purpose** |
| --- | --- |
| Golden Journey | Run critical predefined missions repeatedly across releases/environments. |
| Exploratory Mission | Given a broad goal and budget, autonomously explore plausible paths and edge cases. |
| Regression Compare | Run same mission against baseline and candidate build; highlight changed behavior/metrics/findings. |
| Pillar Audit | Focus execution on one pillar, e.g., crawl/render audit or checkout CRO review. |
| Network Matrix | Repeat selected missions under multiple network and/or ISP egress profiles. |
| Release Gate | Run a bounded critical suite and produce deterministic pass/warn/block recommendations based on configured policies. |

## 11. Core Data Model

```text
Project
 ├─ Environment / Release
 ├─ Persona
 ├─ Mission
 │   └─ MissionVersion
 ├─ NetworkProfile
 ├─ Run
 │   ├─ Step[]
 │   ├─ Observation[]
 │   ├─ Action[]
 │   ├─ Metric[]
 │   └─ Artifact[]
 ├─ CandidateFinding[]
 └─ Finding
     ├─ Evidence[]
     ├─ Replay[]
     ├─ SimilarFinding links
     └─ Baseline/Regression relation
```

### 11.1 Finding Schema

```text
finding_id
title
pillar
classification: defect | regression | risk | opportunity | observation
severity: P0 | P1 | P2 | P3 | info
confidence
mission_id / run_id / step_id
release / URL / browser / viewport
network_profile / egress_profile
expected_behavior
observed_behavior
business_impact
reproduction_steps
reproducibility
evidence_refs[]
telemetry_refs[]
likely_owner
recommendation
verifier_status
model_provider / model / prompt_version
created_at
```

## 12. Safety and Policy Engine

The AI never receives unrestricted authority. The orchestrator validates every action against a deterministic policy before execution.

| **Risk** | **Default Phase 1 policy** |
| --- | --- |
| Real payments | Blocked unless a specific sandbox/test payment profile is configured. |
| Account deletion / destructive changes | Blocked. |
| Publishing/uploading public content | Blocked by default; enable only in a dedicated test environment. |
| OTP / credentials | Use seeded test accounts/secrets from local secret storage; never put secrets in finding text. |
| External navigation | Allow-listed domains only. |
| Action runaway | Per-mission maximum actions, wall-clock timeout and AI-call budget. |
| Sensitive evidence | Redact configured tokens/PII before long-term artifact storage. |

## 13. Efficiency Strategy

Subscription usage is finite, so Phase 1 must minimize unnecessary AI turns. The engine should use deterministic logic whenever AI adds no value.

- Send a new screenshot to the AI only after a meaningful visual/semantic state change or when the agent explicitly requests one.

- Use perceptual hashes/SSIM and DOM/accessibility diffs to suppress unchanged observations.

- Crop high-resolution screenshots to relevant regions when full-frame detail is unnecessary.

- Run cheap deterministic checks (axe, schema parsing, CWV collection, HTTP validation) locally before asking AI to interpret them.

- Batch evaluator work after the journey instead of invoking five models after every action.

- Cache stable page facts within a run and store concise state summaries rather than replaying full history.

- Use a stronger model only for ambiguous planning/verifier tasks; allow a provider router to use a cheaper/faster subscribed model when available.

## 14. Minimum Product Console

| **Screen** | **Must provide** |
| --- | --- |
| Projects | Base URLs, environments, allow-listed domains, credentials/profile references. |
| Missions | Natural-language goal, personas, success criteria, constraints, versions. |
| Run Builder | Browser/viewport, release URL, network profile, egress/ISP route, provider, mode and budgets. |
| Live Run | Current screenshot, current goal/state, last action, network status, timeline and stop button. |
| Findings | Severity, classification, pillar, confidence, replay status, evidence, owner/status. |
| Comparison | Baseline vs candidate findings and metric deltas. |
| Network Profiles | Create/validate impairment profiles and proxy/VPN routes. |
| Settings | AI worker status/login health, browser availability, storage and safety policy. |

## 15. Suggested Repository Structure

```text
product-excellence/
  apps/
    api/                  # FastAPI
    console/              # React/Next.js
  engine/
    orchestrator/
    missions/
    browser/              # Playwright adapters
    ai/                   # CodexWorker, ClaudeWorker, Router
    observation/          # screenshot/DOM/a11y state compiler
    network/              # netem + proxy/VPN adapters
    collectors/           # HTTP, CWV, console, player QoE
    evaluators/
      functionality/
      cro/
      seo_aeo/
      ux_ui/
      performance/
    verifier/
    replay/
    dedup/
    policy/
    evidence/
  prompts/
    journey/
    edge_cases/
    evaluators/
    verifier/
  migrations/
  tests/
    unit/
    integration/
    benchmark/
  profiles/
    network/
    personas/
  docs/
```

## 16. Phase 1 Development Plan

Build vertically. Each milestone must leave a usable end-to-end slice; avoid building all subsystems separately before the first autonomous run works.

| **Milestone** | **Deliverable** | **Exit criterion** |
| --- | --- | --- |
| M0 — Harness | Repo, FastAPI, DB, Playwright runner, run/artifact model, local UI shell. | Manual mission can launch browser and store trace/screenshots. |
| M1 — AI Loop | Codex/Claude worker adapter, observation compiler, action schema, policy engine. | AI completes 3 simple web missions without human action. |
| M2 — Evidence | DOM/a11y/HTTP/console/CWV collectors, run timeline, evidence viewer. | Every action and failure has synchronized evidence. |
| M3 — Network | netem profiles + optional proxy/VPN route adapter + profile verification. | Same mission reproducibly runs under ≥5 network profiles and records active route/profile. |
| M4 — Five Pillars | All evaluators, standardized finding schema, confidence/classification. | Single run produces evidence-backed outputs across relevant pillars. |
| M5 — Verify & Replay | Critic, automatic replay, deduplication and baseline comparison. | Known seeded defects are reproduced and duplicate findings collapse correctly. |
| M6 — Product Console | Mission builder, run matrix, findings, comparison, settings. | Non-engineer can configure and review a complete run. |
| M7 — Benchmark | Seeded defects + UI mutation benchmark + cost/usage measurement. | Acceptance gates met or measured gaps documented before Phase 2. |

## 17. Phase 1 Acceptance Criteria

| **Category** | **Gate** |
| --- | --- |
| Autonomy | ≥95% completion across stable golden journeys after tuning. |
| Defect detection | ≥90% recall on seeded P0/P1 benchmark. |
| Precision | <10% false positives among high-severity reported defects. |
| Reproducibility | ≥85% replay success for deterministic P0/P1 defects. |
| Self-healing | ≥80% of harmless UI text/layout/DOM mutations do not require mission editing. |
| Evidence | 100% of P0/P1 findings include screenshot/trace plus relevant deterministic evidence. |
| Network | At least five impairment profiles reproducible; true ISP route is explicitly distinguished when a real egress is configured. |
| Pillars | All five evaluators operational; objective vs subjective claims clearly separated. |
| Safety | Zero unauthorized destructive/financial actions in benchmark runs. |
| Usability | A product/QA user can create, execute and review a mission without writing browser automation code. |
| Economics | Record subscription usage proxy, AI turns, run duration and human review minutes per journey to establish baseline. |

## 18. Benchmark Design

The benchmark should prove the architecture rather than merely demonstrate it. Select 5–10 business-critical journeys and deliberately introduce known failures and harmless UI changes.

- Seed functional defects: blocked CTA, stale auth state, failed playback initiation, bad recovery route.

- Seed visual defects: clipped text, hidden CTA, overlap, broken responsive layout.

- Seed SEO defects: noindex, wrong canonical, missing SSR content, invalid structured data.

- Seed performance/QoE defects: slow endpoint, artificial long task, player startup delay, network stalls.

- Apply harmless mutations: rename CSS classes/test IDs, reorder DOM wrappers, change button position, minor copy changes.

- Compare valid-defect recall, false positives, mission maintenance effort, run reliability and review time against the existing process.

## 19. Device Expansion Roadmap

After Phase 1, each new phase introduces one device family while preserving the mission/evidence/evaluator layers. Device-specific work is isolated primarily to action adapters, observation/capture, telemetry collectors and environment provisioning.

| **Phase** | **New device family** | **Primary additions** |
| --- | --- | --- |
| Phase 1 | Web | Full product engine; browser runtime; network/ISP layer; all five pillars. |
| Phase 2 | Android Mobile | ADB/Appium/UIAutomator action adapter, screen capture, Android performance/network telemetry. |
| Phase 3 | iOS Mobile | XCUITest/Appium adapter, macOS runner requirement, iOS capture/telemetry. |
| Phase 4 | Android TV | Remote/D-pad semantics, Android TV device/emulator, TV focus/navigation evaluator. |
| Phase 5 | Samsung Tizen TV | Physical/remote Tizen target, network/remote control, capture strategy and TV-specific telemetry. |
| Phase 6 | LG webOS TV | Physical/remote webOS target, control/capture adapter and TV-specific telemetry. |

> **Phase rule — **Do not move to the next device family until the previous phase meets its benchmark. The intelligence/evaluator stack should not be rewritten for each platform; only platform adapters and evidence collectors should expand.

## 20. Decisions to Lock Before Coding

1. Use mission definitions as the durable test contract; never store brittle selectors in mission files.

2. Use Playwright for actuation/telemetry even though the product is intended to move beyond authored Playwright E2E scripts.

3. Keep AIWorker behind one provider-independent interface. Start with authenticated Codex CLI and Claude Code sessions; do not automate chat websites.

4. Use PostgreSQL as soon as multiple runs/history are needed; store large evidence outside the DB.

5. Use Linux as the reference runtime for network shaping. A Linux VPS is the easiest clean deployment for Phase 1.

6. Separate synthetic network profiles from real ISP routing in both configuration and reporting.

7. Keep the AI out of deterministic measurements and safety decisions.

8. Require verification/replay for high-severity findings before release-blocking status.

9. Version prompts, mission definitions, evaluator rules and network profiles just like code.

10. Measure false positives and human review cost from day one; an impressive agent that creates noise is not a successful QA system.

## 21. Recommended Phase 1 Deployment

| **Option** | **Recommendation** |
| --- | --- |
| Developer laptop | Best for development. macOS is fine for browser/AI work, but Linux is preferable for native tc/netem network shaping; use a small Linux VM/container when necessary. |
| Single Linux VPS | Best reference deployment. Runs API, console, PostgreSQL, Playwright browser, AI CLI worker, netem and optional VPN/proxy clients on one host. GUI access is optional because Playwright can run headed through a virtual display when visual debugging is needed. |
| Minimum practical resources | 8 CPU cores, 16 GB RAM, 50+ GB SSD. 32 GB RAM is preferable for concurrent browsers, traces and local tooling. No GPU is required because model inference is remote through the subscribed AI client. |

## 22. Phase 1 Definition of Done

Phase 1 is complete when a product or QA user can open the local console, describe/select a web mission, choose a browser/viewport/persona/network or real egress profile, run it autonomously using a logged-in Codex or Claude subscription, and receive a deduplicated set of verified findings across the five pillars with synchronized screenshots/telemetry/reproduction evidence and a baseline comparison — all on one laptop or one VPS and without authoring a selector-based E2E script.

## 23. Current Technical References

These references validate the external capabilities assumed by this design. They should be rechecked when implementation begins because product/CLI capabilities and subscription limits can change.

- **OpenAI — Using Codex with a ChatGPT plan: **<https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan>

- **OpenAI — ChatGPT Work and Codex usage/sign-in context: **<https://help.openai.com/en/articles/20001275/>

- **Playwright — browser automation for tests/scripts/AI agents: **<https://playwright.dev/>

- **Playwright — browser/CDP connection: **<https://playwright.dev/docs/api/class-browsertype>

- **Linux tc/netem — network emulation: **<https://www.man7.org/linux/man-pages/man8/netem.8.html>

> **Recommended implementation stance — **Build Phase 1 as an internal engineering product, not a SaaS. Prove autonomous journey reliability, finding precision, UI-change resilience, network reproducibility and maintenance reduction first. Only after those metrics are strong should device expansion and API/commercial scaling begin.
