# Security

Use the latest reviewed revision. Security fixes are maintained on `main`; older
releases do not have a separate maintenance commitment.

## Report a vulnerability privately

Do not open a public issue containing a vulnerability, credential, account data,
or private recording. Use GitHub’s **Security → Report a vulnerability** when the
repository enables private reporting. If that option is unavailable, ask the
maintainer to enable it without describing the vulnerability publicly. Include
the affected revision, impact and minimal reproduction using synthetic data.
Never include real passwords, tokens or customer evidence.

## Safe operation

- Run the local console on `127.0.0.1`. It has privileged access to your local
  testing configuration and is not a public multi-user service.
- Share results through the authenticated team server behind HTTPS. Keep its
  port on loopback and configure forwarded headers only for the actual proxy.
- Use test accounts and websites you are authorized to evaluate. Browser policy
  reduces accidental changes; it is not a security sandbox for hostile websites.
  Mission sign-in permits mutating requests on that mission’s allowed domains.
- Keep `data/`, `.env*`, database backups, browser profiles and provider sign-in
  files out of Git and public reports. Ignore rules do not remove existing commits.
- Treat screenshots, recordings, traces and exports as sensitive. Masking is
  incomplete. Review them before sharing; see [privacy](docs/PRIVACY.md).

If a credential was committed or published, revoke or rotate it first. Then
remove it from every affected branch/tag and coordinate history cleanup with
collaborators. Deleting the current file alone does not remove old copies.

Maintainers: follow the [release checklist](docs/PUBLIC_RELEASE.md), enable GitHub
secret scanning and push protection where available, and review dependency alerts.
