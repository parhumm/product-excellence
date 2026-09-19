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


def test_the_standard_limits_survive_a_narrative_that_adds_its_own(run_folder):
    page = build(run_folder, narrative(limits=['The site was mid-migration that week.']))
    assert 'A completed run means the test finished' in page
    assert 'One run, one browser' in page
    assert 'The site was mid-migration that week.' in page


def test_findings_the_reader_need_not_act_on_are_not_counted_as_open(tmp_path, monkeypatch):
    # engine/outcomes.py:actionable drops these two; the score table already does.
    data = record()
    data['findings'] += [{'severity': 'P1', 'title': 'Critic rejected this', 'verifier_status': 'REJECTED'},
                         {'severity': 'P0', 'title': 'Already fixed', 'status': 'resolved',
                          'verifier_status': 'CONFIRMED'}]
    folder = tmp_path / 'artifacts' / RUN_ID
    folder.mkdir(parents=True)
    (folder / 'run.json').write_text(json.dumps(data))
    for step in ('step-000', 'step-001'):
        Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / f'{step}.png')
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    page = build(folder, narrative())
    assert 'Open findings: 1 P2' in page
    assert 'P0' not in page and '1 P1' not in page


def test_an_evidence_id_without_a_screenshot_is_refused(run_folder):
    (run_folder / 'step-001.png').unlink()
    with pytest.raises(SystemExit) as stop:
        build(run_folder, narrative())
    assert 'step-001 has no screenshot' in str(stop.value)


def test_the_report_asks_nothing_of_the_network(run_folder):
    # A report about a private site must not phone a CDN when someone opens it.
    assert 'fonts.googleapis.com' not in build(run_folder, narrative())


# --- Android runs ---------------------------------------------------------------

def android_record():
    """An Android mission keeps the web defaults it never used; the run carries the truth."""
    data = record()
    data['platform'] = 'android'
    data['mission'] |= {'url': '', 'browser': 'chromium', 'viewport': 'desktop', 'locale': 'fa-IR'}
    data['target'] = {'package': 'com.example.app', 'type': 'android'}
    data['app'] = {'version_name': '4.54', 'target_sdk': 35,
                   'sha256': '662d68866a89532c6e209305e8d5003d8fcb9f28a75e11836191aa2bc01d65b7'}
    data['device'] = {'api': 34, 'abi': 'arm64-v8a', 'renderer': 'emulation', 'display': '1080x2400',
                      'density_dpi': 420, 'locale': 'en-US', 'launch_ms': None, 'jank_pct': None,
                      'pss_kb': 109106}
    data['network_applied'] = {'name': 'Baseline', 'scope': 'Device default; no traffic probe'}
    return data


@pytest.fixture()
def android_folder(tmp_path, monkeypatch):
    folder = tmp_path / 'artifacts' / RUN_ID
    folder.mkdir(parents=True)
    (folder / 'run.json').write_text(json.dumps(android_record()))
    for step in ('step-000', 'step-001'):
        Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / f'{step}.png')
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    return folder


def test_an_android_report_states_the_device_it_actually_ran_on(android_folder):
    page = build(android_folder, narrative())
    assert 'com.example.app' in page and 'version 4.54' in page
    assert 'SHA 662d68866a89' in page and 'API 34' in page and 'target SDK 35' in page
    assert 'arm64-v8a' in page and '1080x2400' in page and '420 dpi' in page
    # The mission's web defaults never applied to the emulator.
    assert 'chromium' not in page and 'desktop viewport' not in page
    assert 'One run, one emulated device' in page and 'disposable-emulator lab result' in page
    # An Android run never claims to say whether the website is fine.
    assert 'not that the app is fine' in page and 'website is fine' not in page


def test_android_measurements_taken_are_never_invented(android_folder):
    page = build(android_folder, narrative())
    assert 'PSS 109106 kB' in page          # measured
    assert 'launch ' not in page            # launch_ms was null
    assert 'jank ' not in page              # jank_pct was null


def test_a_blank_condition_never_prints_as_a_bare_label(tmp_path, monkeypatch):
    data = record()
    data['mission'] |= {'viewport': '', 'locale': '', 'network': ''}
    data['network_snapshot'] = {}
    folder = tmp_path / 'artifacts' / RUN_ID
    folder.mkdir(parents=True)
    (folder / 'run.json').write_text(json.dumps(data))
    Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / 'step-000.png')
    Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / 'step-001.png')
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    page = build(folder, narrative())
    # The conditions line drops what was not recorded instead of printing a dangling label.
    assert 'chromium, claude on dynamic, 2 steps, 12 AI calls' in page
    for dangling in (' viewport,', ' network,', 'locale ,', ', ,'):
        assert dangling not in page


# --- Benchmark runs -------------------------------------------------------------

HOME = '1' * 32
PLANS = '2' * 32


