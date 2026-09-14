# Stateful Product QA for Consumer Streaming Apps: Discovering Defects at the Intersection of Identity, Entitlement, Connectivity, Persistence and Navigation

**Research date:** 2026-09-14. **Platform baseline:** Product Excellence v1.5.1. **Prior report:** `extending-product-excellence-advanced-android-failure-discovery.md` (2026-09-14). This report is Output A; the companion `STATEFUL_PRODUCT_QA_CONTEXT.md` (Output B) follows.

## TL;DR
- **Product Excellence should build a "stateful business-journey" capability that treats a defect as a violation of a product rule expressed as `preconditions → event → expected state → allowed delay → prohibited outcomes → evidence source`, enforced by deterministic Python while the AI only interprets the UI and chooses navigation.** The five mandatory families (network-entitlement, download integrity, profile isolation, stale notifications, shared-link auth) are all instances of eight shared failure mechanisms (stale authorization, late async result after identity change, persisted op outliving its session, delayed event referencing obsolete state, intent loss across an intermediate flow, duplicate commands, UI-vs-durable-state divergence, incompatible ownership).
- **The single most important design constraint is evidence provenance: a mock proves only client behavior, never carrier billing or server entitlement; a seed never guarantees backend determinism; and the highest-value QoE/telemetry oracles (Media3 `PlaybackStatsListener`, correlation IDs, entitlement-decision records) require a cooperating test build or authorized backend, not a black-box APK.** Build the intent/binding/recording separation so one scenario can run black-box on staging OR against an instrumented fixture, with the evidence tier recorded honestly.
- **Recommended first vertical slice: Family C (profile/account isolation), because it is fully reproducible with on-device ADB primitives (`adb shell am switch-user`, package-data control) plus a mitmproxy-based controlled backend, needs no carrier integration, and exercises the two hardest mechanisms (in-flight response after identity change; download/notification ownership).** Defer real carrier-billing proof (Family A condition 1) as an authorized-network-only extension.

## Key Findings

1. **The four "free" conditions in Family A are genuinely independent and must be modeled as separate boolean state variables.** (1) Zero-rated transport (carrier does not bill the bytes), (2) free access to otherwise-restricted content (a content-entitlement grant), (3) an unmetered connection (`NET_CAPABILITY_NOT_METERED`, an OS/link property), and (4) a paid subscription (an account attribute) are orthogonal. Android exposes meteredness via `ConnectivityManager` `NetworkCapabilities.hasCapability(NET_CAPABILITY_NOT_METERED)` and, per Android Developers "Add 5G capabilities to your app," the Android-11 `NET_CAPABILITY_TEMPORARILY_NOT_METERED` capability ("A network can't have both NET_CAPABILITY_NOT_METERED and NET_CAPABILITY_TEMPORARILY_NOT_METERED at the same time"), observed through `onCapabilitiesChanged()` — but this proves only the *device's* view of metering, never the carrier's billing decision or the backend's entitlement grant. Zero-rating in real networks is commonly classified by egress IP, or by carrier HTTP header enrichment / SNI/Host inspection (documented in academic measurement studies), which a device-side network label cannot reproduce.

2. **Entitlement staleness during playback is a real, documented class governed by DRM license and streaming-token boundaries, and the correct behavior is a product-policy choice, not a universal.** DRM licenses carry distinct durations: for Widevine/PlayReady/FairPlay, a "rental" key typically lets playback continue to the end after expiry, while a "lease" key requires renewal and will halt mid-stream if not renewed (documented in Apple FairPlay developer forums and ExoPlayer issues). Streaming tokens on HLS/DASH playlist and segment requests expire independently (commonly ~an hour) and are refreshed proactively; a mishandled refresh causes `hlsPlaylistRejected reason=expired` waves. So entitlement is re-evaluated at several boundaries: next playlist/manifest refresh, next segment/CDN request, next license renewal, and next app-initiated authorization call — buffered content can play well past the moment access is lost. Product Excellence must take the expected transition from a configured rule, not assume immediate termination or unlimited continuation.

