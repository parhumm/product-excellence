"""Ready-to-run missions created in every workspace.

Ten of them cover what matters for any online business: the landing page,
registration, sign-in, search, the core feature, pricing and checkout, the
mobile app, SEO and AEO, accessibility, and a slow phone. A website we already
know adds its own pack on top.

Goals are written for the engine's read-only policy: nothing is submitted,
purchased or deleted, navigation stays on the workspace's own domains, and a
password reaches the browser only through the {{password}} placeholder.
"""
import yaml
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from engine import store
from engine.contracts import Mission, PLACEHOLDER

# Bump when presets are added; a workspace already stamped with the current
# value is left alone, so a preset the user deleted does not come back.
PRESET_VERSION = '2026-09-06.1'

AUDIT = {'mode': 'audit', 'provider': 'auto', 'model': 'dynamic', 'ai_budget': 6, 'max_seconds': 600}
JOURNEY = {'mode': 'journey', 'provider': 'auto', 'model': 'dynamic', 'effort': 'medium', 'max_steps': 10, 'ai_budget': 14, 'max_seconds': 900}
FUNCTIONAL = ['functionality', 'cro', 'ux_ui']
# A benchmark answers the same question on the workspace's own site and then on each
# competitor, so max_steps is spent per site and the wall clock covers all of them.
BENCHMARK = {'mode': 'benchmark', 'provider': 'auto', 'model': 'dynamic', 'effort': 'medium', 'max_steps': 5, 'ai_budget': 30, 'max_seconds': 2400}
SPEED = ['functionality', 'performance', 'ux_ui']

GENERIC = [
 {**AUDIT, 'template': 'home-audit', 'name': 'Home page · five-pillar audit',
  'goal': 'Review this home page as a first-time visitor. Judge what the business offers and who it is for, how clear the main call to action is, which trust signals are present, the page title, description and headings, keyboard and contrast accessibility, and how quickly the page becomes usable. Report anything that would make a visitor leave.'},
 {**JOURNEY, 'template': 'register', 'name': 'Register · reach the sign-up form', 'max_steps': 8, 'ai_budget': 12, 'pillars': FUNCTIONAL,
  'goal': 'Find how a new customer creates an account and open the sign-up form. Record which fields are required, whether a phone number, email or another service is needed, and what the form says about verification, price or terms. Type one obviously invalid value into a plain text field to see the validation message. Do not submit the form and do not create an account.'},
 {**JOURNEY, 'template': 'sign-in', 'name': 'Sign in · account access', 'pillars': ['functionality', 'ux_ui'],
  'goal': 'Find the sign-in entry and open it. If this mission has sign-in credentials saved, sign in and confirm the account area opens; type {{password}} into the password field and the engine fills the stored secret for you. Without credentials, inspect the form only: the sign-in methods offered, password recovery, and how errors are explained, then stop. Sign-in that needs a one-time code sent by message cannot be completed; report that as the outcome.'},
 {**JOURNEY, 'template': 'search', 'name': 'Search · find something specific', 'pillars': FUNCTIONAL,
  'goal': 'Use the site search to find a specific item the home page suggests. Judge how easy search is to find, whether the results are relevant, and whether filters or sorting help. Search once for a nonsense word to see the empty state. Then open the best result and confirm it matches what was searched for.'},
 {**JOURNEY, 'template': 'core-features', 'name': 'Core features · detect and use', 'mode': 'explore', 'max_steps': 14, 'ai_budget': 20, 'max_seconds': 1200,
  'goal': 'Work out what this product actually does from its navigation, home page and help pages, then use the three most important features the way a customer would. Do not create an account, pay, publish or delete anything. Report which features work, which are hard to find, and where the product fails or confuses.'},
 {**JOURNEY, 'template': 'pricing-checkout', 'name': 'Pricing and checkout · up to payment', 'max_steps': 12, 'ai_budget': 16, 'pillars': FUNCTIONAL,
  'goal': 'Find the prices or plans, pick the plan a typical customer would take, and follow the purchase path as far as the safety policy allows. Payment and purchase controls are refused on purpose, so report where it stopped. Judge whether the price, currency, billing period, renewal, taxes and refund terms are clear before payment, how many steps the path takes, and which trust signals appear.'},
 {**JOURNEY, 'template': 'mobile-app', 'name': 'Get the app · mobile app download', 'viewport': 'mobile', 'max_steps': 8, 'ai_budget': 10, 'max_seconds': 600, 'pillars': FUNCTIONAL,
  'goal': 'On a phone screen, find how to install the mobile app: store badges, a QR code, a banner or a direct download. Read each link destination from the page instead of following it, because the run stays on this website. Report which platforms are offered, whether the links look correct, and how much the page interrupts reading to promote the app. If there is no app, say so.'},
 {**AUDIT, 'template': 'seo-aeo', 'name': 'SEO and AEO · search and answer readiness', 'pillars': ['seo_aeo'],
  'goal': 'Review this page for search engines and for AI answer engines. Check the title, meta description, canonical link, robots directives, heading order, image alternative text and structured data, and whether the page answers a customer question in plain sentences that could be quoted. Report what is missing, duplicated, contradictory or visible only after JavaScript runs.'},
 {**JOURNEY, 'template': 'accessibility', 'name': 'UX, UI and accessibility · keyboard and screen', 'ai_budget': 12, 'max_seconds': 600, 'pillars': ['ux_ui', 'functionality'],
  'goal': 'Move through the page with the keyboard: Tab and the arrow keys, and Enter inside a search box. Check that focus is always visible, that the order follows the layout, that controls carry labels and that nothing traps focus. Then scroll the whole page and report unreadable text, cramped tap targets, overlapping layout, and anything that hides content or moves while loading.'},
 {**JOURNEY, 'template': 'slow-mobile', 'name': 'Slow mobile · core task on a poor connection', 'viewport': 'mobile', 'network': 'slow-mobile', 'max_steps': 8, 'ai_budget': 12, 'max_seconds': 1200, 'pillars': SPEED,
  'goal': 'On a phone with a slow connection, do the main thing this website is for: reach a detail page and start the primary action. Report what takes a long time, what stays blank or shifts about while loading, whether the page can be used before everything arrives, and anything that fails outright on this connection.'},
]

