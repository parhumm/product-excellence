#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets,json
p=Path('data/netem.json')
if not p.exists():
 token=secrets.token_hex(24);p.write_text(json.dumps({'url':'http://127.0.0.1:8752','token':token}));p.chmod(0o600)
else:token=json.loads(p.read_text())['token']
p=Path('linux/.env');p.write_text('PEX_NETEM_TOKEN='+token+'\n');p.chmod(0o600)
PY
docker compose --project-name product-excellence-netem -f linux/compose.yaml up -d --build
