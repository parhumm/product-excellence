"""Whole missions suggested from a rough sentence typed on the mission form.

A suggestion is a complete alternative: a goal the worker pursues on its own, or
an ordered scenario a tester would carry out. The same call revises a mission the
person already has. The house voice lives in one place, the reference the
pex-mission-write skill reads, so the console button and the skill cannot drift
apart. Nothing here is stored: the user applies one and saves the mission itself.
"""
import json

from . import ai, pricing, store, views
from .contracts import Step

MODES = ['journey', 'explore', 'audit', 'benchmark']
PILLARS = ['functionality', 'cro', 'seo_aeo', 'ux_ui', 'performance']
SHAPES = ['goal', 'scenario']
FIELDS = {k: {'type': 'string'} for k in ('title', 'why', 'caveat', 'goal', 'journey')}
FIELDS['mode'] = {'type': 'string', 'enum': MODES}
FIELDS['shape'] = {'type': 'string', 'enum': SHAPES}
FIELDS['pillars'] = {'type': 'array', 'items': {'type': 'string', 'enum': PILLARS}}

VOICE = (store.ROOT / '.claude/skills/pex-mission-write/references/goal-voice.md').read_text()
STEPS = (store.ROOT / '.claude/skills/pex-mission-write/references/scenario-steps.md').read_text()
# One copy of the step rules: the drafting tool and the mission suggestions must not drift apart.
STEP_RULES = ('- One thing per step: a step is a goal or a manual or an event or a check or a hold, never two of '
              'them, and an event performs one operation. Never combine network with speed, or kill with relaunch, '
              'or a goal with an event; write them as consecutive steps. A speed may carry its own delay_ms.\n'
              '- Establish the screen with a goal before checking text on it, and before any absence check.\n'
              '- Use manual only for sign-in, payment or anything a password reaches. Never put a password in a goal.\n'
              '- An operator step may name one value it needs with ask, such as "one-time code". Name the value, '
              'never write the value itself.\n'
              '- Put an unknown policy on any expectation the tester has not stated as a requirement.\n'
              '- Restore the network with an event when the scenario changed it.\n'
              '- Write <Placeholders> wherever a real title, term or account has to be filled in later.\n'
              '- Give each step a short name. Return at most 40 steps and no prose.\n')
# The order pex-mission-suggest uses to decide which mission is worth running next.
LADDER = ('1. A pillar that already carries open findings and has no mission revisiting it.\n'
          '2. A feature the website advertises that no existing mission touches.\n'
          '3. A journey a real customer completes that the existing missions stop short of.\n'
          '4. A benchmark against the competitor URLs, only when they are listed below.\n'
          '5. An existing mission repeated under a harder condition: mobile, a slow network, another locale.')


def context(project):
    """What the workspace already covers, so a suggestion is not a preset again."""
    missions = store.all_records('mission', project['id'])
    names = [m['name'] for m in missions][:25]
    open_findings = []
    try:
        runs = store.all_records('run', project['id'], limit=40)
        for f in views.findings([r for r in runs if store.workspace_of('run', r) == project['id']], grouped=True):
            if f.get('status', 'open') == 'open': open_findings.append(f"{f.get('pillar','')}: {f.get('title','')}")
    except Exception:  # suggestions are worth giving without the history
        open_findings = []
    return names, open_findings[:8]


def facts(req, project):
    """What the worker needs to know about the product before it writes anything."""
    names, open_findings = context(project)
    target = project.get('_target') or {}
    native = target.get('type') == 'android'
    domains = (target if target else project).get('allowed_domains') or []
    # A workspace can hold several websites; the selected target owns this mission, not the workspace URL.
    site = '' if native else (target.get('url') or project.get('url', ''))
    return native, [f"Workspace: {project.get('name','')}", f"Platform: {'Android' if native else 'web'}",
                    f"Target: {target.get('name','')}", f"Package: {target.get('package','')}",
                    f"Build: {project.get('_build',{}).get('version_name','')} {project.get('_build',{}).get('sha256','')}",
                    f"Website: {site}", f"Start URL for this mission: {req.url or site}",
                    f"Domains the run may visit: {', '.join(domains) or 'the website above only'}",
                    f"Viewport: {req.viewport}", f"Mode currently chosen on the form: {req.mode}",
                    f"Competitor start URLs: {', '.join(req.competitors) or 'none listed'}",
                    f"Missions this workspace already has: {'; '.join(names) or 'none'}",
                    f"Open findings so far: {'; '.join(open_findings) or 'none recorded'}"]


