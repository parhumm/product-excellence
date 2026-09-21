import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest
from engine import ai


@pytest.mark.asyncio
async def test_health_checks_overlap_and_keep_provider_results(monkeypatch):
    monkeypatch.setattr(ai, 'client_binary', lambda provider: provider)
    monkeypatch.setattr(ai, 'codex_models', lambda: ['configured-model'])
    started = set()
    both_started = asyncio.Event()

    async def process(args, **kwargs):
        started.add(args[0])
        if len(started) == 2:
            both_started.set()
        # A serial implementation cannot pass this barrier.
        await asyncio.wait_for(both_started.wait(), 1)
        if args[0] == 'codex':
            assert kwargs['merge_stderr'] is True
            return 'Logged in using ChatGPT'
        return '{"loggedIn":true,"authMethod":"oauth","subscriptionType":"max"}'

    monkeypatch.setattr(ai, 'process', process)
    result = await ai.health()
    assert all(v['logged_in'] for v in result.values())
    # Models are catalog entries the console can render, with an estimated price each.
    claude = {e['value']: e for e in result['claude']['models']}
    assert claude['']['label'] == 'CLI default'
    assert claude['claude-sonnet-5']['price_hint'] == '$2 in / $10 out per MTok'
    configured = [e for e in result['codex']['models'] if e['value'] == 'configured-model']
    assert configured and configured[0]['price_hint'] == ''
    assert result['claude']['subscription'] == 'Max subscription'


@pytest.mark.asyncio
async def test_health_failure_does_not_hide_other_provider(monkeypatch):
    monkeypatch.setattr(ai, 'client_binary', lambda provider: provider)
    monkeypatch.setattr(ai, 'codex_models', lambda: [])

    async def process(args, **kwargs):
        if args[0] == 'codex':
            raise asyncio.TimeoutError()
        return '{"loggedIn":true,"authMethod":"api_key"}'

    monkeypatch.setattr(ai, 'process', process)
    result = await ai.health()
    assert all(v['installed'] and not v['logged_in'] for v in result.values())


@pytest.mark.asyncio
async def test_process_reads_stderr_only_when_requested():
    args = [sys.executable, '-c', 'import sys; print("status", file=sys.stderr)']
    assert await ai.process(args) == ''
    assert (await ai.process(args, merge_stderr=True)).strip() == 'status'


def test_codex_home_ignores_an_inherited_parent_session(monkeypatch, tmp_path):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'configured-home'))
    monkeypatch.delenv('PEX_CODEX_HOME', raising=False)
    assert ai.codex_home() == Path.home() / '.codex'
    selected = tmp_path / 'account-one'
    monkeypatch.setenv('PEX_CODEX_HOME', str(selected))
    assert ai.codex_home() == selected


def test_codex_home_selects_only_signed_in_named_profiles(monkeypatch, tmp_path):
    monkeypatch.setattr(ai.Path, 'home', lambda: tmp_path)
    profile=tmp_path/'.codex-work';profile.mkdir();(profile/'auth.json').write_text('{}')
    assert ai.codex_home('work') == profile
    with pytest.raises(ValueError,match='not signed in'):ai.codex_home('missing')
    with pytest.raises(ValueError,match='available'):ai.codex_home('../escape')


def test_process_error_collapses_repeated_codex_state_warnings():
    warning = ('2026 WARN codex_rollout::list: state db discrepancy during '
               'find_thread_path_by_id_str_in_subdir: falling_back')
    result = ai.process_error(b'', (warning+'\n'+warning+'\nYour workspace is out of credits.').encode())
    assert result == ('Codex recovered from 2 local session-state discrepancies.\n'
                      'Your workspace is out of credits.')


