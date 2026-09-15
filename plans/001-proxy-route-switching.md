# Proxy routes and link speed on web and Android — reviewed implementation plan

Reviewed 2026-09-15 against commit `cc4fae1` and the current working tree.
Source plan: `/Users/parhumm/.claude/plans/structured-mixing-hare.md`.
Status: TODO. Effort: L overall; risk: high in forwarding and cleanup, medium elsewhere.
This review changes the plan only. No implementation or live validation was performed.

## Outcome and boundaries

Keep one scenario vocabulary: a mission selects its initial proxy and link profile;
an event can switch route and optionally change speed/delay. Preserve browser sessions
and the Android app process. A proxy label such as “Germany” is operator metadata;
it does not establish country, ISP, carrier billing, entitlement, or radio conditions.

Use one run-owned local relay for route events on either platform, and for Android
mission-level egress. Retain native Playwright proxy configuration for web missions
without route events, including its existing SOCKS5/netem behavior. Keep the two runner
lifecycle branches; share route resolution, not a new runner framework.

Android support is gated by actual emulator traffic tests. Do not silently substitute
the Android system proxy, add VPN infrastructure, or change guest proxy settings.
Web implementation may proceed independently; do not advertise Android parity until
its gates pass. Mission-level Android shaping remains in scope as a separate stage.

## Review findings resolved by this revision

All findings below have high confidence from the plan and cited code; live transport
coverage remains unknown. Effort/risk describe the correction, not the whole feature.

| Priority | Original gap and evidence | Required correction | Effort / risk |
|---|---|---|---|
| P1 | Design promises old connections finish, but `switch()` closes them | Define a deliberate disconnect; outstanding requests can fail and no retries are guaranteed | S / low |
| P1 | Change 1 strips `Transfer-Encoding` while pumping unchanged HTTP bodies; forwards upstream HTTP verbatim without specifying route auth | Use framed HTTP forwarding, correct URI ports/Host and hop headers, and upstream-only credentials | M / high |
| P1 | Live assertions count relay probes as app traffic; host HTTPX probe bypasses guest/browser shaping | Separate relay health from target traffic and device connectivity; preserve unsuccessful checks | M / medium |
| P1 | `engine/evaluate.py:157` web comparison checks neither scenario nor faults; Android keys at :140 omit initial egress | Extend comparison on both branches and snapshot route configuration without secrets | M / medium |
| P1 | `engine/android.py:236` reads download only and restores `kbits:kbits`; research calls this parser correct | Restore upload/download independently, without integer truncation; unknown values stay unknown | S / medium |
| P1 | Stage 0 proposes system-proxy fallback despite the plan explicitly excluding it | Keep the ownership restriction; report unsupported transport instead of changing architecture | S / low |
| P2 | Android baseline calls `apply_speed`, which always appends a fault at :513; raw HTTPX failures may expose proxy details | Separate baseline configuration from step recording; sanitize public errors | S / medium |
| P2 | `web.SPEEDS` and emulator preset values differ; research mixes command forms and contradicts its own dates | Record actual applied values and verify numeric syntax; do not promise equal throughput from equal labels | S / low |

## Current state and drift check

Run `git status --short` and `git diff cc4fae1 -- engine app.py static/app.js tests pyproject.toml`.
At review, existing edits affected `app.py`, `engine/contracts.py`, `engine/suggest.py`,
`tests/test_phase1.py`, and `.claude/skills/pex-mission-write/references/goal-voice.md`.
Preserve them. Reconcile changed symbols before implementing; line numbers are navigation aids.

Relevant existing code:

```python
# engine/contracts.py:96 — kind and one_operation each collapse speed + delay
if 'speed' in chosen and 'delay_ms' in chosen:chosen.remove('delay_ms')
# engine/scenario.py:189 — event reasons are currently discarded
await self.apply(step['event']);result.update(status='passed',reason='Applied')
# engine/android.py:240 — loses asymmetric upload and fractional kbps
kbits=int(down.group(1))//1000 if down else 0
# engine/runner.py:728 — existing shared interpreter call
await self._scenario(id,r,m,web.Browser(page,context,cdp,profile,r,m,hide,supplied,tabs),pursue,event,start+m['max_seconds'])
```

