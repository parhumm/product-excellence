# Extending Product Excellence for Advanced Android Failure Discovery — Research Report & Engineering Context

**Research date:** September 14, 2026 · **Product Excellence version referenced:** 1.5.1 · **Scope:** research and implementation planning only (no code changes, no live device/AI runs).

## TL;DR

- **Extend, don't replace.** The existing ADB + `uiautomator dump` controller in `engine/android.py` already does the hard parts (device lock, APK SHA-256 verification, hierarchy capture, control revalidation, `am start -W` launch timing, `dumpsys meminfo` PSS, attributable logcat, MP4 evidence, AI plan/critic/replay). The real capability gaps are (1) **verified, bounded fault injection** (network/lifecycle/resource/interruption), (2) **media QoE oracles beyond "a player is visible,"** and (3) a **scenario + evidence/replay contract** that records requested-vs-verified faults and metric provenance — all buildable on the current Python/asyncio/ADB stack.
- **The failures scripted E2E misses are compositional state-restoration failures** — process death after a configuration change during buffering under a constrained network — and they are reachable **today on the designated AVD** using ADB and Android emulator-console primitives on macOS, gated behind a fault-verification contract that always restores on cancel/timeout/failure.
- **Adopt Stack A now** (fault scheduler + oracle module + evidence contract, one Mac, existing AVD and AI CLI). Treat Appium/Maestro, physical devices, `tc`/netem (Linux only), `mitmproxy`, and device farms as **later, demand-driven** additions. Preserve the release rule: **blocking requires a confirmed, reproduced P0/P1** — chaos results must not bypass it.

## Key Findings

1. **The current controller is a one-shot XML dump + ADB input, not a live UI Automator instrumentation session.** It has no `UiWatcher`, no `bySelector` waiting, no synchronized scroll-to-element. This is the only credible motivation for adding a complementary driver later, and only if a concrete gap (multi-touch, robust scroll/wait, deep WebView inspection) is demonstrated.

2. **Emulator network shaping is real but limited.** `adb emu network delay|speed` applies documented profiles (gsm/gprs/edge/umts/hsdpa/lte/full) and is CI-friendly on macOS, but it has **no packet-loss verb** (only total loss via offline) and is **lossless and jitter-free**. Loss/jitter/bandwidth realism requires Linux `tc`/netem, which **does not run natively on macOS**. Application-level manipulation (status codes, partial/malformed bodies, DNS/CDN failures, expired URLs) requires a proxy (`mitmproxy`) or a controlled backend — and **HTTPS pinning defeats a proxy** unless the app is unpinned or a debug build trusts a user CA, while **QUIC/HTTP3 often bypasses a TCP proxy entirely.**

3. **Media QoE has a strict provenance hierarchy.** Authoritative rebuffer count/duration, dropped-frame rate, startup time, bitrate changes and decoder/DRM errors come only from **instrumented Media3 `PlaybackStatsListener`** (Google-maintained, actively supported) — **not available from an arbitrary release APK.** Even instrumented pipelines have gaps: per Alexey Bykov (Android GDE, Staff SWE at Reddit) in "Taking ExoPlayer Further: Reddit's performance techniques" (ProAndroidDev), "in 2024, we discovered that about 47% of our video sessions weren't reported correctly because some of the events used in our composite metrics were missing. Additionally, some events had race conditions in reporting." **Widevine L1 (hardware TEE) blocks screen capture, so screenshots and MP4 render black on protected playback**; even the demo fixture must be DRM-free. **Never infer successful playback from a visible player screen.**

4. **Launch timing is a proxy, not a standardized metric.** `am start -W TotalTime` is not the framework's automatic TTID (the logcat `Displayed` line), not TTFD (`reportFullyDrawn`, app-cooperative), and not a Jetpack Macrobenchmark `StartupTimingMetric`; Google's Macrobenchmark codelab explicitly warns emulator numbers are not representative of real devices. For context, per Android Developers' "App startup time" doc: "Android vitals considers the following startup times for your app excessive: Cold startup takes 5 seconds or longer. Warm startup takes 2 seconds or longer. Hot startup takes 1.5 seconds or longer."

5. **Autonomous exploration adds coverage but is not an oracle.** ByteDance's Fastbot2 (RL model-based, open-source) is production-proven: per the ASE 2022 paper (Lv, Peng, Zhang, Su, Liu & Yang; ACM DOI 10.1145/3551349.3559505), "Fastbot2 has been deployed in the CI pipeline at ByteDance for nearly two years, and 50.8% of the developer-fixed crash bugs were reported by Fastbot2," outperforming Monkey, APE and Stoat on Douyin and Toutiao. LLM-agent testers (GPTDroid, AutoDroid, DroidAgent/Yoon et al. ICST 2024, VisionDroid) raise coverage and catch non-crash functional bugs but are **not reliable standalone oracles** — matching this project's deterministic-critic requirement.

6. **"Any VPS can run emulators" is false.** Accelerated emulation requires the host to expose CPU virtualization extensions; Android's official acceleration docs state you cannot run a VM-accelerated emulator inside another VM (VirtualBox/VMware/Docker) — on Linux this means KVM. Cloud emulation works only with nested virtualization explicitly enabled: GCP Compute Engine on Intel Haswell+ Linux VMs (KVM only; not E2/N2D/A2; not AMD; Google documents a ≥10% performance decrease) or AWS bare-metal `.metal` instances.

## Details

### Existing capabilities and verified gaps

**EXISTING (baseline + code map):** designated disposable AVD via `PEX_ANDROID_AVD`; device locking; APK SHA-256 verify/install + package-reset; SDK/API/ABI checks; `uiautomator dump` hierarchy; ADB screenshots; control revalidation; tap/ASCII-text/scroll/nav/relaunch; `am start -W TotalTime`; `dumpsys meminfo` PSS (KiB); attributable/bounded/best-effort-redacted logcat; bounded `screenrecord` MP4; AI plan/eval/finding/replay; hub sharing (records+evidence, not a scheduler). Tool resolution: `PEX_ANDROID_SDK` → `ANDROID_HOME` → `ANDROID_SDK_ROOT` → Homebrew cmdline-tools → `~/Library/Android/sdk`. Fixture verified: API 34 arm64, usable hierarchy, safe text input, sensitive-field recognition, seekable MP4, PSS, attributable Java crash/ANR logs. Mission fields bind these: `target_id`, `build`, `device`, `visibility`, resolved `platform`.

**VERIFIED GAPS:** network = baseline only (shaping/offline/periodic-disconnect rejected without operator `PEX_ANDROID_PROBE_URL`); no sign-in/password/OTP; non-ASCII input unsupported; Android continue unsupported (replay needs exact APK SHA); benchmark/competitors/personas/proxy-egress/SEO rejected; reload = force-stop+relaunch (**not** low-memory death); jank/gfx null; no continuous soak recording; raw MP4 not maskable; launch ≠ TTID/TTFD/Macrobenchmark; no established media QoE / TalkBack usability / physical fidelity / production performance.

### Android QA taxonomy and high-risk failure modes

Each domain below carries purpose → consequential failures → automation approach → prerequisites → limitations → project value.

