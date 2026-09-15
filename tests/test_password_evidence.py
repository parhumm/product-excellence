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


def web_pause_journey(tmp_path, monkeypatch, planned, controls, release, mission_goal='Sign in with a code',
                      page_text=None, records=None, run_extra=None, **mission_extra):
    """Run one web journey that pauses for the operator, and hand back everything it recorded.

    `controls` names the page's controls for whatever is currently in the field, `release` answers
    the pause. `page_text` is a mutable `{'value': …}` a scenario can change between steps; without
    one the page reflects whatever is in the field. `records` answers reads of other kinds (an
    egress route, say) and `run_extra` puts fields on the run record the runner reads back.
    Returns saved records, prompts, the values filled in, the control ids clicked, and the
    browser, page, context and run the journey used.
    """
    from unittest.mock import Mock
    runtime = importlib.import_module('engine.runner')
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    mission = Mission(name='Fixture', url='https://example.com', goal=mission_goal,
                      browser='firefox', mode='journey', provider='codex',
                      ai_budget=5, max_steps=4, **mission_extra).model_dump()
    run = {'id': 'run-test', 'mission_id': 'mission-test', 'mission': mission,
           'status': 'queued', 'network_snapshot': NetworkProfile(name='Baseline').model_dump(),
           'observations': [], 'actions': [], 'events': [], 'findings': [], 'http': [],
           'console': [], 'coverage': {}, 'ai_calls': 0, 'ai_usage': [], 'ai_totals': {},
           'replay_of': '', 'baseline_id': '', **(run_extra or {})}
    saved, filled, clicked, prompts = [], [], [], []
    # A real field keeps what is already in it: fill replaces, press_sequentially appends.
    box = {'value': ''}

    async def write(kind, record):
        saved.append(copy.deepcopy(record))
        return record

    def visible():
        # The site reflects the number it was given, the way a "code sent to ..." line does.
        if page_text is not None:
            return page_text['value']
        return 'Code sent to ' + box['value'] if box['value'] else 'Sign in'

    async def evaluate(script, *args):
        if 'typeof window.axe' in script:
            return True
        if 'axe.run' in script:
            return {'violations': [], 'passes': [], 'incomplete': []}
        # The reads engine/web.py Browser makes of the live page, each answered as the page would.
        if '()=>document.body?' in script:
            return visible()
        if "querySelector('video,audio')" in script:
            return None
        if 'notifications)||[]).map' in script:
            return []
        if 'dispatchEvent' in script:
            return False
        return {'url': page.url, 'title': 'Sign in', 'text': visible(),
                'controls': controls(box['value']),
                'metadata': {}, 'viewport': {}, 'metrics': {'lcp': 0, 'inp': None}}

    async def screenshot(path, **kwargs):
        from pathlib import Path
        Path(path).write_bytes(b'fake screenshot')

    async def goto(*args, **kwargs):
        return SimpleNamespace(status=200, text=AsyncMock(return_value='<p>Sign in</p>'))

    async def ai_call(provider, prompt, schema, *args, **kwargs):
        prompts.append(prompt)
        if 'Choose ONE legitimate next browser action' in prompt:
            return planned.pop(0), runtime.ai.usage_record(provider, '', '', 'low')
        return ({'findings': [], 'executive_summary': {'headline': 'Reviewed', 'summary': 'All of it.',
                 'next_steps': ['Continue the run.']}}, runtime.ai.usage_record(provider, '', '', 'low'))

    def locator(selector):
        # Each control answers for itself, so the live recheck before actuation sees the real label.
        cid = selector.split('"')[1]
        c = next((x for x in controls(box['value']) if x['id'] == cid), {})
        return SimpleNamespace(
            evaluate=AsyncMock(return_value={'text': c.get('text', ''), 'href': c.get('href', ''),
                                             'input_type': c.get('input_type', ''), 'tag': c.get('tag', '')}),
            fill=AsyncMock(side_effect=lambda value: (filled.append(value), box.update(value=value))),
            press_sequentially=AsyncMock(side_effect=lambda value: (filled.append(value), box.update(value=box['value'] + value))),
            click=AsyncMock(side_effect=lambda: clicked.append(cid)))

    typed = []
    page = SimpleNamespace(url='https://example.com', video=None, set_default_timeout=Mock(),
        set_default_navigation_timeout=Mock(), on=Mock(), goto=goto, wait_for_load_state=AsyncMock(),
        wait_for_timeout=AsyncMock(), evaluate=evaluate, screenshot=screenshot,
        content=AsyncMock(return_value='<p>Sign in</p>'), locator=locator,
        # What engine/web.py Browser drives beyond observation: typing, history and the lifecycle.
        keyboard=SimpleNamespace(type=AsyncMock(side_effect=typed.append)),
        go_back=AsyncMock(), reload=AsyncMock(), bring_to_front=AsyncMock())
    context = SimpleNamespace(tracing=SimpleNamespace(start=AsyncMock(), stop=AsyncMock()),
        add_init_script=AsyncMock(), route=AsyncMock(), new_page=AsyncMock(return_value=page),
        on=Mock(), set_offline=AsyncMock(), close=AsyncMock(), storage_state=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    pw = SimpleNamespace(firefox=SimpleNamespace(launch=AsyncMock(return_value=browser)), stop=AsyncMock())
    monkeypatch.setattr(runtime, 'DATA', tmp_path)
    monkeypatch.setattr(runtime, 'ARTIFACTS', artifacts)
    monkeypatch.setattr(runtime, 'read',
                        AsyncMock(side_effect=lambda kind, id, *args: (records or {}).get(kind, run) if id else None))
    monkeypatch.setattr(runtime, 'write', write)
    monkeypatch.setattr(runtime.hub, 'enabled', lambda: False)
    monkeypatch.setattr(runtime, 'async_playwright', lambda: SimpleNamespace(start=AsyncMock(return_value=pw)))
    monkeypatch.setattr(runtime.ai, 'call', ai_call)

    async def journey():
        worker = runtime.Runner()
        task = asyncio.create_task(worker.execute('run-test'))
        for _ in range(600):
            await asyncio.sleep(0.01)
            if run.get('waiting_for') or task.done():
                break
        # A journey with nothing to ask never pauses; it is simply run to the end.
        waiting = dict(run['waiting_for']) if run.get('waiting_for') else {}
        if waiting:
            await release(worker, waiting, saved)
        await task
        return waiting

    return SimpleNamespace(waiting=asyncio.run(journey()), saved=saved, prompts=prompts,
                           filled=filled, clicked=clicked, box=box, typed=typed,
                           page=page, context=context, browser=browser, run=run)


def test_a_web_run_pauses_for_a_value_fills_it_and_scrubs_it(tmp_path, monkeypatch):
    """The operator supplies what the AI cannot invent, and the value stays out of every record."""
    import pytest
    supplied = '0912 345 6789'
    planned = [{'type': 'ask', 'target': 'pex-0', 'value': 'mobile number', 'options': [],
                'reason': 'The form needs a number I do not have', 'outcome': 'continue'},
               {'type': 'click', 'target': 'pex-1', 'value': '', 'options': [],
                'reason': 'The number is in the field; continue', 'outcome': 'continue'},
               {'type': 'finish', 'target': '', 'value': '', 'options': [], 'reason': 'Signed in', 'outcome': 'success'}]

    def controls(value):
        # Once the value has landed the page reports the field as filled, as observe.js does.
        return [{'id': 'pex-0', 'tag': 'input', 'role': '', 'input_type': 'tel',
                 'text': 'Mobile number', 'href': '', 'filled': bool(value)},
                {'id': 'pex-1', 'tag': 'button', 'role': '', 'input_type': '',
                 'text': 'Continue', 'href': '', 'filled': False}]

    async def release(worker, waiting, saved):
        assert waiting['kind'] == 'ask' and waiting['ask'] == 'mobile number' and waiting['needs_value'] is True
        # redact() blanks every key named token; the published record still has to carry this one.
        assert saved[-1]['waiting_for']['token'] == waiting['token']
        with pytest.raises(ValueError, match='no device to type on'):
            await worker.continue_step('run-test', waiting['step'], waiting['token'])
        await worker.continue_step('run-test', waiting['step'], waiting['token'], supplied)

    out = web_pause_journey(tmp_path, monkeypatch, planned, controls, release)
    # The field is cleared before the value is typed, or a second ask would append to the first.
    assert out.filled == ['', supplied] and out.box['value'] == supplied and 'Mobile number' in out.waiting['instruction']
    final = out.saved[-1]
    assert final['status'] == 'completed', final.get('error')
    assert [a['status'] for a in final['actions']] == ['executed', 'executed', 'executed']
    action_prompts = [p for p in out.prompts if 'Choose ONE legitimate next browser action' in p]
    assert all('A control with filled:true already holds its value' in p for p in action_prompts)
    # The first observation has nothing in the field; the second must carry the flag to the worker.
    assert '"filled":true' not in action_prompts[0] and '"filled":true' in action_prompts[1]
    assert final['observations'][-1]['text'] == 'Code sent to {{supplied}}'
    assert final['waiting_for'] is None
    assert all(supplied not in json.dumps(record) for record in out.saved)
    assert all(supplied not in prompt for prompt in out.prompts)


def test_a_web_run_hands_a_screen_of_several_ways_in_to_the_operator(tmp_path, monkeypatch):
    """A screen offering a password, a code by SMS and Google asks which way in, not for a secret."""
    import pytest
    planned = [{'type': 'choose', 'target': '', 'value': 'how to sign in', 'options': ['pex-0', 'pex-1', 'pex-2'],
                'reason': 'The screen offers three ways in', 'outcome': 'continue'},
               {'type': 'finish', 'target': '', 'value': '', 'options': [], 'reason': 'Signed in', 'outcome': 'success'}]
    ways = [('pex-0', 'Password'), ('pex-1', 'Get the code by SMS'), ('pex-2', 'Sign in with Google')]

    def controls(value):
        return [{'id': cid, 'tag': 'a', 'role': '', 'input_type': '', 'text': text,
                 'href': 'https://example.com/' + cid, 'filled': False} for cid, text in ways]

    async def release(worker, waiting, saved):
        assert waiting['kind'] == 'choose' and [o['label'] for o in waiting['options']] == [t for _, t in ways]
        # Only one of the offered controls releases the pause; anything else is refused.
        with pytest.raises(ValueError, match='Pick one of the offered options'):
            await worker.continue_step('run-test', waiting['step'], waiting['token'], 'pex-9')
        await worker.continue_step('run-test', waiting['step'], waiting['token'], 'pex-1')

    out = web_pause_journey(tmp_path, monkeypatch, planned, controls, release, mission_goal='Sign in')
    assert out.clicked == ['pex-1'] and out.filled == []
    final = out.saved[-1]
    assert final['status'] == 'completed', final.get('error')
    assert [a['status'] for a in final['actions']] == ['executed', 'executed']
    # The run records which way in was taken; a label is not a secret.
    assert (final['actions'][0]['target'], final['actions'][0]['value']) == ('pex-1', 'Get the code by SMS')
    assert 'return action choose' in [p for p in out.prompts if 'Choose ONE legitimate' in p][0]
