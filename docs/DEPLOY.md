# Deploying the team server

The team server holds shared results. When someone finishes a run on their own
Mac, the run publishes itself to the server with its screenshots, recording,
measurements and findings, and everyone signed in to that website sees it.

The server only stores and shows results. It never opens a browser and never
calls an AI, so Run, Replay and the mission forms are switched off there and
read "Coming soon". Everyone keeps running tests on their own machine with their
own Claude or ChatGPT subscription.

Use a domain you control. The landing page is public; `/console` asks for a
website’s username and password and is read only. Publishing this GitHub
repository does not publish your server database or create shared logins.

## What you need

- A Debian or Ubuntu box you can reach as root over SSH.
- [Caddy](https://caddyserver.com) already running on it. Caddy gets the HTTPS
  certificate; the server itself only listens on the box's own loopback address.
- A DNS name pointing at that box.
- A read-only deploy key on the GitHub repository, which the installer creates
  for you in the next section.

## Install it from nothing

Copy the installer to the box and run it:

```bash
scp deploy/install.sh root@<box>:/root/pex-install.sh
ssh root@<box> PEX_DOMAIN=team.example.com bash /root/pex-install.sh
```

The first run stops and prints a public key, because the box cannot read the
repository yet. Add that key to GitHub as a **read-only** deploy key, using the
`gh` command the script prints, then run the same command again.

The second run finishes the job: a `pex` service account, the checkout in
`/opt/pex`, data in `/var/lib/pex`, the service itself, a release timer, a
nightly backup and the Caddy site. It ends by printing three addresses.

The installer is safe to run again at any time. It creates the admin password
once, into `/etc/pex.env`, and leaves it alone afterwards.

For a different name or repository, set them first:

```bash
ssh root@<box> PEX_DOMAIN=team.example.com PEX_REPO=git@github.com:you/repo.git bash /root/pex-install.sh
```

## Create the logins

Open `https://<your domain>/admin` and sign in as `admin` with the password in
`/etc/pex.env` on the box.

Create one workspace per website, each with its own username and a password of
15 characters or more. Leave **Add starter missions** unchecked if you are about
to import an existing website's history. Give each teammate the username and
password for their website some way other than email, and tell them to enter it
under **Settings → Team server** in their own app.

Everyone with a website's password sees the same results and cannot be told
apart, so use test accounts everywhere and treat the evidence as shared.

## Update it

In Claude Code, `/pex-release-ship` does the whole release: it runs the tests and
the UI check, proposes the version, writes the changelog entry, tags the commit,
asks before pushing, and then waits for the box to report the new version. The
manual path is below and stays supported.

Push to `main`. A timer on the box checks GitHub every two minutes and, when
`main` has moved, installs the new version and restarts the service. If the new
version does not answer its health check within twenty seconds, the box puts the
previous one back and says so in its log.

To deploy immediately instead of waiting:

```bash
ssh root@<box> pex-deploy --force
```

## Check it is healthy

```bash
curl https://<your domain>/hub/health
ssh root@<box> systemctl status pex
ssh root@<box> journalctl -u pex -n 50
ssh root@<box> journalctl -u pex-deploy.service -n 50
```

The health endpoint answers with `ok` and the version now running, so you can
confirm a release from your own Mac without opening an SSH session. The last
command shows what the release timer has been doing, including any rollback. Watch free disk space as well, because evidence accumulates.

## Backups

Every night at 04:10 the box copies its database to
`/var/lib/pex/backups/records-<date>.db` and keeps the last fourteen.

Evidence files are not backed up, on purpose: the machine that ran a mission
keeps the original screenshots, recordings and traces, so the durable copy is
already on your teammates' Macs.

Keep a separate, protected copy of `/etc/pex.env`. It holds the admin password,
and the workspace logins cannot be recovered without it.

To restore, stop the service, put a backup copy in place of
`/var/lib/pex/records.db`, and start it again:

```bash
ssh root@<box>
systemctl stop pex
cp /var/lib/pex/backups/records-2026-09-08.db /var/lib/pex/records.db
chown pex:pex /var/lib/pex/records.db
systemctl start pex
curl -fsS http://127.0.0.1:8741/hub/health
```

Rehearse a restore into a spare directory before you need one for real. The
[reference](REFERENCE.md#backup-and-restore) has the full procedure, including
PostgreSQL and the checks worth making afterwards.

## Moving an existing website onto the server

To lift a website's whole history, missions, runs and evidence, out of one
person's Mac and onto the server, see
[importing a workspace](REFERENCE.md#import-a-workspace). Create the target
workspace empty first, with starter missions unchecked, and back both sides up
before starting.

## Before exposing a server

Replace `team.example.com` with your own DNS name. The installer requires
`PEX_DOMAIN`; it never defaults to the maintainer’s server. It assumes Caddy’s
main configuration imports `/etc/caddy/sites/*.caddy`. Install Git, curl, OpenSSL
and Caddy first, and review the installer before running it as root.

Keep `/etc/pex.env`, database backups and `/var/lib/pex` private. Only expose the
HTTPS reverse proxy; keep the application port on loopback. Use long, unique
workspace passwords and distribute them through a private channel. Workspace
members share access to evidence, including recordings. Follow [SECURITY.md](../SECURITY.md)
and the [privacy guide](PRIVACY.md).

The supplied update timer deploys `main` automatically. Protect that branch and
review contributions before merging: a merge can update the running service.
