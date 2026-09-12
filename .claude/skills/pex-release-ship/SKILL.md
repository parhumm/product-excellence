---
name: pex-release-ship
description: Use when the user wants to release a new Product Excellence version, deploy it and verify it.
argument-hint: "[patch|minor|major] [--box HOST] [--domain excellence.jaan.to]"
allowed-tools: Read, Edit, Write, Bash(git:*), Bash(.venv/bin/python:*), Bash(curl:*), Bash(ssh root@*), Bash(./start.command)
disable-model-invocation: true
---

# Ship a version and prove it is live

Test, bump, changelog, tag, push, deploy, verify. Stop at the first failure and
say what to fix. Never force anything.

Read `.claude/skills/_shared/rules.md` first and follow it.

## 1. Preflight

Every step here is read-only. Stop on the first failure.

```bash
git status --porcelain
git fetch origin main
git log --oneline origin/main..HEAD
git describe --tags --abbrev=0
git log --oneline <last tag>..HEAD
.venv/bin/python -m pytest -q
```

- A dirty tree stops the release. Show what is uncommitted.
- Nothing since the last tag means nothing to release. Say so and stop.
- Tests must be green. Show the failing test names and the last 20 lines only.

Then the UI check, on a separate port so a running app is untouched:

```bash
PEX_PORT=8742 ./start.command   # in the background
PEX_BASE_URL=http://127.0.0.1:8742 PEX_UI_ARTIFACTS=<scratchpad>/ui .venv/bin/python -m tests.ui_check
```

Stop that server afterwards. Report head and tail of its output, not all of it.

`tests/hub_smoke.py` starts real browsers and takes minutes. Run it only if the
release changes the team server and the user asks for it.

## 2. Propose the version

Default to a patch. Choose minor when a commit since the last tag adds a
capability a user can see. Choose major only when the user says so.

The version lives in three files and they must agree:

- `pyproject.toml`, the `version` line
- `app.py`, the `FastAPI(...)` call for the local app
- `hub.py`, the `FastAPI(...)` call for the team server

Draft the changelog entry in the file's own style: a `## X.Y.Z — YYYY-MM-DD`
heading above the previous one, then bullets that start with a bold phrase and
say what changed for a user. Take the wording from the commit subjects, which
are already plain sentences. Use today's date.

Show the version, the three edits and the entry. The user confirms both.

## 3. Commit and tag

```bash
.venv/bin/python -m pytest -q tests/test_release.py
git commit -am "Release X.Y.Z"
git tag -a vX.Y.Z -m "Product Excellence X.Y.Z"
```

If the work is on a branch, merge it into `main` with a merge commit, the way
earlier releases were merged. Do not squash and do not rebase `main`.

Then stop and ask before the one irreversible step:

```bash
git push origin main vX.Y.Z
```

If the user declines, leave everything local and tell them how to undo it:
`git tag -d vX.Y.Z` and `git reset --hard origin/main`.

## 4. Deploy

Pushing to `main` is the deploy. A timer on the box installs it within two
minutes and rolls back if the new version does not answer its health check in
twenty seconds.

To deploy at once, when the user gave a box:

```bash
ssh root@<box> pex-deploy --force
```

Then poll the public health endpoint every 15 seconds for up to 5 minutes:

```bash
curl -s https://excellence.jaan.to/hub/health
```

It reports `{"ok": true, "version": "X.Y.Z"}`. The release is live when the
version matches the tag.

If it does not match in five minutes and a box address is known:

```bash
ssh root@<box> journalctl -u pex-deploy.service -n 30
```

Quote the "Deployed <sha>" or the rollback line verbatim. A rollback is a failed
release: report it, do not push again to paper over it, and hand to
`pex-issue-report` if the cause is a defect.

## 5. Report

A checklist, one line each: tests, UI check, version in the three files,
changelog entry, commit, tag, push, deployed version, deploy log line. Mark each
done, skipped or failed. Finish with the live version and the tag it came from.
