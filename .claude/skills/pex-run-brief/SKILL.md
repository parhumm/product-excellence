---
name: pex-run-brief
description: Use when the user wants a shareable report of a finished Product Excellence run, with screenshots.
argument-hint: "[run id] [audience, for example executives or the web team]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*), Bash(.venv/bin/python .claude/skills/pex-run-brief/scripts/build_report.py:*)
disable-model-invocation: true
---

# A report for people who did not watch the run

A run page proves what happened. A report makes someone act on it. It shows the
screens the visitor saw, says what to improve first, and stays inside the
evidence.

Read `.claude/skills/_shared/rules.md` first and follow it.

## 1. Export

```bash
.venv/bin/python scripts/cli.py export <run id> --format json > <scratchpad>/run.json
.venv/bin/python scripts/cli.py export <run id> --format md > <scratchpad>/run.md
```

The Markdown export is the ready-made technical report. This report is shorter,
visual, and written for someone who will not open it.

## 2. Read the run before writing about it

Read the export and the screenshots in the run's artifact folder. Look at the
pages themselves, not only the findings list: a screen can show a problem no
check recorded, and a finding can claim something the evidence contradicts.

For each screen, note what already helps the visitor and what gets in the way.

## 3. Write the narrative

`references/report-outline.md` gives the JSON shape and the rules each field
carries. Write it to the scratchpad. It holds only judgment:

- **headline**: what a visitor would experience, in one sentence.
- **improvements**: three to eight, ranked by how close each sits to the decision
  the journey asked the visitor to make. For each: what you saw, why it costs
  something, and one change worth testing. Mark each `confirmed`, `screenshot`
  or `unverified`, and say in the report that the ranking is yours, not the app's.
- **journey**: the stages worth showing, in order, each with its evidence id.
- **corrections**: where the run's own AI summary disagrees with its evidence.
  A critic's PROBABLE is not a confirmation, and an AI narrative's severity is
  not the app's severity.
- **not_covered**: what the mission deliberately skipped.

Every number, score, deduction, page address and screenshot comes from the
record, and the script writes those. Do not estimate any of them, and do not
invent a conversion effect: name it as a hypothesis to test.

For Android, replace browser and network prose with target, package, app version
and SHA, API, ABI, display, locale, reset policy and applied network. Report
launch time, jank and PSS only when measured, and list crash and ANR log evidence
and unavailable checks. This is a disposable-emulator lab result, not full
accessibility, playback QoE, device-fleet or field-performance certification.

Match the audience: for executives, the effect on customers and the decision to
take. For a web team, the pillar, the page and the evidence.

## 4. Build

```bash
.venv/bin/python .claude/skills/pex-run-brief/scripts/build_report.py <run id> \
  --narrative <scratchpad>/narrative.json --out <path>.html
```

It embeds the screenshots, so the file opens anywhere without the evidence
folder, and it refuses a narrative that cites evidence the run does not contain.
Without `--out` it writes `report.html` beside the run's artifacts.

## 5. Report

Print the path, the headline and the gate. Say which pillars were not scored, and
which improvements are unverified.

A completed run means the test finished, not that the website is fine. Never
include a password, an email address, a token or a persona path. If the run's
evidence contains one, name the artifact instead.