Use existing `ScenarioError`/`AndroidError` and the scenario interpreter's error→skip
behavior. Follow `tests/test_web_scenario.py:scenario_journey` and
`tests/test_android_runner.py` for runner fakes, and `tests/test_scenario.py` for contracts.
`tests/media_proxy.py` is a live smoke script with a deliberately incomplete relay,
not production forwarding code to copy wholesale.

Scope: `engine/{relay,contracts,scenario,web,android,runner,evaluate,suggest}.py`,
`static/app.js`, `pyproject.toml`, the relevant existing tests plus `tests/test_relay.py`
and an opt-in `tests/route_live.py`, docs and the mission-writing scenario reference.
Only touch `app.py` if a demonstrated API validation boundary needs adjustment.
No hub protocol/storage refactor, browser-policy relaxation, prompt encoding change,
new scheduler, TLS interception, SOCKS5 chaining, remote relay, or AI/model-routing work.

## 0. Measure Android transport before implementing its integration

Create an opt-in `tests/route_live.py --android-gate` harness. Use a disposable designated
AVD, a local logging proxy and controlled HTTP/TLS/TCP fixture endpoints. Record emulator
version, API/ABI, launch flags, guest interface and exact console commands. Do not run
this gate as part of pytest. Do not run real AI missions for this gate.

1. Refuse an already-running designated AVD. Launch with `-http-proxy` and retain
   `-no-snapshot`; address all adb calls to its serial. Capture original network state.
2. Exercise browser and fixture-app HTTP, HTTPS and arbitrary-port TCP on Wi-Fi and
   cellular separately. Correlate unique fixture requests with proxy logs and responses.
   A host IP probe alone cannot pass this gate.
3. Test a long-lived connection, then disconnect it at the relay and require the next
   fixture request to use the newly selected upstream. Do not require distinct public
   IPs when both local fake routes have the same internet connection.
4. For each interface, compare a warm baseline with five controlled delayed requests
   and an asymmetric bandwidth transfer. Require traffic through the proxy, console
   readback matching requested values, and a repeatable measured change above baseline
   noise. Record numeric observations; command acknowledgement is not throughput proof.
5. In `finally`, restore captured state and stop only the owned emulator/proxy. Keep
   logs in the chosen artifact directory and a concise pass/fail matrix in the report.

Verify (after creating the harness): `.venv/bin/python -m tests.route_live --android-gate`.
Exit 0 means every advertised interface passed; unavailable prerequisites or a failed
interface must return nonzero with its reason. If the installed emulator cannot meet
the planned coverage, stop Android integration and report the measurements. Do not
guess undocumented flags or quietly downgrade to an app-opt-in system proxy.

## 1. Build the relay with explicit switch semantics

`engine/relay.py`: one `Relay`, loopback ephemeral listener, resolved route map,
`start`, `apply(route_id)`, `stop`. Keep route records/secrets in memory. Delete the
110-line estimate: correctness of a streaming proxy is the acceptance criterion.

**Switch contract:** validate the ID first; atomically advance a route generation and
terminate all old-generation client sockets, upstream sockets and pending connection
tasks. New connections use the new generation. A connection finishing its handshake
after the switch must check its generation before forwarding. Track every accepted
handler before its first await. Reject stale work, including when switching to the same
route again. Do not hold a global lock over network I/O.

Wording: “Switched route and disconnected existing proxied connections. In-flight
requests may be interrupted; new connections use the selected route.” Do not promise
buffered bytes are recalled, uninterrupted playback, or automatic retry of writes.
No transparent direct fallback if an upstream fails.

**Forwarding:** support CONNECT and ordinary HTTP, including uploads and streaming.
Use asyncio for sockets and the already-installed `h11` parser for HTTP framing;
declare `h11>=0.16,<1` directly in `pyproject.toml` rather than relying on HTTPX's
transitive dependency. Installed at review: h11 0.16.0, HTTPX 0.28.1, Playwright 1.62.0.
No framework or cache. Preserve duplicate end-to-end headers and stream bodies.

- CONNECT: validate authority (including bracketed IPv6 and explicit port); for an
  upstream, forward the hostname/IP unchanged and use the target authority as Host.
  HTTP or TLS-to-HTTPS proxy, normal certificate/hostname verification, HTTP/1.1.
  Treat successful CONNECT as a tunnel and preserve bytes buffered after the headers.
