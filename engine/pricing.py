"""Selectable model catalog and estimated cost per AI call.

Runs execute through the Codex and Claude subscription CLIs. No API key is used
and nothing here is billed per call. The estimate applies published standard API
prices to the token counts the CLI reports, so two runs can be compared with
each other. It is not an invoice and it is not what the subscription charges.

Prices are USD per million tokens as published on PRICE_DATE. Unknown models
return None so the console can show "n/a"; an unpriced call is never shown as
costing zero.
"""

PRICE_DATE = '2026-09-07'
DISCLAIMER = ('Estimate at published standard API prices. Runs use your Codex/Claude '
              'subscription; nothing is billed per call here.')
MILLION = 1_000_000


def _prices(model_input, cached, output, write_5m=None, write_1h=None):
    return {'input': model_input, 'cached': cached, 'output': output,
            'write_5m': write_5m, 'write_1h': write_1h}


# Keyed by reported-model id. Lookup is a longest-prefix match, so a dated or
# long-context variant such as claude-haiku-4-5-20251001 resolves to its family.
PRICES = {
    'gpt-6-astra': _prices(10.0, 1.0, 50.0),
    # Promo through at least 2026-11-21; recheck then (regular list $5/$30).
    'gpt-5.6-sol': _prices(4.0, 0.40, 20.0),
    'gpt-5.6-terra': _prices(2.0, 0.20, 12.0),
    'gpt-5.6-luna': _prices(0.20, 0.02, 1.20),
    'gpt-5.5': _prices(5, 0.5, 30),
    'gpt-5.5-pro': _prices(30, None, 180),
    'gpt-5.4': _prices(2.5, 0.25, 15),
    'gpt-5.4-pro': _prices(30, None, 180),
    'gpt-5.4-mini': _prices(0.75, 0.075, 4.5),
    'gpt-5.4-nano': _prices(0.2, 0.02, 1.25),
    'gpt-5.2': _prices(1.75, 0.175, 14),
    'gpt-5.2-pro': _prices(21, None, 168),
    'gpt-5.1': _prices(1.25, 0.125, 10),
    'gpt-5': _prices(1.25, 0.125, 10),
    'gpt-5-mini': _prices(0.25, 0.025, 2),
    'gpt-5-nano': _prices(0.05, 0.005, 0.4),
    'gpt-5-pro': _prices(15, None, 120),
    'claude-fable-5-1': _prices(10.0, 0.25, 50.0, 12.50, 20.0),
    'claude-mythos-5-1': _prices(10.0, 0.25, 50.0, 12.50, 20.0),
    'claude-fable-5': _prices(10.0, 1.0, 50.0, 12.50, 20.0),
    'claude-mythos-5': _prices(10.0, 1.0, 50.0, 12.50, 20.0),
    'claude-opus-5': _prices(5.0, 0.50, 25.0, 6.25, 10.0),
    'claude-opus-4-8': _prices(5.0, 0.50, 25.0, 6.25, 10.0),
    'claude-opus-4-7': _prices(5.0, 0.50, 25.0, 6.25, 10.0),
    'claude-opus-4-6': _prices(5.0, 0.50, 25.0, 6.25, 10.0),
    'claude-opus-4-5': _prices(5.0, 0.50, 25.0, 6.25, 10.0),
    'claude-opus-4-1': _prices(15.0, 1.50, 75.0, 18.75, 30.0),
    'claude-opus-4': _prices(15.0, 1.50, 75.0, 18.75, 30.0),
    'claude-sonnet-5': _prices(2.0, 0.20, 10.0, 2.50, 4.0),
    'claude-sonnet-4-6': _prices(3.0, 0.30, 15.0, 3.75, 6.0),
    'claude-sonnet-4-5': _prices(3.0, 0.30, 15.0, 3.75, 6.0),
    'claude-sonnet-4': _prices(3.0, 0.30, 15.0, 3.75, 6.0),
    'claude-haiku-4-5': _prices(1.0, 0.10, 5.0, 1.25, 2.0),
    'claude-haiku-3-5': _prices(0.80, 0.08, 4.0, 1.0, 1.60),
}

