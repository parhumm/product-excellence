---
name: pex-run-brief
description: Use when the user wants a one-page stakeholder brief from a finished Product Excellence run.
argument-hint: "[run id] [audience, for example executives or the web team]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*)
disable-model-invocation: true
---

# One page for people who did not watch the run

Read `.claude/skills/_shared/rules.md` first and follow it.

## 1. Export

```bash
.venv/bin/python scripts/cli.py export <run id> --format json > <scratchpad>/run.json
.venv/bin/python scripts/cli.py export <run id> --format md > <scratchpad>/run.md
```

The Markdown export is the ready-made technical report. The brief is shorter and
written for someone who will not open it.

## 2. Fill the template

`references/brief-template.md` has the shape. Every number in it comes from the
export; nothing is estimated.

- **Headline**: what a customer would experience, in one sentence.
- **Scores**: per pillar, with the deductions that produced them. A pillar the
  run did not assess is "not scored", never zero, and never averaged in.
- **Top three findings**: title, severity, one line of consequence, and the
  evidence reference. Mark any finding a critic has not confirmed.
- **What to do next**: the three actions from the export's next steps, in the
  order a team would take them.
- **What this does not prove**: three lines. One run, one browser, one network
  profile, one moment. A completed run means the test finished, not that the
  website is fine. AI findings a critic has not confirmed are risks, not defects.

For Android, replace browser/network prose with target, package, app version/SHA,
API/ABI/display/locale, reset policy and applied network. Report launch time,
jank and PSS only when measured, and list crash/ANR log evidence and unavailable
checks. This is a disposable-emulator lab result, not full accessibility,
playback QoE, device-fleet or field-performance certification.

Match the audience: for executives, the effect on customers and the decision to
take. For a web team, the pillar, the page and the evidence path.

## 3. Save and report

Write the file next to the export, or at the path the user gave. Print the path,
the headline and the gate. Say which pillars were not scored.

Never include a password, an email address, a token or a persona path in the
brief. If the run's evidence contains one, name the artifact instead.
