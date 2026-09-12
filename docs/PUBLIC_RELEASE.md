# Public release review

Reviewed and published 2026-09-12 as a clean root commit. This is a scoped
release review, not a guarantee that the project is free of every vulnerability.

## Findings and preparation

| Area | Result |
| --- | --- |
| Published source | Gitleaks 8.30.1 reported no secrets across the 116 release files |
| Git history | The former private history and commit metadata passed Gitleaks scans before being replaced. The public repository contains one root commit; old remote branches, tags and releases were removed |
| Runtime files | No historical `data/`, environment, key or database paths found in the filename inventory; generated `linux/.env` is ignored |
| Python runtime dependencies | pip-audit reported no known vulnerabilities across 30 locked dependencies |
| Bundled media | Seven introduction screenshots visually inspected; no visible credentials found |
| GitHub extras | No release attachments or Actions artifacts; no open or closed issues or pull requests, and no workflow runs; release notes also passed a secret scan; Pages and wiki disabled at review time |
| Reflected passwords | Structured observations, console text and error messages now scrub exact stored mission-password text before persistence and prompt use; generated identifiers and policy decisions retain their original values |
| Shared evidence URLs | Console links now accept only safe artifact paths within the same run; malformed links are inert |
| Documentation | Public HTTPS clone instructions, own-workspace setup, privacy guide, contribution guide, security policy and third-party notices added or corrected |
| Installation | Team-server installer requires an explicit domain instead of defaulting to the maintainer’s domain |

The scan is pattern-based. No detected secret is not proof of no secret. It does
not certify binary redaction, provider behavior, the optional Linux container’s
OS/npm dependencies, or a live server. Existing private runtime data was not
copied into the release or comprehensively inspected. Old evidence is not
retroactively scrubbed by these changes.

## Verification

The final full offline suite passed **174 tests**, including the added
observation-to-prompt regression. The isolated
browser UI check passed with no JavaScript errors. Shell syntax and relative
Markdown file links passed. No live AI quality claim is made by these checks.

## Publication completed

1. Apache License 2.0 is included for project code and documentation. Preserve
   [third-party notices](../THIRD_PARTY_NOTICES.md).
2. The reviewed files were published as a clean root commit. Old remote branches,
   tags and releases were removed before the repository became public.
3. Private vulnerability reporting is enabled. GitHub secret scanning is available
   automatically for public repositories and supplements this review.
4. For future releases, run the checks below and inspect branches, tags, issues,
   release notes, workflow logs and attachments before publishing.
5. The supplied team-server deployment timer follows `main`, so pushing there may
   also deploy to an existing server. Protect and review changes to that branch.

## Repeatable checks

Install Gitleaks separately, then run:

```bash
.venv/bin/python -m pytest -q
gitleaks git . --log-opts='--all' --redact --no-banner
git diff --check
git status --short
```

For uncommitted/new files, inspect the proposed file list and scan a temporary
copy containing only those release files. A history scan does not check your
uncommitted edits. Never upload a ZIP of the whole working folder: Git ignore
rules do not protect files copied by ordinary archive tools.

To create a source-only archive **after committing the approved changes**:

```bash
git archive --format=zip --output=/tmp/product-excellence-source.zip HEAD
```

Review the archive’s contents before sharing it. It contains tracked files only,
but any accidentally tracked private file would still be included.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the isolated UI check and
[SECURITY.md](../SECURITY.md) for credential exposure response.