def benchmark_record(run_id, name, path, sites):
    """sites: [(host, outcome, rank, lcp)]; the first is the product's own site."""
    own = sites[0][0]
    return {
        'id': run_id, 'status': 'completed', 'mission_outcome': 'success', 'gate': 'pass',
        'created_at': '2026-01-02T10:00:00+00:00', 'ai_calls': 7, 'provider': 'claude',
        'mission': {'name': name, 'mode': 'benchmark', 'url': f'https://{own}{path}', 'browser': 'chromium',
                    'viewport': 'mobile', 'network': 'baseline', 'locale': 'en-US',
                    'competitors': [f'https://{h}{path}' for h, *_ in sites[1:]]},
        'observations': [{'id': f'step-00{i}', 'url': f'https://{h}{path}'} for i, (h, *_) in enumerate(sites)],
        'sites': [{'url': f'https://{h}{path}', 'outcome': outcome, 'reason': '',
                   'evidence_id': f'step-00{i}', 'metrics': {'lcp': lcp, 'ttfb_ms': 200}}
                  for i, (h, outcome, _, lcp) in enumerate(sites)],
        'benchmark': [{'url': f'https://{h}{path}', 'observed': f'{h} showed an error page' if outcome != 'success' else 'ok',
                       'rank': rank} for h, outcome, rank, _ in sites],
        'findings': [], 'actions': [],
    }


@pytest.fixture()
def benchmark_folders(tmp_path, monkeypatch):
    runs = {
        HOME: benchmark_record(HOME, 'Home benchmark', '/', [
            ('own.example', 'success', 2, 7368), ('alpha.example', 'success', 1, 3396),
            ('beta.example', 'success', 3, None)]),
        PLANS: benchmark_record(PLANS, 'Plans benchmark', '/plans', [
            ('own.example', 'success', 2, 3160), ('gamma.example', 'blocked', 3, 1668),
            ('alpha.example', 'success', 1, 2400)]),
    }
    for run_id, data in runs.items():
        folder = tmp_path / 'artifacts' / run_id
        folder.mkdir(parents=True)
        (folder / 'run.json').write_text(json.dumps(data))
        for seen in data['observations']:
            Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / f'{seen["id"]}.png')
            (folder / f'{seen["id"]}.dom.txt').write_text(
                '<html><head><title>Series | Own</title><meta name="robots" content="noindex nofollow"></head></html>')
    monkeypatch.setenv('PEX_DATA', str(tmp_path))
    return tmp_path


def playbook(**overrides):
    base = {
        'title': 'Own Benchmark',
        'headline': 'Own ranks second on both pages; the fixes are wording and layout.',
        'pages': {HOME[:8]: {'label': 'Home page', 'question': 'Is it clear what this is?',
                             'names': {'own.example': 'Own', 'alpha.example': 'Alpha'}}},
        'plays': [{
            'title': 'Say what the product is on the first screen', 'impact': 'high',
            'confidence': 'screenshot', 'copy_from': 'Alpha',
            'screens': [
                {'run': HOME[:8], 'evidence': 'step-000', 'who': 'Own · home', 'caption': 'Posters only.',
                 'marks': [{'x': 2, 'y': 11, 'w': 96, 'h': 4.5, 'label': 'First heading', 'below': True}]},
                {'run': HOME, 'evidence': 'step-001', 'who': 'Alpha · home', 'caption': 'Headline and price.'}],
            'code': [{'run': HOME[:8], 'evidence': 'step-000', 'side': 'today', 'who': 'Own',
                      'lines': ['<meta name="robots" content="noindex nofollow">']}],
            'today': 'The first heading is a poster row.',
            'best': ['Alpha: “Starts at €6.99. Cancel anytime.”'],
            'do': ['Add a one-line headline above the posters.']}],
        'keep': ['A free first episode.'],
    }
    return base | overrides


def build_benchmark(root, data, runs=(HOME, PLANS)):
    path = root / 'benchmark.json'
    path.write_text(json.dumps(data))
    out = root / 'benchmark.html'
    assert module().main([*runs, '--narrative', str(path), '--out', str(out)]) == 0
    return out.read_text()


def test_a_benchmark_report_takes_ranks_outcomes_and_speed_from_the_runs(benchmark_folders):
    page = build_benchmark(benchmark_folders, playbook())
    assert '<title>Own Benchmark</title>' in page
    # The product is placed among the sites that answered; a blocked site is struck, not ranked.
    assert '<b>2nd</b><span>of 3</span>' in page
    assert '<b>2nd</b><span>of 2 that answered</span>' in page
    assert '<li class="fail" title="blocked">gamma.example</li>' in page
    assert 'gamma.example did not answer in run 22222222 (blocked). gamma.example showed an error page' in page
    # Measured values are shown as measured; a missing one is never drawn as zero.
    assert '7.37 s' in page and '2.40 s' in page and 'not recorded' in page
    assert '1.67 s' not in page  # the blocked site's error page is not a comparison
    assert '14 AI calls' in page and '6 page visits' in page
    assert 'masks password, email, phone and one-time-code fields' in page


def test_benchmark_cards_show_whole_screenshots_with_marks(benchmark_folders):
    page = build_benchmark(benchmark_folders, playbook())
    assert page.count('width="390" height="844"') == 2  # never cropped or zoomed
    assert 'class="hl below" style="left:2%;top:11%;width:96%;height:4.5%"' in page
    assert 'Own · home' in page and 'https://own.example/ · step-000' in page
    assert '&lt;meta name=&quot;robots&quot; content=&quot;noindex nofollow&quot;&gt;' in page
    assert 'Copy: Alpha' in page and 'High impact' in page and 'Seen in screenshot' in page
    assert 'A free first episode.' in page


