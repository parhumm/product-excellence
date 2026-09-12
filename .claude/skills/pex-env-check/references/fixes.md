# Known problems and their fixes

The wording comes from README.md, "When something goes wrong". Keep it.

| What you see | What it means | Fix |
| --- | --- | --- |
| `cli.py health` refuses to connect | the app is not running | `./start.command`, or leave the existing terminal window open |
| Settings says no AI worker is available | neither subscription is signed in | `claude auth login` or `codex login`, then reload Settings. Missions marked "No AI" still run |
| A browser is missing, or a run fails to start one | Playwright browsers are absent or broken | `./scripts/setup.sh` again; it is safe to repeat |
| "Another local app or import is using this data directory" | a second copy of the app holds `data/runtime.lock` | use that terminal window, or close it first |
| Settings shows pending uploads | the team server was unreachable when a run finished | press Retry uploads, or POST `/api/hub/retry`. The evidence is safe on this Mac until it succeeds |
| Safari keeps asking for the team server password | the sign-out is not finished | press Cancel once after signing out |
| A benchmark competitor never loads | the competitor blocks automated browsers | expected; report it as the outcome for that site |
| Anything else | unknown | `.venv/bin/python scripts/cli.py health` prints the version and what the app thinks is ready. Include that output in a bug report |

## What a healthy `health` shows

- a `version` matching `pyproject.toml`
- `browsers` listing chromium, firefox and webkit
- `networks` including baseline, slow-mobile, poor-mobile and offline
- an `ai` block with at least one provider showing `logged_in: true`

## What a healthy `hub/status` shows

- no team server configured, or a configured server with `pending` empty
- pending uploads are not an error on their own; they are an error when they do
  not clear after a retry
