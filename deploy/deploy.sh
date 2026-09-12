#!/usr/bin/env bash
# Pull main into /opt/pex and restart the team server.
# A release that does not answer /hub/health is rolled back to the commit that did.
# Installed as /usr/local/bin/pex-deploy; run by pex-deploy.timer every two minutes.
set -euo pipefail
export HOME=/root
APP=/opt/pex
PORT=8741

cd "$APP"
# -F /dev/null so a github.com entry in root's ssh config cannot substitute a wider key.
export GIT_SSH_COMMAND="ssh -F /dev/null -i /root/.ssh/pex_deploy_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/root/.ssh/known_hosts"
git fetch --quiet origin main
old=$(git rev-parse HEAD)
new=$(git rev-parse origin/main)
if [ "$old" = "$new" ] && [ "${1:-}" != "--force" ]; then
    echo "Already at $old"
    exit 0
fi

release() {
    git reset --hard --quiet "$1"
    uv sync --frozen --no-dev --quiet
    systemctl restart pex
}

healthy() {
    # A drill sets PEX_DEPLOY_TEST_FAIL=1 to prove the rollback path without breaking the code.
    [ "${PEX_DEPLOY_TEST_FAIL:-}" = 1 ] && return 1
    for _ in $(seq 20); do
        # -fs, not -fsS: a restart is expected to refuse connections for a second or two.
        curl -fs -m 2 "http://127.0.0.1:$PORT/hub/health" >/dev/null && return 0
        sleep 1
    done
    return 1
}

release "$new"
if healthy; then
    echo "Deployed $new"
    exit 0
fi

echo "Health check failed for $new; rolling back to $old" >&2
release "$old"
if PEX_DEPLOY_TEST_FAIL= healthy; then
    echo "Rolled back to $old" >&2
else
    echo "Rollback to $old is not healthy; the service needs attention" >&2
fi
exit 1