def test_worker_schemas_require_every_object_property():
    def check(schema):
        if schema.get('type') == 'object':
            assert set(schema['required']) == set(schema['properties'])
            assert schema['additionalProperties'] is False
            for child in schema['properties'].values(): check(child)
        if schema.get('type') == 'array': check(schema['items'])
    for schema in (ai.ACTION_SCHEMA, ai.EVAL_SCHEMA, ai.VERIFY_SCHEMA): check(schema)


@pytest.mark.asyncio
@pytest.mark.parametrize('event', [
    {'type': 'error', 'message': 'invalid_json_schema: Missing benchmark'},
    {'type': 'turn.failed', 'error': {'message': 'invalid_json_schema: Missing benchmark'}},
])
async def test_process_reports_structured_failure_over_startup_noise(event):
    script = ('import sys; print("Reading prompt from stdin... model refresh timeout", file=sys.stderr); '
              f'print({json.dumps(event)!r}); print("null"); print("not JSON"); sys.exit(1)')
    with pytest.raises(RuntimeError, match='^invalid_json_schema: Missing benchmark$'):
        await ai.process([sys.executable, '-c', script])


SCHEMA = {'type': 'object', 'properties': {'answer': {'type': 'string'}},
          'required': ['answer'], 'additionalProperties': False}
CLAUDE_RESULT = json.dumps({
    'type': 'result', 'structured_output': {'answer': 'ok'}, 'duration_ms': 4012,
    'total_cost_usd': 0.0071, 'modelUsage': {'claude-haiku-4-5-20251001': {'costUSD': 0.0071}},
    'usage': {'input_tokens': 20, 'cache_read_input_tokens': 4629, 'output_tokens': 40,
              'cache_creation_input_tokens': 5087,
              'cache_creation': {'ephemeral_5m_input_tokens': 5087, 'ephemeral_1h_input_tokens': 0}}})
CODEX_EVENTS = '\n'.join([
    json.dumps({'type': 'session.created', 'session': {'model': 'gpt-5.6-terra'}}),
    'not json at all',
    json.dumps({'type': 'item.completed', 'item': {'type': 'reasoning'}}),
    json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 900,
                                                    'cached_input_tokens': 400, 'output_tokens': 60}}),
])


@pytest.fixture
def worker(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, 'client_binary', lambda provider: provider)
    monkeypatch.setattr(ai, 'DATA', tmp_path)
    seen = {}

    def record(reply, write_answer=False):
        async def process(args, text='', timeout=120, cwd=None, merge_stderr=False,
                          env_overrides=None):
            seen.update(args=args, text=text, timeout=timeout, env_overrides=env_overrides)
            if write_answer:
                (Path(cwd) / 'answer.json').write_text(json.dumps({'answer': 'ok'}))
            return reply
        monkeypatch.setattr(ai, 'process', process)
    return seen, record


@pytest.mark.asyncio
async def test_claude_call_replaces_the_client_system_prompt_and_reports_usage(worker):
    seen, record = worker
    record(CLAUDE_RESULT)
    result, usage = await ai.call('claude', 'Only the task text.', SCHEMA, model='claude-haiku-4-5')
    assert result == {'answer': 'ok'}
    # The safety rules travel as the system prompt, so they are not repeated in the input.
    assert '--system-prompt' in seen['args']
    assert seen['args'][seen['args'].index('--system-prompt') + 1] == ai.SAFE_SYSTEM
    assert seen['text'] == 'Only the task text.'
    assert usage['model_reported'] == 'claude-haiku-4-5-20251001'
    assert (usage['input_tokens'], usage['cached_tokens']) == (20, 4629)
    assert (usage['cache_write_5m_tokens'], usage['cache_write_1h_tokens']) == (5087, 0)
    assert (usage['output_tokens'], usage['cli_cost_usd'], usage['duration_ms']) == (40, 0.0071, 4012)
    assert usage['est_cost_usd'] == pytest.approx(round(0.00704164, 6))
    # The wrapper keeps its original single-value contract.
    assert await ai.ask('claude', 'Only the task text.', SCHEMA,
                        model='claude-haiku-4-5') == {'answer': 'ok'}