- Ordinary HTTP: derive destination and Host from the absolute URI, including its
  non-default port; origin-form direct, absolute-form upstream. Decode/re-encode
  framing with h11; never strip transfer coding while forwarding its encoded body.
  Strip hop headers and fields named by Connection, regenerating necessary framing.
  Reject ambiguous lengths and malformed requests; preserve request/response semantics
  for HEAD, no-body responses, informational responses and HTTP upgrades/WebSockets.
- Strip inbound proxy credentials. Inject this route's Basic credentials only on the
  upstream hop, for both CONNECT and ordinary HTTP. Never log credentials, auth headers,
  arbitrary upstream reason text, or raw proxy exceptions. Use fixed error categories.
- Bound headers (64 KiB), connect/header waits (5 s/10 s), concurrent handlers (128),
  buffers (64 KiB chunks) and shutdown (5 s); stream lifetime follows the run budget.
  Use `drain`; propagate half-close only when `can_write_eof()` allows it. Handle TLS
  closure explicitly. Cancel and await sibling tasks on errors, switch and shutdown.
  `stop()` is idempotent, closes the listener, handlers and pending dials.

Verify: `.venv/bin/python -m pytest -q tests/test_relay.py` → all pass, offline.
Cases: direct/upstream HTTP and CONNECT, authenticated HTTP as well as CONNECT,
non-default ports/IPv6, chunked upload/response, HEAD, upgrade, slow/malformed headers,
407/non-2xx/refused connection, untrusted upstream TLS, half-close, and switching
during a paused dial/handshake. Assert old-generation traffic cannot resume, credentials
never reach the origin/output, and repeated stop/cancel leaves no handlers/listener.

## 2. Define evidence and validation before wiring adapters

Relay `apply` switches then probes via itself using a fresh HTTPX client with
`proxy=...`, `trust_env=False`, redirects disabled and `ipaddress.ip_address` validation.
Try ipify then icanhazip under a single `asyncio.timeout` of at most 15 s, reduced to
the remaining mission budget. HTTPX's per-operation timeout is not a total deadline.

Append a check before attempting the change: generation, route ID/name, step index
(null for initial setup), requested/finished time, status, probe endpoint, observed IP
or null, safe error, disconnected count. Failed/cancelled checks survive finalization.
Both endpoints failing means “route verification unavailable”, not proof the route is
dead. Stop the step/run as infrastructure failure; do not create an app defect or
silently roll back. Following checks are skipped through existing scenario handling.

Keep total accepted/successful connections and forwarded bytes per generation as
transport diagnostics. Label probe traffic separately (identify the probe's own local
connection, not all requests to the probe hostname). Counters alone are not proof of
app traffic: correlate controlled target requests in live validation. Host probes do
not prove guest offline, throughput, CDN reachability or actual app exit IP. Keep
initial setup plus each event: two route events normally produce **three** checks.

Extend contracts and `scenario.event_kind` consistently: `route` plus optional `speed`
and/or `delay_ms` is one event; any other operation combined with it is rejected.
Use `event.get('route') is not None`; recognize `direct`. IDs must resolve to actual
stored egress records before forming secret paths; do not treat arbitrary text as a path.

In `_submit` validate the union of initial egress and step routes (minus direct).
Keep existing global/local egress ownership semantics and workspace scoping for missions,
targets/runs; do not invent workspace-owned proxy records. Require existing local secret
files (empty credentials are valid), supported HTTP(S) upstreams when relay is engaged,
and local browser backend. Recheck availability at execution. Snapshot non-secret route
IDs, servers and relevant configuration for comparison; names/timestamps/IPs are not
compatibility fields. Secrets never enter run records, prompts, hub uploads or logs.

Verify: `.venv/bin/python -m pytest -q tests/test_relay.py tests/test_scenario.py tests/test_phase1.py`
→ valid combined events pass; unrelated operations, missing/deleted routes, malformed
IDs, missing local configuration, SOCKS5 switching and netem switching are rejected.
Exercise the actual submit endpoint; saved drafts need not perform runtime validation.

## 3. Wire web execution and replay

