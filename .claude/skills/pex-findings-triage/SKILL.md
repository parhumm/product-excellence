---
name: pex-findings-triage
description: Use when the user wants Product Excellence findings turned into tickets, owners or a release delta.
argument-hint: "[workspace or run id] [--baseline RUN_ID]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*)
---

# Turn findings into work

Group what a run found, write one ticket per issue worth fixing, and write the
decisions back so the Findings page shows them.

Read `.claude/skills/_shared/rules.md` first and follow it.

## 1. Collect

```bash
.venv/bin/python scripts/cli.py findings --project <workspace id> --grouped
.venv/bin/python scripts/cli.py findings --run <run id>
```

Use `--grouped` for a whole workspace so one issue is one row across runs. Use
`--run` for a single run.

Each finding carries `id`, `run_id`, `title`, `severity` (P0 to P3), `pillar`,
`status`, `owner`, `evidence_id`, `verifier_status` and `source`.

## 2. Sort before you write anything

Separate, and keep the separation visible:

- open findings from `accepted`, `resolved` and `dismissed` ones
- deterministic findings from AI findings a critic has not confirmed
  (`verifier_status` of `UNCONFIRMED` or `PROBABLE`)
- P0 and P1, which block a release gate when confirmed and reproduced, from the
  rest

Never promote an unconfirmed AI finding to a fact. Say "reported by the AI, not
confirmed" and offer a replay to settle it.

## 3. Write the tickets

One ticket per open P0, P1 or P2, in a file in the scratchpad:

- **Title**: the symptom, in the user's words, not the pillar name.
- **What happens**: the observed behaviour, quoted from the finding.
- **How to see it**: the steps from the run's timeline, numbered.
- **Evidence**: the paths under `data/artifacts/<run id>/` for the screenshot,
  the recording and the run record.
- **Severity**: the finding's own, with one line of why it is that.
- **Suggested owner**: from the pillar. Say it is a suggestion.

Group P3 and informational findings into one list at the end, one line each.

The reply carries the counts by severity, the top three titles, and the file
path. Do not paste the whole file.

## 4. Compare against a baseline

With `--baseline`:

```bash
.venv/bin/python scripts/cli.py compare <baseline run id> <candidate run id>
```

Report four groups: `new`, `resolved`, `not_assessed` and `uncertain`. If
`compatible` is false, list the `mismatches` first and say the comparison is not
a like-for-like release delta, because the two runs did not ask the same
question under the same conditions.

For Android, require the comparison to report the same target/package and
compatible device/network provenance. A changed APK SHA is a release comparison,
not an incompatible replay; label both versions. Keep review state scoped to the
target and SHA so a newer build does not mark an older-build issue fixed.

## 5. Write decisions back

Only if the user asks, and after one confirmation for the whole batch:

```bash
.venv/bin/python scripts/cli.py review <run id> <finding id> --status accepted --owner "Name"
```

Statuses are `open`, `accepted`, `resolved` and `dismissed`. A run that is still
queued or running refuses the edit; wait for it to finish. Each write reports how
many earlier reports of the same issue it synced. Print the total synced count
and the number of findings changed.
