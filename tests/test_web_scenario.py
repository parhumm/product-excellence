"""One full scenario driven through the web runner: checks, an event, a hold, a screen, a pause and a goal.

The scaffold is the one the operator-pause tests already use, so the browser here is as real as it is
there: no Playwright, no AI, one fake page whose text the scenario changes under it.
"""
import asyncio
import importlib
import json
import time

import pytest

from tests.test_password_evidence import web_pause_journey

SCENARIO = [
    {'check': {'text': 'Now playing', 'within': 1}},
    {'event': {'network': 'offline'}},
    {'hold': {'text': 'Now playing', 'for': 1}},
    {'check': {'screen': {'contains': 'example.com'}, 'within': 1}},
    {'manual': 'Enter the code from the SMS', 'ask': 'SMS code', 'timeout': 30},
    {'goal': 'Open the account page'},
    {'check': {'no_crash': True, 'within': 1}},
]


def scenario_journey(tmp_path, monkeypatch, steps=SCENARIO, code='482913'):
    """Run one web scenario, releasing its operator step with `code`, and hand back what it recorded."""
    text = {'value': 'Now playing'}
    planned = [{'type': 'finish', 'target': '', 'value': '', 'options': [],
                'reason': 'The account page is open', 'outcome': 'success'}]

    def controls(value):
        return [{'id': 'pex-0', 'tag': 'input', 'role': '', 'input_type': 'tel',
                 'text': 'Code', 'href': '', 'filled': bool(value)}]

    async def release(worker, waiting, saved):
        assert waiting['ask'] == 'SMS code' and waiting['instruction'].startswith('Enter the code')
        # The page moves on while the operator works, the way a site does behind a person's hands.
        text['value'] = 'Account'
        await worker.continue_step('run-test', waiting['step'], waiting['token'], code)

    return web_pause_journey(tmp_path, monkeypatch, planned, controls, release,
                             mission_goal='Play a title across a dropped connection',
                             page_text=text, scenario=steps, pillars=['functionality'],
                             max_seconds=120)


def test_a_web_scenario_runs_its_steps_in_order_and_records_what_each_one_established(tmp_path, monkeypatch):
    out = scenario_journey(tmp_path, monkeypatch)
    run = out.run
    assert [s['status'] for s in run['scenario']] == ['passed'] * 7
    # The event reached the browser's own control, not a per-platform stand-in.
    assert out.context.set_offline.await_args_list[-1].args == (True,)
    assert run['scenario'][2]['kind'] == 'hold' and run['scenario'][3]['kind'] == 'check'
    assert run['scenario'][4]['reason'] == 'The operator supplied SMS code'
    assert run['mission_outcome'] == 'success' and run['scenario_coverage']['status'] == 'evaluated'
    assert run['scenario_digest'] and not [f for f in run['findings'] if f['rule'].startswith('scenario-')]


def test_the_value_the_operator_typed_is_typed_into_the_page_and_scrubbed_from_every_record(tmp_path, monkeypatch):
    out = scenario_journey(tmp_path, monkeypatch, code='482913')
    assert out.typed == ['482913']
    assert '482913' not in json.dumps(out.saved) and '482913' not in json.dumps(out.run)


def test_a_failed_required_check_blocks_the_steps_that_follow_and_becomes_a_finding(tmp_path, monkeypatch):
    async def release(worker, waiting, saved):
        raise AssertionError('This scenario asks nobody for anything')

    out = web_pause_journey(tmp_path, monkeypatch, [], lambda value: [], release,
                            mission_goal='Check the downloads screen', page_text={'value': 'Now playing'},
                            scenario=[{'check': {'text': 'Downloads', 'within': 1}},
                                      {'check': {'text': 'Now playing', 'within': 1}}],
                            pillars=['functionality'], max_seconds=120)
    run = out.run
    assert [s['status'] for s in run['scenario']] == ['failed', 'skipped']
    finding = next(f for f in run['findings'] if f['rule'].startswith('scenario-'))
    assert finding['rule'].endswith('-1-text') and finding['classification'] == 'defect'
    assert run['mission_outcome'] == 'blocked' and run['scenario_coverage']['status'] == 'partial'


def test_a_scenario_run_cannot_be_continued(tmp_path, monkeypatch):
    scenario_journey(tmp_path, monkeypatch)
    runtime = importlib.import_module('engine.runner')
    with pytest.raises(ValueError, match='cannot be continued'):
        asyncio.run(runtime.Runner().resume('run-test', 5, 5))


# --- a journey that changes its way out mid-run ------------------------------------------------

ROUTE = {'id': 'route-alpha-01', 'name': 'Route A', 'server': 'http://127.0.0.1:9001'}


def routed_journey(tmp_path, monkeypatch, exits, steps, **extra):
    """One web journey wired to a real relay whose probe answers with `exits`, in order.

    The relay itself is proved offline in tests/test_relay.py; what this exercises is the wiring:
    which proxy the context is given, what the run records, and what a failed switch does.
    """
    from unittest.mock import AsyncMock
    runtime = importlib.import_module('engine.runner')
    monkeypatch.setattr(runtime.routing.Relay, '_probe', AsyncMock(side_effect=exits))
    (tmp_path / 'secrets').mkdir()
    (tmp_path / 'secrets' / (ROUTE['id'] + '.json')).write_text('{"username": "u", "password": "p"}')

    async def release(worker, waiting, saved):
        raise AssertionError('This scenario asks nobody for anything')

    return web_pause_journey(tmp_path, monkeypatch, [], lambda value: [], release,
                             mission_goal='Watch a title from another country',
                             page_text={'value': 'Now playing'}, records={'egress': ROUTE},
                             run_extra={'routes': [dict(ROUTE)]}, scenario=steps,
                             pillars=['functionality'], max_seconds=120, **extra)


