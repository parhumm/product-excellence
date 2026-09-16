"""The bundled report builder stays truthful to the run it is given."""
import importlib.util
import json
import pathlib

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.claude' / 'skills' / 'pex-run-brief' / 'scripts' / 'build_report.py'

RUN_ID = '0' * 32


def module():
    spec = importlib.util.spec_from_file_location('build_report', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def record():
    return {
        'id': RUN_ID, 'status': 'completed', 'mission_outcome': 'success', 'gate': 'warn',
        'created_at': '2026-01-02T10:00:00+00:00', 'duration_seconds': 630, 'ai_calls': 12,
        'provider': 'claude', 'ai_model': 'dynamic', 'policy_blocked_requests': 3,
        'mission': {'name': 'Example journey', 'url': 'https://example.test', 'browser': 'chromium',
                    'viewport': 'mobile', 'network': 'baseline', 'locale': 'en-US'},
        'network_snapshot': {'name': 'Baseline'},
        'actions': [{'summary': 'Click «Start»'}, {'summary': 'Finish: success'}],
        'observations': [{'id': 'step-000', 'url': 'https://example.test/'},
                         {'id': 'step-001', 'url': 'https://example.test/pricing'}],
        'findings': [{'severity': 'P2', 'title': 'Plans do not say whether they renew', 'pillar': 'cro',
                      'evidence_id': 'step-001', 'verifier_status': 'PROBABLE'}],
        'scores': {
            'cro': {'score': 85, 'deductions': [{'title': 'Plans do not say whether they renew',
                                                 'severity': 'P2', 'verifier_status': 'PROBABLE', 'points': 15}]},
            'performance': {'status': 'not_evaluated', 'score': None,
                            'reason': 'This pillar was not evaluated in this run'},
            'overall': {'score': 85, 'scored': 1, 'of': 2}},
        'ai_summary': {'headline': 'Recorded headline'},
    }


@pytest.fixture()
def run_folder(tmp_path, monkeypatch):
    folder = tmp_path / 'artifacts' / RUN_ID
    folder.mkdir(parents=True)
    (folder / 'run.json').write_text(json.dumps(record()))
    for step in ('step-000', 'step-001'):
        Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / f'{step}.png')
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    return folder


def narrative(**overrides):
    base = {
        'headline': 'A visitor can reach the plans but cannot tell whether they renew.',
        'improvements': [{'title': 'State whether plans renew', 'summary': 'No renewal wording anywhere.',
                          'impact': 'high', 'confidence': 'confirmed', 'evidence': 'step-001',
                          'alt': 'Pricing page', 'saw': 'Only "Cancel anytime" under the button.',
                          'matters': 'People cannot tell whether they will be charged again.',
                          'try': 'Add renewal wording under each plan.'}],
        'journey': [{'name': 'Home', 'evidence': 'step-000', 'alt': 'Home page',
                     'works': ['Plans are one tap away'], 'improve': ['No price on the first screen']}],
        'corrections': ['The run summary called the page gated; the screenshot shows it public.'],
        'not_covered': ['Checkout'],
    }
    return base | overrides


def build(folder, data):
    path = folder / 'narrative.json'
    path.write_text(json.dumps(data))
    out = folder / 'report.html'
    assert module().main([RUN_ID, '--narrative', str(path), '--out', str(out)]) == 0
    return out.read_text()


def test_the_report_carries_the_runs_own_numbers(run_folder):
    page = build(run_folder, narrative())
    assert 'release check warn' in page
    assert '85 of 100 across 1 of 2 pillars' in page and '>85<' in page
    # A pillar without an evaluation is never rendered as a zero.
    assert 'not scored' in page
    assert 'chromium' in page and 'mobile viewport' in page and '12 AI calls' in page
    assert 'Plans do not say whether they renew −15 (not confirmed)' in page
    assert 'https://example.test/pricing' in page
    assert '1 P2' in page and '3 mutating requests were blocked' in page


def test_the_narrative_supplies_only_judgment(run_folder):
    page = build(run_folder, narrative())
    assert 'cannot tell whether they renew' in page
    assert 'State whether plans renew' in page and 'High impact' in page and 'Confirmed' in page
    assert 'Add renewal wording under each plan.' in page
    assert 'the screenshot shows it public' in page
    assert 'data:image/jpeg;base64,' in page  # evidence travels with the file
    assert 'A completed run means the test finished' in page


def test_evidence_that_the_run_does_not_contain_is_refused(run_folder):
    broken = narrative(improvements=[{'title': 'Invented', 'evidence': 'step-404', 'saw': 'nothing'}])
    with pytest.raises(SystemExit) as stop:
        build(run_folder, broken)
    assert 'step-404' in str(stop.value)


def test_secrets_are_redacted(run_folder):
    leaky = narrative(not_covered=['Sign-in as person@example.test with password: hunter2'])
    page = build(run_folder, leaky)
    assert 'person@example.test' not in page and 'hunter2' not in page
    assert '&lt;email&gt;' in page


def test_a_missing_export_says_what_to_run(tmp_path, monkeypatch):
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    with pytest.raises(SystemExit) as stop:
        module().main(['a' * 32])
    assert 'cli.py export' in str(stop.value)
