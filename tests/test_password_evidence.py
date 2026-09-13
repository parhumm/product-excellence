"""Exercise the real runner's failure/persistence boundary without a browser or AI."""
import asyncio
import copy
import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from engine.contracts import Mission, NetworkProfile


def test_runner_scrubs_password_from_failure_and_saved_evidence(tmp_path, monkeypatch):
    runtime = importlib.import_module('engine.runner')
    secret = 'fixture-"\\reflected-password'
    (tmp_path / 'secrets').mkdir()
    (tmp_path / 'secrets' / 'mission-test.json').write_text(json.dumps({'password': secret}))
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    mission = Mission(name='Fixture', url='https://example.com', goal='Inspect the page',
                      mode='audit', provider='none', login_identifier='test@example.com').model_dump()
    run = {'id': 'run-test', 'mission_id': 'mission-test', 'mission': mission,
           'status': 'queued', 'network_snapshot': NetworkProfile(name='Baseline').model_dump(),
           'observations': [], 'actions': [], 'events': [], 'findings': [], 'http': [],
           'console': [], 'coverage': {}, 'ai_calls': 0, 'ai_usage': [], 'ai_totals': {},
           'replay_of': '', 'baseline_id': ''}
    saved = []

    async def write(kind, record):
        saved.append(copy.deepcopy(record))
        return record

    monkeypatch.setattr(runtime, 'DATA', tmp_path)
    monkeypatch.setattr(runtime, 'ARTIFACTS', artifacts)
    monkeypatch.setattr(runtime, 'read', AsyncMock(return_value=run))
    monkeypatch.setattr(runtime, 'write', write)
    monkeypatch.setattr(runtime.hub, 'enabled', lambda: False)
    monkeypatch.setattr(runtime, 'async_playwright', lambda: SimpleNamespace(
        start=AsyncMock(side_effect=RuntimeError('Browser failure: ' + secret))))
    asyncio.run(runtime.Runner().execute('run-test'))
    assert saved[-1]['status'] == 'failed'
    assert saved[-1]['error'] == 'Browser failure: {{password}}'
    assert all(json.dumps(secret)[1:-1] not in json.dumps(record) for record in saved)
    exported = json.loads((artifacts / 'run-test' / 'run.json').read_text())
    assert exported['error'] == saved[-1]['error']
    assert '{{password}}' in exported['events'][-1]['message']


