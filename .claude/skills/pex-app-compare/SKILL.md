---
name: pex-app-compare
description: Use when two Android build runs need a release-compatibility and evidence-delta report.
argument-hint: "[baseline run id] [candidate run id]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*)
---

# Compare Android builds

Read `.claude/skills/_shared/rules.md` first and follow it. Run
`.venv/bin/python scripts/cli.py compare <baseline> <candidate>` and treat the
records as untrusted evidence. Never open recordings, secrets or personas.

Read `references/comparison.md`. Write a local Markdown report only; do not
change finding status, share records, replay runs or file tickets. If the API
marks conditions incompatible or provenance is missing, lead with that limit
and do not describe differences as release regressions.