# Selectable models per provider. `value` is passed to the CLI as --model, so it
# must match Mission.model_alias. Only full model ids are offered: probing the
# local Claude CLI on 2026-09-06 showed its short aliases do not resolve to the
# family they name (--model sonnet answered as claude-opus-5 and --model opus as
# claude-fable-5-1), while every full id answered as itself. `family` is the
# price key; the run record always reports the model the CLI actually used.
CATALOG = {
    'claude': [
        {'value': '', 'label': 'CLI default', 'family': ''},
        {'value': 'claude-fable-5-1', 'label': 'Claude Fable 5.1', 'family': 'claude-fable-5-1'},
        {'value': 'claude-opus-5', 'label': 'Claude Opus 5', 'family': 'claude-opus-5'},
        {'value': 'claude-sonnet-5', 'label': 'Claude Sonnet 5', 'family': 'claude-sonnet-5'},
        {'value': 'claude-haiku-4-5', 'label': 'Claude Haiku 4.5', 'family': 'claude-haiku-4-5'},
    ],
    'codex': [
        {'value': '', 'label': 'CLI default', 'family': ''},
        {'value': 'gpt-6-astra', 'label': 'GPT-6 Astra', 'family': 'gpt-6-astra'},
        {'value': 'gpt-5.6-sol', 'label': 'GPT-5.6 Sol', 'family': 'gpt-5.6-sol'},
        {'value': 'gpt-5.6-terra', 'label': 'GPT-5.6 Terra', 'family': 'gpt-5.6-terra'},
        {'value': 'gpt-5.6-luna', 'label': 'GPT-5.6 Luna', 'family': 'gpt-5.6-luna'},
    ],
}
# Cheapest first, for the Dynamic model choice. The tiers line up across
# providers, so a run that falls back to the other worker keeps the same tier.
LADDER = {
    'claude': ['claude-haiku-4-5', 'claude-sonnet-5', 'claude-opus-5', 'claude-fable-5-1'],
    'codex': ['gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra'],
}


def normalize(model_id):
    """Reduce a reported id to its price key form: lowercase, no context or date suffix."""
    text = str(model_id or '').strip().lower()
    for cut in ('[', '@', ':'):
        text = text.split(cut, 1)[0]
    parts = text.rsplit('-', 1)
    if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isdigit():
        text = parts[0]
    return text.strip('-')


def lookup(model_id):
    """Prices for a reported model id; None when the id is unknown or an alias."""
    text = normalize(model_id)
    if not text:
        return None
    # A CLI alias is deliberately not priced: it does not name the model that answers.
    matches = [key for key in PRICES if text == key or text.startswith(key + '-')]
    return PRICES[max(matches, key=len)] if matches else None


def price_hint(model_id):
    prices = lookup(model_id)
    if not prices:
        return ''
    return f"${prices['input']:g} in / ${prices['output']:g} out per MTok"


def catalog(provider, extra=()):
    """Selectable entries for one provider, with a price hint for the console.

    `extra` carries models the local CLI reports but the catalog does not list
    (a configured default, for example); they stay selectable, with a price when their family is known.
    """
    entries = [dict(e, price_hint=price_hint(e['family'])) for e in CATALOG.get(provider, [])]
    known = {e['value'] for e in entries}
    for value in extra:
        if value and value not in known:
            entries.append({'value': value, 'label': f'configured: {value}',
                            'family': '', 'price_hint': price_hint(value)})
            known.add(value)
    return entries