@pytest.mark.asyncio
async def test_claude_streaming_transcript_yields_the_same_usage(worker, tmp_path):
    seen, record = worker
    image = tmp_path / 'shot.png'; image.write_bytes(b'PNG')
    record('\n'.join(['{"type":"system"}', '', CLAUDE_RESULT]))
    _, usage = await ai.call('claude', 'Task', SCHEMA, image=image)
    assert '--input-format' in seen['args'] and usage['input_tokens'] == 20
    assert usage['est_cost_usd'] == pytest.approx(round(0.00704164, 6))


@pytest.mark.asyncio
async def test_several_screens_travel_as_several_images(worker, tmp_path):
    """The report reads a whole journey, so one call carries more than one screen."""
    seen, record = worker
    shots = []
    for name in ('step-000.png', 'step-001.png'):
        shot = tmp_path / name; shot.write_bytes(b'PNG'); shots.append(shot)
    record('\n'.join(['{"type":"system"}', CLAUDE_RESULT]))
    await ai.call('claude', 'Task', SCHEMA, image=shots)
    blocks = json.loads(seen['text'])['message']['content']
    assert [b['type'] for b in blocks] == ['image', 'image', 'text']
    assert {b['source']['data'] for b in blocks[:2]} == {base64.b64encode(b'PNG').decode()}
    record(CODEX_EVENTS, write_answer=True)
    await ai.call('codex', 'Task', SCHEMA, image=shots)
    assert [seen['args'][i + 1] for i, a in enumerate(seen['args']) if a == '--image'] == [str(p) for p in shots]


@pytest.mark.asyncio
async def test_codex_call_parses_event_usage_and_separates_cached_input(worker):
    seen, record = worker
    record(CODEX_EVENTS, write_answer=True)
    result, usage = await ai.call('codex', 'Task', SCHEMA)
    assert result == {'answer': 'ok'} and '--json' in seen['args']
    assert seen['env_overrides'] == {'CODEX_HOME': ai.codex_home()}
    assert seen['text'].startswith(ai.SAFE_SYSTEM)
    assert usage['model_reported'] == 'gpt-5.6-terra'
    # Codex counts cached tokens inside input_tokens; the shared shape keeps them apart.
    assert (usage['input_tokens'], usage['cached_tokens'], usage['output_tokens']) == (500, 400, 60)
    assert usage['est_cost_usd'] == pytest.approx(round((500 * 2 + 400 * .2 + 60 * 12) / 1e6, 6))


@pytest.mark.asyncio
async def test_codex_call_uses_the_selected_account(worker, monkeypatch, tmp_path):
    seen, record = worker
    record(CODEX_EVENTS, write_answer=True)
    selected=tmp_path/'selected-codex'
    monkeypatch.setattr(ai, 'codex_home', lambda account='': selected if account=='work' else tmp_path)
    await ai.call('codex','Task',SCHEMA,codex_account='work')
    assert seen['env_overrides'] == {'CODEX_HOME':selected}


@pytest.mark.asyncio
async def test_codex_without_a_model_event_falls_back_to_the_configured_model(worker, monkeypatch):
    seen, record = worker
    monkeypatch.setattr(ai, 'codex_models', lambda: ['gpt-6-astra'])
    record(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}),
           write_answer=True)
    _, usage = await ai.call('codex', 'Task', SCHEMA)
    assert usage['model_reported'] == 'gpt-6-astra'
    assert usage['model_reported_source'] == 'configured'
    assert usage['cached_tokens'] is None and usage['est_cost_usd'] == pytest.approx(3.5e-4)


