"""Two mission goals suggested from a rough sentence typed on the mission form.

The house voice lives in one place, the reference the pex-mission-write skill
reads, so the console button and the skill cannot drift apart. Nothing here is
stored: the user applies a suggestion to the form and saves the mission itself.
"""
from . import ai, pricing, store, views

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
    domains = project.get('allowed_domains') or []
    facts = [f"Workspace: {project.get('name','')}", f"Website: {project.get('url','')}",
             f"Start URL for this mission: {req.url or project.get('url','')}",
             f"Domains the run may visit: {', '.join(domains) or 'the website above only'}",
             f"Viewport: {req.viewport}", f"Mode currently chosen on the form: {req.mode}",
             f"Competitor start URLs: {', '.join(req.competitors) or 'none listed'}",
             f"Missions this workspace already has: {'; '.join(names) or 'none'}",
             f"Open findings so far: {'; '.join(open_findings) or 'none recorded'}"]
    return ('A product team member wrote a rough idea for a browser mission. Return exactly two mission goals '
            'that would make this website better for its business, written in the voice described below.\n\n'
            + '\n'.join(facts) + '\n\n--- The house voice and the mission fields ---\n' + VOICE +
            '\n--- Which mission is worth running ---\n' + LADDER +
            '\n\nThe two suggestions must differ in what the business learns, not in wording: take the two '
            'highest rungs the rough idea supports.\n\nRules for every suggestion:\n'
            '- goal: 40 to 120 words, plain sentences, no markdown, no lists.\n'
            '- Stay on the domains listed above. Never ask to defeat the read-only policy: nothing is submitted, '
            'purchased, published or deleted, and a password appears only as the {{password}} placeholder.\n'
            '- Name the stop explicitly when the journey approaches submitting, paying, publishing or deleting.\n'
            '- mode: one of ' + ', '.join(MODES) + '. Choose benchmark only when competitor URLs are listed above.\n'
            '- pillars: only what the goal actually judges.\n'
            '- title: at most eight words, in the style "Subject - what it does".\n'
            '- why: one sentence naming what the business learns from running it.\n'
            '- caveat: name what is missing if the mission needs a test account, a saved persona or competitor '
            'URLs the workspace does not have. Otherwise an empty string.\n\n'
            'The rough idea, written by the user:\n' + req.goal)


def clean(item, competitors):
    pillars = [p for p in item.get('pillars') or [] if p in PILLARS] or PILLARS
    mode = item.get('mode') if item.get('mode') in MODES else 'journey'
    # A benchmark without competitor URLs cannot be saved, so offer it as the journey it really is.
    if mode == 'benchmark' and not competitors: mode = 'journey'
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
    # Writing a goal is judgment work: the subscription's standard model, never the cheap or the frontier tier.
    model = pricing.LADDER[provider][1]
    result, usage = await ai.call(provider, prompt(req, project), SCHEMA, timeout=120,
                                  model=model, effort='medium', codex_account=account)
    items = [clean(s, req.competitors) for s in (result.get('suggestions') or []) if s.get('goal')][:2]
    if not items: raise RuntimeError('The worker returned no usable goal')
    return {'suggestions': items, 'usage': usage}
