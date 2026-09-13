# Causes, evidence and fixes

Statuses: `completed`, `blocked`, `failed`, `cancelled`, `interrupted`. Blocked
means the run finished under control without reaching its goal. Failed means the
engine itself broke.

## Blocked

| Cause | Evidence in the run | Fix |
| --- | --- | --- |
| Goal not reached | `error` starts "Mission did not reach success:", `mission_outcome` is `blocked` | read `success_basis` and the last actions; usually the goal asked for more than the steps allowed, or `success_text` never appeared |
| Two refusals in a row | `error` starts "Stopped after two consecutive refused actions" | the quoted reason names it: a risky control or a host outside `allowed_domains` |
| Payment or destructive control | an action with `status: policy_blocked` and "Payment, publication or destructive control blocked" | working as designed; end the goal before that step and report where it stopped |
| Off-domain navigation | refusal "Navigation to HOST refused; allowed hosts: ..." | add the host to `allowed_domains` only if the workspace owns it; a competitor belongs in `competitors` on a benchmark |
| Mutating request blocked | `blocked_request_log` entries with "Mutating method blocked", `policy_blocked_requests` above zero, `coverage_note` set | expected on forms; the flow is incomplete, say which part |
| AI-call budget | `mission_outcome: budget_stop` with `ai_calls` at the mission `ai_budget` | the review still ran, so the report is complete; continue the run with `cli.py continue <run id> --ai-calls N --wait` to finish the journey, or narrow the goal to one task |
| Time budget | `error` "Time budget exhausted" or "Wall-clock time budget exhausted" | raise `max_seconds`, or use a faster network profile |
| Site refused the visit | `error` "Target returned HTTP ..." | an access or regional restriction; try another egress route or check the URL |
| Page never loaded | `error` "Target could not be loaded under this network/route", `navigation_error` set | test on `baseline` first, then the impaired profile |
| No AI worker | `error` "No subscription AI worker is signed in" or "Autonomous missions require a signed-in AI provider" | hand to `pex-env-check`; an audit can run with `provider: none` |
| Missing password | `error` "Sign-in password is not stored for this mission" | edit the mission and enter the password again; it is stored outside the run record |
| Missing persona | `error` "Persona session is missing" | recapture with `scripts/capture-persona.py` |
| One-time code sign-in | events show the form reached and a code requested | cannot be completed by the engine; use a persona captured while signed in |
| Network profile needs Linux | `error` mentions netem, packet loss or jitter | use `baseline`, or start the netem runner from the deployment guide |
| Profile needs Chromium | `error` "This impairment profile requires Chromium" | set `browser: chromium` |
| Missing network profile | `error` "Network profile does not exist" | pick a profile listed by `cli.py health` |

## Failed

| Cause | Evidence | Fix |
| --- | --- | --- |
| Browser could not start | `status: failed`, the error names playwright or a browser binary | `./scripts/setup.sh`, then `pex-env-check` |
| Service restarted mid-run | `status: interrupted`, "Service restarted. Replay this run to continue." | replay the run |
| Anything else | `status: failed` with a stack trace | this is a bug in the tool; hand to `pex-issue-report` |

## Cancelled

`status: cancelled`, `error: "Cancelled by user"`. Nothing to diagnose.

## Completed but thin

- `evaluation_error` set: the pillar review itself failed, usually because the
  time budget ended or the AI worker errored. Deterministic findings stand;
  pillar scores from AI findings are missing. A run that merely spent its
  AI-call budget is not this case: the review is given one call past the budget,
  so it completes. Continue the run to carry the journey on without repeating it.
- `coverage_note` set: some flows were incomplete because mutating requests were
  blocked. The scores stand, the coverage does not.
- A benchmark where one entry in `sites` has an `outcome` other than success:
  that competitor blocked the browser. Expected; report it per site.