- **Functional/integration/UI/E2E:** happy-path correctness. Already covered by scripted E2E; baseline regression only.
- **Exploratory/model-based/state-machine/property-based:** discover unspecified states (dead ends, back-stack corruption, illegal transitions). AI-proposed actions over a state graph with semantic state identity + property invariants. **Core differentiator — very high value.**
- **Fuzzing/Monkey/unusual behavior:** crashes/ANRs/IME/emoji. Wrap seeded `adb shell monkey --throttle`; optional Fastbot2 coverage engine. High value.
- **Lifecycle/process death/configuration:** state restoration — highest value (below).
- **Network/offline/recovery:** resilience — very high value (below).
- **Fragmentation/resource pressure:** OOM, storage, CPU via `am send-trim-memory`/`am kill`/storage fill/Doze. High.
- **Interruptions/cross-app/system UI:** calls/notifications/permission dialogs via emulator console + `am`. High.
- **Performance (startup/render/memory/battery/thermal):** `am start -W`, `dumpsys gfxinfo/meminfo/batterystats`. Medium-high; instrumentation caveats.
- **Media (playback/downloads/DRM):** QoE — very high for VOD (below).
- **Accessibility/localization/RTL:** ATF + config sweeps. High.
- **Permissions/notifications/background:** `pm grant/revoke`, WorkManager under Doze. High.
- **Security/privacy (MASVS/MASTG):** data-at-rest, TLS, exported components. High, scoped.
- **Upgrade/migration/soak:** state preservation, leaks over hours. High; blocked by current package-reset.
- **Autonomous testing/failure oracles:** the meta-capability (below).

**Prioritize:** silent state loss after process death; playback that shows a frame but is stalled; unrecovered Wi-Fi→cellular transition leaving a permanent spinner; permission-revocation crash; back-stack/PiP corruption; ANR on Doze wake; data loss on upgrade.

### Lifecycle and configuration testing

Precisely what each injection proves:

- **Activity recreation** ("Don't keep activities" / config change): proves `onSaveInstanceState`/`ViewModel` restoration; **not** full process death.
- **`am force-stop`** (user kill): clears back stack; **not** system-death saved-state restoration — this is what the current reload uses, explicitly not equivalent to low-memory death.
- **`am kill <pkg>`** (backgrounded only): on the emulator, most closely simulates **system-initiated process death** and triggers `SavedStateHandle`/`onRestoreInstanceState`. Requires app not foreground.
- **`am send-trim-memory <pkg> <LEVEL>`**: delivers `onTrimMemory` (MODERATE…COMPLETE) without killing.
- **Low-memory killing (LMK):** true per-app LMK needs memory pressure; not reliably reproducible without platform changes — approximate with `am kill` after backgrounding and document the approximation.
- **Task removal (recents swipe):** distinct lifecycle; `am` cannot fully reproduce — MANUAL/PARTIAL.
- **Reboot (`adb reboot`):** boot-completed receivers, re-auth; bounded but slow.
- **Package reset:** current data-reset path; wipes state (blocks preserved-state upgrade tests).

Configuration injections (each with mandatory reset on cancel/timeout/failure): rotation (`settings`/`wm`), split-screen/PiP (PARTIAL on emulator), font scaling (`settings put system font_scale 1.3`), density (`wm density <dpi>` / `wm density reset`), size (`wm size WxH` / `wm size reset`), locale/RTL, timezone, light/dark (`cmd uimode night yes|no`). Each proves resource re-selection and re-composition survival; none proves visual correctness without a visual oracle. Classification: recreation/force-stop/`am kill`/trim/config = **PROPOSED (extends `engine/android.py`)** via standard ADB, emulator-sufficient. True LMK / task removal / real foldable hinge = **UNVERIFIED / REQUIRES ADDITIONAL INFRASTRUCTURE**.

### Network and resource chaos

**Transport injection ≠ response manipulation.** Transport (latency/loss/bandwidth) is injectable at the emulator/host; response manipulation (status codes, partial bodies, malformed media) needs a proxy or controlled backend, and for HTTPS a debug build trusting a user CA or an unpinned app.

Per-technique record (macOS feasibility / Linux / emulator+physical / root-cert-instrumentation / scope / determinism / verify-restore):

- **Emulator console** (`adb emu network delay|speed`, `gsm data off`): macOS-feasible (emulator telnet backend); **emulator-only** (physical returns unsupported); no root/cert; scope = emulator radio; **no packet-loss verb** (total loss only via offline); lossless/jitter-free; verify `adb emu network status`; restore `network speed full`/`delay none`. **Primary CI injector, already reachable from the subprocess layer.**
- **Android Studio Extended Controls Network tab:** GUI presets + packet-loss/duplicate sliders; not scriptable headless — reference only.
- **Linux `tc`/netem:** full delay/jitter/loss/duplication/bandwidth (ifb for both directions); **does not run natively on macOS**; needs the Linux hub/host; targets host interfaces; deterministic; restore by deleting qdisc. **REQUIRES ADDITIONAL INFRASTRUCTURE (Linux).** Inspect `engine/netem.py` scope before claiming Android reuse — its name does not guarantee Android traffic shaping.
- **Proxy (`mitmproxy`, Python — reuses conceptual asyncio/HTTPX stack):** application-level manipulation (status, latency toxics, partial/truncated, DNS/CDN failures, expired URLs); requires device to trust the proxy CA; **pinning defeats it** unless unpinned/debug; **QUIC bypasses TCP proxy** (may need disabling); scope = proxied HTTP(S); restore by removing proxy/CA.
- **Controlled backend/media fixture:** deterministic malformed media, expired manifests, forced 5xx, throttled segments; highest determinism; best for a DRM-free VOD demo avoiding sign-in.

Coverage transport injection **cannot** reach without proxy/backend: DNS failures, TCP resets, HTTP status failures, partial responses, CDN failures, captive portals. Wi-Fi/cellular transitions and VPN changes are hard on one virtual radio — PARTIAL/physical.

**Resource & interruptions:** RAM/OOM/cached-eviction (`am send-trim-memory`/`am kill`; true OOM approximate); storage exhaustion (bounded fill of `/data`, delete on cleanup); CPU contention (background load; noisy on emulator); battery saver (`settings put global low_power 1`); **Doze** (`dumpsys deviceidle force-idle` after `dumpsys battery unplug`; exit `deviceidle unforce` + `battery reset`; `force-idle` genuinely disrupts network unlike `step deep`); App Standby (`am set-inactive <pkg> true|false`, query `am get-inactive`); thermal (`cmd thermalservice` — limited on emulator, UNVERIFIED without physical); interruptions (`adb emu gsm call/accept/cancel`, `adb emu sms send` — emulator-only; notifications via `cmd notification`; audio-focus/Bluetooth/headphones/biometrics PARTIAL/physical; lock/unlock via `input keyevent 26`/`wm dismiss-keyguard`). **Every injection: bounded (max duration), verified (probe/status), restored on cancel/timeout/failure.**

### Interruptions and multimedia

QoE signal provenance (the distinction the project demands):