def test_a_benchmark_card_cannot_cite_what_the_runs_did_not_capture(benchmark_folders):
    missing = playbook()
    missing['plays'][0]['screens'][0]['evidence'] = 'step-009'
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, missing)
    assert 'step-009' in str(stop.value)

    stranger = playbook()
    stranger['plays'][0]['screens'][0]['run'] = '9' * 8
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, stranger)
    assert '99999999' in str(stop.value)


def test_a_code_excerpt_must_come_from_the_saved_page_source(benchmark_folders):
    invented = playbook()
    invented['plays'][0]['code'][0]['lines'] = ['<meta name="robots" content="index, follow">']
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, invented)
    assert 'not in the saved page source' in str(stop.value)


def test_a_mark_must_stay_on_the_screenshot(benchmark_folders):
    outside = playbook()
    outside['plays'][0]['screens'][0]['marks'][0]['x'] = 40
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, outside)
    assert 'inside it' in str(stop.value)


def test_only_benchmark_runs_share_a_report(benchmark_folders, run_folder):
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, playbook(), runs=(HOME, RUN_ID))
    assert 'every one of them is a benchmark run' in str(stop.value)


def test_a_mark_label_stays_on_its_screenshot(benchmark_folders):
    marks = playbook()
    marks['plays'][0]['screens'][0]['marks'] = [
        {'x': 44, 'y': 1, 'w': 35, 'h': 5, 'label': 'Only main action: Subscribe now, to /payment'},
        {'x': 2, 'y': 11, 'w': 96, 'h': 4.5, 'label': 'First heading'},
        {'x': 60, 'y': 30, 'w': 30, 'h': 5, 'label': 'Kept on the left', 'right': False}]
    page = build_benchmark(benchmark_folders, marks)
    # With more room to the left of the box, the label ends at the box's right edge and wraps there.
    assert 'class="hl right" style="left:44%;top:1%;width:35%;height:5%"><span style="max-width:calc(79cqw - 4px)">' in page
    assert 'class="hl" style="left:2%;top:11%;width:96%;height:4.5%"><span style="max-width:calc(98cqw - 4px)">' in page
    assert 'class="hl" style="left:60%;top:30%;width:30%;height:5%"><span style="max-width:calc(40cqw - 4px)">' in page


def test_a_site_that_did_not_answer_is_described_without_cutting_a_word(benchmark_folders):
    path = benchmark_folders / 'artifacts' / PLANS / 'run.json'
    record = json.loads(path.read_text())
    record['benchmark'][1]['observed'] = ('The page showed an error: "Da ist etwas schiefgelaufen" ("Something went '
                                          'wrong"). The product and promotions APIs returned 403, so no plans, prices, '
                                          'renewal terms or gift options appeared on the page at all.')
    path.write_text(json.dumps(record))
    page = build_benchmark(benchmark_folders, playbook())
    assert 'so no plans, prices, renewal terms or gift options…' in page
    assert 'gift options a<' not in page and 'gift options a…' not in page


def test_each_ranking_card_keeps_the_release_check_and_pillar_scores(benchmark_folders):
    path = benchmark_folders / 'artifacts' / HOME / 'run.json'
    record = json.loads(path.read_text())
    record['gate'] = 'warn'
    record['scores'] = {'cro': {'score': 58, 'deductions': []}, 'ux_ui': {'score': 52, 'deductions': []},
                        'overall': {'score': 55, 'scored': 2, 'of': 2}}
    path.write_text(json.dumps(record))
    page = build_benchmark(benchmark_folders, playbook())
    assert 'Release check <b>warn</b> · overall <b>55</b> of 100' in page
    assert '<li>Conversion <b>58</b></li>' in page and '<li>UX and UI <b>52</b></li>' in page
    # A pillar the run did not assess is named as not scored, never shown as zero.
    assert '<li class="unscored">Performance not scored</li>' in page
    assert 'Performance <b>0</b>' not in page
    assert 'Release check <b>pass</b>' in page  # the plans run keeps its own gate


def test_a_speed_card_can_chart_one_page_and_leave_the_rest_to_the_speed_section(benchmark_folders):
    one = playbook()
    one['plays'][0]['speed'] = HOME[:8]
    page = build_benchmark(benchmark_folders, one)
    card, section = page.split('id="speed"')
    assert 'Home page</td>' in card and 'Plans benchmark</td>' not in card
    assert 'Plans benchmark</td>' in section and 'Home page</td>' not in section

    everything = playbook()
    everything['plays'][0]['speed'] = True
    assert 'id="speed"' not in build_benchmark(benchmark_folders, everything)

    unknown = playbook()
    unknown['plays'][0]['speed'] = '9' * 8
    with pytest.raises(SystemExit) as stop:
        build_benchmark(benchmark_folders, unknown)
    assert '99999999' in str(stop.value)
