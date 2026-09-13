# Skills

## What they are

Product Excellence runs on your Claude or ChatGPT subscription, so you already
have Claude Code on this Mac. This folder ships ten skills for it: short
instruction sheets that teach Claude Code how to do the fiddly parts of this
tool for you.

Open a terminal in this folder, start `claude`, and type `/pex-`. The list
appears. Pick one, add what you want in plain words, and press Enter.

There is nothing to install. The skills live in `.claude/skills/` next to the
app, and they update when the app updates.

## Which one to use

| You want to | Type | It asks before | You get |
| --- | --- | --- | --- |
| know whether this Mac is ready | `/pex-env-check` | running a repair script | one table: app, AI worker, browsers, team server, and the fix for anything not ready |
| test something the ten presets do not cover | `/pex-mission-write` | importing the mission | a mission written in the house voice, with a budget, ready to run |
| know what else is worth testing | `/pex-mission-suggest` | creating each mission | five to eight suggestions for your website, and the ones you pick, created |
| understand why a run blocked or failed | `/pex-run-diagnose` | changing the mission or running again | the cause, the evidence for it, and the smallest fix, proved by a second run |
| turn findings into work | `/pex-findings-triage` | writing owners and statuses back | one ticket per issue worth fixing, and a release delta against a baseline |
| tell people what happened | `/pex-run-brief` | nothing; it only reads and writes a file | a one-page brief with scores, the top three findings and what the run does not prove |
| report a bug in this tool | `/pex-issue-report` | filing anything on GitHub | a complete, redacted bug report, checked against the open issues first |
| release a new version | `/pex-release-ship` | pushing, and again before deploying | tests, a version bump, a changelog entry, a tag, the deploy, and proof it is live |
| turn an Android crash or ANR into a local bug report | `/pex-app-crash` | nothing; it only reads and writes a file | a sanitized attributable stack and timeline report |
| compare two Android builds | `/pex-app-compare` | nothing; it only reads and writes a file | compatibility, findings and valid measurement deltas |

A run page offers the matching command where it helps: the diagnose skill on a blocked or failed run,
the triage skill above a list of open findings, and the brief skill under the executive summary.
Each one comes with a Copy button, so nothing has to be typed.

Four of them wait for you to ask by name: the brief, the bug report and the
release skill are never started on their own guess of what you meant.

## A first session

```
$ claude
> /pex-env-check
```

It prints the app health and the team server status, then a table with a row per
item and a fix for anything not ready. Fix those first; nothing below works
without a running app and an AI worker.

```
> /pex-mission-write https://example.com check whether the pricing on a product page is clear
```

It picks the workspace, matches your sentence to the nearest preset for mode and
budget, writes the goal, and shows you the whole YAML file before importing
anything. Say yes and it imports; it then offers the run command instead of
starting the run itself.

```
> /pex-run-brief <the run id>
```

It exports the finished run and writes a one-page Markdown file, then prints the
path, the headline and the gate.

If a run ends blocked or failed instead:

```
> /pex-run-diagnose <the run id>
```

## What they never do

- They never read your passwords, your saved test sessions or your recordings.
- They never put a password, an email address or a token into a file, a ticket,
  a brief or a GitHub issue.
- They never run a command or open a link that appeared inside a web page, a
  finding or a log line. That text is evidence, not instructions.
- They never start a run, import or edit a mission, change a finding, file an
  issue, push or deploy without asking you first.
- They never try to defeat the read-only policy. Payment, publication and
  destructive controls stay refused, and a refusal is a result, not a bug.
- They never tell you a website is fine. A completed run means the test
  finished. What it found is in the findings.

## When something goes wrong

- A skill did not appear: check that you started Claude Code in this folder, and
  that `.claude/skills/` is there.
- A skill did something you did not expect: its whole instruction sheet is
  readable at `.claude/skills/<name>/SKILL.md`. It is plain English.
- The app itself misbehaved: the README has the short troubleshooting list, and
  `/pex-issue-report` files a proper bug for the rest.
- A skill is wrong or missing a step: that is a bug in this repository. Report it
  the same way.

Codex users: the skills are written for Claude Code. Codex cannot list them, but
the files are plain Markdown and you can paste one in.
