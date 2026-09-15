# Implementation plans

| Plan | Priority | Effort | Status |
|---|---|---|---|
| [001 — Proxy routes and link speed](001-proxy-route-switching.md) | P1 | L | Done |

Reviewed 2026-09-15 at `cc4fae1` plus noted working-tree edits. The plan supersedes
the previous contents of `/Users/parhumm/.claude/plans/structured-mixing-hare.md`.
Implemented 2026-09-15 in `85c2657`..`1559713`, all stages in order, both platforms.
The Android transport gate passed on emulator 36.6.11.0 — routing works on Wi-Fi and
cellular, shaping on cellular only — and the live web and Android acceptance runs passed;
transcripts are in `artifacts/android-gate/` and `artifacts/route-live/`.

Rejected shortcuts: system-proxy fallback, unframed HTTP forwarding, probe-only proof
of app routing, symmetric restoration of asymmetric rates, and a fixed relay line budget.