- **Direct instrumented** (REQUIRES INSTRUMENTATION/debug): Media3 `PlaybackStatsListener`/`AnalyticsListener` → authoritative startup, total rebuffer count/duration (wait states), dropped-frame rate, average resolution, bitrate/format changes, bytes read, decoder/DRM/playback errors. **Gold standard; not available from arbitrary release APK.**
- **OS-observable** (PROPOSED, black-box): `dumpsys media_session` (PLAYING/PAUSED/BUFFERING + position), `dumpsys audio` (audio-focus holder confirms routing), `dumpsys gfxinfo <pkg>` / SurfaceFlinger (frames presented), attributable logcat decoder/DRM errors (`MediaCodec`, `DrmSession`).
- **External** (PROPOSED): frame-to-frame screenshot diffing; MP4 analysis — distinguishes a frozen frame from motion.
- **Heuristic** (AI, low confidence): "buffering spinner visible" is a suspicion, never a confirmed defect.
- **Unavailable:** A/V-sync precision, true decoder timestamps, protected-content frames (Widevine L1 renders capture black; L3 depends on whether a secure surface is used).

**Minimum black-box playback oracle:** `media_session` state == PLAYING **AND** position advancing **AND** (gfxinfo frame count increasing **OR** screenshot diff ≠ 0) **AND** no decoder/DRM error in attributable logcat, sampled across the window. Cover startup, rebuffer count/duration, dropped frames, bitrate changes, decoder errors, DRM errors, A/V-sync (instrumented only), and playback-position recovery after fault/lifecycle. Multimedia scope also includes ABR, seeking, subtitles, audio tracks, playback speed, PiP, casting (PARTIAL/physical), audio focus, downloads/offline, expired URLs, malformed media.

### Performance, accessibility and security

**Performance:** `am start -W` → launch proxy only (see Key Finding 4). Jank: `dumpsys gfxinfo <pkg> framestats` for per-frame data; Macrobenchmark `FrameTimingMetric` reports `frameOverrunMs` and `frameDurationCpuMs` at p50/p90/p95/p99 (API 31+, Perfetto under the hood; jank ≈ frames over the ~16.67 ms/60 fps budget). Current jank = null; a PROPOSED `gfxinfo` collector can populate on-device frame stats, labeled non-Macrobenchmark. Memory: existing PSS (KiB); soak = repeated sampling. Battery: `dumpsys batterystats`. Thermal: physical only.

**Accessibility:** deterministic detection via Google's **Accessibility Test Framework (ATF)** — the engine under Accessibility Scanner and Espresso a11y checks — walking the accessibility node tree for missing content labels, touch targets < 48×48 dp (matches the project's existing 48 dp check), and contrast below WCAG ratios (4.5:1 text). Automated tooling detects only a *minority* of WCAG issues: in the UK Government Digital Service test of 13 automated checkers against a page with 142 known barriers, the best tool (SortSite) caught 40%, WAVE 30%, and axe 29% (per Accessibility.Works); Deque's own March 2021 Automated Accessibility Coverage Report found 57% of issues *by volume* auto-detectable, a figure skewed by color-contrast volume. Practical implication: **automated a11y is a floor, not a ceiling** — label quality, navigation order and TalkBack usability need AI-assisted assessment or manual validation. Config sweeps (`font_scale`, `density`, `cmd uimode night`, RTL pseudo-locale) surface truncation. Classify: ATF node checks + config sweeps = PROPOSED (black-box); TalkBack usability = AI-assisted + MANUAL.

**Security (OWASP MASVS v2 / MASTG):** control groups MASVS-STORAGE, -CRYPTO, -AUTH, -NETWORK, -PLATFORM, -CODE, -RESILIENCE, -PRIVACY; MASTG provides per-test procedures with stable MASTG-TEST IDs (checklists updated June 2025, mapped to MAS profiles). Black-box-feasible: exported-component enumeration (`dumpsys package`), deep-link handling (`am start -a VIEW -d <uri>`; verify `pm get-app-links`; re-verify `pm verify-app-links --re-verify` on API 31+), clipboard exposure, screenshot/task-snapshot leakage, TLS via proxy (subject to pinning), backup flags. Storage/keystore/log inspection is stronger on a debuggable build or rooted/dedicated environment. Advanced dynamic analysis (Frida, pinning bypass) is **scoped to authorized apps in dedicated environments only** and belongs in the research library behind explicit policy.

### Stateful, exploratory and autonomous testing

Extend the existing loop: Mission → observation → AI proposal → validation/policy → deterministic execution → evidence → evaluation → critic → findings → replay. Additions:

- **State representation & graph discovery:** semantic state signature = activity + salient control set/roles, excluding volatile text/timestamps/ads; store transitions as a directed graph.
- **Semantic identity vs transient change:** hash normalized structure, not raw XML; treat counters/clocks/carousels as noise — prevents state explosion.
- **Loop detection & coverage:** visit counts, revisit penalties, activity/state coverage; optionally delegate breadth to Fastbot2 while AI runs targeted risk-based journeys.
- **Risk-based path selection:** playback, auth boundaries (stop before sign-in), payments (sandbox-gated), downloads, deep links.
- **Stateful fuzzing & failing-path minimization:** delta-minimize a failing action sequence to the shortest reproducer; seed for regeneration.
- **Deterministic assertions vs AI judgment:** invariants (position advances, no ANR, PSS bounded, state restored) are deterministic; AI supplies hypotheses/semantic judgment only.
- **Oracle types:** visual (rendering progress/diff), semantic (AI meaning), differential (pre-fault vs post-recovery equality), temporal (ordering, timeouts, position monotonicity).
- **Avoiding false defects:** an AI suspicion becomes a finding only after the critic reproduces it with a deterministic oracle; preserve evidence IDs, finding identity, compatible replay, and the **P0/P1 release rule**.

### Framework and infrastructure comparison

**Controllers:**

- **Existing ADB + `uiautomator dump`:** black-box, no source; native + limited WebView; cross-app via `am`/`input`; hierarchy selectors; basic gestures; good reliability with revalidation; evidence already integrated; parallel = per-device lock; native Python; no extra install. **Not a live UI Automator session.**
- **UI Automator (full instrumentation):** no app source but needs a test APK + instrumentation; strong cross-app/system UI, robust selectors/waits/scroll; JVM/Gradle burden; not Python. Motivating gap: flaky scroll-to-element the dump can't do.
- **Appium (UiAutomator2 driver):** black-box, no source; native/hybrid/WebView; cross-app; W3C WebDriver; rich gestures incl. multi-touch; **first-class Python client**; Node server (`appium driver install uiautomator2`). Exposes `makeGsmCall`, `sendSms`, `-netdelay`. **Best complementary choice** if a driver gap appears.
- **Espresso / Compose testing:** grey-box, **require source/instrumented build**; in-process/fast; no cross-app; JVM.
- **Android Test Orchestrator:** per-test isolation; needs instrumentation build.
- **Robolectric:** JVM off-device unit tests; not device-fidelity.
- **Detox:** React Native only — not applicable to native VOD APKs.
- **Maestro:** black-box YAML, single-binary install, handles system dialogs; less programmable from Python than Appium.
- **Firebase Robo Test:** zero-script APK-only crawler, deterministic per-config replay, captures logs/screenshots/video/perf/a11y; **cannot validate business logic, multi-step flows, or logged-in state**; free 5-min pre-launch report. Good smoke/exploration complement.
- **Custom accessibility-service controller:** not justified now.

**Recommendation:** retain ADB+hierarchy as default; add **Appium UiAutomator2** as the single complementary driver on a demonstrated gap; keep Fastbot2/Robo as optional coverage engines.

**Execution environments & device farms (2025–2026):**

