---
name: pex-env-check
description: Use when Product Excellence will not start, has no AI worker, or the user asks if the Mac is ready.
argument-hint: "(no arguments)"
allowed-tools: Read, Bash(.venv/bin/python scripts/cli.py:*), Bash(curl -s http://127.0.0.1:*), Bash(claude auth status), Bash(codex login status), Bash(ls:*), Bash(./scripts/setup.sh)
---

# Is this Mac ready to run tests?

Answer in one table, then offer only the safe fixes.

Read `.claude/skills/_shared/rules.md` first and follow it.

## What the app reports

- App health: !`.venv/bin/python scripts/cli.py health`
- Team server: !`curl -s http://127.0.0.1:8741/api/hub/status`

If those two lines are empty or refused, the app is not running. Say so, give
`./start.command` as the fix, and stop; nothing below is meaningful without it.

## 1. Check the rest

```bash
claude auth status
codex login status
ls ~/.cache/ms-playwright
ls -l data/runtime.lock
```

From `health`, read the version, the browsers, the network profiles and the `ai`
block. From `hub/status`, read whether a team server is configured and how many
uploads are pending.

## 2. Report one table

| Item | State | What to do |
| --- | --- | --- |

One row each for: the app, the version, an AI worker (Claude or Codex), the
Playwright browsers, Android SDK/designated AVD status from `health.android`,
the data directory lock, the team server connection, and pending uploads. An
Android failure does not make a web-only console unready. Say "ready" or the
exact problem, never a guess.

`references/fixes.md` maps each failure to the fix the README gives. Use its
wording so the user sees the same advice twice.

## 3. Offer the safe fixes

Only these, and only after the user agrees:

- `./scripts/setup.sh` for missing or broken browsers. Safe to repeat.
- `./scripts/setup.sh --android` for missing Android tooling. It may prompt for
  SDK licences; never accept those licences on the user's behalf.
- Retry pending uploads: `curl -s -X POST -H 'X-PEX-Request: 1' http://127.0.0.1:8741/api/hub/retry`

Never delete or move anything under `data/`. Never sign anyone in or out. If the
lock file is held by a second copy of the app, say which terminal window to use
and let the user close it.

Finish with one line: ready to run, or the single thing blocking a run.