def shapes(native):
    """The one place that explains what a goal is, what a scenario is, and when each is honest."""
    return ('Every suggestion is a complete mission in one of two shapes.\n'
            '- goal: the worker pursues the goal text on its own. steps is empty and journey is an empty string.\n'
            '- scenario: an ordered list of steps one tester carries out, in order, once the '
            + ('app' if native else 'page') + ' is open.\n'
            'Both shapes carry the goal text: a scenario states in prose what the run is finding out, and its steps '
            'are how it finds out. A scenario with empty goal text is not a mission and cannot be offered.\n'
            'A scenario sets journey to one sentence describing what the tester does, mode to journey, and includes '
            'functionality in pillars. A goal leaves steps empty.\n\n'
            '--- The step vocabulary ---\n' + STEPS + '\n--- Rules for steps ---\n' + STEP_RULES)


def fields(native):
    return ('- goal: 40 to 120 words, plain sentences, no markdown, no lists.\n'
            '- Stay on the domains listed above. Never ask to defeat the read-only policy: nothing is submitted, '
            'purchased, published or deleted, and a password appears only as the {{password}} placeholder.\n'
            '- Name the stop explicitly when the journey approaches submitting, paying, publishing or deleting.\n'
            '- mode: one of ' + ', '.join(MODES) + '. Choose benchmark only when competitor URLs are listed above.\n'
            + ('- Android: use baseline networking, never benchmark, SEO/AEO, stored credentials, personas or proxy. '
               'An operator can still be asked to sign in from a manual step.\n' if native else '') +
            '- pillars: only what the goal actually judges.\n'
            '- title: at most eight words, in the style "Subject - what it does".\n'
            '- why: one sentence naming what the business learns from running it.\n'
            '- caveat: name what is missing if the mission needs a test account, a saved persona or competitor '
            'URLs the workspace does not have. Otherwise an empty string.\n')


def prompt(req, project):
    native, told = facts(req, project)
    return ('A product team member wrote a rough idea for a ' + ('native Android app' if native else 'browser')
            + ' mission. Return four missions: two the worker can pursue from a goal alone, and two written as '
            'ordered scenarios whose steps are already spelled out. Every one of them should make this product '
            'better for its business, written in the voice described below.\n\n'
            + '\n'.join(told) + '\n\n--- The house voice and the mission fields ---\n' + VOICE +
            '\n--- Which mission is worth running ---\n' + LADDER +
            '\n\n--- Goal or scenario ---\n' + shapes(native) +
            '\n\nWrite both scenarios even when the idea does not obviously turn on state: a scenario is the same '
            'question asked at a particular moment, so find the moment — going offline and back, '
            + ('a kill and relaunch, sending the app home and back, ' if native else 'a reload, going back, ')
            + 'a slow link, a pause that must survive. A scenario carries every step it needs; the person will '
            'not write them. Use <Placeholders> for anything real that has to be filled in later.\n\n'
            'The two goals take the two highest rungs the rough idea supports. The two scenarios differ in the '
            'moment they test, not in wording.\n\nRules for every suggestion:\n' + fields(native) +
            '\nThe rough idea, written by the user:\n' + req.goal)


def revision(req, project):
    """One mission back: the same one, with the change the person asked for and nothing else."""
    native, told = facts(req, project)
    current = req.current.model_dump(by_alias=True, exclude_none=True)
    return ('A product team member wants one change made to the mission below. Return exactly one mission: the same '
            'mission with that change made and everything else preserved, written in the voice described below.\n\n'
            + '\n'.join(told) + '\n\n--- The house voice and the mission fields ---\n' + VOICE +
            '\n\n--- Goal or scenario ---\n' + shapes(native) +
            '\n\nRules for the mission you return:\n' + fields(native) +
            '- Keep the shape unless the requested change needs the other one.\n'
            '- Give it a title that matches what it now does, even if that means renaming it.\n'
            '- Return the whole mission, not a patch: every step the mission still needs, in order.\n\n'
            '--- The mission as it stands now, as data ---\n' + json.dumps(current, ensure_ascii=False)[:20000] +
            '\n\n--- The change the person asked for, in their words ---\n' + req.goal)