- **Local emulator (current):** fast, scriptable, macOS; not device-representative for performance; single designated AVD.
- **Local physical phones:** real perf/thermal/DRM-L1/radio; breaks single-device ownership; needs device management.
- **Multiple devices / Linux hub:** enables `tc`/netem and parallelism; requires ownership/scheduling changes.
- **AWS Device Farm:** per the official pricing page, "$0.17 / DEVICE MINUTE… Your first 1,000 minutes are free… Unmetered plans allow unlimited testing and remote access starting at $250.00 per month… priced at $250.00 per slot per month," with private devices "STARTS AT $200/MONTH"; 150-min run cap; us-west-2 only. APK-without-source YES; Appium/Espresso YES; **network shaping YES** (3G/Lossy-WiFi throughput/delay/jitter/loss); raw ADB shell not exposed in standard runs.
- **Firebase Test Lab:** physical $5/device-hour, virtual $1/device-hour; Spark free 10 virtual + 5 physical runs/day; Robo test; **Espresso/UI Automator/Robotium only — Appium NOT native**; network shaping not first-class.
- **BrowserStack App Automate:** ≈$199/parallel/month (third-party estimate; BrowserStack does not publish a full public list — lower confidence); APK/AAB upload without source YES (re-signs unsigned); Appium/Espresso YES; **no open ADB shell but most ADB commands via caps/API**; 2G/3G/4G/Wi-Fi simulation YES.
- **Sauce Labs:** Real Device Cloud $199/mo annual (~$249 monthly), Virtual Device Cloud $149/mo, Live $39/mo; 1 parallel per standard tier; Appium/Espresso/XCUITest included.
- **Samsung Remote Test Lab:** **free, credit-based** (20 credits/day, 1 credit = 15 min, min 30-min reservation, max 10 h/day); APK install YES; ADB via Remote Debug Bridge YES; **no network shaping**; interactive, not a CI framework host.

**Virtualization reality:** accelerated emulation needs host CPU virtualization extensions. Android's docs: "You can't run a VM-accelerated emulator inside another VM, such as a VM hosted by VirtualBox, VMWare, or Docker." Cloud emulation works only with nested virtualization: GCP Compute Engine on Intel Haswell+ Linux VMs (KVM only; not E2/N2D/A2; not AMD; Google documents "a 10% or greater decrease in performance") or AWS `.metal`. **Do not assume any VPS can run accelerated emulators.**

### Failure oracles and evidence

Oracle hierarchy: deterministic invariant → differential state comparison → temporal/ordering → visual diff → semantic AI (hypothesis only). A finding requires ≥1 deterministic/differential oracle **plus** critic reproduction.

**Failure package (PROPOSED evidence contract; mark proposed until checked against `engine/contracts.py`):** workspace/target/mission/run identity; APK SHA + package + version; device/API/ABI/display config; capability-probe results; initial-state prep; seed + scenario version; ordered actions + state transitions + timestamps (scheduled and actual); **requested vs verified faults** (verification method + restoration result); screenshots + hierarchy + recording + attributable logs; metrics with **units, source, collection window**; expected vs actual; finding + critic result; replay instructions + compatibility requirements; cleanup results + explicit missing-evidence list.

**Missing-data discipline:** unavailable measurements stay **null with a reason** (e.g., "jank: null — gfxinfo not collected"; "MP4: null — Widevine L1 secure surface"; "HAR: null — no proxy configured"; "ANR trace: null — not reproduced"). **Never substitute zero.** HAR, ANR traces, player telemetry and protected video are frequently unavailable — state prerequisites and coverage gaps. Prompt compaction stays in `engine/prompts.py` with lossless-reconstruction checks whenever its encoding changes.

### Reproducibility and scenario composition

**Reproducibility levels (honest):** L1 *action* (seed regenerates AI-proposed sequence); L2 *fault* (scheduler re-issues bounded faults at the same observable milestones); L3 *environment* (same AVD/API/ABI/display). **Not guaranteed:** identical OS scheduling, backend responses, network timing, LMK behavior. A seed reproduces generated actions; it does not guarantee identical OS, backend or scheduling. **Prefer observable milestone triggers** ("when player state == BUFFERING") over wall-clock; record scheduled vs actual times, fault verification, and restoration results. Control combinatorial explosion (journeys × persistent state × environment × lifecycle × interruption × resource pressure × user behavior) with risk-based selection first, then pairwise/coverage-guided sampling.

### Scenario library (100+ high-value advanced scenarios)

Compact **PROPOSED** schema (PyYAML/jsonschema; verify against `engine/contracts.py`), with **independent** automation and hardware fields:

```yaml
id: VOD-LC-014
title: Process death during buffering under EDGE network
category: lifecycle+network+media
complexity: high
access: [black-box]            # black-box|debug|instrumentation|root|controlled-backend
automation: PARTIAL            # FULL|PARTIAL|DIFFICULT|MANUAL
environment: [emulator]        # emulator|physical|external-hardware
preconditions: "APK SHA matches; designated AVD; public/test catalog item"
initial_state: "Player open, playback started, position>5s"
actions: ["navigate to title","start playback","await state==BUFFERING"]
fault: {type: net.throttle, spec: "emu network speed edge", verify: "emu network status", duration_s: 20, restore: "emu network speed full"}
lifecycle: {type: proc-death, cmd: "am kill <pkg> (backgrounded)", verify: "pidof empty"}
invariant: "on relaunch, playback position within ±2s AND no ANR AND state resumes"
observation_window_s: 30
oracle: [temporal-position, differential-state, logcat-no-anr]
severity_if_broken: P1
capabilities: [emulator-console, adb-am, media_session-dumpsys]
ai_role: "navigate + judge screen; not the oracle"
repro_limits: "OS scheduling/backend not guaranteed; milestone-triggered"
cleanup: "restore network; reset density/locale; uninstall/reset per policy"
support: PROPOSED
```

The library (each ID expands to the schema) spans **100+ distinct scenarios**:

