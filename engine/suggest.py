"""Two mission goals suggested from a rough sentence typed on the mission form.

The house voice lives in one place, the reference the pex-mission-write skill
reads, so the console button and the skill cannot drift apart. Nothing here is
stored: the user applies a suggestion to the form and saves the mission itself.
"""
from . import ai, pricing, store, views
from .contracts import Step

MODES = ['journey', 'explore', 'audit', 'benchmark']
PILLARS = ['functionality', 'cro', 'seo_aeo', 'ux_ui', 'performance']
FIELDS = {k: {'type': 'string'} for k in ('title', 'why', 'caveat', 'goal')}
FIELDS['mode'] = {'type': 'string', 'enum': MODES}
FIELDS['pillars'] = {'type': 'array', 'items': {'type': 'string', 'enum': PILLARS}}
# Codex rejects minItems/maxItems in a strict output schema, so "exactly two" is enforced below.
SCHEMA = {'type': 'object', 'properties': {'suggestions': {'type': 'array', 'items': {
    'type': 'object', 'properties': FIELDS, 'required': list(FIELDS), 'additionalProperties': False}}},
    'required': ['suggestions'], 'additionalProperties': False}

VOICE = (store.ROOT / '.claude/skills/pex-mission-write/references/goal-voice.md').read_text()
STEPS = (store.ROOT / '.claude/skills/pex-mission-write/references/scenario-steps.md').read_text()
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


def prompt(req, project):
    names, open_findings = context(project)
    target=project.get('_target') or {};native=target.get('type')=='android'
    domains = (target if target else project).get('allowed_domains') or []
    facts = [f"Workspace: {project.get('name','')}", f"Platform: {'Android' if native else 'web'}",
             f"Target: {target.get('name','')}", f"Package: {target.get('package','')}",
             f"Build: {project.get('_build',{}).get('version_name','')} {project.get('_build',{}).get('sha256','')}", f"Website: {project.get('url','') if not native else ''}",
             f"Start URL for this mission: {req.url or project.get('url','')}",
             f"Domains the run may visit: {', '.join(domains) or 'the website above only'}",
             f"Viewport: {req.viewport}", f"Mode currently chosen on the form: {req.mode}",
             f"Competitor start URLs: {', '.join(req.competitors) or 'none listed'}",
             f"Missions this workspace already has: {'; '.join(names) or 'none'}",
             f"Open findings so far: {'; '.join(open_findings) or 'none recorded'}"]
    return ('A product team member wrote a rough idea for a '+('native Android app' if native else 'browser')+' mission. Return exactly two mission goals '
            'that would make this product better for its business, written in the voice described below.\n\n'
            + '\n'.join(facts) + '\n\n--- The house voice and the mission fields ---\n' + VOICE +
            '\n--- Which mission is worth running ---\n' + LADDER +
            '\n\nThe two suggestions must differ in what the business learns, not in wording: take the two '
            'highest rungs the rough idea supports.\n\nRules for every suggestion:\n'
            '- goal: 40 to 120 words, plain sentences, no markdown, no lists.\n'
            '- Stay on the domains listed above. Never ask to defeat the read-only policy: nothing is submitted, '
            'purchased, published or deleted, and a password appears only as the {{password}} placeholder.\n'
            '- Name the stop explicitly when the journey approaches submitting, paying, publishing or deleting.\n'
            '- mode: one of ' + ', '.join(MODES) + '. Choose benchmark only when competitor URLs are listed above.\n'
            + ('- Android: use baseline networking, never benchmark, SEO/AEO, credentials, personas or proxy; stop before sign-in/password/OTP.\n' if native else '') +
            '- pillars: only what the goal actually judges.\n'
            '- title: at most eight words, in the style "Subject - what it does".\n'
            '- why: one sentence naming what the business learns from running it.\n'
            '- caveat: name what is missing if the mission needs a test account, a saved persona or competitor '
            'URLs the workspace does not have. Otherwise an empty string.\n\n'
            'The rough idea, written by the user:\n' + req.goal)