def clean(item, competitors, native=False):
    allowed=[p for p in PILLARS if not native or p!='seo_aeo']
    pillars = [p for p in item.get('pillars') or [] if p in allowed] or allowed
    mode = item.get('mode') if item.get('mode') in MODES else 'journey'
    # A benchmark without competitor URLs cannot be saved, so offer it as the journey it really is.
    if mode == 'benchmark' and (native or not competitors): mode = 'journey'
    return {'title': str(item.get('title', ''))[:200], 'why': str(item.get('why', ''))[:400],
            'caveat': str(item.get('caveat', ''))[:200], 'goal': str(item.get('goal', ''))[:4000],
            'mode': mode, 'pillars': pillars}


# Keywords a strict output schema rejects. The shapes and enums survive; the limits are
# re-applied by Step.model_validate below, which is the only schema that decides what is valid.
UNSUPPORTED = ('minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'exclusiveMinimum',
               'exclusiveMaximum', 'minItems', 'maxItems', 'default', 'format', 'title', 'examples')


def strict(node):
    """The same Step contract, spelled the way a strict JSON-schema worker will accept."""
    if isinstance(node, dict):
        out = {k: strict(v) for k, v in node.items() if k not in UNSUPPORTED}
        if out.get('type') == 'object':
            out['additionalProperties'] = False
            out['required'] = list(out.get('properties', {}))
        return out
    if isinstance(node, list): return [strict(n) for n in node]
    return node


def strict_step():
    """The Step contract as a strict worker schema, and the definitions it refers to."""
    generated = strict(Step.model_json_schema(by_alias=True))
    return generated, generated.pop('$defs', {})


def step_schema():
    generated, defs = strict_step()
    return {'type': 'object', '$defs': defs, 'additionalProperties': False, 'required': ['steps'],
            'properties': {'steps': {'type': 'array', 'items': generated}}}


def suggest_schema():
    """Whole missions. The step definitions are hoisted so every $ref still resolves from the root."""
    generated, defs = strict_step()
    item = dict(FIELDS, steps={'type': 'array', 'items': generated})
    # Codex rejects minItems/maxItems in a strict output schema, so counts are enforced below.
    return {'type': 'object', '$defs': defs, 'additionalProperties': False, 'required': ['suggestions'],
            'properties': {'suggestions': {'type': 'array', 'items': {
                'type': 'object', 'properties': item, 'required': list(item), 'additionalProperties': False}}}}


def prune(value):
    """Drop the nulls and empty strings a strict output schema forces out of the worker.

    A false and a zero are answers, not absences, so they survive.
    """
    if isinstance(value, list): return [prune(v) for v in value]
    if not isinstance(value, dict): return value
    kept = {}
    for key, raw in value.items():
        item = prune(raw)
        if item is None or (isinstance(item, (str, list, dict)) and not item): continue
        kept[key] = item
    return kept


def why(error):
    """What a rejected step says to the person: the rule it broke, never pydantic's title or docs link."""
    try: first = error.errors()[0]
    except Exception: return str(error).split(chr(10))[0][:160]
    field = '.'.join(str(p) for p in first.get('loc') or ())
    message = str(first.get('msg', '')).replace('Value error, ', '')
    return ((field + ': ' if field else '') + message)[:160]


def normalize_step(item):
    """One step in the spelling the rows, the YAML and the runner all use. Raises if it is not one."""
    if not isinstance(item, dict): raise ValueError('a step is an object with one key such as goal, check or event')
    return Step.model_validate(prune(item)).model_dump(by_alias=True, exclude_defaults=True, exclude_none=True)


def candidate(item, competitors, native=False):
    """One complete alternative, or a ValueError naming why this one cannot be offered.

    A suggestion is an alternative the person chooses whole. Dropping an invalid step would
    hand them a scenario missing its prerequisite, its network restoration or its check, and
    call it ready; so a bad step rejects the candidate it came from.
    """
    if not isinstance(item, dict): raise ValueError('not a mission')
    mission = clean(item, competitors, native)
    if not mission['goal'].strip(): raise ValueError('no goal')
    raw = item.get('steps') or []
    if not isinstance(raw, list): raise ValueError('steps is not a list')
    shape = item.get('shape') if item.get('shape') in SHAPES else ('scenario' if raw else 'goal')
    if shape == 'goal':
        if raw: raise ValueError('a goal mission carries no steps')
        return {**mission, 'shape': 'goal', 'journey': '', 'steps': []}
    if not raw: raise ValueError('a scenario with no steps is a goal, not a scenario')
    if len(raw) > 40: raise ValueError(f'a scenario holds at most 40 steps, not {len(raw)}')
    steps = []
    for number, step in enumerate(raw, 1):
        try: steps.append(normalize_step(step))
        except Exception as error: raise ValueError(f'step {number}: ' + why(error))
    # A scenario verdict is recorded under Functionality, and it is a journey by construction.
    mission['mode'] = 'journey'
    if 'functionality' not in mission['pillars']: mission['pillars'] = ['functionality'] + mission['pillars']
    return {**mission, 'shape': 'scenario', 'journey': str(item.get('journey', '') or '')[:400], 'steps': steps}