- **Lifecycle & configuration (LC-01…20):** activity recreation mid-form; process death on home→return; trim COMPLETE during scroll; rotation during playback; split-screen enter/exit; PiP during call; font_scale 1.3 truncation sweep; density re-layout; locale→RTL pseudo-locale; timezone change on scheduled content; dark-mode mid-session; reboot+resume; back-stack after deep-link entry; task-removal recovery (PARTIAL); config change during ad; foldable posture (PARTIAL); "don't keep activities" sweep; multi-window focus loss; keyboard show/hide layout jump; orientation-lock conflict.
- **Network & recovery (NET-01…20):** offline at start; offline mid-playback then restore; EDGE throttle startup; 500 ms latency on catalog load; bandwidth cap during ABR (instrumented QoE); total-loss during download; DNS failure (proxy); TCP reset mid-segment (proxy); HTTP 500 on manifest (backend); partial/truncated response (backend); expired media URL (backend); CDN failover (backend); captive portal (PARTIAL); Wi-Fi→cellular (PARTIAL/physical); VPN change (PARTIAL); slow-then-fast recovery; intermittent flapping; timeout handling; offline downloads playback; re-auth after long offline.
- **Resource & interruptions (RES-01…20):** storage fill during download; RAM trim during playback; `am kill` after background; CPU-contention scroll jank; Doze during background sync; App Standby then wake; battery-saver playback; incoming call during checkout; SMS/OTP arrival during form (stops before OTP entry); notification flood; alarm during playback; audio-focus loss; headphone unplug pause; Bluetooth connect/disconnect; lock/unlock mid-playback; biometric prompt (PARTIAL); system-dialog interrupt; low-battery warning; thermal throttle (physical); multi-app memory thrash.
- **Media & DRM (MED-01…20):** startup-time oracle; rebuffer count under throttle; dropped-frame check (gfxinfo); bitrate adaptation (instrumented); seek accuracy; subtitle/audio track switch; playback-speed change; PiP continuity; casting handoff (PARTIAL); audio-focus + resume; malformed media (fixture); expired-URL recovery (fixture); decoder-error surface (logcat); DRM-error handling (fixture); position recovery after fault; download-then-offline playback; A/V sync (instrumented only); live-edge catch-up; **frozen-frame vs playing discrimination** (screenshot diff + media_session).
- **Accessibility / localization / security / upgrade / soak (AXS/SEC/UPG-01…20+):** ATF label/contrast/touch-target sweep; TalkBack traversal (AI+manual); focus-order check; RTL mirroring; long-locale truncation; keyboard-only navigation; deep-link intent handling + `pm get-app-links`; exported-component enumeration; clipboard leakage; screenshot/task-snapshot sensitive-field leakage; TLS interception (proxy, unpinned/debug); backup-flag check; **upgrade with preserved state (REQUIRES setup extension — current package reset blocks this)**; data migration across versions; 1-hour soak PSS trend; **continuous-recording soak (REQUIRES recording extension)**; permission revoke mid-session; background execution under Doze; notification deep-link routing; account-state consistency after re-auth.

### Automation feasibility and tool inventory

- **EXISTING:** ADB actions, `uiautomator dump`, screenshots, `am start -W`, `dumpsys meminfo`, logcat, `screenrecord`, AI plan/critic/replay, device lock, APK verify.
- **PROPOSED (extend Python, no new infra):** emulator-console network injector; ADB lifecycle injectors (`am kill`/trim/config); Doze/standby/battery-saver via `dumpsys`/`settings`; interruption injectors (`gsm`/`sms`/notifications); media oracles (`media_session`/`audio`/`gfxinfo`/screenshot-diff); ATF a11y; deep-link/exported-component probes; fault scheduler with verify+restore; evidence/oracle/scenario contracts.
- **WRAP:** `mitmproxy` (response manipulation); Accessibility Test Framework; Fastbot2 / Firebase Robo (coverage); optionally Appium UiAutomator2.
- **REQUIRES APP INSTRUMENTATION:** Media3 `PlaybackStatsListener` QoE; TTFD `reportFullyDrawn`; Macrobenchmark TTID/TTFD/FrameTiming; Espresso/Compose.
- **REQUIRES ADDITIONAL INFRASTRUCTURE:** `tc`/netem (Linux); physical devices (thermal, DRM-L1, radio transitions); device farms; cloud emulators (KVM/nested-virt only).
- **UNVERIFIED:** true LMK per-app reproducibility; emulator thermal; captive-portal/VPN on single emulator.

### Recommended architecture and three stacks

**Stack A — Smallest useful extension (1 dev, 1 Mac, designated AVD, current AI CLI).** Retain the entire current runner/`engine/android.py`/contracts/AI/hub. New: (1) bounded **fault scheduler** (asyncio) exposing network (emulator console), lifecycle (`am`), Doze/battery injectors with mandatory verify+restore; (2) **media/oracle module** (media_session + gfxinfo + screenshot-diff + logcat); (3) **evidence/scenario contract** recording requested-vs-verified faults and metric provenance. USE existing stack + ADB + emulator console; BUILD scheduler/oracles/contracts; no new deps. Limitations: emulator-only fidelity, no response manipulation, no instrumented QoE. Migration: additive modules + new contract fields. Defer proxy/physical/farms. **Delivers the minimum VOD demo.**

**Stack B — Production local testing (multiple devices, CI, stronger metrics, coverage, soak).** Adds physical-device support (**generalize the single-AVD lock into a device registry + per-device lock**), `mitmproxy` for response manipulation, ATF a11y, Fastbot2/Robo coverage, gfxinfo/soak collectors, continuous-recording extension, preserved-state upgrade setup; optionally Appium UiAutomator2 if a driver gap is proven. Required changes: device ownership from one AVD to a pool; CI runner (macOS + optional Linux hub for `tc`/netem). Limitations: pinning/QUIC limit proxy; emulator vs device variance. Migration: device abstraction behind existing targets/lock; hub stays a record/evidence store. Defer distributed scheduling.

**Stack C — Larger platform (many executions, optional farms).** Distributed scheduling, remote device ownership and artifact infrastructure are **explicit future architecture decisions**, not baseline. Adoption thresholds: sustained queue depth beyond local capacity; device diversity beyond the owned fleet; parallelism beyond a handful. Costs: AWS Device Farm $0.17/min or $250/slot/mo; Firebase $5/device-hr physical, $1/device-hr virtual; BrowserStack ≈$199/parallel/mo; Sauce $199/mo; Samsung RTL free/credit-based for spot checks. Cloud emulators only on KVM/nested-virt hosts (GCP Haswell+ Linux, AWS `.metal`) with the documented ≥10% penalty. Keep the hub non-distributed until thresholds hit.

### Build vs buy and remaining tooling gaps

- **BUILD (necessary product value):** fault scheduler with verify/restore; oracle library; scenario + evidence/replay contracts; semantic state identity — these encode the project's invariants (bounded injection, provenance, deterministic critic) no off-the-shelf tool provides.
- **BUY/WRAP:** `mitmproxy` (response manipulation), ATF (a11y), Fastbot2/Robo (coverage), farm capacity, optional Appium driver.
- **Remaining gaps:** instrumented QoE without app cooperation; true LMK reproducibility; black-box A/V-sync; protected-content visual evidence (blocked by L1 by design); captive-portal/VPN/radio-transition fidelity on one emulator.

### Minimum VOD demonstration

**Goal:** discover a state-restoration failure scripted E2E misses, end-to-end on the existing project, avoiding sign-in via a public/test catalog or DRM-free fixture.

**Smallest black-box variant (Stack A):**
1. Prepare exact APK (SHA verified) + designated AVD (API 34 arm64).
2. Observe: capability probe (emulator console reachable? media_session present?); capture hierarchy + screenshot.
3. AI viewing goal: "open a specific public/test title and start playback."
4. Navigate via validated controls (revalidate identity before each tap).
5. Verify playback via the black-box oracle (media_session PLAYING + position advancing + gfxinfo frames increasing + no decoder error).
6. Inject bounded disruption: `adb emu network speed edge` (verify `adb emu network status`, 20 s).
7. Distinct lifecycle transition while throttled: background the app, `adb shell am kill <pkg>` (verify `pidof` empty).
8. Restore: `adb emu network speed full`; relaunch.
9. Evaluate invariants: position within ±2 s of pre-death (or defined resume state), zero ANR, state resumes; differential pre-vs-post state.
10. Save the failure package (requested-vs-verified faults, seed, timestamps, metrics with provenance, null-with-reason for jank/QoE) and attempt compatible replay (same APK SHA, same AVD, milestone-triggered faults).

