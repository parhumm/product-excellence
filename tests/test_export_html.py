"""Export HTML from the run page: one AI call writes the reading, the record keeps the numbers."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app as service
from engine import ai, report, store
from engine.runner import Runner
from tests.test_skill_report import RUN_ID, record

NARRATIVE = {
    'headline': 'A visitor reaches the plans but cannot tell whether they renew.',
    'improvements': [
        {'title': 'State whether plans renew', 'summary': 'No renewal wording anywhere.', 'impact': 'high',
         'confidence': 'screenshot', 'evidence': 'step-001', 'alt': 'Pricing page',
         'saw': 'Only "Cancel anytime" under the button.', 'matters': 'People cannot tell whether they pay again.',
         'try': 'Add renewal wording under each plan.'},
        {'title': 'A screen this run never captured', 'summary': 'Invented.', 'impact': 'low',
         'confidence': 'unverified', 'evidence': 'step-404', 'alt': 'Nothing', 'saw': 'Nothing',
         'matters': 'Nothing', 'try': 'Nothing'}],
    'journey': [{'name': 'Home', 'evidence': 'step-000', 'alt': 'Home page',
                 'works': ['Plans are one tap away'], 'improve': ['No price on the first screen']}],
    'corrections': [], 'not_covered': ['Checkout']}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    monkeypatch.setattr(store, 'engine', engine)
    monkeypatch.setattr(store, 'Session', sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.setattr(store, 'ARTIFACTS', tmp_path / 'artifacts')
    store.ARTIFACTS.mkdir()
    worker = Runner()
    monkeypatch.setattr(service, 'runner', worker)

    async def no_execute():
        await asyncio.Event().wait()

    monkeypatch.setattr(worker, 'loop', no_execute)
    with TestClient(service.app, headers={'X-PEX-Request': '1'}) as c:
        yield c
    engine.dispose()


@pytest.fixture()
def run(client):
    """A finished run with its evidence on disk, as the console holds it."""
    saved = record() | {'project_id': 'default', 'mission_id': 'm1', 'visibility': 'local'}
    store.save('run', saved, local=True)
    folder = store.ARTIFACTS / RUN_ID
    folder.mkdir(parents=True)
    for step in ('step-000', 'step-001'):
        Image.new('RGB', (390, 844), (20, 24, 28)).save(folder / f'{step}.png')
    return folder


@pytest.fixture()
def worker(monkeypatch):
    """The AI worker, answered from here. Every call it receives is recorded."""
    seen = []

    async def health():
        return {'codex': {'logged_in': True, 'installed': True}, 'claude': {'logged_in': True, 'installed': True}}

    async def call(provider, prompt, schema, image=None, timeout=100, model='', effort='low', codex_account=''):
        seen.append({'provider': provider, 'prompt': prompt, 'images': image, 'model': model,
                     'effort': effort, 'codex_account': codex_account})
        return dict(NARRATIVE), {'model_reported': 'claude-opus-5'}

    monkeypatch.setattr(ai, 'health', health)
    monkeypatch.setattr(ai, 'call', call)
    return seen


def export(client, **body):
    return client.post(f'/api/runs/{RUN_ID}/report', json={'provider': 'claude', **body})


def test_the_report_is_html_the_run_can_back(client, run, worker):
    r = export(client)
    assert r.status_code == 200, r.text
    assert r.headers['content-type'].startswith('text/html')
    assert f'run-{RUN_ID}.html' in r.headers['content-disposition']
    page = r.text
    # The reading is the model's; every number stays the record's own.
    assert 'State whether plans renew' in page and 'cannot tell whether they renew' in page
    assert '85' in page and 'not scored' in page
    assert 'data:image/jpeg;base64,' in page
    assert 'Narrative written by claude · claude-opus-5' in page
    # A cited screen the run never captured is dropped, not rendered and not fatal.
    assert 'step-404' not in page and 'A screen this run never captured' not in page
    # A report about a private site must not phone a CDN when someone opens it.
    assert 'fonts.googleapis.com' not in page and 'src="http' not in page


def test_the_worker_reads_the_screens_and_is_told_what_not_to_invent(client, run, worker):
    export(client)
    assert len(worker) == 1
    sent = worker[0]
    assert [p.name for p in sent['images']] == ['step-000.png', 'step-001.png']
    assert 'Never invent a number' in sent['prompt'] and 'step-001' in sent['prompt']
    assert sent['provider'] == 'claude'


def test_the_choice_of_model_is_the_users_and_reaches_the_worker(client, run, worker):
    export(client, provider='codex', model='gpt-5.6-terra', codex_account='work')
    assert worker[0]['provider'] == 'codex'
    assert worker[0]['model'] == 'gpt-5.6-terra' and worker[0]['codex_account'] == 'work'
    # A named model is not the Dynamic ladder, so it runs at the review effort.
    assert worker[0]['effort'] == 'high'


def test_a_model_id_that_is_not_one_never_reaches_a_command_line(client, run, worker):
    assert export(client, model='claude-opus-5; rm -rf /').status_code == 422
    assert worker == []


def test_the_reading_is_paid_for_once_but_the_numbers_stay_current(client, run, worker):
    export(client)
    export(client)
    assert len(worker) == 1, 'The same worker and model reuse the narrative already written'
    kept = json.loads((run / 'report-narrative.json').read_text())
    assert kept['asked'] == {'provider': 'claude', 'model': ''}
    # A finding closed after the report was written shows up without another AI call.
    saved = store.get('run', RUN_ID)
    saved['scores']['cro']['score'] = 100
    store.save('run', saved, local=True)
    assert '100' in export(client).text
    assert len(worker) == 1
    # Another model is another reading.
    export(client, model='claude-sonnet-5')
    assert len(worker) == 2


def test_a_reading_survives_the_page_that_asked_for_it(client, run, monkeypatch):
    """A browser that drops mid-call must not throw minutes of paid reading away."""
    started, release = asyncio.Event(), asyncio.Event()

    async def health():
        return {'codex': {'logged_in': True, 'installed': True}, 'claude': {'logged_in': True, 'installed': True}}

    async def call(*a, **k):
        started.set()
        await release.wait()
        return dict(NARRATIVE), {'model_reported': 'claude-opus-5'}

    monkeypatch.setattr(ai, 'health', health)
    monkeypatch.setattr(ai, 'call', call)
    saved = store.get('run', RUN_ID)

    async def drop_then_ask_again():
        asked = asyncio.ensure_future(report.write_report(saved, run, 'claude'))
        await started.wait()
        asked.cancel()  # the connection goes, as uvicorn cancels the handler
        with pytest.raises(asyncio.CancelledError):
            await asked
        release.set()
        await asyncio.sleep(0)  # the worker was never waiting on the browser
        return json.loads((run / 'report-narrative.json').read_text())

    kept = asyncio.run(drop_then_ask_again())
    assert kept['narrative']['headline'] == NARRATIVE['headline']


def test_two_clicks_wait_on_one_call(client, run, worker):
    """The same run and choice asked for twice at once is one reading, not two bills."""
    saved = store.get('run', RUN_ID)

    async def both():
        return await asyncio.gather(report.write_report(saved, run, 'claude'),
                                    report.write_report(saved, run, 'claude'))

    first, second = asyncio.run(both())
    assert len(worker) == 1
    assert first == second


def test_a_fresh_reading_can_be_asked_for(client, run, worker):
    export(client)
    export(client, refresh=True)
    assert len(worker) == 2


def test_a_run_still_going_has_nothing_to_report(client, run, worker):
    saved = store.get('run', RUN_ID)
    saved['status'] = 'running'
    store.save('run', saved, local=True)
    r = export(client)
    assert r.status_code == 409 and 'finish' in r.json()['detail']
    assert worker == []


def test_a_worker_that_never_answers_says_so_instead_of_failing(client, run, worker, monkeypatch):
    async def call(*a, **k):
        raise TimeoutError

    monkeypatch.setattr(ai, 'call', call)
    r = export(client)
    # A reader waiting minutes deserves the reason, not a 500 they have to read a log for.
    assert r.status_code == 504 and 'faster model' in r.json()['detail']
    assert not (run / 'report-narrative.json').exists()


def test_a_worker_that_is_not_signed_in_says_so(client, run, monkeypatch):
    async def health():
        return {'codex': {'logged_in': False, 'installed': False}, 'claude': {'logged_in': False, 'installed': True}}

    monkeypatch.setattr(ai, 'health', health)
    r = export(client)
    assert r.status_code == 409 and 'Settings' in r.json()['detail']