async def worker(req, project):
    """The signed-in subscription and the account this workspace uses for it."""
    health = await ai.health()
    provider = req.provider if req.provider in ('codex', 'claude') and health[req.provider]['logged_in'] else ''
    provider = provider or next((p for p in ('codex', 'claude') if health[p]['logged_in']), '')
    if not provider: raise ValueError('No AI worker is signed in. Open Settings to sign in Codex or Claude.')
    return provider, req.codex_account or project.get('codex_account') or 'default'


async def suggest(req, project):
    """Four whole missions from a rough idea — two goals and two scenarios — or one revised mission."""
    provider, account = await worker(req, project)
    native = (project.get('_target') or {}).get('type') == 'android'
    wanted = 1 if req.revise else 4
    per_shape = 1 if req.revise else 2   # two of each shape; a revision returns its one mission
    # The subscription's standard model, never the cheap or the frontier tier, but at low
    # effort: a short mission does not need deliberation, and this button is waited on.
    result, usage = await ai.call(provider, revision(req, project) if req.revise else prompt(req, project),
                                  suggest_schema(), timeout=120, model=pricing.LADDER[provider][1],
                                  effort='low', codex_account=account)
    offered = result.get('suggestions') if isinstance(result, dict) else None
    if not isinstance(offered, list): raise RuntimeError('The worker returned no list of missions')
    # A mission the worker got wrong costs its own card, not the whole minute of waiting.
    items, rejected = [], []
    for number, item in enumerate(offered, 1):
        if len(items) >= wanted: break
        try: got = candidate(item, req.competitors, native)
        except Exception as error:
            rejected.append(f'Mission {number}: ' + str(error).split(chr(10))[0][:160]); continue
        if sum(1 for x in items if x['shape'] == got['shape']) >= per_shape: continue
        items.append(got)
    if not items:
        raise RuntimeError('The worker returned no usable mission; try again. ' + '; '.join(rejected)[:400])
    return {'suggestions': items, 'rejected': rejected[:5], 'usage': usage}


async def draft(req, project):
    """Scenario steps from a description. Nothing runs and no device is touched."""
    provider, account = await worker(req, project)
    target = project.get('_target') or {}
    known = [t.strip()[:200] for t in req.texts if t.strip()][:30]
    native = target.get('type') == 'android'
    where = 'on an Android device' if native else 'in a web browser on ' + (target.get('url') or 'the site')
    ask = (f'A tester described one journey to run {where}. Return the ordered steps that carry '
           'it out, using only the vocabulary below.\n\n'
           f"{'App' if native else 'Site'}: {target.get('name','')} ({target.get('package') or target.get('url','')})\n"
           f"Build: {project.get('_build',{}).get('version_name','')}\n"
           'Text the tester says appears in this app: ' + ('; '.join(known) or 'none given') + '\n\n'
           '--- The step vocabulary ---\n' + STEPS +
           '\n--- Rules ---\n' + STEP_RULES + '\n'
           'What the tester wrote:\n' + req.description)
    result, usage = await ai.call(provider, ask, step_schema(), timeout=120,
                                  model=pricing.LADDER[provider][1], effort='low', codex_account=account)
    steps, rejected = [], []
    for index, item in enumerate((result.get('steps') or [])[:40], 1):
        try: steps.append(normalize_step(item))
        except Exception as error: rejected.append(f'Step {index}: ' + why(error))
    if not steps: raise RuntimeError('The worker returned no usable step. ' + ('; '.join(rejected)[:400]))
    return {'steps': steps, 'rejected': rejected[:5], 'usage': usage}
