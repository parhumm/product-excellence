"""One version, three files, one changelog entry: a half-done bump fails here."""
import pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]

def declared(path,pattern):
    found=re.search(pattern,(ROOT/path).read_text())
    assert found,f'no version found in {path}'
    return found.group(1)

def test_the_three_version_strings_agree():
    project=declared('pyproject.toml',r'(?m)^version\s*=\s*"([^"]+)"')
    assert declared('app.py',r"FastAPI\(title='Product Excellence',version='([^']+)'")==project
    assert declared('hub.py',r"FastAPI\(title='Product Excellence team server',version='([^']+)'")==project

def test_the_changelog_leads_with_that_version():
    project=declared('pyproject.toml',r'(?m)^version\s*=\s*"([^"]+)"')
    heading=re.search(r'(?m)^##\s+(\S+)\s+—\s+(\d{4}-\d{2}-\d{2})\s*$',(ROOT/'CHANGELOG.md').read_text())
    assert heading,'the newest changelog entry needs "## X.Y.Z — YYYY-MM-DD"'
    assert heading.group(1)==project,f'changelog says {heading.group(1)}, pyproject says {project}'

def test_the_team_server_reports_its_version():
    # pex-release-ship confirms a deploy from this field alone, without SSH.
    assert "'version':app.version" in (ROOT/'hub.py').read_text()