def test_reported_model_is_the_one_that_answered_not_a_side_call():
    """The CLI bills a small side call to another model; usage belongs to the answer."""
    outer = {'usage': {'input_tokens': 2, 'output_tokens': 53, 'cache_read_input_tokens': 675,
                       'cache_creation_input_tokens': 0},
             'modelUsage': {'claude-haiku-4-5-20251001': {'inputTokens': 898, 'outputTokens': 11,
                                                          'cacheReadInputTokens': 0,
                                                          'cacheCreationInputTokens': 0,
                                                          'costUSD': 0.000953},
                            'claude-opus-5': {'inputTokens': 2, 'outputTokens': 53,
                                              'cacheReadInputTokens': 675,
                                              'cacheCreationInputTokens': 0, 'costUSD': 0.001672}}}
    assert ai.claude_usage(outer, 'claude-opus-5', 'low')['model_reported'] == 'claude-opus-5'
    # With no exact match the largest consumer answered; a single entry needs no choice.
    outer['usage'] = {}
    assert ai.claude_usage(outer, '', 'low')['model_reported'] == 'claude-opus-5'
    outer['modelUsage'].pop('claude-opus-5')
    assert ai.claude_usage(outer, '', 'low')['model_reported'] == 'claude-haiku-4-5-20251001'


def test_dynamic_choice_uses_deep_review_below_the_frontier():
    choose = ai.dynamic_choice
    assert choose('claude', 'action') == ('claude-haiku-4-5', 'low')
    assert choose('claude', 'verify') == ('claude-sonnet-5', 'low')
    assert choose('claude', 'judgment') == ('claude-sonnet-5', 'medium')
    # Deep review needs Opus/Sol; a frontier ceiling is an allowance, not a target.
    assert choose('claude', 'review') == ('claude-opus-5', 'high')
    assert choose('codex', 'review') == ('gpt-5.6-sol', 'high')
    assert choose('claude', 'review', 'claude-fable-5-1') == ('claude-opus-5', 'high')
    assert choose('claude', 'review', 'claude-sonnet-5') == ('claude-sonnet-5', 'high')
    # A ceiling caps the cheap calls too, and never below itself.
    assert choose('claude', 'verify', 'claude-haiku-4-5') == ('claude-haiku-4-5', 'low')


def test_dynamic_choice_escalates_a_stuck_journey_within_the_ceiling():
    assert ai.dynamic_choice('claude', 'action', '', 1) == ('claude-sonnet-5', 'medium')
    assert ai.dynamic_choice('claude', 'action', '', 2) == ('claude-opus-5', 'high')
    assert ai.dynamic_choice('claude', 'action', 'claude-sonnet-5', 2) == ('claude-sonnet-5', 'high')
    # Effort stops at the top of the scale even when the boost keeps growing.
    assert ai.dynamic_choice('codex', 'action', '', 9) == ('gpt-6-astra', 'xhigh')


def test_dynamic_choice_keeps_the_tier_when_the_run_falls_back_to_the_other_worker():
    # The mission named a Claude ceiling; Codex answers at the same tier, not above it.
    assert ai.dynamic_choice('codex', 'review', 'claude-opus-5') == ('gpt-5.6-sol', 'high')
    assert ai.dynamic_choice('codex', 'action', 'claude-opus-5') == ('gpt-5.6-luna', 'low')
    # A model id the catalog does not list still caps the ladder.
    assert ai.dynamic_choice('claude', 'review', 'claude-sonnet-4-5') == ('claude-sonnet-4-5', 'high')


def test_dynamic_p1_critic_boost_respects_ceiling_and_provider():
    assert ai.dynamic_choice('claude', 'verify', boost=1) == ('claude-opus-5', 'medium')
    assert ai.dynamic_choice('codex', 'verify', boost=1) == ('gpt-5.6-sol', 'medium')
    assert ai.dynamic_choice('codex', 'verify', 'claude-sonnet-5', 1) == ('gpt-5.6-terra', 'medium')
    assert ai.dynamic_choice('claude', 'review', 'custom-model') == ('custom-model', 'high')
