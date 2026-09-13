#!/bin/bash
# Install everything Product Excellence needs. Safe to run again at any time.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
android=0
if [[ "${1:-}" == "--android" ]]; then android=1
elif [[ $# -gt 0 ]]; then printf 'Usage: %s [--android]\n' "$0" >&2; exit 2
fi

if ! command -v uv >/dev/null; then
    echo 'Installing uv (the Python installer this project uses)...'
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# uv downloads a matching Python itself, so no separate Python install is needed.
uv sync --frozen
.venv/bin/playwright install chromium firefox webkit

if [[ "$android" -eq 1 ]]; then
    command -v brew >/dev/null || { printf 'Android setup automation currently requires Homebrew on macOS.\n' >&2; exit 1; }
    brew list android-commandlinetools >/dev/null 2>&1 || brew install android-commandlinetools
    brew list openjdk@17 >/dev/null 2>&1 || brew install openjdk@17
    sdk=$(brew --prefix)/share/android-commandlinetools
    java_home=$(brew --prefix openjdk@17)/libexec/openjdk.jdk/Contents/Home
    export JAVA_HOME="$java_home"
    arch=arm64-v8a; [[ "$(uname -m)" == arm64 ]] || arch=x86_64
    image="system-images;android-34;google_apis;$arch"
    "$sdk/cmdline-tools/latest/bin/sdkmanager" 'platform-tools' 'emulator' 'build-tools;36.0.0' 'platforms;android-34' "$image"
    avd=${PEX_ANDROID_AVD:-pex-test}
    if [[ -e "${ANDROID_AVD_HOME:-$HOME/.android/avd}/$avd.avd" ]]; then
        printf 'Keeping existing AVD %s\n' "$avd"
    else
        printf 'no\n' | "$sdk/cmdline-tools/latest/bin/avdmanager" create avd --name "$avd" --package "$image" --device pixel_7
    fi
    printf 'Android ready. Set PEX_ANDROID_AVD=%s when starting the console.\n' "$avd"
fi

printf '\nSetup complete. Start with ./start.command\n'