Give `Browser` an optional relay and a fault list. Keep interpreter dispatch generic:
apply route, then optional shaping; propagate its successful reason. Record the route
operation before attempting it; retain verification separately. A shaping failure after
successful switching must retain the route evidence and prevent a passed combined step.

Record one requested fault per external operation, avoiding double records when
`apply_network('wifi'/'cellular')` delegates to `apply_speed`. Include restore operations.
Keep original speed/offline semantics; route changes never implicitly bring a device online.

In `Runner.execute`, create the relay inside the existing guarded lifecycle before
context creation, set the local proxy and initial route, then pass it to Browser.
No route events means the existing native proxy path. Preserve `route_guard`, domain
controls, read-only behavior, tracing, masking and session storage. Copy partial faults
and route evidence in `finally`, not only after successful scenario completion. Close
browser/context before relay; stop relay even if evidence finalization raises. Publish
terminal records only after cleanup evidence and referenced artifacts are finalized.

Update **both** branches of `compare_runs` in `engine/evaluate.py`: compare scenario
digest, initial route/configuration, stable requested faults and applied profile values.
Ignore probe IPs/times, port, traffic counters and route labels. Old runs without new
fields remain mutually comparable; do not claim a legacy run verified new route
conditions. New route evidence missing/failed makes reproduction unverified. Add tests
for route record changed under the same ID and same route with a rotated observed IP.
Retain all existing critic/reproduction/release-gate requirements.

Web continuation must append route checks/faults and re-establish the initial route for
the scenario it re-executes, rather than silently overwriting prior-part evidence.

Verify: `.venv/bin/python -m pytest -q tests/test_web_scenario.py tests/test_scenario.py tests/test_engine.py tests/test_phase1.py`
→ native proxy regression passes; switched route and partial failure evidence persist;
changed scenario/fault/config is incompatible; IP rotation alone remains compatible;
cancel/startup/probe failure and continuation clean up and preserve evidence.

## 4. Integrate Android routing and mission shaping after the gate passes

Pass the resolved run profile and optional relay into Device. Inside its existing AVD
lock, refuse an already-running AVD when proxy routing is requested, before touching
its state. Launch the owned emulator with the local `-http-proxy` address. Keep APK
verification, reset/snapshot behavior, recording and ownership-safe termination.

Fix `console_network` before enabling profiles: parse upload and download independently,
convert bits/s to kbps without integer truncation, preserve asymmetric and unlimited
values. Missing/malformed state must not become a successful restoration to invented
defaults. Capture before mutation; mark changed before issuing commands; read back
restoration and keep failures visible. Extend the old symmetric fixture accordingly.

Accept local profiles with only latency/down/up effects. Reject `backend=netem`,
offline, jitter, loss, reordering, duplication and periodic disconnect. Nonzero
`disconnect_seconds` alone is inert when periodic disconnect is disabled.
Use numeric up:down kbps and verified delay syntax from Stage 0; do not silently clamp
positive rates to zero/unlimited. Capture original settings before applying baseline,
then launch the app. A private shaping helper can serve baseline and step calls;
baseline does not append a step fault. Do not append and then remove history entries.

Keep two restoration targets explicit: `network: restore` restores the mission's
baseline profile and original transport state; final cleanup restores the exact
pre-run settings. After a step restore, baseline shaping still needs final cleanup.
Route reset is explicit `route: direct`; network restore does not change egress.
Persist actual applied settings, backend, verification method and tested interface
scope. Same preset names do not imply equal numerical profiles on web and Android.

Android runner finalization always stops the device and relay independently, copies
faults/checks/restoration even on startup failure/cancellation, then compares/publishes.

Verify: `.venv/bin/python -m pytest -q tests/test_android.py tests/test_android_runner.py tests/test_phase1.py tests/test_scenario.py`
→ owned launch args correct; running AVD untouched; asymmetric/fractional/unlimited
restore passes; malformed capture fails honestly; baseline produces no step fault;
step restore and final restore reach their distinct targets; failed cleanup retains evidence.

## 5. Finish the builder, docs and live acceptance