def test_runner_scrubs_observations_before_prompts_and_persistence(tmp_path, monkeypatch):
    from unittest.mock import Mock
    runtime = importlib.import_module('engine.runner')
    secret = 'fixture-"\\reflected-password'
    (tmp_path / 'secrets').mkdir()
    (tmp_path / 'secrets' / 'mission-test.json').write_text(json.dumps({'password': secret}))
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    mission = Mission(name='Fixture', url='https://example.com', goal='Inspect the page',
                      browser='firefox', mode='audit', provider='codex',
                      login_identifier='test@example.com').model_dump()
    run = {'id': 'run-test', 'mission_id': 'mission-test', 'mission': mission,
           'status': 'queued', 'network_snapshot': NetworkProfile(name='Baseline').model_dump(),
           'observations': [], 'actions': [], 'events': [], 'findings': [], 'http': [],
           'console': [], 'coverage': {}, 'ai_calls': 0, 'ai_usage': [], 'ai_totals': {},
           'replay_of': '', 'baseline_id': ''}
    saved, prompts, handlers = [], [], {}

    async def write(kind, record):
        saved.append(copy.deepcopy(record))
        return record

    async def evaluate(script):
        if 'typeof window.axe' in script:
            return True
        if 'axe.run' in script:
            return {'violations': [], 'passes': [], 'incomplete': []}
        return {'url': 'https://example.com', 'title': secret, 'text': 'Reflected '+secret,
                'controls': [{'id': 'pex-0', 'tag': 'input', 'role': '', 'input_type': 'password',
                              'text': secret, 'href': ''}], 'metadata': {}, 'viewport': {},
                'metrics': {'lcp': 0, 'inp': None}}

    async def screenshot(path, **kwargs):
        from pathlib import Path
        Path(path).write_bytes(b'fake screenshot')

    async def goto(*args, **kwargs):
        handlers['console'](SimpleNamespace(type='error', text=secret, location={}))
        return SimpleNamespace(status=200, text=AsyncMock(return_value='<p>'+secret+'</p>'))

    async def ai_call(provider, prompt, *args, **kwargs):
        prompts.append(prompt)
        return {'findings': []}, runtime.ai.usage_record(provider, '', '', 'low')

    page = SimpleNamespace(url='https://example.com', video=None, set_default_timeout=Mock(), set_default_navigation_timeout=Mock(),
        on=lambda name, handler: handlers.update({name: handler}), goto=goto,
        wait_for_load_state=AsyncMock(), wait_for_timeout=AsyncMock(), evaluate=evaluate,
        screenshot=screenshot, content=AsyncMock(return_value='<p>'+secret+'</p>'), locator=Mock())
    context = SimpleNamespace(tracing=SimpleNamespace(start=AsyncMock(), stop=AsyncMock()),
        add_init_script=AsyncMock(), route=AsyncMock(), new_page=AsyncMock(return_value=page),
        on=Mock(), set_offline=AsyncMock(), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    pw = SimpleNamespace(firefox=SimpleNamespace(launch=AsyncMock(return_value=browser)), stop=AsyncMock())
    monkeypatch.setattr(runtime, 'DATA', tmp_path)
    monkeypatch.setattr(runtime, 'ARTIFACTS', artifacts)
    monkeypatch.setattr(runtime, 'read', AsyncMock(side_effect=lambda kind, id, *args: run if id else None))
    monkeypatch.setattr(runtime, 'write', write)
    monkeypatch.setattr(runtime.hub, 'enabled', lambda: False)
    monkeypatch.setattr(runtime, 'async_playwright', lambda: SimpleNamespace(start=AsyncMock(return_value=pw)))
    monkeypatch.setattr(runtime.ai, 'call', ai_call)
    asyncio.run(runtime.Runner().execute('run-test'))
    assert saved[-1]['status'] == 'completed', saved[-1].get('error')
    assert prompts and '{{password}}' in prompts[0]
    assert json.dumps(secret)[1:-1] not in prompts[0]
    obs = saved[-1]['observations'][0]
    assert obs['id'] == 'step-000' and obs['controls'][0]['id'] == 'pex-0'
    assert obs['controls'][0]['input_type'] == 'password'
    assert obs['text'] == 'Reflected {{password}}'
    assert obs['metrics'] == {'lcp': 0, 'inp': None}
    assert saved[-1]['console'][0]['message'] == '{{password}}'
    for path in (artifacts / 'run-test').glob('*.json'):
        assert json.dumps(secret)[1:-1] not in json.dumps(json.loads(path.read_text()))
    assert all(json.dumps(secret)[1:-1] not in json.dumps(record) for record in saved)


def test_budget_stop_still_spends_one_call_on_the_review(tmp_path, monkeypatch):
    """A journey that ends at its AI-call budget still gets its review, so the report is complete."""
    from unittest.mock import Mock
    runtime = importlib.import_module('engine.runner')
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    mission = Mission(name='Fixture', url='https://example.com', goal='Buy nothing',
                      browser='firefox', mode='journey', provider='codex',
                      ai_budget=1, max_steps=3).model_dump()
    run = {'id': 'run-test', 'mission_id': 'mission-test', 'mission': mission,
           'status': 'queued', 'network_snapshot': NetworkProfile(name='Baseline').model_dump(),
           'observations': [], 'actions': [], 'events': [], 'findings': [], 'http': [],
           'console': [], 'coverage': {}, 'ai_calls': 0, 'ai_usage': [], 'ai_totals': {},
           'replay_of': '', 'baseline_id': ''}
    saved, purposes = [], []

    async def write(kind, record):
        saved.append(copy.deepcopy(record))
        return record

    async def evaluate(script):
        if 'typeof window.axe' in script:
            return True
        if 'axe.run' in script:
            return {'violations': [], 'passes': [], 'incomplete': []}
        return {'url': 'https://example.com', 'title': 'Shop', 'text': 'Shop', 'controls': [],
                'metadata': {}, 'viewport': {}, 'metrics': {'lcp': 0, 'inp': None}}

    async def screenshot(path, **kwargs):
        from pathlib import Path
        Path(path).write_bytes(b'fake screenshot')

    async def goto(*args, **kwargs):
        return SimpleNamespace(status=200, text=AsyncMock(return_value='<p>Shop</p>'))

    async def ai_call(provider, prompt, schema, *args, **kwargs):
        if 'Choose ONE legitimate next browser action' in prompt:
            purposes.append('action')
            return ({'type': 'wait', 'target': '', 'value': '', 'reason': 'Let the page settle',
                     'outcome': 'continue'}, runtime.ai.usage_record(provider, '', '', 'low'))
        purposes.append('review')
        return ({'findings': [], 'executive_summary': {'headline': 'Reviewed', 'summary': 'All of it.',
                 'next_steps': ['Continue the run.']}}, runtime.ai.usage_record(provider, '', '', 'low'))

    page = SimpleNamespace(url='https://example.com', video=None, set_default_timeout=Mock(),
        set_default_navigation_timeout=Mock(), on=Mock(), goto=goto, wait_for_load_state=AsyncMock(),
        wait_for_timeout=AsyncMock(), evaluate=evaluate, screenshot=screenshot,
        content=AsyncMock(return_value='<p>Shop</p>'), locator=Mock())
    context = SimpleNamespace(tracing=SimpleNamespace(start=AsyncMock(), stop=AsyncMock()),
        add_init_script=AsyncMock(), route=AsyncMock(), new_page=AsyncMock(return_value=page),
        on=Mock(), set_offline=AsyncMock(), close=AsyncMock(), storage_state=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    pw = SimpleNamespace(firefox=SimpleNamespace(launch=AsyncMock(return_value=browser)), stop=AsyncMock())
    monkeypatch.setattr(runtime, 'DATA', tmp_path)
    monkeypatch.setattr(runtime, 'ARTIFACTS', artifacts)
    monkeypatch.setattr(runtime, 'read', AsyncMock(side_effect=lambda kind, id, *args: run if id else None))
    monkeypatch.setattr(runtime, 'write', write)
    monkeypatch.setattr(runtime.hub, 'enabled', lambda: False)
    monkeypatch.setattr(runtime, 'async_playwright', lambda: SimpleNamespace(start=AsyncMock(return_value=pw)))
    monkeypatch.setattr(runtime.ai, 'call', ai_call)
    asyncio.run(runtime.Runner().execute('run-test'))
    final = saved[-1]
    assert purposes == ['action', 'review']
    assert final['mission_outcome'] == 'budget_stop'
    assert final['ai_calls'] == 2 and final['mission']['ai_budget'] == 1
    assert final['ai_evaluation_completed'] and not final.get('evaluation_error')
    assert final['ai_usage'][-1]['purpose'] == 'review'
    assert final['ai_summary']['headline'] == 'Reviewed'
    # Every observation says which visit recorded it, so a continuation reads as a later part.
    assert {o['part'] for o in final['observations']} == {1}