def clean(item, competitors, native=False):
    allowed=[p for p in PILLARS if not native or p!='seo_aeo']
    pillars = [p for p in item.get('pillars') or [] if p in allowed] or allowed
    mode = item.get('mode') if item.get('mode') in MODES else 'journey'
    # A benchmark without competitor URLs cannot be saved, so offer it as the journey it really is.
    if mode == 'benchmark' and (native or not competitors): mode = 'journey'
    return {'title': str(item.get('title', ''))[:200], 'why': str(item.get('why', ''))[:400],
            'caveat': str(item.get('caveat', ''))[:200], 'goal': str(item.get('goal', ''))[:4000],
            'mode': mode, 'pillars': pillars}


async def suggest(req, project):
    """Two goals from the signed-in subscription, on its normal-price model."""
    health = await ai.health()
    provider = req.provider if req.provider in ('codex', 'claude') and health[req.provider]['logged_in'] else ''
    provider = provider or next((p for p in ('codex', 'claude') if health[p]['logged_in']), '')
    if not provider: raise ValueError('No AI worker is signed in. Open Settings to sign in Codex or Claude.')
    account = req.codex_account or project.get('codex_account') or 'default'
    # The subscription's standard model, never the cheap or the frontier tier, but at low
    # effort: two short goals do not need deliberation, and this button is waited on.
    model = pricing.LADDER[provider][1]
    result, usage = await ai.call(provider, prompt(req, project), SCHEMA, timeout=60,
                                  model=model, effort='low', codex_account=account)
    items = [clean(s, req.competitors,(project.get('_target') or {}).get('type')=='android') for s in (result.get('suggestions') or []) if s.get('goal')][:2]
    if not items: raise RuntimeError('The worker returned no usable goal')
    return {'suggestions': items, 'usage': usage}


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


def step_schema():
    generated = strict(Step.model_json_schema(by_alias=True))
    defs = generated.pop('$defs', {})
    return {'type': 'object', '$defs': defs, 'additionalProperties': False, 'required': ['steps'],
            'properties': {'steps': {'type': 'array', 'items': generated}}}


async def draft(req, project):
    """Scenario steps from a description. Nothing runs and no device is touched."""
    health = await ai.health()
    provider = req.provider if req.provider in ('codex', 'claude') and health[req.provider]['logged_in'] else ''
    provider = provider or next((p for p in ('codex', 'claude') if health[p]['logged_in']), '')
    if not provider: raise ValueError('No AI worker is signed in. Open Settings to sign in Codex or Claude.')
    target = project.get('_target') or {}
    known = [t.strip()[:200] for t in req.texts if t.strip()][:30]
    ask = ('A tester described one journey to run on an Android device. Return the ordered steps that carry '
           'it out, using only the vocabulary below.\n\n'
           f"App: {target.get('name','')} ({target.get('package','')})\n"
           f"Build: {project.get('_build',{}).get('version_name','')}\n"
           'Text the tester says appears in this app: ' + ('; '.join(known) or 'none given') + '\n\n'
           '--- The step vocabulary ---\n' + STEPS +
           '\n--- Rules ---\n'
           '- Establish the screen with a goal before checking text on it, and before any absence check.\n'
           '- Use manual only for sign-in, payment or anything a password reaches. Never put a password in a goal.\n'
           '- Put an unknown policy on any expectation the tester has not stated as a requirement.\n'
           '- Restore the network with an event when the scenario changed it.\n'
           '- Write <Placeholders> wherever a real title, term or account has to be filled in later.\n'
           '- Give each step a short name. Return at most 40 steps and no prose.\n\n'
           'What the tester wrote:\n' + req.description)
    account = req.codex_account or project.get('codex_account') or 'default'
    result, usage = await ai.call(provider, ask, step_schema(), timeout=120,
                                  model=pricing.LADDER[provider][1], effort='low', codex_account=account)
    steps, rejected = [], []
    for index, item in enumerate((result.get('steps') or [])[:40], 1):
        clean = {k: v for k, v in item.items() if v not in (None, '', [], {})}
        try: steps.append(Step.model_validate(clean).model_dump(by_alias=True, exclude_defaults=True, exclude_none=True))
        except Exception as error: rejected.append(f'Step {index}: ' + str(error).split('\n')[1 if '\n' in str(error) else 0][:160])
    if not steps: raise RuntimeError('The worker returned no usable step. ' + ('; '.join(rejected)[:400]))
    return {'steps': steps, 'rejected': rejected[:5], 'usage': usage}
