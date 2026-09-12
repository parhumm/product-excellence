# Working on this project

- Python/FastAPI backend: `app.py`, `engine/`. Plain JavaScript UI: `static/`.
- `README.md` is the plain-language front door; `docs/REFERENCE.md` holds the full
  technical detail and `docs/DEPLOY.md` the team-server operations. Keep a change
  that affects installing, running or deploying reflected in them.
- Start with the files relevant to the task. Search before reading whole files.
  Exclude `data/`, `.venv/`, `static/vendor/`, lockfiles and the bundled
  `engine/schemas/schemaorg.jsonld` from broad searches. Read them only when needed.
- Default verification: `.venv/bin/python -m pytest -q` (offline unit/API tests).
  Use a targeted test while iterating; run the full suite once before delivery.
- UI check against a running server: `.venv/bin/python -m tests.ui_check`.
  `PEX_BASE_URL` and `PEX_UI_ARTIFACTS` select a separate test server/output folder.
- Other `tests/*.py` scripts can create missions, run real browsers, contact
  external websites and consume AI quota. Use only when relevant and authorized.
- Claude Code skills live in `.claude/skills/<name>/SKILL.md` and share the rules in
  `.claude/skills/_shared/rules.md` instead of repeating them. `tests/test_skills.py`
  guards their front matter, their references and the skill names used in the docs;
  `docs/SKILLS.md` is the user-facing guide.
- Team server: `hub.py` (server) and `engine/hub.py` (client). `tests/test_hub.py` and
  `tests/test_hub_integration.py` run offline; `tests/hub_smoke.py` starts real browsers.
  Keep workspace scoping in every server-side predicate, expected-revision writes,
  origin-owned recovery, and terminal status published only after verified uploads.
- Preserve the read-only browser policy (a mission with sign-in credentials relaxes
  it only for its own allowed domains), evidence IDs, missing-versus-zero metrics,
  critic verification, replay compatibility and release-gate requirements.
- Keep raw evidence complete. Prompt compaction belongs in `engine/prompts.py`;
  verify lossless reconstruction when changing its encoding.
- Report concise results and measured limits. Prompt characters are not token
  counts. Do not claim live AI quality from deterministic tests alone.
