"""Lossless prompt compaction; stored browser evidence stays unchanged."""
import json


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def evidence_json(packet):
    """Share identical observation fields without truncating or summarizing them.

    References always point to an earlier, explicitly supplied field. Use the
    encoding only when its explanation and references are smaller than plain JSON.
    """
    plain = compact_json(packet)
    observations = packet.get('observations', [])
    ids = [o.get('id') for o in observations]
    if not observations or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        return plain
    if any('same_as' in o for o in observations):
        return plain
    seen = {}
    packed = []
    for observation in observations:
        item = {}
        references = {}
        for field, value in observation.items():
            encoded = compact_json(value)
            key = (field, encoded)
            previous = seen.get(key)
            if field != 'id' and previous is not None and len(encoded) > len(compact_json(previous)) + 16:
                references[field] = previous
            else:
                item[field] = value
                seen.setdefault(key, observation['id'])
        if references:
            item['same_as'] = references
        packed.append(item)
    note = ('Observation same_as maps omitted field names to earlier observation IDs. '
            'Each omitted value is exactly equal to that earlier field, not missing.\n')
    encoded = note + compact_json({**packet, 'observations': packed})
    return encoded if len(encoded) < len(plain) else plain


# --- Task-specific projections -------------------------------------------------
# Each projection removes only fields the receiving task cannot use, or restates
# them more briefly. Stored evidence on disk is never touched. Every reshaping
# rule below is disclosed to the model once, through prompt_note().

CONTROL_NOTE = ('Control fields that are empty, false or an empty list are omitted; '
                'box is the on-screen rectangle in whole CSS pixels.')
HTTP_NOTE = ('http lists every response that failed or used a non-GET method; '
             'http.ok counts the remaining successful responses by resource type.')
ACTION_NOTE = ('Each observation carries the page state and its controls. problems lists console '
               'errors, failed responses and requests the read-only policy blocked, all seen '
               'since the previous observation.')
REVIEW_NOTE = ('Observations keep their full text, metadata, metrics, accessibility counts, '
               'console and video evidence. A metric that is null was not measurable, which '
               'is different from a measured zero. Timestamps and artifact paths are omitted. '
               'A console event keeps its source location; its stack trace and page URL stay in '
               'stored evidence and in the finding that reports it.')
NOTES = {'action': ' '.join([ACTION_NOTE, CONTROL_NOTE, HTTP_NOTE]),
         'review': ' '.join([REVIEW_NOTE, CONTROL_NOTE, HTTP_NOTE]),
         'verify': ' '.join([REVIEW_NOTE, CONTROL_NOTE, HTTP_NOTE])}
OUTCOME_RULE = ('Finish with outcome success when the task is done, or when the question the mission asks is answered by what was observed — '
                'including the answer that the website does not offer something or requires an account; put that answer in reason. '
                'Finish blocked only when the policy, missing credentials, a host outside the allowed list or a website failure '
                'stopped the mission before it could be answered. ')
EMPTY = ('', False, [], {})


def _is_empty(value):
    # A numeric zero is evidence, not emptiness, so only these exact types are dropped.
    return any(type(value) is type(e) and value == e for e in EMPTY)
# Fields the reviewer cannot act on: fixed capability lists, artifact URLs and identifiers.
DROP_METRICS = ('supported', 'inp_note')
DROP_OBSERVATION = ('screenshot', 'dom', 'at')
DROP_FINDING = ('id', 'run_id', 'fingerprint', 'confidence', 'status', 'owner',
                'verifier_status', 'source')
DROP_CONSOLE = ('at', 'stack', 'page_url')


def prompt_note(purpose):
    """The disclosure line for a projected prompt; empty for unprojected packets."""
    return NOTES.get(purpose, '')


def _drop_empty(value):
    return {k: v for k, v in value.items() if not _is_empty(v)}


def prompt_controls(controls):
    """Controls without empty fields, with integer boxes. IDs and text are kept as they are."""
    out = []
    for control in controls or []:
        item = _drop_empty(control)
        box = control.get('box')
        if isinstance(box, dict):
            item['box'] = {k: (round(v) if isinstance(v, (int, float)) else v) for k, v in box.items()}
        out.append(item)
    return out


def prompt_http(events):
    """Failed or non-GET responses in full; successful ones as counts by resource type."""
    kept, counts = [], {}
    for event in events or []:
        status = event.get('status')
        interesting = (not isinstance(status, int)) or status >= 300 or event.get('method') not in (None, 'GET')
        if interesting:
            kept.append({k: v for k, v in event.items() if k != 'at'})
        else:
            resource = event.get('resource') or 'other'
            counts[resource] = counts.get(resource, 0) + 1
    packet = {}
    if kept:
        packet['events'] = kept
    if counts:
        packet['ok'] = counts
    return packet


def _problems(observation):
    console = [str(e.get('message', ''))[:200] for e in observation.get('console_events') or []
               if e.get('kind') in ('pageerror', 'error')]
    failed = [{'url': e.get('url'), 'status': e.get('status')} for e in observation.get('http_events') or []
              if isinstance(e.get('status'), int) and e['status'] >= 400]
    blocked = [f"{e.get('method')} {e.get('url')}" for e in observation.get('blocked_requests') or []]
    problems = {}
    if console:
        problems['console'] = console
    if failed:
        problems['failed_http'] = failed
    if blocked:
        problems['blocked_by_policy'] = blocked
    return problems


def prompt_observation(observation, purpose):
    """One observation reduced to what `purpose` ('action', 'review' or 'verify') can use."""
    if purpose == 'action':
        item = {k: observation[k] for k in ('id', 'url', 'title', 'lang', 'dir', 'text',
                                            'visual_changed', 'viewport') if k in observation}
        headings = (observation.get('metadata') or {}).get('headings')
        if headings:
            item['headings'] = headings
        item['controls'] = prompt_controls(observation.get('controls'))
        problems = _problems(observation)
        if problems:
            item['problems'] = problems
        return item
    item = {k: v for k, v in observation.items() if k not in DROP_OBSERVATION}
    if isinstance(item.get('metrics'), dict):
        item['metrics'] = {k: v for k, v in item['metrics'].items() if k not in DROP_METRICS}
    if 'controls' in item:
        item['controls'] = prompt_controls(item['controls'])
    if 'http_events' in item:
        item['http_events'] = prompt_http(item['http_events'])
    if 'console_events' in item:
        item['console_events'] = [{k: v for k, v in e.items() if k not in DROP_CONSOLE} for e in item['console_events']]
    return item


def prompt_observations(observations, purpose):
    return [prompt_observation(o, purpose) for o in observations or []]


def prompt_findings(findings):
    """Known findings as the reviewer needs them: what the issue is and where."""
    out = []
    for finding in findings or []:
        item = {'key': finding.get('rule') or finding.get('issue_key') or finding.get('fingerprint'),
                'pillar': finding.get('pillar'), 'severity': finding.get('severity'),
                'title': finding.get('title'), 'url': finding.get('url'),
                'evidence_id': finding.get('evidence_id'), 'source': finding.get('source')}
        out.append({k: v for k, v in item.items() if v is not None})
    return out


def prompt_actions(actions):
    """Action history without timestamps and the model's own outcome label."""
    keep = ('type', 'target', 'value', 'reason', 'step', 'status', 'error',
            'evidence_before', 'evidence_after', 'state_changed')
    return [{k: a[k] for k in keep if k in a} for a in actions or []]


def prompt_finding(finding):
    """One finding as the critic sees it: the claim and its evidence, no bookkeeping."""
    return {k: v for k, v in finding.items() if k not in DROP_FINDING}
