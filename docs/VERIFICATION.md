# Delivery verification

Verification is intentionally brand-neutral. The repository contains a local
fixture and reserved `example.*` domains for deterministic boundary tests; it
does not publish customer, competitor or site-specific run history.

## Offline checks

Run the full unit and API suite:

```bash
.venv/bin/python -m pytest -q
```

Run the isolated browser UI check against a disposable local data directory:

```bash
PEX_PORT=8742 PEX_DATA=/tmp/pex-ui-data ./start.command
PEX_BASE_URL=http://127.0.0.1:8742 PEX_UI_ARTIFACTS=/tmp/pex-ui-artifacts \
  .venv/bin/python -m tests.ui_check
```

The suite covers browser policy boundaries, request validation, persistence,
workspace scoping, revision conflicts, evidence publication and recovery,
prompt reconstruction, deterministic findings, scoring, comparisons, reports,
CLI behavior, release-version agreement and skill metadata.

## Live checks

The scripts outside the pytest suite can start real browsers, contact external
websites and spend AI subscription quota. Use them only for a target you are
authorized to test. Record any live result outside the public repository unless
it has been reviewed for publication.

## Release scope

This is an internal engineering release. Deterministic checks do not certify AI
quality, authenticated workflows, payment completion, native-device behavior,
real ISP routing or the PRD's statistical quality targets. Missing measurements
remain distinct from zero, and high-severity release blocking still requires
confirmed, reproduced evidence.