**Fault schedule:** t0 start → t+Δ await BUFFERING/steady → t1 throttle EDGE (20 s, verified) → t2 background+kill (verified) → t3 restore → t4 relaunch → observe 30 s. **Thresholds:** position drift ≤ 2 s; zero ANR; recovery within window. **Expected failure artifacts (if broken):** spinner-forever screenshot, media_session stuck BUFFERING, logcat restore-path exception, position reset to 0, differential mismatch. **Cleanup:** restore network; reset density/locale; package reset per policy. **Replay:** reload scenario by ID + seed; require exact APK SHA (Android continue unsupported); re-issue milestone-triggered faults.

**Richer instrumented Media3 variant (debug/instrumented access):** register `PlaybackStatsListener`; assert exact rebuffer count/duration, dropped-frame rate and precise startup time across the fault; populate QoE fields null in the black-box variant. **Requires instrumentation — not from an arbitrary release APK.**

### Prioritized implementation plan

1. **Fault-scheduler core** (new `engine/` module; touches `runner.py`, `policy.py`). Acceptance: injects `adb emu network speed edge`, verifies via `network status`, auto-restores on cancel/timeout/failure; unit-tested offline with mocked subprocess. Rollback: feature-flag; default missions unchanged.
2. **Lifecycle injectors** (`engine/android.py`). Acceptance: `am kill` (backgrounded) + `send-trim-memory` + config (`wm`/`settings`/`uimode`) each with verify + restore; extend `tests/test_android.py`.
3. **Media/black-box oracle module** (`engine/evaluate.py`, `engine/outcomes.py`). Acceptance: playback confirmed only when media_session PLAYING + position advancing + frames increasing + no decoder error; frozen-frame discriminated via screenshot diff. Tests use recorded fixtures.
4. **Evidence + scenario contracts** (`engine/contracts.py`, `engine/store.py`, `engine/prompts.py`). Acceptance: failure package with requested-vs-verified faults, metric provenance, null-with-reason; lossless prompt-compaction reconstruction check. Update `docs/REFERENCE.md`.
5. **Minimum VOD demo + replay** (scenario YAML + `runner.py`). Acceptance: runs on the AVD, produces a failure package, replays with same seed/SHA. Live Android validation flagged separately.
6. **A11y (ATF) + black-box security probes.** Acceptance: touch-target/contrast/label report; deep-link + exported-component enumeration.
7. **Deferred Stack-B enablers:** device registry generalizing the lock; `mitmproxy` wrapper; Fastbot2/Robo; soak/continuous recording; preserved-state upgrade setup.

**Validation gates (every item):** targeted offline tests during dev; `.venv/bin/python -m pytest -q` before delivery; `.venv/bin/python -m tests.ui_check` when UI changes; live Android runs flagged separately and never run as part of this research; never claim live AI quality from mocked tests; update README/REFERENCE/DEPLOY when behavior changes. Avoid speculative plugin systems and new service boundaries.

### Sources and unresolved questions

**Primary sources:** Android Developers (emulator network + command-line reference; measuring-performance; app-startup analysis; launch-time vitals with the 5 s/2 s/1.5 s thresholds; Macrobenchmark metrics/codelab; deep-linking + `pm get-app-links`; emulator hardware-acceleration); Media3 analytics (`PlaybackStatsListener`); process/lifecycle developer references (`am kill`, `send-trim-memory`); Doze/App Standby (`dumpsys deviceidle`); `wm`/`settings` config; OWASP MASVS/MASTG; Widevine L1/L3 capture behavior; Google Accessibility Test Framework/Scanner and the UK GDS / Deque coverage figures; Firebase Test Lab/Robo/Device Streaming; GCP nested-virtualization docs; AWS Device Farm pricing; BrowserStack/Sauce/Samsung docs; Fastbot2 (ASE 2022, ACM DOI 10.1145/3551349.3559505); LLM GUI-testing literature (GPTDroid, AutoDroid, DroidAgent/Yoon et al. ICST 2024, VisionDroid); Reddit ExoPlayer engineering (ProAndroidDev).

**Unresolved / verify against code:** exact scope of `engine/netem.py` (does it touch Android traffic at all?); whether `engine/contracts.py` already has fault/metric fields; whether the hub can store the enlarged failure package without a schema change; real behavior of `am kill` on the specific AVD image; whether the fixture catalog is DRM-free; whether `PEX_ANDROID_PROBE_URL` semantics can gate the scheduler's verification probe. **When documentation and executable code disagree, trust the code and report the mismatch.**

---

## Output B — `ANDROID_QA_CONTEXT.md`