def test_a_route_step_switches_the_way_out_and_records_what_it_established(tmp_path, monkeypatch):
    out = routed_journey(tmp_path, monkeypatch, ['203.0.113.7', '198.51.100.4'],
                         [{'event': {'route': ROUTE['id']}}, {'check': {'text': 'Now playing', 'within': 1}}])
    run = out.run
    # The browser is pointed at the local relay, never at the upstream and never at its credentials.
    proxy = out.browser.new_context.await_args.kwargs['proxy']
    assert proxy['server'].startswith('http://127.0.0.1:') and set(proxy) == {'server'}
    assert [s['status'] for s in run['scenario']] == ['passed', 'passed']
    assert run['scenario'][0]['reason'] == 'Connections now exit through Route A from 198.51.100.4'
    # The initial route and the switch, each with the address it was seen to exit from.
    assert [c['status'] for c in run['route_checks']] == ['verified', 'verified']
    assert [c['observed_ip'] for c in run['route_checks']] == ['203.0.113.7', '198.51.100.4']
    assert [c['step'] for c in run['route_checks']] == [None, 1]
    assert run['faults'] == [{'route': ROUTE['id']}]
    assert 'DNS is resolved on the host' in run['egress']['verification']
    assert run['egress']['observed_ip'] == '203.0.113.7'
    assert run['route_traffic'][0]['generation'] == 1
    # The upstream's credentials stay in the relay: they reach neither the record nor the browser.
    assert '"password"' not in json.dumps(out.saved)


def test_a_switch_that_cannot_be_verified_stops_the_run_and_keeps_its_evidence(tmp_path, monkeypatch):
    out = routed_journey(tmp_path, monkeypatch, ['203.0.113.7', OSError('refused'), OSError('refused')],
                         [{'event': {'route': ROUTE['id']}}, {'check': {'text': 'Now playing', 'within': 1}}])
    run = out.run
    assert [s['status'] for s in run['scenario']] == ['error', 'skipped']
    assert 'could not be established' in run['scenario'][0]['reason']
    # The switch was requested and is recorded as such; nothing rolled back to direct.
    assert run['faults'] == [{'route': ROUTE['id']}]
    assert [c['status'] for c in run['route_checks']] == ['verified', 'unavailable']
    assert run['mission_outcome'] == 'blocked'


def test_a_run_with_no_route_steps_keeps_the_native_proxy(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    runtime = importlib.import_module('engine.runner')
    probe = AsyncMock()
    monkeypatch.setattr(runtime.routing.Relay, '_probe', probe)
    (tmp_path / 'secrets').mkdir()
    (tmp_path / 'secrets' / (ROUTE['id'] + '.json')).write_text('{"username": "u", "password": "p"}')

    async def release(worker, waiting, saved):
        raise AssertionError('This scenario asks nobody for anything')

    out = web_pause_journey(tmp_path, monkeypatch, [], lambda value: [], release,
                            mission_goal='Watch a title', page_text={'value': 'Now playing'},
                            records={'egress': ROUTE}, egress_id=ROUTE['id'],
                            scenario=[{'check': {'text': 'Now playing', 'within': 1}}],
                            pillars=['functionality'], max_seconds=120)
    assert out.browser.new_context.await_args.kwargs['proxy'] == {'server': ROUTE['server'],
                                                                  'username': 'u', 'password': 'p'}
    assert not probe.await_count and 'route_checks' not in out.run and 'faults' not in out.run


def test_shaping_asked_for_alongside_a_route_cannot_undo_the_switch_it_rides_on(tmp_path, monkeypatch):
    """One event, two operations. The route goes first, stands on its own, and a shaping failure
    after it still leaves the step un-passed. The mission contract rejects this pairing on a browser
    without CDP, so what is exercised here is what happens when shaping fails at the moment of use."""
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    web = importlib.import_module('engine.web')
    scenario = importlib.import_module('engine.scenario')
    check = {'status': 'verified', 'route_name': 'Route A', 'observed_ip': '198.51.100.4', 'error': ''}
    relay = SimpleNamespace(apply=AsyncMock(return_value=check), verify=AsyncMock())
    run = {'console': [], 'scenario': []}
    browser = web.Browser(None, None, None, {}, run, {}, str, [], [], relay)
    steps = scenario.Scenario([], browser, notify=None, goal='', deadline=time.monotonic() + 30)

    with pytest.raises(scenario.ScenarioError, match='Chromium'):
        asyncio.run(steps.apply({'route': ROUTE['id'], 'speed': 'edge'}))
    # The switch happened and is recorded; nothing rolled it back because the shaping failed.
    assert relay.apply.await_args.args == (ROUTE['id'], None) and relay.verify.await_count == 1
    assert browser.faults == [{'route': ROUTE['id']}]
