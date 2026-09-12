#!/usr/bin/env bash
# Install or repair the Product Excellence team server on a Debian/Ubuntu box that
# already runs other services behind Caddy. Idempotent: safe to run again at any time.
#
# It creates no credentials in this file. The admin password is generated here into
# /etc/pex.env; workspace logins are created later on the /admin page.
#
#   scp deploy/install.sh root@<box>:/root/pex-install.sh
#   ssh root@<box> bash /root/pex-install.sh
#
# The first run prints a deploy public key and stops. Add it to the repository as a
# read-only deploy key, then run the script again.
set -euo pipefail

REPO=${PEX_REPO:-git@github.com:parhumm/product-excellence.git}
DOMAIN=${PEX_DOMAIN:?Set PEX_DOMAIN to a DNS name you control}
PORT=8741
APP=/opt/pex
DATA=/var/lib/pex
ENVF=/etc/pex.env
KEY=/root/.ssh/pex_deploy_ed25519
SITE=/etc/caddy/sites/$DOMAIN.caddy
SLUG=${REPO#*:};SLUG=${SLUG%.git}   # owner/name, for the gh command printed below

[ "$(id -u)" = 0 ] || { echo "Run as root." >&2; exit 1; }

step() { printf '\n== %s\n' "$1"; }

step "Service account and data directory"
id -u pex >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin pex
install -d -o pex -g pex -m 750 "$DATA" "$DATA/backups" "$DATA/artifacts"

step "uv"
if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi
uv --version

step "Deploy key and checkout"
install -d -m 700 /root/.ssh
[ -f "$KEY" ] || ssh-keygen -t ed25519 -N '' -C "pex-deploy@$(hostname)" -f "$KEY" >/dev/null
# -F /dev/null: this box may carry an account-wide GitHub key in root's ssh config,
# and the deploy must use the read-only key generated here and nothing else.
export GIT_SSH_COMMAND="ssh -F /dev/null -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/root/.ssh/known_hosts"
if [ ! -d "$APP/.git" ]; then
    if ! git clone --quiet "$REPO" "$APP"; then
        cat <<EOF

The box cannot read the repository yet. Add this read-only deploy key, then run
this script again:

$(cat "$KEY.pub")

    gh repo deploy-key add <the key above> -R $SLUG -t vps-$DOMAIN
EOF
        exit 1
    fi
fi

step "Environment file"
# 640 root:pex so the service reads it and no other account on the box can.
if [ ! -f "$ENVF" ]; then
    cat > "$ENVF" <<EOF
PEX_DATA=$DATA
DATABASE_URL=sqlite:///$DATA/records.db
PEX_HUB_ADMIN_PASSWORD=$(openssl rand -base64 24)
EOF
    chown root:pex "$ENVF"
    chmod 640 "$ENVF"
    echo "Wrote $ENVF with a fresh admin password."
else
    echo "$ENVF exists; leaving it and its admin password alone."
fi

step "systemd units"
cat > /etc/systemd/system/pex.service <<EOF
[Unit]
Description=Product Excellence team server
After=network-online.target
Wants=network-online.target

[Service]
User=pex
Group=pex
WorkingDirectory=$APP
EnvironmentFile=$ENVF
# A long artifact upload must not hold a release back: uvicorn waits for open connections
# forever by default, which turned a two-second restart into ninety seconds of downtime.
ExecStart=$APP/.venv/bin/uvicorn hub:app --host 127.0.0.1 --port $PORT --proxy-headers --forwarded-allow-ips 127.0.0.1 --timeout-graceful-shutdown 10
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA
MemoryHigh=384M
MemoryMax=512M
CPUWeight=50

[Install]
WantedBy=multi-user.target
EOF

ln -sf "$APP/deploy/deploy.sh" /usr/local/bin/pex-deploy
chmod +x "$APP/deploy/deploy.sh"

cat > /etc/systemd/system/pex-deploy.service <<EOF
[Unit]
Description=Deploy the current main of Product Excellence

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pex-deploy
EOF

cat > /etc/systemd/system/pex-deploy.timer <<EOF
[Unit]
Description=Check for a new Product Excellence release

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
EOF

step "Nightly database backup"
# Artifacts are not backed up: each teammate's machine keeps the durable copy of its evidence.
cat > /usr/local/bin/pex-backup <<EOF
#!/usr/bin/env python3
"""Copy the team server database with SQLite's own backup API, then keep 14 days."""
import datetime, pathlib, sqlite3

data = pathlib.Path("$DATA")
out = data / "backups" / f"records-{datetime.date.today().isoformat()}.db"
with sqlite3.connect(data / "records.db") as src, sqlite3.connect(out) as dst:
    src.backup(dst)
for old in sorted((data / "backups").glob("records-*.db"))[:-14]:
    old.unlink()
print("Wrote", out)
EOF
chmod +x /usr/local/bin/pex-backup

cat > /etc/systemd/system/pex-backup.service <<EOF
[Unit]
Description=Back up the Product Excellence database

[Service]
Type=oneshot
User=pex
Group=pex
ExecStart=/usr/local/bin/pex-backup
EOF

cat > /etc/systemd/system/pex-backup.timer <<EOF
[Unit]
Description=Nightly Product Excellence database backup

[Timer]
OnCalendar=*-*-* 04:10:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload

step "First release"
/usr/local/bin/pex-deploy --force

step "Enable services"
systemctl enable --now pex pex-deploy.timer pex-backup.timer
curl -fsS "http://127.0.0.1:$PORT/hub/health" && echo " <- team server answers on 127.0.0.1:$PORT"

step "Caddy site"
# The main Caddyfile is never edited; it already imports /etc/caddy/sites/*.caddy.
install -d /etc/caddy/sites
# The shared box defines this snippet; a box without it gets the site without the import.
HEADERS=''
if grep -q galaxy_secure_headers /etc/caddy/Caddyfile 2>/dev/null; then HEADERS='    import galaxy_secure_headers'; fi
cat > "$SITE" <<EOF
$DOMAIN {
    encode zstd gzip
$HEADERS
    reverse_proxy 127.0.0.1:$PORT {
        header_up X-Real-IP {remote_host}
        transport http {
            read_timeout 600s
            write_timeout 600s
        }
    }
}
EOF
# adapt only parses; unlike validate it never provisions or touches a running listener.
if ! caddy adapt --config /etc/caddy/Caddyfile >/dev/null; then
    rm -f "$SITE"
    echo "Caddy refused the new site; removed $SITE and left the running config untouched." >&2
    exit 1
fi
systemctl reload caddy
sleep 2
curl -s localhost:2019/config/ | grep -q "$DOMAIN" || {
    echo "Caddy reloaded but is not serving $DOMAIN; check DNS and 'journalctl -u caddy'." >&2
    exit 1
}

cat <<EOF

Done.
  Landing page  https://$DOMAIN/
  Console       https://$DOMAIN/console   (a workspace username and password)
  Admin         https://$DOMAIN/admin     (user "admin", password in $ENVF)

Next: open /admin, create one workspace per website with "Add starter missions"
unchecked, and hand each teammate their username and password out of band.
EOF
