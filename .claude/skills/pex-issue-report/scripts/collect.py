#!/usr/bin/env python3
"""Facts for a bug report about Product Excellence itself, with secrets removed.

    .venv/bin/python .claude/skills/pex-issue-report/scripts/collect.py [run id]

Prints markdown on stdout. It reads only the version files, git, the local API
and the two application logs. It never opens data/secrets, personas or
recordings, and it redacts anything shaped like a password, token, cookie,
email address or sign-in identifier before printing.
"""
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[4]
API = 'http://127.0.0.1:8741/api'
LOGS = ('data/app.log', 'data/server.log', 'data/service.log')

SECRET = [
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '<email>'),
    (re.compile(r'(?i)\b(password|passwd|secret|token|cookie|authorization|api[_-]?key|login_identifier)\b\s*[:=]\s*\S+'), r'\1: <redacted>'),
    (re.compile(r'(?i)\bbearer\s+\S+'), 'bearer <redacted>'),
    # A run id or a fingerprint is lower-case hex and belongs in the report; anything
    # else this long is a token, a cookie or a session identifier.
    (re.compile(r'\b[A-Za-z0-9_-]{32,}\b'), lambda m: m.group() if re.fullmatch(r'[0-9a-f]{32}', m.group()) else '<redacted-long-string>'),
    (re.compile(r'\b(?:\+?\d[\d -]{8,}\d)\b'), '<number>'),
]


def clean(text):
    text = str(text)
    for pattern, replacement in SECRET:
        text = pattern.sub(replacement, text)
    return text


def run(*command):
    try:
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:  # a missing tool is a fact worth printing, not a crash
        return f'not available ({e.__class__.__name__})'


def get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=10) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {'error': f'{e.__class__.__name__}: {e}'}


def summary(health):
    """The readiness facts, without the model catalogue that dwarfs them."""
    if 'error' in health:
        return health
    ai = {k: {'logged_in': v.get('logged_in'), 'subscription': v.get('subscription')}
          for k, v in (health.get('ai') or {}).items()}
    return {k: v for k, v in health.items() if k in ('ok', 'version', 'database', 'browsers', 'networks')} | {'ai': ai}


def tail(path, keep, run_id):
    p = ROOT / path
    if not p.is_file():
        return []
    lines = p.read_text(errors='replace').splitlines()
    return [l for l in lines if (run_id and run_id in l) or 'Traceback' in l or 'ERROR' in l or 'Error' in l][-keep:]


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else ''
    version = ''
    for line in (ROOT / 'pyproject.toml').read_text().splitlines():
        if line.startswith('version'):
            version = line.split('=', 1)[1].strip().strip('"')
            break

    out = ['## Environment', '',
           f'- Product Excellence {version}',
           f"- commit {run('git', 'rev-parse', '--short', 'HEAD')} on {run('git', 'rev-parse', '--abbrev-ref', 'HEAD')}",
           f"- macOS {run('sw_vers', '-productVersion')} on {run('uname', '-m')}",
           f"- Python {sys.version.split()[0]}", '']

    health = get('/health')
    out += ['<details><summary>Health</summary>', '', '```json',
            clean(json.dumps(summary(health), indent=2)[:4000]), '```', '</details>', '']

    if run_id:
        r = get(f'/runs/{run_id}')
        events = [e.get('message', '') for e in (r.get('events') or [])][-5:]
        out += ['## The run', '',
                f"- id `{run_id}`",
                f"- status {r.get('status', 'unknown')}, outcome {r.get('mission_outcome', 'none')}",
                f"- error: {clean(r.get('error') or 'none')}",
                f"- mode {(r.get('mission') or {}).get('mode', '?')}, browser {(r.get('mission') or {}).get('browser', '?')},"
                f" viewport {(r.get('mission') or {}).get('viewport', '?')}, network {(r.get('mission') or {}).get('network', '?')},"
                f" provider {r.get('provider', '?')}", '',
                'Last events:', '']
        out += [f'- {clean(e)}' for e in events] or ['- none recorded']
        out.append('')

    logged = False
    for path in LOGS:
        lines = tail(path, 25, run_id)
        if lines:
            logged = True
            out += [f'<details><summary>{path}</summary>', '', '```',
                    clean('\n'.join(lines)), '```', '</details>', '']
    if not logged:
        out += ['No error or matching lines in ' + ', '.join(LOGS) + '.', '']

    print('\n'.join(out))


if __name__ == '__main__':
    main()
