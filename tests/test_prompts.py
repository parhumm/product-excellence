import copy
import json

from engine.prompts import compact_json, evidence_json


def restore(encoded):
    packet = json.loads(encoded.split('\n', 1)[-1])
    originals = {}
    for observation in packet.get('observations', []):
        for field, source in observation.pop('same_as', {}).items():
            observation[field] = originals[source][field]
        originals[observation['id']] = observation
    return packet


def example_packet():
    observation = {
        'id': 'step-000', 'url': 'https://example.com',
        'text': 'فیلم Search movies — browsing evidence. ' * 100,
        'controls': [{'id': f'pex-{i}', 'text': f'Movie {i}', 'disabled': False,
                      'box': {'x': i * 10, 'y': 0, 'width': 100, 'height': 20}} for i in range(30)],
        'metrics': {'lcp': None, 'cls': 0, 'video': [{'stall_count': 0}]},
        'http_events': [], 'console_events': [],
    }
    return {'goal': 'Search movies', 'observations': [
        {**copy.deepcopy(observation), 'id': f'step-{i:03d}', 'visual_changed': i == 0}
        for i in range(4)], 'actions': [{'type': 'scroll', 'value': 'down'}]}


def test_repeated_evidence_round_trips_without_mutation():
    packet = example_packet()
    # Changed values, including unavailable vs zero, must remain explicit.
    packet['observations'][2]['metrics']['lcp'] = 0
    packet['observations'][3]['console_events'] = [{'kind': 'pageerror', 'message': 'failure'}]
    original = copy.deepcopy(packet)
    encoded = evidence_json(packet)
    assert restore(encoded) == packet == original
    assert len(encoded) < len(json.dumps(packet, ensure_ascii=False)) * .4
    assert 'فیلم' in encoded


def test_small_unique_and_reserved_observations_use_plain_json():
    for observations in [[], [{'id': 'a', 'text': 'A'}, {'id': 'b', 'text': 'B'}],
                         [{'id': 'a'}, {'id': 'a'}], [{'text': 'no ID'}],
                         [{'id': 'a', 'same_as': {'literal': 'content'}}]]:
        packet = {'observations': observations}
        assert evidence_json(packet) == compact_json(packet)


def test_compact_json_preserves_null_empty_false_and_unicode():
    packet = {'missing': None, 'zero': 0, 'disabled': False, 'empty': '', 'text': 'فیلم\nA B'}
    assert json.loads(compact_json(packet)) == packet


def observation():
    return {
        'id': 'step-003', 'url': 'https://example.com/x', 'title': 'خانه', 'lang': 'fa', 'dir': 'rtl',
        'text': 'فیلم Search movies', 'visual_changed': True,
        'viewport': {'width': 390, 'height': 844, 'scroll_y': 0},
        'controls': [{'id': 'pex-0', 'tag': 'a', 'role': '', 'text': 'Movie 1', 'input_type': '',
                      'href': 'https://example.com/movie?id=1', 'disabled': False, 'options': [],
                      'box': {'x': 24.546875, 'y': 0.4, 'width': 100.5, 'height': 20}},
                     {'id': 'pex-1', 'tag': 'select', 'role': 'listbox', 'text': '', 'input_type': '',
                      'href': '', 'disabled': True, 'options': [{'label': 'A', 'value': 'a'}],
                      'box': {'x': 0, 'y': 0, 'width': 0, 'height': 0}}],
        'metadata': {'description': 'd', 'robots': '', 'canonical': 'https://example.com/x',
                     'headings': [{'level': 1, 'text': 'H'}],
                     'jsonld': [{'@type': 'Movie'}], 'overflow': False},
        'metrics': {'lcp': None, 'cls': 0, 'inp': None, 'long_tasks': 2,
                    'video': [{'stall_count': 3, 'duration': 0}], 'player_events': [{'kind': 'waiting'}],
                    'errors': [], 'supported': ['lcp', 'cls'], 'ttfb_ms': 12.5, 'requests': 4,
                    'inp_note': 'Interaction latency needs a real interaction'},
        'axe': {'violations': 2, 'passes': 30, 'incomplete': 1},
        'screenshot': '/api/runs/a/artifacts/step-003.png', 'dom': '/api/runs/a/artifacts/step-003.dom.txt',
        'at': '2026-09-06T00:00:00Z',
        'http_events': [{'url': 'https://example.com/a.png', 'status': 200, 'method': 'GET',
                         'resource': 'image', 'at': '2026-09-06T00:00:00Z'},
                        {'url': 'https://example.com/b.png', 'status': 200, 'method': 'GET',
                         'resource': 'image', 'at': '2026-09-06T00:00:01Z'},
                        {'url': 'https://example.com/api', 'status': 500, 'method': 'GET',
                         'resource': 'fetch', 'at': '2026-09-06T00:00:02Z'},
                        {'url': 'https://example.com/post', 'status': 204, 'method': 'POST',
                         'resource': 'xhr', 'at': '2026-09-06T00:00:03Z'}],
        'console_events': [{'kind': 'pageerror', 'message': 'boom ' * 100, 'at': '2026-09-06T00:00:04Z'},
                           {'kind': 'warning', 'message': 'slow', 'at': '2026-09-06T00:00:05Z'}],
        'blocked_requests': [{'method': 'POST', 'url': 'https://example.com/api/auth/lookup'}],
    }