def seed_project(project, session=None):
    """Create the presets this workspace is missing, then stamp it."""
    if not project.get('url'): return project
    if project.get('presets') == PRESET_VERSION: return project
    known = {m.get('template') or m['name'] for m in store.all_records('mission', project['id'], session=session)}
    domains = project.get('allowed_domains') or [urlsplit(project['url']).hostname.lower()]
    for spec in reversed(GENERIC):  # newest first in the table, so seed backwards
        spec = dict(spec)
        template = spec.pop('template')
        if template in known or spec['name'] in known: continue
        mission = Mission(project_id=project['id'], url=urljoin(project['url'], spec.pop('path', '')),
                          allowed_domains=domains + spec.pop('allowed_domains', []), **spec)
        store.save('mission', {'version': 1, 'template': template, **mission.model_dump(exclude={'login_password'})}, session=session)
    return store.save('project', {**project, 'presets': PRESET_VERSION}, session=session)
# --- shipped scenario templates ---------------------------------------------
# The order the journeys are usually worked through, not alphabetical. A journey carries
# no platform: the target the author picks decides whether it runs on a device or a page.
PRESET_ORDER=('entitlement-switch','weak-network-download','profile-isolation','stale-notification','shared-link-login',
              'playback-offline','session-survives-restart','sign-out-really-signs-out','filter-survives-restart',
              'back-after-search','form-rejects-bad-input','checkout-on-slow-link')

def scenarios():
    """The shipped journeys: display text, what each one needs, and the blanks still to fill."""
    found={}
    for path in (Path(__file__).parent/'scenarios').glob('*.yaml'):
        raw=yaml.safe_load(path.read_text(encoding='utf-8'))
        mission=raw['mission']
        text=' '.join([mission['name'],mission['goal'],yaml.safe_dump(mission.get('scenario') or [],allow_unicode=True)])
        found[raw['id']]={'id':raw['id'],'name':raw['name'],'about':' '.join(raw['about'].split()),
                          'tags':raw.get('tags') or [],'needs':raw.get('needs') or [],
                          'blanks':list(dict.fromkeys(PLACEHOLDER.findall(text))),'mission':mission}
    return [found[id] for id in PRESET_ORDER if id in found]+[v for k,v in sorted(found.items()) if k not in PRESET_ORDER]
