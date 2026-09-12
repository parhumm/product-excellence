import re

import pytest
from engine import pricing
from engine.contracts import Mission


def test_lookup_resolves_dated_and_long_context_ids():
    assert pricing.lookup('claude-haiku-4-5-20251001') == pricing.PRICES['claude-haiku-4-5']
    assert pricing.lookup('claude-opus-5[1m]') == pricing.PRICES['claude-opus-5']
    assert pricing.lookup('CLAUDE-SONNET-5') == pricing.PRICES['claude-sonnet-5']
    assert pricing.lookup('gpt-5.6-sol') == pricing.PRICES['gpt-5.6-sol']


# The CLI aliases are not priced: measured locally, `sonnet` answers as Opus 5 and
# `opus` as Fable 5.1, so guessing a family from an alias would report a wrong cost.
@pytest.mark.parametrize('model', ['unknown-model', 'codex-auto-review', '', None, 'claude', 'opus-5',
                                   'sonnet', 'opus', 'haiku', 'fable'])
def test_unknown_models_have_no_price(model):
    assert pricing.lookup(model) is None
    assert pricing.price_hint(model) == ''


def test_claude_estimate_uses_every_reported_token_class():
    usage = {'model_reported': 'claude-haiku-4-5-20251001', 'input_tokens': 20,
             'cached_tokens': 4629, 'cache_write_5m_tokens': 5087, 'cache_write_1h_tokens': 100,
             'output_tokens': 40}
    expected = (20 * 1.0 + 4629 * 0.10 + 5087 * 1.25 + 100 * 2.0 + 40 * 5.0) / 1_000_000
    assert pricing.estimate(usage) == round(expected, 6)


def test_codex_estimate_prices_cached_input_separately():
    usage = {'model_reported': 'gpt-5.6-terra', 'input_tokens': 500, 'cached_tokens': 400,
             'output_tokens': 60}
    assert pricing.estimate(usage) == round((500 * 2.0 + 400 * 0.20 + 60 * 12.0) / 1_000_000, 6)


@pytest.mark.parametrize('usage', [
    {'model_reported': 'unknown-model', 'input_tokens': 10, 'output_tokens': 10},
    {'model_reported': 'claude-sonnet-5', 'input_tokens': None, 'output_tokens': 10},
    {'model_reported': 'claude-sonnet-5', 'input_tokens': 10, 'output_tokens': None},
    {'model_reported': '', 'model_requested': '', 'input_tokens': 10, 'output_tokens': 10},
    # Codex reports no cache-write classes, so a Codex model cannot price them.
    {'model_reported': 'gpt-6-astra', 'input_tokens': 10, 'output_tokens': 10, 'cache_write_5m_tokens': 5},
])
def test_unpriceable_calls_are_unknown_not_zero(usage):
    assert pricing.estimate(usage) is None


def test_zero_token_call_is_priced_as_zero():
    # A measured zero is different from a missing count.
    assert pricing.estimate({'model_reported': 'claude-sonnet-5', 'input_tokens': 0,
                             'output_tokens': 0}) == 0.0


def test_catalog_offers_only_full_ids_the_cli_honours():
    values = [e['value'] for e in pricing.catalog('claude')[1:]]
    assert values and all(v.startswith('claude-') for v in values), values


def test_catalog_entries_are_selectable_and_priced():
    for provider in ('claude', 'codex'):
        entries = pricing.catalog(provider)
        assert entries[0]['value'] == '' and entries[0]['label'] == 'CLI default'
        for entry in entries[1:]:
            assert re.fullmatch(r'[A-Za-z0-9._-]+', entry['value']), entry
            assert Mission.model_validate({'name': 'M', 'url': 'https://example.com',
                                           'goal': 'Audit this page', 'mode': 'audit',
                                           'provider': provider,
                                           'model': entry['value']}).model == entry['value']
            assert entry['price_hint'], entry


def test_configured_model_outside_the_catalog_stays_selectable_without_a_price():
    entries = pricing.catalog('codex', ['unknown-model'])
    extra = [e for e in entries if e['value'] == 'unknown-model']
    assert len(extra) == 1 and extra[0]['price_hint'] == ''
    # A model already listed is not duplicated.
    assert [e['value'] for e in pricing.catalog('codex', ['gpt-6-astra'])].count('gpt-6-astra') == 1


def test_totals_flag_partial_costs_and_collect_models():
    priced = {'model_reported': 'claude-sonnet-5', 'input_tokens': 1000, 'cached_tokens': 200,
              'cache_write_5m_tokens': 100, 'output_tokens': 50}
    priced['est_cost_usd'] = pricing.estimate(priced)
    unpriced = {'model_reported': '', 'input_tokens': None, 'output_tokens': None,
                'est_cost_usd': None}
    totals = pricing.totals([priced, unpriced])
    assert totals['calls'] == 2 and totals['models'] == ['claude-sonnet-5']
    # Cache writes are input tokens that were billed at a different rate.
    assert totals['input_tokens'] == 1100 and totals['cached_tokens'] == 200
    assert totals['cost_partial'] is True and totals['est_cost_usd'] == priced['est_cost_usd']
    assert pricing.totals([unpriced])['est_cost_usd'] is None
    assert pricing.money(None) == 'n/a' and pricing.money(0.05026).startswith('≈$0.0503')


def test_input_total_counts_cache_writes_as_input():
    # A cached Claude prompt reports almost all of its input as a cache write.
    assert pricing.input_total({'input_tokens': 2, 'cache_write_5m_tokens': 0,
                                'cache_write_1h_tokens': 4712, 'cached_tokens': 0}) == 4714
    assert pricing.input_total({'input_tokens': 500, 'cached_tokens': 400}) == 500
    assert pricing.input_total({'input_tokens': None, 'cache_write_5m_tokens': None}) is None
    assert pricing.input_total({'input_tokens': 0}) == 0


def test_report_shows_the_summed_input_and_never_a_missing_count_as_zero():
    run = {'ai_calls': 1, 'provider': 'claude',
           'ai_usage': [{'call': 1, 'purpose': 'review', 'model_reported': 'claude-sonnet-5',
                         'input_tokens': 2, 'cache_write_1h_tokens': 4712, 'cached_tokens': None,
                         'output_tokens': 777, 'wall_ms': 11589, 'est_cost_usd': 0.026622}],
           'ai_totals': {'calls': 1, 'input_tokens': 4714, 'cached_tokens': 0,
                         'output_tokens': 777, 'est_cost_usd': 0.026622, 'cost_partial': False,
                         'models': ['claude-sonnet-5']}}
    text = pricing.report(run)
    assert '4,714 in' in text and '— cached' in text and 'claude-sonnet-5' in text
    assert pricing.DISCLAIMER in text and pricing.PRICE_DATE in text


def test_research_prices_and_current_catalog():
    assert pricing.lookup('gpt-5.6-sol') == pricing._prices(4, .4, 20)
    assert pricing.lookup('gpt-5.4-mini-20260317') == pricing._prices(.75, .075, 4.5)
    assert pricing.lookup('gpt-5.5-pro') == pricing._prices(30, None, 180)
    assert pricing.catalog('codex', ['gpt-5.5'])[-1]['price_hint'] == '$5 in / $30 out per MTok'
    assert {e['value'] for e in pricing.catalog('claude')[1:]} == set(pricing.LADDER['claude'])
    assert pricing.lookup('claude-sonnet-4-5')['input'] == 3