def test_control_projection_keeps_content_and_only_rounds_boxes():
    from engine.prompts import prompt_controls
    original = observation()['controls']
    projected = prompt_controls(original)
    assert [c['id'] for c in projected] == ['pex-0', 'pex-1']
    assert projected[0]['href'] == original[0]['href'] and projected[0]['text'] == 'Movie 1'
    assert projected[0]['box'] == {'x': 25, 'y': 0, 'width': 100, 'height': 20}
    # Empty, false and absent are the same thing for a control; a true flag is evidence.
    assert 'role' not in projected[0] and 'options' not in projected[0] and 'disabled' not in projected[0]
    assert projected[1]['disabled'] is True and projected[1]['options'] == [{'label': 'A', 'value': 'a'}]
    assert projected[1]['box'] == {'x': 0, 'y': 0, 'width': 0, 'height': 0}
    assert prompt_controls(original) == projected and observation()['controls'] == original


def test_http_projection_keeps_failures_and_counts_the_rest():
    from engine.prompts import prompt_http
    events = observation()['http_events']
    projected = prompt_http(events)
    assert projected['events'] == [{k: v for k, v in e.items() if k != 'at'}
                                   for e in events if e['status'] >= 300 or e['method'] != 'GET']
    assert projected['ok'] == {'image': 2}
    assert sum(projected['ok'].values()) + len(projected['events']) == len(events)
    assert prompt_http([]) == {}


def test_review_projection_keeps_every_kind_of_evidence():
    from engine.prompts import prompt_observation
    projected = prompt_observation(observation(), 'review')
    assert projected['text'] == observation()['text'] and projected['title'] == 'خانه'
    assert projected['metadata']['jsonld'] == [{'@type': 'Movie'}]
    # An unmeasurable metric stays null and a measured zero stays zero.
    assert projected['metrics']['lcp'] is None and projected['metrics']['cls'] == 0
    assert projected['metrics']['video'] == [{'stall_count': 3, 'duration': 0}]
    assert projected['metrics']['player_events'] == [{'kind': 'waiting'}]
    assert projected['axe'] == {'violations': 2, 'passes': 30, 'incomplete': 1}
    assert [e['message'] for e in projected['console_events']] == [c['message'] for c in observation()['console_events']]
    assert all('at' not in e for e in projected['console_events'])
    for dropped in ('screenshot', 'dom', 'at'):
        assert dropped not in projected
    assert 'supported' not in projected['metrics'] and 'inp_note' not in projected['metrics']


def test_action_projection_carries_state_and_problems_only():
    from engine.prompts import prompt_observation
    projected = prompt_observation(observation(), 'action')
    assert projected['id'] == 'step-003' and projected['visual_changed'] is True
    assert projected['headings'] == [{'level': 1, 'text': 'H'}]
    assert len(projected['controls']) == 2
    assert projected['problems']['failed_http'] == [{'url': 'https://example.com/api', 'status': 500}]
    assert projected['problems']['blocked_by_policy'] == ['POST https://example.com/api/auth/lookup']
    assert len(projected['problems']['console'][0]) == 200
    for dropped in ('metrics', 'metadata', 'axe', 'screenshot', 'dom', 'at', 'http_events'):
        assert dropped not in projected


def test_finding_and_action_projections_drop_bookkeeping_only():
    from engine.prompts import prompt_actions, prompt_finding, prompt_findings
    finding = {'id': 'x', 'run_id': 'r', 'fingerprint': 'fp', 'confidence': None, 'status': 'open',
               'owner': '', 'verifier_status': 'UNCONFIRMED', 'source': 'ai', 'rule': 'missing-h1',
               'pillar': 'seo_aeo', 'severity': 'P2', 'title': 'No H1', 'observed': 'none',
               'expected': 'one', 'recommendation': 'add', 'evidence_id': 'step-003',
               'url': 'https://example.com/x', 'classification': 'defect'}
    critic = prompt_finding(finding)
    assert critic['observed'] == 'none' and critic['title'] == 'No H1'
    assert not {'id', 'run_id', 'fingerprint', 'verifier_status'} & set(critic)
    assert prompt_findings([finding]) == [{'key': 'missing-h1', 'pillar': 'seo_aeo', 'severity': 'P2',
                                           'title': 'No H1', 'url': 'https://example.com/x',
                                           'evidence_id': 'step-003', 'source': 'ai'}]
    actions = [{'type': 'click', 'target': 'pex-0', 'value': '', 'reason': 'open movie',
                'outcome': 'continue', 'at': '2026-09-06T00:00:00Z', 'step': 0, 'status': 'executed',
                'evidence_before': 'step-002', 'evidence_after': 'step-003', 'state_changed': True}]
    assert prompt_actions(actions) == [{k: v for k, v in actions[0].items() if k not in ('at', 'outcome')}]


def test_each_projected_prompt_discloses_its_reshaping_once():
    from engine.prompts import CONTROL_NOTE, HTTP_NOTE, prompt_note
    for purpose in ('action', 'review', 'verify'):
        note = prompt_note(purpose)
        assert note.count(CONTROL_NOTE) == 1 and note.count(HTTP_NOTE) == 1
    assert prompt_note('unprojected') == ''


def test_review_keeps_console_source_and_leaves_stacks_in_evidence():
    from engine.prompts import prompt_observation, REVIEW_NOTE
    observation = {'id': 'step-000', 'url': 'https://example.com', 'console_events': [
        {'kind': 'pageerror', 'message': 'boom', 'name': 'TypeError', 'step': 1,
         'source': 'render (https://example.com/app.js:12:5)',
         'page_url': 'https://example.com/movie', 'stack': 'TypeError: boom\n at render', 'at': '2026-09-06T00:00:00Z'}]}
    event = prompt_observation(observation, 'review')['console_events'][0]
    assert event['source'] == 'render (https://example.com/app.js:12:5)'
    assert event['message'] == 'boom' and event['name'] == 'TypeError' and event['step'] == 1
    assert 'stack' not in event and 'page_url' not in event and 'at' not in event
    assert 'stack trace' in REVIEW_NOTE