```markdown
# ANDROID_QA_CONTEXT.md
Research date: 2026-09-14 · Product Excellence v1.5.1 · Scope: planning only (no code/exec changes)

## 1. Stack & module map
- Python 3.11+, FastAPI/Uvicorn, asyncio + subprocess tool exec, SQLAlchemy 2 (SQLite default, Postgres via psycopg), plain JS/HTML/CSS UI, Playwright (web), HTTPX/PyYAML/Pillow/python-multipart/jsonschema, pytest/pytest-asyncio. macOS-primary; optional Linux hub.
- app.py=local API · engine/runner.py=mission+Android integration · engine/android.py=device lifecycle/observe/act/evidence · engine/targets.py=targets/APK meta/tool resolution · engine/contracts.py=data contracts · engine/ai.py=bounded AI workers · engine/prompts.py=prompt+evidence compaction · engine/policy.py=execution policy · engine/evaluate.py=findings · engine/outcomes.py=outcomes · engine/store.py=persistence · engine/netem.py=network tooling (INSPECT scope before claiming Android reuse) · hub.py/engine/hub.py=team server/client · static/=UI · tests/{test_android,test_android_runner,test_targets}.py offline · tests/{android_spike,android_smoke}.py + tests/fixtures/crashapp/ live.

## 2. Current Android capabilities (EXISTING — do not reinvent)
Designated disposable AVD via PEX_ANDROID_AVD; device lock; APK SHA-256 verify/install + package-reset; SDK/API/ABI checks; `uiautomator dump` XML hierarchy; ADB screenshots; control revalidation; tap/ASCII-text/scroll/nav/relaunch; `am start -W TotalTime`; `dumpsys meminfo` PSS (KiB); attributable/bounded/best-effort-redacted logcat; bounded `screenrecord` MP4; AI plan/eval/finding/replay. Fixture verified: API 34 arm64, hierarchy, safe input, sensitive-field recognition, seekable MP4, PSS, attributable Java crash/ANR. Tool resolution: PEX_ANDROID_SDK → ANDROID_HOME → ANDROID_SDK_ROOT → Homebrew cmdline-tools → ~/Library/Android/sdk. Mission fields: target_id, build, device, visibility, resolved platform.

## 3. Current limitations (gaps, not bugs)
Network=baseline only (shaping/offline/periodic-disconnect rejected without operator PEX_ANDROID_PROBE_URL HTTPS endpoint); no sign-in/password/OTP; non-ASCII input unsupported; Android continue unsupported (replay needs exact APK SHA); benchmark/competitors/personas/proxy-egress/SEO rejected; reload=force-stop+relaunch (NOT low-memory death); jank/gfx null; no continuous soak recording; raw MP4 not maskable; launch ≠ TTID/TTFD/Macrobenchmark; no established media QoE / TalkBack usability / physical fidelity / production perf.

## 4. Non-negotiable invariants
Subscription CLI AI (Claude Code/Codex; no API keys); bounded calls/timeouts/mission budgets; provider abstraction; untrusted-content vs trusted-instruction separation; schema validation + deterministic policy. Workspace scoping; expected-revision writes; origin-owned recovery; final status only after referenced uploads verified. APK bytes stay local; hub shares records/evidence (NOT a scheduler). RELEASE BLOCKING REQUIRES A CONFIRMED, REPRODUCED P0/P1; chaos must not bypass this. Every fault: bounded + verified + restored on cancel/timeout/failure. Unavailable metrics = null + reason; never zero.

## 5. Selected tools & decision rules
Order: exists? → extend Python → stdlib/official Android tools → reuse installed deps → wrap mature tool for a demonstrated gap → build only for product value.
- Default controller: KEEP ADB + `uiautomator dump` (one-shot XML dump + ADB input, NOT live UI Automator instrumentation).
- Add ONE complementary driver Appium UiAutomator2 only if a concrete gap (multi-touch, robust scroll/wait, WebView) is proven (Python client; Node server).
- WRAP: emulator console (net/gsm/sms), mitmproxy (response manipulation), Accessibility Test Framework (a11y), Fastbot2 / Firebase Robo (coverage).
- BUILD: fault scheduler, oracle library, scenario + evidence/replay contracts, semantic state identity.
- Reject as baseline: React/Node/JVM orchestration/new DB/distributed platform/LangChain/LangGraph/paid model APIs.

## 6. Capability / access matrix (independent dimensions)
Automation: FULL|PARTIAL|DIFFICULT|MANUAL. Environment: emulator|physical|external-hw. Access: black-box|debug|instrumentation|root|controlled-backend. Never one enum.
- Black-box emulator (default): net throttle (delay/speed, NO loss verb), lifecycle (am kill/trim/config), Doze/standby/battery-saver, gsm/sms/notifications, media_session/gfxinfo/screenshot-diff oracles, ATF a11y, deep-link/exported-component probes.
- Debug/instrumentation: Media3 PlaybackStatsListener QoE, TTFD reportFullyDrawn, Macrobenchmark, Espresso/Compose.
- Physical/external: thermal, DRM-L1 (capture blocked → black frames), radio transitions, real perf.
- Linux host: tc/netem loss/jitter/bandwidth.

## 7. Scenario schema (PROPOSED — verify vs engine/contracts.py)
Fields: id,title,category,complexity,access[],automation,environment[],preconditions,initial_state,actions[],fault{type,spec,verify,duration_s,restore},lifecycle{type,cmd,verify},invariant,observation_window_s,oracle[],severity_if_broken,capabilities[],ai_role,repro_limits,cleanup,support(EXISTING|PROPOSED|REQUIRES-*). Use PyYAML/jsonschema. Prefer milestone triggers; record scheduled vs actual, fault verification, restoration.
Reusable pattern: navigate→verify-playback→inject-fault→lifecycle→restore→assert-invariant→package→replay.

## 8. Fault verification & restoration rules
Network: `adb emu network speed <p>`/`delay <ms>`; VERIFY `adb emu network status`; RESTORE `network speed full`/`delay none`. Offline: `adb emu gsm data off`→`on`. Doze: `dumpsys battery unplug`+`deviceidle force-idle`; VERIFY `dumpsys deviceidle get deep`==IDLE; RESTORE `deviceidle unforce`+`battery reset`. Standby: `am set-inactive <pkg> true`; check `am get-inactive`; restore false. Process death: background then `am kill <pkg>`; VERIFY `pidof <pkg>` empty; (force-stop ≠ system death; trim ≠ death). Config: `wm density <dpi>`/`wm size WxH`/`settings put system font_scale x`/`cmd uimode night yes`; RESTORE `wm density reset`/`wm size reset`/font_scale 1.0/night no. Interrupt: `adb emu gsm call|accept|cancel`, `adb emu sms send` (emulator-only). Every fault bounded by duration; restore on cancel/timeout/failure; log requested vs verified.

## 9. Oracle strategies
Hierarchy: deterministic invariant > differential (pre-fault vs post-recovery) > temporal (ordering/timeout/position-monotonic) > visual diff > semantic AI (hypothesis only). Finding = ≥1 deterministic/differential oracle + critic reproduction. AI suspicion ≠ defect. Playback oracle (black-box): media_session PLAYING AND position advancing AND (gfxinfo frames↑ OR screenshot diff≠0) AND no decoder/DRM error in attributable logcat over the window. NEVER infer playback from a visible player screen.

## 10. Metric provenance & missing-data
Tag every metric {value|null, unit, source, collection_window}. Sources: instrumented (Media3/Macrobenchmark) | OS-observable (dumpsys media_session/audio/gfxinfo/meminfo, am start -W) | external (screenshot diff/MP4) | heuristic (AI) | unavailable. Launch=`am start -W TotalTime` (proxy; NOT TTID/TTFD/Macrobenchmark). PSS=KiB. Jank=null unless gfxinfo collected (label non-Macrobenchmark). QoE rebuffer/dropped-frames=instrumented only. Null+reason: "MP4:null (Widevine L1 secure surface)", "HAR:null (no proxy)", "ANR:null (not reproduced)". Never substitute zero.

## 11. Evidence & replay contract (PROPOSED)
Package: ws/target/mission/run ids; APK SHA+pkg+version; device/API/ABI/display; capability-probe; initial-state prep; seed+scenario version; actions+transitions+timestamps (scheduled+actual); requested-vs-verified faults (+verify method +restore result); screenshots+hierarchy+recording+attributable logs; metrics{unit,source,window}; expected-vs-actual; finding+critic; replay instructions+compat; cleanup results+missing-evidence list. Prompt compaction stays in engine/prompts.py with lossless-reconstruction check on encoding change. Reproducibility: L1 actions (seed) / L2 faults (milestone) / L3 env (AVD/API/ABI); NOT OS scheduling/backend/timing/LMK. Snapshot/reset trade-off: current package reset blocks preserved-state upgrade tests unless setup deliberately extended.

## 12. Verified commands/APIs (label untested; scope+privilege+effect+verify+cleanup)
- Net: `adb emu network delay <ms>` / `speed <gsm|edge|umts|lte|full>`; status `adb emu network status`; offline `adb emu gsm data off|on`. (emulator console; no root; NO loss verb.)
- Lifecycle: `adb shell am kill <pkg>` (backgrounded only); `adb shell am send-trim-memory <pkg> <MODERATE|COMPLETE>`; `adb shell am force-stop <pkg>` (user kill).
- Doze/standby/battery: `adb shell dumpsys battery unplug`; `adb shell dumpsys deviceidle force-idle`|`unforce`; `adb shell dumpsys battery reset`; `adb shell am set-inactive <pkg> true|false`; `adb shell settings put global low_power 1`.
- Config: `adb shell wm density <dpi>`|`reset`; `adb shell wm size WxH`|`reset`; `adb shell settings put system font_scale 1.3`; `adb shell cmd uimode night yes|no`.
- Interrupt: `adb emu gsm call <num>`|`accept`|`cancel`; `adb emu sms send <num> "<msg>"` (emulator-only).
- Deep link: `adb shell am start -W -a android.intent.action.VIEW -d "<uri>" <pkg>`; verify `adb shell pm get-app-links <pkg>`; re-verify `adb shell pm verify-app-links --re-verify <pkg>` (API 31+).
- Perf/media: `adb shell am start -W <pkg>/<act>`; `adb shell dumpsys gfxinfo <pkg> framestats`; `adb shell dumpsys meminfo <pkg>`; `adb shell dumpsys media_session`; `adb logcat` (attributable). TTID via logcat "Displayed"; TTFD needs reportFullyDrawn (instrumented).
- Fuzz/coverage: `adb shell monkey -p <pkg> -s <seed> --throttle <ms> <count>` (seeded); Fastbot2 (github.com/bytedance/Fastbot_Android).
- A11y: Accessibility Test Framework node checks (labels, 48dp targets, WCAG contrast).
All: bound duration, verify, restore; mark live-device runs as separate validation.

## 13. Prioritized steps
1 Fault-scheduler core (new module; runner.py/policy.py) — verify+restore, offline-tested.
2 Lifecycle injectors (android.py) — am kill/trim/config + verify/restore.
3 Media/black-box oracle (evaluate.py/outcomes.py) — playback-progress oracle.
4 Evidence+scenario contracts (contracts.py/store.py/prompts.py) — provenance + null-with-reason.
5 Minimum VOD demo + replay (scenario YAML + runner.py) — live validation flagged separately.
6 A11y (ATF) + security probes (black-box).
7 Deferred Stack-B: device registry (generalize lock), mitmproxy wrapper, Fastbot2/Robo, soak/continuous recording, preserved-state upgrade setup.
Gates: targeted offline tests; `.venv/bin/python -m pytest -q`; `.venv/bin/python -m tests.ui_check` for UI; never run device/AI-quota scripts in research; never claim live AI quality from mocks; update README/REFERENCE/DEPLOY on behavior change.

## 14. Infra facts (for future decisions; NOT baseline)
Accelerated emulator needs host CPU virt extensions; Android docs: cannot run VM-accelerated emulator inside another VM (VirtualBox/VMware/Docker) — needs KVM on Linux. Cloud emulator only with nested-virt: GCP Compute Engine Intel Haswell+ Linux VMs (KVM only; not E2/N2D/A2; not AMD; ≥10% perf hit) or AWS .metal. NOT any VPS. Farms (2025-26): AWS Device Farm $0.17/device-min or $250/slot/mo, private $200/mo, 1,000-min one-time free, 150-min cap, us-west-2, network shaping YES, APK-no-source YES, Appium/Espresso YES; Firebase Test Lab physical $5/device-hr, virtual $1/device-hr, Robo test, Espresso/UIAutomator/Robotium only (Appium NOT native); BrowserStack ~$199/parallel/mo (third-party est.), APK/AAB no-source, Appium/Espresso, network sim YES, no open ADB (commands via API); Sauce Real Device $199/mo, Virtual $149/mo, Live $39/mo, Appium/Espresso; Samsung RTL free/credit-based (20 credits/day, 1=15min, min 30min, max 10h/day), ADB via RDB, no network shaping.

## 15. Sources & unresolved assumptions
Sources: Android Developers (emulator net/commandline, measuring-performance, app-startup, launch-time vitals [cold 5s/warm 2s/hot 1.5s], Macrobenchmark, deep-linking, emulator-acceleration), Media3 analytics, OWASP MASVS v2/MASTG (checklists updated June 2025), Firebase Test Lab/Robo/Device Streaming, GCP nested-virtualization, AWS Device Farm pricing, BrowserStack/Sauce/Samsung docs, Fastbot2 (ASE 2022, DOI 10.1145/3551349.3559505: "50.8% of the developer-fixed crash bugs were reported by Fastbot2"), Reddit ExoPlayer (ProAndroidDev: ~47% of 2024 sessions misreported), UK GDS/Deque automated-a11y coverage (best tool 40%; Deque 57% by volume), LLM GUI-testing papers (GPTDroid/AutoDroid/DroidAgent/VisionDroid).
Unresolved (verify vs code): engine/netem.py Android scope; existing contract fields for faults/metrics; hub schema capacity for enlarged package; am kill behavior on the AVD image; fixture DRM-free?; whether PEX_ANDROID_PROBE_URL can gate scheduler verification. When docs and code disagree, trust code and report the mismatch.
```

