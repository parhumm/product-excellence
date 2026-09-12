# Feature status

Product Excellence is an internal release for testing authorized websites. It
ships no customer, competitor or site-specific workspace, preset, fixture or
historical run record.

| Capability | Delivery state |
| --- | --- |
| Local console and SQLite/PostgreSQL history | Implemented and covered offline |
| Chromium, Firefox and WebKit | Covered on the local fixture |
| Codex and Claude subscription workers | Implemented; authentication and quota still depend on the local CLI account |
| Per-mission worker, model, effort and account selection | Covered offline and exposed in the console, API and YAML |
| Dynamic model routing with a mission ceiling | Covered offline; live quality and speed are not certified |
| Screenshots, DOM, HTTP, trace, JSON and video evidence | Implemented and covered offline |
| Five evaluation pillars and deterministic release gate | Implemented and covered offline |
| Ten generic starter missions per workspace | Created on first use and not recreated after deletion |
| Benchmark and competitor review | Implemented; competitor failures remain missing rather than zero |
| Workspace-scoped missions, runs, findings, schedules and comparisons | Covered offline |
| Shared team server, revision conflicts and evidence upload recovery | Covered by offline and isolated integration tests |
| Mission import, versions, schedules, CLI and reports | Covered offline |
| Network profiles, disconnects and Linux netem controls | Implemented; packet-level controls require the Linux runner |
| Test personas and mission credentials | Stored locally with restricted permissions; no credentials are bundled |
| Payments, publishing and destructive browser actions | Refused by policy |
| Full Schema.org validation | Not implemented; local vocabulary checks are narrower |
| Statistical quality targets | Not established by deterministic or smoke tests |

The default verification command is:

```bash
.venv/bin/python -m pytest -q
```

The isolated browser check is:

```bash
.venv/bin/python -m tests.ui_check
```

Live browser scripts and AI-enabled missions may use external services or
subscription quota. Run them only for an authorized target.

## Claude Code skills

Eight skills live under `.claude/skills/` and are documented in
`docs/SKILLS.md`. `tests/test_skills.py` checks their front matter, references
and documented names. The skills do not bundle site-specific missions or data.