In `static/app.js`, add route to the existing event builder with saved routes + direct,
optional speed/delay and name-based summary. Preserve selection through YAML roundtrip,
edit/reload, event-kind changes and target changes. Keep missing routes visible as
invalid; never silently select direct. Escape all route names/IP/error strings and use
existing labelled native controls. Enable Android egress/profile fields only for the
implemented supported scope; retain server-side validation and clear error messages.
Show initial and per-step route checks, including unavailable/failed verification.

Update the scenario skill reference, `engine/suggest.py`, README, `docs/REFERENCE.md`,
`docs/DEPLOY.md`, `docs/USER_MANUAL.md`, `docs/FEATURE_STATUS.md`, and CHANGELOG.
Explain owned-emulator requirement, local-only relay, HTTP(S) upstreams, deliberate
connection interruption, scope of probes, DNS uncertainty and unproxied UDP/QUIC.
Describe preset numbers as platform-specific configuration, not measured throughput.
Keep full gate transcripts in artifacts; CHANGELOG gets only a summary and reference.

Extend the opt-in live harness with `--web` and `--android`: controlled HTTP/HTTPS
fixture, two tagged upstreams, long-lived connection, switch+speed, target assertion,
direct switch, and cancel cleanup. App/target requests must appear on the intended
upstream after each switch. Public exit IP checks are a separate internet-dependent
test; identical IPs are valid. For Android require the fixture app itself to generate
network traffic; `check no_crash` alone cannot verify routing. Test every claimed web
engine for route-only scenarios; combined shaping remains Chromium-only.

Verify:

- `.venv/bin/python -m pytest -q` → full offline suite passes once before delivery.
- `.venv/bin/python -m tests.ui_check` against a running isolated server, using
  `PEX_BASE_URL` / `PEX_UI_ARTIFACTS` → builder operations and roundtrips pass.
- `.venv/bin/python -m tests.route_live --web` and `--android` → pass for advertised
  platforms, with request correlation, transport measurements and closed relay port.
- `git diff --check` → clean. No unrelated source changes or exposed secret values.

These are future implementation checks, not results of this plan review. A failed or
unavailable live gate must be reported as such; deterministic tests cannot substitute
for it. This feature is complete only when both requested platforms pass their gates.

## Research use and corrections

Used `docs/researches/proxy-route-switching.md` for topology and uncertainties,
`extending-product-excellence-advanced-android-failure-discovery.md` for bounded,
verified, restored faults, and `stateful-product-qa-for-consumer-streaming-apps.md`
for entitlement/evidence limits. Pricing and model-routing research is unrelated to
this change and supplies no implementation requirements. This is a targeted plan
review, not a full repository/security audit or a fresh survey of all research claims.

Primary references checked on the review date:

- [RFC 9112, message framing](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3):
  stripping transfer coding without processing the body is unsafe; ambiguous framing
  must be handled explicitly. The original research's forwarding shortcut is rejected.
- [h11 usage](https://h11.readthedocs.io/en/stable/basic-usage.html): use its streaming
  HTTP events instead of writing another body-framing parser.
- [asyncio streams](https://docs.python.org/3/library/asyncio-stream.html): check
  `can_write_eof`, apply backpressure and await closure; TLS is not a plain TCP half-close.
- [Android proxy docs](https://developer.android.com/studio/run/emulator-networking-proxy):
  emulator proxy supports TCP; system proxy may be ignored by apps. Neither establishes
  the runtime coverage of this specific installed emulator/fixture combination.
- [Android console](https://developer.android.com/studio/run/emulator-console): documents
  netsim Wi-Fi separation and asymmetric rate syntax. Readback and traffic measurement
  resolve command/version uncertainty. The research's “post-netsim” date argument and
  assertion that the repository restore parser is correct are not acceptance evidence.

## Stop conditions and maintenance

Stop the affected stage if required transport coverage fails, protocol correctness
requires dropping requested HTTP/streaming behavior, or route isolation/cleanup cannot
be proven. Report evidence and a concrete revised scope; do not silently add a proxy
fallback or weaken release requirements. Continue independent stages where possible.
No commits, deployment or live AI quota use are part of this review.

Future owners should re-run the transport gate on emulator/Playwright upgrades and
revisit evidence compatibility whenever route/profile semantics change. Add SOCKS5
chaining, remote hosting, ISP/ASN verification or entitlement simulation only for a
specific subsequent requirement. Do not build them into this relay in anticipation.
