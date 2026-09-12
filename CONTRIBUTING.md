# Contributing

Use a small branch or fork, describe the problem and resulting behavior, and
include the checks you ran. Follow [AGENTS.md](AGENTS.md). Do not include secrets,
private website evidence or unrelated generated files in a contribution.

## Setup and checks

The supported local environment is macOS. Setup installs Python through `uv`,
locked dependencies and Playwright browsers:

```bash
./scripts/setup.sh
.venv/bin/python -m pytest -q
```

The default tests use isolated databases and loopback services. They do not call
AI providers or production websites. They need permission to bind local ports.
Node.js runs the offline JavaScript evidence-link regression; that check is
explicitly skipped when Node is absent.

For a UI change, start an isolated local console in one terminal:

```bash
mkdir -p /tmp/pex-review
PEX_DATA=/tmp/pex-review DATABASE_URL=sqlite:////tmp/pex-review/records.db \
  .venv/bin/uvicorn app:app --host 127.0.0.1 --port 8742
```

Then in another terminal:

```bash
PEX_BASE_URL=http://127.0.0.1:8742 PEX_UI_ARTIFACTS=/tmp/pex-review-ui \
  .venv/bin/python -m tests.ui_check
```

Other scripts in `tests/` can run browsers against real websites and consume AI
quota. Read them first and run only what your task authorizes.

## Documentation

Keep [README.md](README.md) useful to a first-time user. Update
[docs/REFERENCE.md](docs/REFERENCE.md) for technical changes and
[docs/DEPLOY.md](docs/DEPLOY.md) for installation or server changes. Preserve the
version agreement checked by `tests/test_release.py` when cutting a release.

Use synthetic data in examples and issue reports. Report security problems as
explained in [SECURITY.md](SECURITY.md), not in a public issue.
