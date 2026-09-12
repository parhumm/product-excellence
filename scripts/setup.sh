#!/bin/bash
# Install everything Product Excellence needs. Safe to run again at any time.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data

if ! command -v uv >/dev/null; then
    echo 'Installing uv (the Python installer this project uses)...'
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# uv downloads a matching Python itself, so no separate Python install is needed.
uv sync --frozen
.venv/bin/playwright install chromium firefox webkit

printf '\nSetup complete. Start with ./start.command\n'