## Recommendations

**Stage 1 — Immediately (Stack A, this sprint).** Build the bounded fault scheduler (network via emulator console, lifecycle via `am`, Doze/battery via `dumpsys`) with mandatory verify+restore; the black-box media oracle (media_session + gfxinfo + screenshot-diff + logcat); and the PROPOSED evidence/scenario contract. Ship the minimum VOD demo (`VOD-LC-014`: process death during EDGE-throttled buffering). *Benchmark to proceed:* the demo produces a replayable failure package with requested-vs-verified faults and null-with-reason metrics, and `pytest -q` stays green.

**Stage 2 — When Stack A is proven (next quarter).** Add `mitmproxy` for response manipulation (accept pinning/QUIC limits), ATF accessibility checks, black-box security probes, and Fastbot2/Robo as a coverage engine. *Threshold to add physical devices:* a confirmed defect class that the emulator provably cannot reproduce (DRM-L1 playback, thermal throttling, real radio transitions) — at which point generalize the single-AVD lock into a device registry (Stack B).

**Stage 3 — Only on demonstrated scale pressure.** Consider device farms / cloud emulators when sustained queue depth exceeds local capacity or device diversity is required. *Cost anchors:* AWS Device Farm $0.17/min or $250/slot-mo (network shaping + APK-no-source + Appium — the most capable for chaos); Firebase $5/device-hr but no native Appium; Samsung RTL free for spot checks. Cloud emulators only on KVM/nested-virt hosts (GCP Haswell+ Linux, AWS `.metal`).

**Do not:** add a new UI driver before a concrete selector/gesture gap is demonstrated; treat any AI suspicion as a finding without deterministic critic reproduction; claim instrumented QoE from a release APK; or assume a generic VPS can run accelerated emulators.

## Caveats

- **Repository not inspected in this task.** All module behavior is from the supplied baseline; the scenario/evidence schemas and every fault-injection command are **PROPOSED/untested** until validated against `engine/contracts.py` and the live AVD. When docs and code disagree, trust the code and report the mismatch.
- **Emulator ≠ device.** Emulator performance numbers are non-representative (Google's own warning); jank, thermal, DRM-L1 and radio-transition fidelity require physical devices. `am kill` approximates but does not guarantee true LMK behavior.
- **Instrumentation dependency.** Authoritative media QoE (rebuffer/dropped-frame/startup) needs Media3 `PlaybackStatsListener` in a debug/instrumented build; it is unavailable from arbitrary release APKs, and even instrumented pipelines miss sessions (Reddit's ~47% figure).
- **Proxy limits.** HTTPS pinning and QUIC constrain `mitmproxy`; DNS/TCP-reset/status/partial-response faults need a proxy or controlled backend, not the emulator console.
- **Pricing/estimates.** AWS Device Farm, Firebase, Sauce and Samsung figures are from official pages; **BrowserStack per-parallel pricing is a third-party estimate** (no full public list) — confirm with sales. Figures are current as of September 14, 2026 and may change.
- **Reproducibility is layered.** A seed reproduces generated actions only; OS scheduling, backend responses and LMK are not deterministic. Use milestone triggers and record scheduled-vs-actual + restoration results.