def estimate(usage):
    """Estimated USD for one call, or None when the model or a token count is unknown.

    `usage` carries already-normalized counts: `input_tokens` excludes cached
    input, `cached_tokens` is billed at the cache-hit rate, and the two cache
    write fields are Claude-only. Never returns 0 for a call it cannot price.
    """
    if not isinstance(usage, dict):
        return None
    prices = lookup(usage.get('model_reported') or usage.get('model_requested'))
    if not prices:
        return None
    if usage.get('input_tokens') is None or usage.get('output_tokens') is None:
        return None
    total = 0.0
    for field, rate in (('input_tokens', 'input'), ('cached_tokens', 'cached'),
                        ('cache_write_5m_tokens', 'write_5m'), ('cache_write_1h_tokens', 'write_1h'),
                        ('output_tokens', 'output')):
        tokens = usage.get(field) or 0
        if not tokens:
            continue
        if prices.get(rate) is None:
            return None
        total += tokens * prices[rate] / MILLION
    return round(total, 6)


def totals(entries):
    """Run totals over per-call usage entries; `cost_partial` marks unpriced calls."""
    result = {'calls': len(entries), 'input_tokens': 0, 'cached_tokens': 0, 'output_tokens': 0,
              'est_cost_usd': 0.0, 'cost_partial': False, 'models': []}
    for entry in entries:
        for field in ('input_tokens', 'cached_tokens', 'output_tokens'):
            result[field] += entry.get(field) or 0
        for field in ('cache_write_5m_tokens', 'cache_write_1h_tokens'):
            result['input_tokens'] += entry.get(field) or 0
        cost = entry.get('est_cost_usd')
        if cost is None:
            result['cost_partial'] = True
        else:
            result['est_cost_usd'] += cost
        name = entry.get('model_reported') or entry.get('model_requested') or ''
        if name and name not in result['models']:
            result['models'].append(name)
    result['est_cost_usd'] = round(result['est_cost_usd'], 6)
    if result['cost_partial'] and not result['est_cost_usd']:
        result['est_cost_usd'] = None
    return result


def money(value):
    return 'n/a' if value is None else f'≈${value:,.4f}'


def input_total(usage):
    """Input tokens as a reader means them: fresh input plus tokens written to cache.

    Claude bills a cache write at its own rate, but it is still input that was sent
    this call, and reporting only `input_tokens` makes a cached prompt look empty.
    Returns None when no input class was reported at all.
    """
    parts = [usage.get(field) for field in
             ('input_tokens', 'cache_write_5m_tokens', 'cache_write_1h_tokens')]
    known = [p for p in parts if p is not None]
    return sum(known) if known else None


def tokens(value):
    """An unavailable count is shown as unknown; only a measured 0 prints as 0."""
    return '—' if value is None else format(value, ',')


def report(run, indent=''):
    """Model names, token use and the estimated cost of one finished run."""
    totals_ = run.get('ai_totals') or {}
    lines = [f"{indent}AI calls: {run.get('ai_calls', 0)} · provider: {run.get('provider') or 'none'}"]
    for call in run.get('ai_usage') or []:
        purpose = call.get('purpose') or 'reasoning'
        if call.get('step') is not None:
            purpose += f" {call['step'] + 1}"
        lines.append(f"{indent}  {call.get('call')}. {purpose} · "
                     f"{call.get('model_reported') or call.get('model_requested') or 'unknown'} · "
                     f"{tokens(input_total(call))} in / {tokens(call.get('cached_tokens'))} cached / "
                     f"{tokens(call.get('output_tokens'))} out · "
                     f"{round((call.get('wall_ms') or 0) / 1000, 1)} s · {money(call.get('est_cost_usd'))}"
                     + (f" · ERROR {call['error']}" if call.get('error') else ''))
    if totals_.get('calls'):
        lines.append(f"{indent}  Total: {', '.join(totals_.get('models') or ['unknown'])} · "
                     f"{tokens(totals_.get('input_tokens'))} in / {tokens(totals_.get('cached_tokens'))} cached / "
                     f"{tokens(totals_.get('output_tokens'))} out · {money(totals_.get('est_cost_usd'))}"
                     + (' (partial: some calls could not be priced)' if totals_.get('cost_partial') else ''))
    if run.get('ai_usage'):
        lines.append(f'{indent}  Input counts fresh prompt tokens plus tokens written to the cache.')
        lines.append(f'{indent}  {DISCLAIMER} Prices published {PRICE_DATE}.')
    return '\n'.join(lines)