3. **Resumable-download correctness depends on HTTP validators, and "100%" or file-existence is not proof.** Resumable transfers use `Range`/`Content-Range` with `Accept-Ranges: bytes`; safe resume uses `If-Range` with a **strong** ETag or a Last-Modified date — if the validator matches the server returns `206 Partial Content`, and if the resource changed it returns `200 OK` with the full body (per MDN and the HTTP spec). A documented real failure (aria2-next issue #43): some CDNs only honor `If-Range` with an HTTP-date, so an ETag `If-Range` yields a `200` on a ranged request and the client aborts with `CANNOT_RESUME`. This means download integrity oracles must verify final byte identity (hash) and validator handling, not progress UI. On Android, background downloads under WorkManager retry with `BackoffPolicy` LINEAR/EXPONENTIAL — per Android Developers "Define work requests," the default policy is EXPONENTIAL with a **30-second** delay, and the minimum allowed backoff is 10 seconds (`MIN_BACKOFF_MILLIS`; `MAX_BACKOFF_MILLIS` = 5 hours) — and WorkManager exposes `StopReason` (e.g., `STOP_REASON_CONSTRAINT_CONNECTIVITY`) when a connectivity constraint is lost mid-run, which is exactly the weak-connectivity pause/resume race to test.

4. **Notification and shared-link failures are rooted in PendingIntent identity semantics and OAuth state preservation.** Android `PendingIntent` identity comparison **ignores extras**; two notifications built with the same requestCode and `FLAG_UPDATE_CURRENT` can resolve to the same stale destination unless a unique requestCode or distinct intent data is used (documented Android behavior; Android 12+ also requires `FLAG_IMMUTABLE`/`FLAG_MUTABLE`). For shared-link→auth, the OAuth/OIDC `state` parameter carries destination context across the redirect, and PKCE-based mobile flows must **persist verifier/state to storage and make the deep-link handler idempotent** because the app can be killed and cold-started between browser and callback, and links can be delivered twice (documented in mobile OAuth security guides). Deep links are testable deterministically via `adb shell am start -W -a android.intent.action.VIEW -d "<URI>" <pkg>`.

5. **App in-app "profiles" are NOT Android OS users, and this distinction drives Family C test design.** OS users (`adb shell pm create-user`, switched with `adb shell am switch-user <id>`, listed via `adb shell pm list users`, each with isolated storage the AOSP "Test multiple users" doc reaches at the exact path form `adb shell ls /data/user/10/com.bar.foo/`) are sandboxed accounts; a streaming app's in-app viewer profiles under one login live entirely inside one app's data directory and are invisible to `pm`/`am`. Therefore profile switching must be driven through the app UI (AI-interpreted), while account/OS-user switching can be driven deterministically by ADB. AOSP notes a real evidence-collection constraint: "adb (or more accurately the adbd daemon) always runs as the system user (user ID = 0) regardless of which user is current. Therefore device paths that are user dependent (such as /sdcard/) always resolve as the system user" — the documented workaround is to "install and use an existing content provider that reads and writes files to the user-specific /sdcard path."

6. **The highest-fidelity playback QoE evidence requires an instrumented build.** Media3's `PlaybackStatsListener` (an `AnalyticsListener`) computes `PlaybackStats` with `totalRebufferCount`, `totalPlayTimeMs`/`getTotalPlayTimeMs()`, `getTotalWaitTimeMs()` (JOINING_FOREGROUND+BUFFERING+SEEKING), `getMeanTimeBetweenRebuffers()`, join-time via `getTotalJoinTimeMs()`/`totalValidJoinTimeMs`, per-state durations via `getPlaybackStateDurationMs`, and `fatalErrorHistory`/`nonFatalErrorHistory`; callbacks `onPlaybackStateChanged`, `onDroppedVideoFrames(EventTime, int, long)`, and `onPlayerError(EventTime, PlaybackException)` expose buffering and errors live. **All of this is in-process and requires the app to wire the listener (`exoPlayer.addAnalyticsListener(...)`) before media load (`STATE_IDLE`) — it is not observable black-box.** This confirms the prior report's provenance hierarchy: instrumented > OS-observable (`dumpsys`) > external (screenshot/MP4) > heuristic (AI).

## Details

### Gap ledger (existing coverage → missing business behavior → new research question)

| Existing coverage (prior report) | Missing business behavior (this report) | New research question |
|---|---|---|
| Bounded fault injection: `adb emu network delay/speed`, Doze, `am kill`, config injection | Faults tied to **business-state transitions** (entitlement re-eval, identity switch, ownership) not just transport degradation | How to inject an *entitlement/eligibility change* and prove the app re-evaluated it at the correct boundary? |
| Media QoE oracles (Media3 PlaybackStatsListener, dumpsys) | QoE tied to an **access-policy transition mid-playback** (continue vs interrupt vs message) | What is the product rule for playback continuity when the grant is lost, and which telemetry proves it? |
| Scenario + evidence/replay contract recording requested-vs-verified faults | Contract must also record **identity, entitlement decision, destination-before/after, ownership, correlation IDs, ordering** | Smallest mission-contract extension to express business state, events, ordering, invariants? |
| Network chaos on macOS (no packet loss, jitter-free; mitmproxy for app-level; QUIC bypasses TCP proxy) | **Application-level policy simulation** (eligibility responses, stale/absent entitlement service, response ordering) | How to deterministically order responses/events across two identities and prove no cross-contamination? |
| Reproducibility layers L1 actions / L2 faults / L3 env; backend NOT guaranteed | **Bounded eventual consistency** for async ops that outlive a screen/session | How to assert "eventually correct within budget" AND "forbidden state never appears in window"? |
| APK bytes local; untrusted-content separation; release gate = reproduced P0/P1 | **Business-policy ambiguity** must not be mislabeled a defect | How to distinguish confirmed defect from unresolved requirement / policy choice? |

Overlap assessment note: the previous report's full content was **not** fetched from the repository during this research; the ledger above uses the supplied scope summary. Where I rely on the prior report's claims (e.g., macOS has no netem, QUIC bypasses a TCP proxy, Widevine L1 renders black), I treat them as inherited inputs and flag any that materially affect this design.

**Inherited-premise correction:** the prior report states media QoE is best obtained via Media3 `PlaybackStatsListener` and lists it above OS-observable sources. That ranking is correct, but the operative constraint for *this* work is stronger and must be stated plainly: `PlaybackStatsListener` is an **in-process API that does not exist for a black-box APK** — it requires a cooperating debug/test build that wires the listener before `STATE_IDLE`. Any Family-A/B scenario that claims rebuffer counts or join time as evidence is therefore an *instrumented-tier* scenario; the black-box binding of the same intent can only produce screenshot/MP4/`dumpsys media_session` evidence and must be recorded at that lower tier.

### Family A — Network-dependent entitlement during playback

**Failure class:** an authorization decision (network eligibility → content grant) becomes stale mid-journey; buffered content masks the transition; client and server entitlement state diverge.

**Mechanism research.** An "eligible network" can be identified by egress IP allow-list, carrier operator integration, HTTP header enrichment (carrier gateways inject subscriber/network identifiers; documented in SIGCOMM/measurement literature), TLS SNI/Host classification (shown abusable for "free-riding" in the MobileAtlas study), account attributes, or session claims. Because classification is server/carrier-side, **switching an emulator's network label or toggling `NET_CAPABILITY_NOT_METERED` does not reproduce a carrier billing or entitlement transition** — it only changes the device's local view. Entitlement is re-evaluated at: next manifest/playlist refresh, next segment/CDN request, DRM license acquisition/renewal (lease vs rental duration), and explicit authorization calls. Buffering allows continuation after access changes; the four independent conditions (zero-rated transport, free content grant, unmetered link, paid subscription) must each be a separate variable so the oracle does not conflate them.

**How to test the transition, and what each proves:**
- **Controlled backend eligibility responses (mitmproxy addon or controlled backend):** proves the *client's* reaction to an eligibility flip (message, interrupt, recover). Does **not** prove real carrier billing. HTTPS pinning defeats a proxy unless the build is unpinned or trusts a user CA; QUIC/HTTP3 bypasses a TCP proxy (inherited).
- **Authorized real network routes (eligible SIM/APN vs ineligible):** the only thing that proves a real carrier/entitlement transition. Requires authorized infrastructure; out of baseline scope.
- **Test fixtures / documented test hooks:** a backend "set eligibility=false for session X" hook proves policy wiring end-to-end within staging.
- **Instrumented observation:** Media3 telemetry proves whether playback actually continued/stalled and for how long, when black-box screenshots are ambiguous.

**Expected result comes from product policy.** Configure per-content and per-condition rules; do not assume immediate termination or unlimited continuation.

### Family B — Download integrity under weak connectivity and repeated pause/resume

**Failure class:** a persisted operation (download) outlives its screen; duplicate workers/retry races create conflicting work; UI progress diverges from durable state; terminal state must be truthful.

**Mechanism research.** Resume correctness hinges on `Range`/`If-Range`/`ETag` (strong validator) with `206` vs `200` fallback; segmented media (HLS `.ts`/DASH `.m4s`, CMAF) means "partially downloaded" is a set of segments plus a manifest, not one file. WorkManager retries with exponential backoff (default 30s, floor 10s) and surfaces `StopReason` (`STOP_REASON_CONSTRAINT_CONNECTIVITY`) when connectivity is lost — the mechanism behind pause/resume-under-weak-signal. Offline licenses have dual expiry (storage duration vs playback duration); a documented ExoPlayer defect (google/ExoPlayer issue #2622) shows moving device time backward extends offline license life: with a license period set to 300 sec, "if the device time is changed to 5 minutes ago, LicenseDurationRemaining increases and the playback continues even though the time to expire has passed... mediadrm have not detected a change in device time" — i.e., **changing device time does not reliably advance or enforce server-anchored expiry**. Distinguish *pausing the download* from *pausing the preview/player* — separate variants.

**Evidence:** final content hash equals expected identity; completeness across all segments; correct ownership (which account/profile the download belongs to); playback validity (seek, subtitles, audio tracks); no lost/duplicated work beyond allowed retries; truthful terminal state (not "100%" while bytes are missing).

### Family C — Account and profile isolation on a shared device

**Failure class:** an async result arrives after identity changes; the same content appears under incompatible ownership; UI/cache retains previous identity's data.

**Mechanism research.** Account switching (OS user or app login change) vs profile switching (in-app, one account) are different layers — the former is ADB-drivable, the latter UI-only. Separate the rules for: stored bytes, list visibility, ownership, and authorization (do **not** assume physically separate media files per profile). Critical races: an in-flight response from identity A populating identity B's screen (a documented anti-pattern — "old account's response must not populate the new account's screen"); a background download completing after a switch (ownership must follow the initiating identity, not the foreground one); notifications created under a previous identity. Transition to validate: `A/A1 → A2 → B → A/A1`, specifying at each step what persists, disappears, refreshes, or stays inaccessible.

### Family D — Delayed notifications and stale destinations

**Failure class:** a delayed event refers to obsolete state; opening the app is conflated with reaching the correct destination.

**Mechanism research.** `PendingIntent` identity ignores extras, so a replaced/updated notification can carry a stale destination unless requestCode/data differ; `FLAG_ONE_SHOT` prevents repeated triggering; back-stack behavior determines where "back" goes. A notification opened much later may reference a download that completed/cancelled/failed/was deleted, content removed or expired, a changed account/profile, a logged-out session, or a restarted process. Verify: correct content/operation identity, correct active account/profile, current state (not stale notification text), auth/entitlement checks before protected content, appropriate fallback when the destination no longer exists, and idempotent/consistent behavior when an old notification is opened repeatedly.

### Family E — Shared content link → authentication → original destination

**Failure class:** an intermediate flow (auth) loses the original user intent; duplicate link delivery; wrong-account state.

**Mechanism research.** Destination identity is preserved across auth via the OAuth `state` parameter (also CSRF protection) and/or persisted app state; PKCE flows must persist verifier+state and make the deep-link handler idempotent because process death during auth is common and links can arrive twice. Distinguish: (a) post-authentication destination restoration (baseline), (b) link handling when the app is installed (baseline), (c) post-install deferred deep linking (optional extension — on Android typically via Play Install Referrer, since the install boundary strips intent data). The correct destination (details, playback, purchase, or explanation) is a product-rule decision; content removal, regional restriction, or changed entitlement can redirect it.

### Shared failure mechanisms → techniques

For each of the eight mechanisms, the applicable technique, a concrete example, required access, implementation, and limits:

- **Extended state machines with guards and business variables** — model the journey with variables `{account, profile, subscription, zeroRated, contentGrant, metered, downloadState, sessionValid, destinationId}` and guarded transitions. Example (A): guard `contentGrant==true` on `PLAYING`; event `eligibilityLost` transitions to a policy-defined state. Access: rule table. Implementation: a Python transition table in `engine/contracts.py`. Limit: only as correct as the encoded rules.
- **Model-based & stateful property-based testing (Hypothesis `RuleBasedStateMachine`)** — generate operation sequences (switch profile, start download, lose network, open notification) and assert `@invariant`s (e.g., "visible list belongs to current profile"). Example (C): random `A1/A2/B` switch sequences must never show A1's history under B. Access: a model of expected state; the app or a controlled backend. Implementation: `rule`/`precondition`/`invariant`; Hypothesis shrinks a failing sequence to a minimal reproducer. Limit: needs a reliable model oracle; backend nondeterminism can cause flakiness — pair with bounded polling.
- **Temporal assertions & bounded eventual consistency** — assert "converges to X within budget T" AND, for forbidden states, observe the *entire* window (proving a leaked record never appears requires watching the whole window, not stopping at first empty read). Example (B): download reaches truthful terminal state within N seconds after connectivity restoration. Access: state readouts (UI, API, or entity version/ETag). Implementation: bounded polling with terminal-failure surfacing, not fixed sleeps. Limit: budgets are per-rule configured tolerances, never universal.
- **Race-condition testing via controlled response/event ordering (mitmproxy)** — hold response A, switch identity, release A, assert it does not populate B. Example (C): in-flight response after switch. Access: proxy or controlled backend; unpinned/CA-trusting build for HTTPS. Implementation: mitmproxy addon that gates flows on a milestone signal. Limit: cannot order QUIC/HTTP3 over a TCP proxy.
- **Metamorphic testing** — when exact expected content is unknown, assert relations: filtering a list returns a subset; the same content under profile A2 must differ from A1 by exactly the profile-scoped delta. Example (C/E). Access: two related executions. Implementation: compare outputs of source vs follow-up runs. Limit: no violation ≠ correctness.
- **Differential testing across identities/policy configs** — run identical journeys under free vs paid, eligible vs ineligible; divergences flag policy bugs. Example (A). Access: multiple fixtures. Implementation: cross-reference oracle. Limit: both implementations could share a bug.
- **Contract testing for entitlement/download/routing boundaries (Pact-style provider states)** — pin the shape of entitlement, download-URL, and routing responses with `given(...)` provider states. Example: "given session is ineligible, entitlement endpoint returns grant=false." Access: authorized backend contract. Implementation: consumer-declared expectations verified against provider; supports negative/edge cases (auth failures, empty sets). Limit: contract fidelity ≠ production behavior; do not treat as full integration.
- **Risk-based interaction coverage** — prioritize the state-pair interactions with highest business risk (identity×download ownership, entitlement×buffering) rather than exhaustive device/network permutations.

Do not introduce formal methods or specialized frameworks merely for academic interest; the above are all lightweight wrappers over the existing Python platform.

### Oracle and requirements-discovery strategy

Classify every expected behavior as **Confirmed** (from spec/acceptance criteria, operator rule table, authorized backend contract, or a reviewed reference), **Inferred** (AI hypothesis or derived from existing tests, requiring confirmation), or **Unknown/Contradictory**. When a rule is unknown, the platform emits a **requirements question** or **suspicious inconsistency**, never a confirmed defect — a business-policy choice must not be labeled a P0/P1. Rules are expressed as `preconditions → event → expected state → allowed delay → prohibited outcomes → evidence source`.

Deterministic oracles by family: C and D have deterministic oracles (identity-scoped data comparison; destination-ID match; auth-before-protected-content check) because expected state is knowable from fixtures. A and B have *partially* deterministic oracles (validator/hash for downloads; state-transition for playback) but the *continuity policy* (continue vs interrupt) must be configured; where continuity is unspecified the AI proposes a hypothesis and the critic reviews it as unconfirmed. Ordering-sensitive assertions to encode: old account's response must not populate the new account's screen; a cancelled download must not become completed from a stale callback; authentication must preserve the selected content identity; entitlement must be checked at the product-specified boundary. Use configured tolerances only.

### Test data and controllable environments

**Minimum fixture catalog:** accounts with distinct subscription states (none/free/paid/expired); ≥2 profiles per account (incl. one restricted/child); known distinct search histories per profile; content items tagged public/restricted/removed/expired; small downloadable media with known SHA-256 and expected properties (duration, tracks, subtitles); eligible/ineligible network-policy states (as backend/proxy fixtures); notifications and shared links carrying traceable destination IDs; expiring sessions, download URLs, and offline licenses.

**Five approaches, simulation vs proof:**
1. **Black-box vs staging** — proves real end-to-end behavior of that staging build; cannot control timing/ordering; lowest evidence control, highest realism.
2. **Authorized fixture/setup APIs (via existing HTTPX)** — proves state setup and readback; simulates preconditions deterministically; does not prove production infra.
3. **Controlled backend responses (mitmproxy/controlled backend)** — proves client reaction to specific responses/ordering; **simulates** policy, does not prove the real server's policy.
4. **App instrumentation/test hooks** — proves internal state (playback stats, entitlement decision, ownership) unavailable black-box; must be isolated from production behavior.
5. **Real network/provider verification** — the only proof of carrier billing/zero-rating and real entitlement transitions; authorized infra only.

**Safe time-dependent testing:** prefer short-lived fixtures and server-controlled expiry; use injectable clocks only where the build supports them. Changing device time may not advance server-side expiry or scheduled work (documented Widevine behavior: backward time change extended offline license remaining time; server-anchored TTLs and WorkManager scheduling are unaffected by device clock). Keep all test-only hooks isolated from production code paths.

### Technology decisions (capability → tool/API → access → effort → evidence → limits → decision)

- **Stateful test generation** — Hypothesis `RuleBasedStateMachine` supplies sequence generation + shrinking for journey models. Access: model oracle. Effort: low (pure Python). Evidence: minimal failing sequence. Limits: needs deterministic-ish oracle. **Decision: ADD** (dev/test dependency) for model-based families C/D; justified because no existing module generates and shrinks operation sequences.
- **Android controller for auth/system UI/stable selectors** — ADB + `uiautomator dump` (existing) handles most, but system-UI/notification-shade/cross-app and stable selectors are weak. Access: device. Effort: medium. Evidence: hierarchy/screens. Limits: prior report notes gfx/jank unavailable; sign-in flows stop at credential entry today. **Decision: EXTEND** `engine/android.py` with notification-shade and deep-link (`am start`) primitives and multi-user (`pm`/`am switch-user`) control; **DEFER** adding UiAutomator2/Appium unless stable selectors prove insufficient.
- **Authorized fixture/setup APIs** — existing **HTTPX**. Access: staging setup API + credentials refs. Effort: low. Evidence: setup/readback records. **Decision: REUSE**.
- **Controlled backend / response ordering** — **mitmproxy** (Python, scriptable addons; hot-reload; can gate flows on milestones and rewrite status/body/latency). Access: proxy + unpinned/CA-trusting build. Effort: medium. Evidence: requested-vs-served response log. Limits: pinning/QUIC (inherited). **Decision: WRAP** mitmproxy behind a Python fault/ordering controller.
- **Contract testing** — **Pact-style provider states** for entitlement/download/routing. Access: authorized backend. Effort: medium-high. **Decision: DEFER** to a later phase; start with mitmproxy simulation, adopt Pact only if the backend team can own provider states.
- **Notification/navigation/background-work mechanisms** — `am start` deep links, notification shade via controller, WorkManager `StopReason`/backoff *if the app uses it* (detect first). **Decision: EXTEND** (capability-detected).
- **Download/player telemetry** — Media3 `PlaybackStatsListener`/`AnalyticsListener` **from a test build only**. **Decision: ADD** (requires app cooperation; record as instrumented tier).
- **Rules & scenarios representation** — existing JSON/YAML contracts. **Decision: EXTEND** `engine/contracts.py`.

Do not assume the target app uses Media3, WorkManager, DownloadManager, or a specific nav library — gate implementation-specific techniques behind capability detection or a declared architecture.

### Scenario contract and execution design

Smallest extension to mission contracts adds three separable blocks:
- **Scenario intent** (environment-independent): `business_goal`, `family`, `account_refs`/`profile_refs` (aliases + credential references, never secrets), `product_rule_refs`, `required_capabilities`, ordered `journey` (user actions), `external_events` (eligibility flip, response hold/release, notification post, link delivery), `milestone_triggers` + `ordering_constraints`, `expected_invariants`, `prohibited_outcomes`, `observation_windows`, `cleanup`.
- **Environment bindings**: maps intent to a concrete target — `black_box_staging` OR `instrumented_fixture` OR `controlled_backend` — plus credential references, backend fixture version, proxy config, and the **evidence tier** each binding can produce.
- **Recorded execution**: requested-vs-observed events, ordering/timing, correlation IDs, entitlement decision + policy version, destination before/after auth, ownership, and evidence IDs.

The AI interprets the UI and chooses a navigation path; deterministic code enforces identity/scope, injects events at milestones, evaluates assertions, and records evidence. A single intent binds to black-box or instrumented environments but **the evidence tier is recorded honestly** — a mock binding proves client behavior only.

### Thirty-plus focused scenarios

Format for compact entries: **ID · Title | Risk | Rule(status) | Preconditions/fixtures | Journey | Event | Invariants/Prohibited | Oracle+Evidence | Tools/Access | Feasibility | Gap | Cleanup/Repro limit.** One representative scenario per family is fully expanded first.

#### Family A — fully expanded representative

**A1 · Eligible→ineligible network mid-playback, no subscription.**
- **Business risk:** the app either keeps serving otherwise-restricted content for free after the grant is lost (revenue leak) or terminates abruptly with a wrong/absent message (UX/regression).
- **Product rule (Unknown → operator must confirm):** on `eligibilityLost` during playback with `subscription=none`, expected state = *[policy]* one of {continue-to-buffer-end-then-gate, gate-at-next-segment, immediate-message+pause}; allowed delay = configured tolerance to next segment/manifest boundary; prohibited = indefinite free playback with no re-check.
- **Preconditions/fixtures:** account `subscription=none`; content `restricted` but `contentGrant=true` while on eligible network; controlled backend serving manifest+segments+entitlement.
- **Ordered journey:** launch → open restricted title → start playback on eligible binding → confirm playing → flip eligibility → continue observing to next segment/manifest fetch.
- **Event:** mitmproxy flips the entitlement/eligibility response to `grant=false` at milestone "playing confirmed".
- **Invariants/Prohibited:** entitlement re-checked at ≤ configured boundary; UI message matches policy; **prohibited**: new segment/license requests succeed with grant=false and no user-visible gate.
- **Oracle+Evidence:** deterministic on entitlement-response log (requested-vs-served) + boundary timing; playback continuation proven by Media3 `PlaybackStats` (instrumented) or screenshot/`dumpsys media_session` (black-box tier). Correlation IDs tie segment requests to the decision.
- **Tools/Access:** mitmproxy, controlled backend, optional instrumented build; unpinned/CA-trusting build for HTTPS.
- **Feasibility:** high for client-reaction proof; carrier billing NOT proven.
- **Gap:** current runner is baseline-only networking; needs mitmproxy wrapper + entitlement fixture.
- **Cleanup/Repro limit:** reset fixture; backend timing not guaranteed deterministic — bound with polling.

- **A2** Ineligible→eligible mid-playback (grant appears): free content should unlock only at the policy boundary; prohibited: stale "upgrade" prompt persists after grant. Oracle: entitlement log + UI state. Instrumented/controlled backend. Gap: eligibility flip injection.
- **A3** Rapid repeated toggling eligible⇄ineligible (flapping): no thrash of play/pause; debounced per policy; prohibited: crash/ANR or contradictory messages. Oracle: state-transition trace. Controlled backend. Gap: milestone-ordered multi-flip.
- **A4** Entitlement service unavailable (503/timeout) during re-check: fail per policy (fail-closed vs fail-open is a rule); prohibited: silent fail-open on restricted content. Oracle: response-injection log. mitmproxy. Gap: fault injection tied to re-check boundary.
- **A5** Stale cached grant after token expiry: client keeps a cached grant past TTL; must re-fetch at boundary; prohibited: playback continues on expired token without re-auth. Oracle: token/correlation log. Controlled backend. Gap: TTL fixture + clock note (server-anchored).
- **A6** Unmetered↔metered link change without entitlement change (independence check): playback quality/download policy may adapt but **content grant must not change**; prohibited: conflating meteredness with entitlement. Oracle: differential run (metered vs unmetered, grant held constant). ADB network label + controlled backend. Gap: separate variables in model.
- **A7** Zero-rated transport lost but subscription=paid: playback must continue (paid overrides transport); prohibited: gating a paying user on a metering change. Oracle: differential (paid vs none). Controlled backend. Gap: 4-condition matrix fixtures.
- **A8** DRM lease license expiry mid-stream vs rental: lease halts unless renewed; rental continues to end — assert per configured key type; prohibited: rental halting or lease continuing without renewal. Oracle: license-request log + playback state. Instrumented + controlled license server. Gap: license fixture.

#### Family B — fully expanded representative

**B1 · Weak-connectivity repeated pause/resume reaches truthful terminal state.**
- **Business risk:** download shows "100%/complete" while bytes are missing or corrupt, so offline playback fails later — a trust-destroying, hard-to-reproduce field bug.
- **Product rule (Confirmed for integrity; Inferred for retry budget):** terminal state must equal actual byte state; completed download must play per offline rules; allowed delay = convergence budget after connectivity restored; prohibited = "completed" with hash≠expected or missing segments.
- **Preconditions/fixtures:** small media, known SHA-256, known segment count/tracks; server supporting `Range`/`If-Range`/ETag; download URL with defined validator behavior.
- **Ordered journey:** start download → degrade link (`adb emu network delay/speed`) → pause → resume → repeat pause/resume ≥3× → restore link → wait for terminal state → attempt offline playback.
- **Event:** repeated pause/resume commands under weak signal + one mid-pause connectivity restoration.
- **Invariants/Prohibited:** on resume, client sends `Range` with `If-Range` strong validator; server `206` continues, `200` restarts cleanly; final hash == expected; all segments present; **prohibited**: duplicated bytes, `CANNOT_RESUME` swallowed as success, "100%" with short file.
- **Oracle+Evidence:** deterministic — final SHA-256 vs fixture; segment-completeness manifest check; playback validity (seek/subtitle/audio) via instrumented telemetry or screenshot; HTTP validator log from proxy.
- **Tools/Access:** ADB network shaping (no packet loss on macOS — inherited), mitmproxy to observe/inject validator behavior, filesystem/hash access (may need content provider for secondary users).
- **Feasibility:** high; requires no-reset mode to preserve partial download.
- **Gap:** runner resets package data before missions (conflicts with persistence) — needs no-reset mode; baseline-only networking.
- **Cleanup/Repro limit:** clear partial files after; exact byte-timing of pause is nondeterministic — assert on terminal invariants, not intermediate progress.

- **B2** App restart while download pending: on relaunch, download resumes or reports truthful state; prohibited: orphaned/duplicate worker. Oracle: single-worker check + terminal hash. WorkManager `StopReason`/tag inspection if used. Gap: process-death injection tied to pending op.
- **B3** Duplicate resume commands (double-tap) create retry race: exactly-once effective work; prohibited: two concurrent writers corrupting the file. Oracle: byte integrity + request log. mitmproxy. Gap: rapid duplicate command injection.
- **B4** Expired download URL on resume: client re-mints URL or fails per policy; prohibited: silent stall or corrupt append. Oracle: 403/expired response injection + recovery. mitmproxy. Gap: URL-expiry fixture.
- **B5** Offline license expired when playing a completed download: playback gated/renewed per policy; prohibited: play past expiry (see #2622 device-time caveat). Oracle: license state + playback. Instrumented + license server. Gap: license TTL fixture.
- **B6** Cancel during weak connectivity then restore: cancelled download must NOT become completed from a stale callback; prohibited: resurrected download. Oracle: observe whole window for forbidden "completed". Controlled backend. Gap: stale-callback injection.
- **B7** Account/profile switch while download running: ownership follows initiator (Family C overlap); prohibited: download visible/owned by wrong identity. Oracle: ownership attribution record. ADB switch + backend. Gap: cross-family ownership assertion.
- **B8** CDN honors `If-Range` only with date not ETag (aria2 #43 class): client must fall back to clean restart, not corrupt; prohibited: `200`-on-ranged treated as append. Oracle: validator log + hash. mitmproxy rewriting validator behavior. Gap: validator-manipulation addon.
- **B9** Pause player vs pause download disambiguation: pausing the preview must not pause/cancel the background download and vice versa. Oracle: two independent state machines. UI + WorkManager. Gap: distinct command modeling.

#### Family C — fully expanded representative

**C1 · In-flight response from account A must not populate account B's screen.**
- **Business risk:** a slow response from the previous account renders another user's library/history on the new account — a privacy breach and P0-class isolation failure.
- **Business risk / rule (Confirmed):** data shown must belong to the current active identity; prohibited = any A-owned record appearing under B within the whole observation window.
- **Preconditions/fixtures:** account A with distinct history H_A; account B with distinct history H_B; controlled backend able to hold a response.
- **Ordered journey:** sign in A → trigger a library/history fetch → **hold** that response at proxy → switch to account B (`am switch-user` for OS-user model, or UI logout/login for app-login model) → **release** held A-response → observe B's screen.
- **Event:** held A-response released after identity switch.
- **Invariants/Prohibited:** released A-response is discarded/ignored for B's UI; **prohibited**: any H_A item rendered under B; correlation ID of the response must not match B's session.
- **Oracle+Evidence:** deterministic — compare rendered list against H_B; assert absence of H_A tokens across the full window (not first empty read); request/response correlation IDs; screenshots with safe aliases.
- **Tools/Access:** mitmproxy (hold/release), ADB `am switch-user` or UI login, distinct-history fixtures.
- **Feasibility:** high (the flagship first-slice scenario).
- **Gap:** needs mitmproxy hold/release + identity-scoped evidence fields; sign-in currently stops at credentials (needs authorized sign-in or pre-provisioned OS users/personas).
- **Cleanup/Repro limit:** reset both identities; `/sdcard` for secondary users blocked since Android 9 — use content provider for evidence.

- **C2** Transition chain `A/A1→A2→B→A/A1`: specify per step which state persists/refreshes/disappears; prohibited: A1 history surviving into A2 or B. Oracle: per-step identity-scoped comparison. ADB+UI. Gap: multi-step scripted transitions.
- **C3** Background download completes after switch: ownership = initiator (A1), visible to A1 only; prohibited: appears under B. Oracle: ownership record + visibility. Backend. Gap: ownership attribution.
- **C4** Search history isolation local vs server-owned: local cache must be identity-scoped and server history must reload per identity; prohibited: cached H_A leaking to A2. Oracle: differential local vs server. Backend. Gap: cache-scope inspection.
- **C5** Notification created under A opened after switch to B: must gate/reroute per identity (Family D overlap); prohibited: opening A's content under B. Oracle: active-identity check at open. `am start` + backend. Gap: cross-identity notification.
- **C6** Logout/session-expiry mid-session: protected screens must gate; prohibited: stale authorized view after logout. Oracle: auth-gate check. Backend token invalidation. Gap: session-expiry injection.
- **C7** Restricted/child profile content hiding: age-restricted titles absent from child profile lists and playback-blocked; prohibited: restricted content reachable. Oracle: list diff + playback attempt. UI profile switch. Gap: restricted-profile fixture.
- **C8** Profile deletion while its download exists: bytes/visibility/ownership handled per policy; prohibited: orphaned playable content owned by nobody. Oracle: post-deletion state. UI+backend. Gap: deletion flow.
- **C9** Concurrent activity on another device changes this device's expected state (e.g., server history update): only where it changes this device — assert bounded eventual convergence; prohibited: permanent divergence. Oracle: bounded polling to convergence. Backend. Gap: multi-device fixture (optional).

#### Family D — fully expanded representative

**D1 · Notification opened long after the download it references was deleted.**
- **Business risk:** tapping a stale "download complete" notification crashes, opens a dead screen, or shows content the user no longer has — eroding trust and possibly exposing removed content.
- **Product rule (Confirmed for state-freshness; fallback is a policy):** on open, the app must reflect *current* state, not the notification's stale text; if the destination no longer exists, show a defined fallback (e.g., library with an explanation); prohibited = crash, blank screen, or "play" of a deleted item.
- **Preconditions/fixtures:** a completed download with a notification carrying destination ID D; then delete the download.
- **Ordered journey:** produce download-complete notification → delete the download (or expire content) → open the notification much later.
- **Event:** notification tap resolves a PendingIntent to destination D that no longer exists.
- **Invariants/Prohibited:** destination-ID resolution validates existence; auth/entitlement checked before protected content; correct fallback rendered; **prohibited**: stale text acted on, crash, or reaching a protected screen without a check.
- **Oracle+Evidence:** deterministic — destination existence check + rendered fallback matches policy; `am start` launch status; screenshots; logcat for crash/ANR.
- **Tools/Access:** `am start` deep-link/notification injection, backend to delete/expire, notification-shade control.
- **Feasibility:** high.
- **Gap:** needs notification-shade + `am start` primitives and destination-ID evidence field.
- **Cleanup/Repro limit:** clear notifications; PendingIntent extras-ignored identity means test must vary requestCode/data to avoid false reuse.

- **D2** Notification opened after cancellation/failure: reflects cancelled/failed, not "complete"; prohibited: stale success text. Oracle: state-vs-text. `am start`. Gap: same primitives.
- **D3** Newer notification replaces older (same requestCode, `FLAG_UPDATE_CURRENT`): opening resolves to the *current* target, not stale extras; prohibited: stale-extras destination. Oracle: destination-ID match. Gap: PendingIntent-identity awareness.
- **D4** Notification opened after account/profile change: routes to correct identity or gates; prohibited: wrong-identity content. Oracle: active-identity check. Gap: cross with C.
- **D5** Notification opened after logout/session expiry: auth gate before protected content; prohibited: bypass. Oracle: auth-gate. Gap: session state.
- **D6** Notification opened after app process death/restart: cold-start resolves destination correctly; prohibited: lost intent → home screen. Oracle: destination reached vs home. `am kill` + `am start`. Gap: process-death sequencing.
- **D7** Same old notification opened repeatedly: idempotent, consistent current-state each time; prohibited: duplicate side effects (use `FLAG_ONE_SHOT` semantics where applicable). Oracle: repeat-open invariance. Gap: repeat injection.
- **D8** Notification for content since region-restricted/expired: shows explanation, not playback; prohibited: play blocked content. Oracle: fallback match. Backend. Gap: content-state fixture.

#### Family E — fully expanded representative

**E1 · Signed-out user opens shared movie link, authenticates, lands on the intended destination.**
- **Business risk:** losing the intended destination after login drops the user on home, killing conversion and confusing sharers; landing straight on playback when a purchase is required is a revenue/logic bug.
- **Product rule (Unknown → operator must confirm destination type):** after successful auth, reach the policy-defined destination for content C (details/playback/purchase/explanation); destination identity C must be preserved across auth; allowed delay = auth round-trip; prohibited = home screen, wrong content, or wrong-account view.
- **Preconditions/fixtures:** signed-out app installed; shared link carrying destination ID C; valid credentials (referenced, not embedded).
- **Ordered journey:** open shared link while signed out → app routes to auth → complete authentication → observe destination.
- **Event:** authentication completes; app must restore destination C.
- **Invariants/Prohibited:** OAuth `state`/persisted context carries C; deep-link handler idempotent; post-auth destination matches policy for C's entitlement; **prohibited**: C lost (lands home), wrong content, or wrong-account state.
- **Oracle+Evidence:** deterministic on destination-ID before/after auth; correlation of `state` param; screenshots; `am start` status. (Automation stops before actual credential entry per platform constraint — the check verifies destination preservation up to and immediately after the auth boundary using a pre-provisioned session/persona where allowed.)
- **Tools/Access:** `am start` link delivery, persona/pre-provisioned session, backend for entitlement of C.
- **Feasibility:** medium — sign-in constraint means using captured sessions/personas rather than driving OTP/password.
- **Gap:** Android missions currently stop at sign-in; needs authorized sign-in capability or persona reuse for the post-auth assertion.
- **Cleanup/Repro limit:** clear session; process death during auth is a separate variant (E5).

- **E2** Auth cancelled then retried: returns to link's destination on success, safe state on cancel; prohibited: dead-end after cancel. Oracle: destination-ID. Gap: cancel/retry sequencing.
- **E3** Profile selection required as intermediate step: destination preserved through profile pick; prohibited: intent lost at profile screen. Oracle: destination-ID after profile select. Gap: multi-step intent preservation.
- **E4** Multiple links arrive before auth completes: last/first-wins per policy, deterministic; prohibited: mixed/duplicated destinations. Oracle: which C is reached. Gap: concurrent link injection.
- **E5** Process recreation during auth (low memory/kill): persisted verifier/state restored, handler idempotent; prohibited: lost C, CSRF-state mismatch. Oracle: destination-ID after cold start. `am kill` mid-flow. Gap: process-death-during-auth.
- **E6** Already signed in but wrong account opens link: prompt/switch per policy; prohibited: silently showing C under wrong account. Oracle: active-account check. Gap: wrong-account fixture.
- **E7** Link to removed/region-restricted content: explanation/fallback, not playback; prohibited: error/crash. Oracle: fallback match. Backend. Gap: content-state fixture.
- **E8** Duplicate delivery of the same link: idempotent single navigation; prohibited: double navigation/back-stack pollution. Oracle: back-stack + single destination. Gap: duplicate injection.
- **E9** Post-install deferred deep link (optional extension): first open reaches C via install-referrer; prohibited baseline requirement — treat as optional. Oracle: destination-ID on first run. Play Install Referrer. Gap: deferred-link infra (DEFER).

### Evidence and reproduction extensions

Add to the evidence model: safe account/profile aliases; content/download/notification IDs; entitlement decision + policy version; destination-before/after auth; request/response correlation IDs; requested-vs-observed operation state; event ordering + timing; backend fixture version. Observable black-box: UI hierarchy, screenshots, MP4, attributable logcat, `am start` launch status, `dumpsys media_session`/`audio`. Requires backend/app support: entitlement decision records, correlation IDs, `PlaybackStats` counters, ownership attribution. Preserve existing invariants: evidence IDs, missing-vs-zero (null + reason, never zero), finding identity/issue keys, critic review (≤2 within budget), compatible replay reusing the issue catalog, workspace scoping, verified publication, and APK bytes staying local (mode 0600, never uploaded). Never expose passwords/tokens/sensitive history in AI context or reports; raw MP4 cannot be masked (inherited) so avoid capturing credential entry.

**Release gate unchanged:** blocking a release requires a confirmed, reproduced P0/P1. A business-policy ambiguity is a requirements question, not a blocker.

## Recommendations

**Phase 0 — Rule table + contract skeleton (offline).** Deliver the `preconditions → event → expected state → allowed delay → prohibited outcomes → evidence source` schema and a Confirmed/Inferred/Unknown classifier in `engine/contracts.py`/`engine/policy.py`. Offline tests: schema validation via `.venv/bin/python -m pytest -q`. Product decision required: seed rule table for one content item. Acceptance: a rule can be authored, validated, and referenced by a mission. Change threshold: proceed only when one rule round-trips through store/replay.

**Phase 1 — First vertical slice: Family C isolation (live).** Extend `engine/android.py` with `pm create-user`/`am switch-user`/`pm list users` and package-data control; drive in-app profile switch via AI+UI; add mitmproxy wrapper to hold/release an in-flight response across a switch (scenario C1). Live validation: prove one real cross-identity leak or its absence end-to-end. Acceptance: a reproduced finding with identity-scoped evidence and correlation IDs; replay reproduces it. Limitation: `/sdcard` access for secondary users blocked since Android 9 — use `content` provider or root on userdebug.

**Phase 2 — Family D notifications + Family E shared-link auth.** Add notification-shade + `am start` deep-link primitives; encode destination-ID preservation and idempotent repeat-open oracles; OAuth `state`/PKCE persistence checks stop before credential entry (platform constraint — use personas/captured sessions). Acceptance: stale-destination (D1) and intent-preservation (E1) findings reproduced. Product decisions: correct fallback when destination gone; correct post-auth destination (details/playback/purchase/explanation).

**Phase 3 — Family B download integrity.** Range/If-Range/ETag validator checks via mitmproxy; final-hash + segment-completeness + playback-validity oracles; WorkManager `StopReason` observation if used; add no-reset execution mode. Live validation under `adb emu network delay/speed` (no packet loss on macOS — inherited). Acceptance: truthful terminal-state finding (B1); "100%-but-corrupt" caught.

**Phase 4 — Family A entitlement (staged; carrier proof deferred).** mitmproxy eligibility flip + Media3 telemetry (instrumented build) prove client reaction and continuity policy (A1); real carrier/zero-rating proof deferred to authorized-network extension. Acceptance: continuity-policy finding with instrumented evidence tier recorded; explicit note that billing is not proven.

Do not build the whole framework before Phase 1 demonstrates one real business-state failure end to end. **Benchmarks that change the plan:** if in-app profile switching proves un-drivable by AI+UI within a bounded attempt budget, escalate the Android-controller decision from EXTEND to ADD (UiAutomator2/Appium); if the backend team can own provider states, promote contract testing from DEFER to ADD ahead of Phase 4; if HTTPS pinning cannot be bypassed on any available build, Families A/B controlled-backend scenarios drop to black-box tier and their entitlement/validator oracles become unavailable (record null + reason).

## Caveats

- **Simulation ≠ proof:** mitmproxy/mocks prove client behavior only; carrier billing, zero-rating, and real server entitlement require authorized real-network verification. A seed guarantees L1 action order, not backend determinism (inherited). UI checks never prove media integrity — use hashes + Media3 telemetry.
- **Instrumentation dependency:** the strongest QoE/entitlement/ownership evidence needs a cooperating test build; black-box bindings drop to screenshot/MP4/`dumpsys` tier and this must be recorded, not hidden.
- **Platform gaps to close:** current runner is baseline-only networking, resets package data before missions (conflicts with persistent-download and profile-persistence tests — needs a no-reset mode), restricts execution to a designated AVD, and stops before sign-in/password/OTP (Families C/E need an authorized sign-in capability or pre-provisioned OS users/personas). These are unverified against the live repo — labeled proposed.
- **Device-time and expiry:** changing device time does not reliably advance server-anchored expiry or WorkManager scheduling; a documented Widevine case (ExoPlayer #2622) shows backward time extending offline-license remaining time. Use server-controlled expiry and short-lived fixtures.
- **Unresolved product decisions (must be operator-supplied):** playback continuity policy on grant loss; download ownership vs visibility vs playback rights per profile; correct notification fallback; correct post-auth destination (details/playback/purchase/explanation); whether restricted/child profiles must hide specific content; fail-open vs fail-closed on entitlement-service outage; deferred-deep-link support (optional).
- **Source limits:** the prior report was not re-fetched from the repo; the exact Media3 field spelling `totalRebufferTimeMs` and the canonical join-time metric (`getTotalJoinTimeMs` vs `totalValidJoinTimeMs`) were not first-party-verbatim confirmed and are flagged — verify against the PlaybackStats javadoc before relying on them; several download/OAuth mechanism details come from vendor/community sources corroborated across multiple independent pages.

## Sources
- MDN, *HTTP range requests*; http.dev, *If-Range* / *Range request* — Range/Content-Range/Accept-Ranges, If-Range strong-validator semantics, 206 vs 200 fallback.
- GitHub aria2-next issue #43 — CDN If-Range/ETag CANNOT_RESUME real failure.
- Apple Developer Forums (FairPlay lease vs rental); google/ExoPlayer issues #2622, #2962, #10800 — DRM license expiry mid-stream, device-time bypass (verbatim: "if the device time is changed to 5 minutes ago, LicenseDurationRemaining increases and the playback continues"), token refresh during license request.
- GitHub rafaelcg/pqp PR #527 — HLS viewer token expiry (`hlsPlaylistRejected reason=expired`) and proactive renewal.
- Android Developers — *Add 5G capabilities* (NET_CAPABILITY_TEMPORARILY_NOT_METERED, Android 11; mutual exclusivity with NET_CAPABILITY_NOT_METERED) / *Monitor connectivity* / *Read network state* (NET_CAPABILITY_NOT_METERED, onCapabilitiesChanged).
- SIGCOMM 2015 *Header Enrichment or ISP Enrichment?*; arXiv 2403.08507 *MobileAtlas* / 2403.08066 *Zero-Rating, One Big Mess* — carrier classification by egress IP / header enrichment / SNI-Host, free-riding.
- Android Developers — WorkManager *Define work requests* (default EXPONENTIAL 30s; MIN_BACKOFF_MILLIS 10s; MAX 5h); ProAndroidDev — WorkManager StopReason (STOP_REASON_CONSTRAINT_CONNECTIVITY).
- Medium/AndroidDevelopers — *All About PendingIntents*; PendingIntent identity ignores extras, FLAG_UPDATE_CURRENT/IMMUTABLE/ONE_SHOT.
- Auth0 / Cossack Labs / Contensu — OAuth `state` parameter, PKCE, persisting verifier/state across process death, idempotent deep-link handler.
- AppsFlyer / Singular / Software Mansion — deferred deep linking on Android (Play Install Referrer), post-install intent-data loss.
- Android Developers / community — *Test deep links with adb* (`am start -W -a VIEW -d`).
- Hypothesis docs — `RuleBasedStateMachine`, rule/precondition/invariant, shrinking.
- Wikipedia / arXiv / IEEE — metamorphic testing (Chen et al.), differential testing (McKeeman).
- Pact docs / Pactflow / Baeldung — consumer-driven contract testing, provider states.
- mitmproxy docs — addon events, response modification, hot-reload.
- OneUptime / QASkills — bounded eventual-consistency polling, observe-whole-window for forbidden states, entity-version staleness detection.
- Android Developers *Analytics (Media3)* + androidx.de javadoc + google/ExoPlayer #10668 — PlaybackStatsListener, totalRebufferCount, getTotalPlayTimeMs, getTotalWaitTimeMs, getMeanTimeBetweenRebuffers, getTotalJoinTimeMs/totalValidJoinTimeMs, onPlaybackStateChanged/onDroppedVideoFrames/onPlayerError, in-process requirement.
- AOSP *Test multiple users* — pm create-user/list-users/remove-user, am switch-user/get-current-user, "adbd daemon always runs as the system user (user ID = 0)", /sdcard secondary-user access resolves as system user (content-provider workaround), `/data/user/10/com.bar.foo/` isolation, Tradefed host-driven switching.

---

# Output B — `STATEFUL_PRODUCT_QA_CONTEXT.md`

## Scope boundary with previous Android research
This document governs **stateful business-journey** testing: identity/profile, subscription/entitlement, network-dependent access/charging, downloads/persistent data, auth boundaries, notifications/links/deferred navigation, and async/backend-state changes. It **depends on but does not repeat** `ANDROID_QA_CONTEXT.md` (lifecycle/network-chaos catalogs, media QoE measurement mechanics, device infra, fault-injection primitives). Reference prior capabilities only to declare a dependency.

## Required capabilities
- Deterministic control of identity: OS user (`pm create-user`, `am switch-user <id>`, `pm list users`, `pm remove-user`) and app-login switch (UI-driven).
- Controlled backend/response ordering (mitmproxy wrapper): hold/release flows on milestones; rewrite status/body/latency; requires unpinned or user-CA-trusting build.
- Deep-link/notification injection: `am start -W -a android.intent.action.VIEW -d "<uri>" <pkg>`; notification-shade interaction.
- Fixture setup/readback via HTTPX against authorized staging APIs.
- Optional instrumented telemetry: Media3 `PlaybackStatsListener` wired before `STATE_IDLE`.
- No-reset execution mode (preserve package data across a mission) for persistence tests.

## Five family templates
Each scenario = `intent {family, goal, account_refs, profile_refs, rule_refs, required_capabilities, journey[], external_events[], milestones[], ordering[], invariants[], prohibited[], observation_windows[], cleanup}` + `binding {mode, credentials_ref, fixture_version, proxy, evidence_tier}` + `recording {requested_vs_observed[], ordering, correlation_ids[], entitlement_decision, policy_version, destination_before/after, ownership, evidence_ids[]}`.

- **A Network-entitlement:** event=eligibility flip at boundary; invariant=continuity per policy; prohibited=silent free-content past grant loss / wrong message. Evidence tier: instrumented (PlaybackStats) or black-box (screens+dumpsys).
- **B Download integrity:** event=weak-connectivity pause/resume; invariant=truthful terminal state + hash identity + segment completeness + playback validity; prohibited=100%-but-corrupt, duplicated work.
- **C Isolation:** event=identity switch with in-flight response; invariant=identity-scoped data + ownership follows initiator; prohibited=A's response populates B.
- **D Notifications:** event=delayed open after state change; invariant=current state + auth/entitlement gate + correct fallback + idempotent repeat-open; prohibited=stale destination/text.
- **E Shared-link auth:** event=auth completes/cancels/retries with process death; invariant=destination identity preserved + correct back-stack; prohibited=landing on home/wrong account/wrong content.

## State variables and transition rules
`{account, profile, subscription∈{none,free,paid,expired}, zeroRatedTransport∈bool, contentGrant∈bool, metered∈bool, sessionValid∈bool, downloadState∈{none,running,paused,failed,completed,cancelled}, downloadOwner, licenseState∈{none,valid,expired,lease,rental}, destinationId, notificationId}`. The four "free" conditions are independent booleans; never derive one from another. Guards on `PLAYING` re-evaluate `contentGrant` at manifest/segment/license/auth boundaries. Ownership is set at operation initiation and is immutable across later identity switches.

## Oracle definitions
Confirmed | Inferred | Unknown/Contradictory. Deterministic where fixtures make expected state knowable (C, D destination-ID, auth-gate). Policy-dependent continuity (A, B) uses configured tolerances; unspecified continuity → AI hypothesis reviewed by critic as unconfirmed. Ordering assertions: no cross-identity population; no stale-callback completion of a cancelled op; auth preserves content identity; entitlement checked at product-specified boundary. Forbidden-state checks observe the whole window (do not stop at first empty read).

## Fixture requirements
Accounts (none/free/paid/expired); ≥2 profiles incl. restricted/child; distinct per-profile histories; content public/restricted/removed/expired; small media with known SHA-256 + track/subtitle properties; eligible/ineligible network-policy fixtures; notifications/links with traceable destination IDs; expiring sessions/URLs/licenses (server-controlled expiry, short TTL).

## Selected technologies and access limitations
Hypothesis (ADD, dev) | HTTPX (REUSE) | mitmproxy (WRAP; pinning/QUIC limits) | ADB multi-user + `am start` (EXTEND) | Media3 telemetry (ADD, instrumented only) | Pact (DEFER). Device-time changes do not advance server expiry. `adbd`=user 0; secondary `/sdcard` resolves as system user (use content provider); user data at `/data/user/{id}`.

## Proposed contract fields
See family template above (intent/binding/recording). Credentials by reference only. Evidence tier mandatory per binding.

## Module integration map
`engine/contracts.py` (schema, rule table), `engine/policy.py` (Confirmed/Inferred/Unknown + release-gate), `engine/android.py` (multi-user, deep-link, notification-shade), `engine/ai.py`/`prompts.py` (UI interpretation only), `engine/evaluate.py` (invariants, bounded polling), `engine/outcomes.py` (findings, correlation IDs), `engine/store.py` (recording, evidence IDs), `engine/runner.py` (milestone/event injection, mitmproxy control), `app.py`/`static/` (rule/scenario UI).

## Acceptance criteria
Phase 1 reproduces one real cross-identity leak (or proves absence) with identity-scoped evidence + replay. Each family: a reproduced finding with correct evidence tier; business-policy ambiguity surfaces as a requirements question, not a P0/P1. Release blocking requires confirmed reproduced P0/P1.

## Open product-policy questions
Playback continuity on grant loss; download ownership vs visibility vs playback rights per profile; notification fallback when destination gone; post-auth destination (details/playback/purchase/explanation); restricted/child content hiding; fail-open vs fail-closed on entitlement-service outage; deferred-deep-link support (optional).

## Source links
Same as Output A Sources.