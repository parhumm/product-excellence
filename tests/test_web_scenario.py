"""One full scenario driven through the web runner: checks, an event, a hold, a screen, a pause and a goal.

The scaffold is the one the operator-pause tests already use, so the browser here is as real as it is
there: no Playwright, no AI, one fake page whose text the scenario changes under it.
"""
import asyncio
import importlib
import json

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
