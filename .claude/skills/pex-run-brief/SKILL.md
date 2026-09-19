---
name: pex-run-brief
description: Use when the user wants a brief or a shareable screenshot report of a finished Product Excellence run.
argument-hint: "[run id, or several benchmark run ids] [audience, for example executives or the web team]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*), Bash(.venv/bin/python .claude/skills/pex-run-brief/scripts/build_report.py:*)
disable-model-invocation: true
---

# For people who did not watch the run

A run page proves what happened. This skill makes someone act on it, in one of
two shapes. Both stay inside the evidence.

- **The one-page brief**, Markdown, for pasting into a ticket or a message.
  `references/brief-template.md`. Default when the user says brief, summary, or
  names somewhere it has to be pasted.
- **The report**, a standalone HTML file with the screens embedded, for sending
  to someone who will read it rather than copy it. Default when the user says
  report, asks for screenshots, or names benchmark runs.

Ask which one only if neither is implied. Sections 1 and 2 apply to both; then
take section 3 for the brief, or sections 4 to 6 for the report.

Read `.claude/skills/_shared/rules.md` first and follow it.

## 1. Export

```bash
.venv/bin/python scripts/cli.py export <run id> --format json > <scratchpad>/run.json
.venv/bin/python scripts/cli.py export <run id> --format md > <scratchpad>/run.md
```

The Markdown export is the ready-made technical report. Both the brief and the
report are shorter and written for someone who will not open it.

## 2. Read the run before writing about it

Read the export and the screenshots in the run's artifact folder. Look at the
pages themselves, not only the findings list: a screen can show a problem no
check recorded, and a finding can claim something the evidence contradicts.

For each screen, note what already helps the visitor and what gets in the way.

## 3. The one-page brief

`references/brief-template.md` has the shape. Every number in it comes from the
export; nothing is estimated.

- **Headline**: what a customer would experience, in one sentence.
- **Scores**: per pillar, with the deductions that produced them. A pillar the
  run did not assess is "not scored", never zero, and never averaged in.
- **Top three findings**: title, severity, one line of consequence, and the
  evidence reference. Mark any finding a critic has not confirmed.
- **What to do next**: the three actions from the export's next steps, in the
  order a team would take them.
- **What this does not prove**: three lines. One run, one network profile, one
  moment, on one browser for a web run or one emulated device for an Android run.
  A completed run means the test finished, not that the website, or for Android
  the app, is fine. AI findings a critic has not confirmed are risks, not
  defects. An Android brief adds the disposable-emulator line and leaves out the
  mission's `browser` and `viewport` defaults, which never applied.

Write the file next to the export, or at the path the user gave, then go to
section 6. The rest of this file is the report.

## 4. Write the narrative

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

For Android the script writes the conditions itself — target, package, app
version and SHA, API, target SDK, ABI, display, density, locale, renderer and
applied network — and reports launch time, jank and PSS only where the emulator
measured them. Do not restate them. An Android mission still carries the web
defaults `browser: chromium` and `viewport: desktop`; they never applied, so
never repeat them from the export. What is left for you: crash and ANR log
evidence, and the checks that were unavailable. The report says on its own that
this is a disposable-emulator lab result, not full accessibility, playback QoE,
device-fleet or field-performance certification.

Match the audience: for executives, the effect on customers and the decision to
take. For a web team, the pillar, the page and the evidence.

### Benchmark runs

A benchmark run gets a different report: a playbook, not a journey. Its reader
wants to know, for each thing worth fixing, who already does it well and what
exactly to copy. Several benchmark runs can share one report, usually one run
per page type, because a benchmark review sees only the last screen of each site.

Write the narrative from `references/benchmark-outline.md`. Each card shows the
product's own whole screenshot beside the competitor screenshots that show the
fix, never cropped or zoomed, with the element in question outlined. Look at
every screenshot before placing a mark or quoting a competitor, and say when a
claim comes from page text because a banner covered the screen.

## 5. Build

```bash
.venv/bin/python .claude/skills/pex-run-brief/scripts/build_report.py <run id> \
  --narrative <scratchpad>/narrative.json --out <path>.html
```

For benchmark runs, pass every run id before `--narrative`; the script takes the
benchmark layout when all of them are benchmark runs.

It embeds the screenshots, so the file opens anywhere without the evidence
folder. It refuses a narrative that cites evidence the runs do not contain, or a
code excerpt that is not in the saved page source.
Without `--out` it writes `report.html` beside the first run's artifacts.

## 6. Report

Print the path, the headline and the gate. Say which pillars were not scored, and
which improvements are unverified. For a benchmark, say which sites did not
answer, since they are missing from the comparison.

A completed run means the test finished, not that the website, or for an Android
run the app, is fine. Never include a password, an email address, a token or a persona path. If the run's
evidence contains one, name the artifact instead.
