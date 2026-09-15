---
name: pex-mission-write
description: Use when the user wants a Product Excellence mission written from a plain sentence and imported.
argument-hint: "[website or workspace] [what to test]"
allowed-tools: Read, Write, Bash(.venv/bin/python scripts/cli.py:*)
---

# Write a mission from a sentence

Turn "check whether the pricing page explains renewal" into a mission the engine
accepts, with a goal in the house voice and a budget that fits the work.

Read `.claude/skills/_shared/rules.md` first and follow it.

The mission form's **Suggest two better goals** button reads the same
`references/goal-voice.md`, so a change to the voice belongs in that file and
nowhere else.

## 1. Learn the workspace

```bash
.venv/bin/python scripts/cli.py health
.venv/bin/python scripts/cli.py missions
```

`health` shows which AI workers are signed in. `missions` shows what already
exists, with each mission's `project_id`.

List `.venv/bin/python scripts/cli.py targets` and bind a new mission to the
named target. For a website, its `allowed_domains` come from that target. Never
add a domain it does not own; a competitor URL belongs in `competitors` on a
benchmark mission instead. For Android, use its package/build, baseline network,
no benchmark/SEO/sign-in/persona/proxy, and stop before password or OTP entry.

If the user gave a website with no matching workspace, say so and offer to create
one before going further.

## 2. Choose the shape

Read `references/goal-voice.md` for the mode table, the field defaults and three
preset goals to imitate.

Match the sentence to the nearest preset in `engine/presets.py` and start from
its budget block (`AUDIT`, `JOURNEY`, `BENCHMARK`). One page judged without
clicking is an audit. A task carried out is a journey. "Work out what this does"
is explore. The same question asked of competitors is a benchmark.

Write the goal the way the presets are written:

- Address the engine as a first-time visitor with one task.
- Say what to judge and what to report, in plain sentences.
- Name the stop explicitly: before submitting, paying, publishing or deleting.
- Use the `{{password}}` placeholder if the journey signs in, never a real password.
- Keep it inside the workspace's own domains.

Set `pillars` to what the goal actually judges. Raise `max_steps`, `max_seconds`
and `ai_budget` only as far as the task needs, and tell the user what you chose.

## 2b. Journeys that need more than one goal

A question about state rather than a single task becomes a `scenario`: an ordered
list of steps on one device or in one browser page. Downloads that survive a weak
link, a second account on the same phone, a notification opened an hour later, a
filter that survives a restart. One vocabulary runs on both platforms; the target
decides what each step acts on. Read `references/scenario-steps.md` for the five
step kinds, the facts a check or hold may state, the events and the three
modifiers, including the "On the web" column and the two web caveats.

Start from the nearest shipped journey in `engine/scenarios/` rather than an
empty list. There are twelve, none of them tied to a platform, and the console
lists them with their display text at `/api/scenarios`:

| Journey | Answers |
| --- | --- |
| `entitlement-switch` | Does playback survive a move to another transport? |
| `weak-network-download` | Does a paused and resumed download finish and play? |
| `profile-isolation` | Are downloads and search history separate per account? |
| `stale-notification` | Does a notification opened much later land in the right place? |
| `shared-link-login` | Does a shared link still reach its page after signing in? |
| `playback-offline` | Does playback survive the connection being cut? |
| `session-survives-restart` | Is the account still signed in after a restart? |
| `sign-out-really-signs-out` | Does signing out really end the session? |
| `filter-survives-restart` | Is a filter still on after a restart? |
| `back-after-search` | Does going back from a result keep the search? |
| `form-rejects-bad-input` | Does a form reject one invalid value before sending? |
| `checkout-on-slow-link` | Does checkout reach payment on a slow link? |

Keep the shape they set:

- Anchor a screen with a `goal` before asserting text on it, and never assert
  that text is absent without anchoring first.
- Use `manual` only for sign-in, payment and one-time codes. Recording stops
  while a person works, so every manual step costs coverage: use the fewest.
- Mark a fact `policy: unknown` whenever nobody has confirmed what the app should
  do. It is then recorded as an observation, not held against the release.
- Leave blanks for real titles and accounts, two to four of them, each phrased as
  an instruction to the person filling it in (`<Text shown only when signed in>`,
  not `<text>`). Say in your summary which ones the user has to replace before the
  mission can be saved.
- Set `reset: fresh` unless the journey needs what the last run left. `snapshot`
  names a device state saved on that one Mac and is refused on a website mission.
- On a website target, `speed`, `delay_ms` and `network: wifi | cellular` need
  Chromium. Say so in `needs` rather than letting the save fail.
- Budget for the waits: `max_seconds` has to cover every `within`, `for`, `wait`
  and operator timeout plus the app's own work. The presets start at 1800.

Say plainly what the scenario cannot establish, using the last section of
`references/scenario-steps.md`.

## 3. Show it, then import it

Write the YAML to the scratchpad using the mission schema,
show the whole file, and say in one line what it will and will not do.

After the user agrees:

```bash
.venv/bin/python scripts/cli.py import <path>.yaml
```

## 4. Offer the run

Offer, do not start:

```bash
.venv/bin/python scripts/cli.py run <mission id> --wait
```

If the goal needs a signed-in account, do not offer a run yet. Point at
`scripts/capture-persona.py` to save a test session, or at the mission's
`login_identifier` and `login_password` fields, and say that sign-in needing a
one-time code cannot be completed by the engine.

If a run finishes badly, hand over to `pex-run-diagnose`.
