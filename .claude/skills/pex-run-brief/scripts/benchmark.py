"""The benchmark layout of the run report.

A benchmark run answers one question on the product's own page and then on each
competitor. A benchmark report reads one or more of those runs, usually one per
page type, and turns them into a playbook: for every problem worth fixing, the
product's own screen beside the competitor screen that shows the fix, with the
element in question outlined.

The records supply every rank, outcome, metric, page address and screenshot.
The narrative supplies the cards. Nothing is cited unless the runs captured it:
a screen must be an evidence id of a named run, and a code excerpt must appear
in that screen's saved page source.
"""
import html
import math
import re
import sys
from urllib.parse import urlsplit

IMPACT = ('high', 'medium', 'low')
CONFIDENCE = {'confirmed': 'Confirmed', 'screenshot': 'Seen in screenshot', 'unverified': 'Needs checking'}
# The engine masks these fields in every screenshot (engine/runner.py), so a filled
# box over one is the tool's doing, not the site's.
MASKED = 'password, email, phone and one-time-code fields'


def host(url):
    name = (urlsplit(str(url or '')).hostname or str(url or '')).lower()
    return name[4:] if name.startswith('www.') else name


def ordinal(number):
    suffix = 'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
    return f'{number}{suffix}'


def seconds(ms):
    return f'{ms / 1000:.2f} s' if isinstance(ms, (int, float)) else '–'


class Runs:
    """The benchmark runs a report is built from, addressable by id or an 8+ character prefix."""

    def __init__(self, loaded):
        self.items = loaded  # [(run_id, record, folder)]

    def __iter__(self):
        return iter(self.items)

    def find(self, ref):
        if not ref and len(self.items) == 1:
            return self.items[0]
        ref = str(ref or '')
        matches = [item for item in self.items if len(ref) >= 8 and item[0].startswith(ref)]
        if len(matches) != 1:
            known = ', '.join(run_id[:8] for run_id, _, _ in self.items)
            sys.exit(f'The narrative names run "{ref}", which is not one of the runs given ({known}). '
                     'Name a run by its id or its first eight characters.')
        return matches[0]


def observation(runs, ref, evidence):
    run_id, record, folder = runs.find(ref)
    for seen in record.get('observations') or []:
        if seen.get('id') == evidence:
            return run_id, record, folder, seen
    known = ', '.join(o.get('id', '?') for o in record.get('observations') or [])
    sys.exit(f'The narrative cites {evidence} in run {run_id[:8]}, which that run does not contain. '
             f'Known evidence ids: {known or "none"}.')


def normal(text):
    return re.sub(r'\s+', ' ', html.unescape(str(text or ''))).strip()


def check(narrative, runs):
    """Refuse a card that cites a screen, a mark or a code excerpt the runs cannot back."""
    for play in narrative.get('plays') or []:
        for screen in play.get('screens') or []:
            _, _, folder, _ = observation(runs, screen.get('run'), screen.get('evidence'))
            if not (folder / f'{screen["evidence"]}.png').is_file():
                sys.exit(f'{screen["evidence"]} has no screenshot in {folder}.')
            for mark in screen.get('marks') or []:
                box = [mark.get(k) for k in ('x', 'y', 'w', 'h')]
                if not all(isinstance(v, (int, float)) for v in box) or min(box) < 0 \
                        or box[0] + box[2] > 100.5 or box[1] + box[3] > 100.5:
                    sys.exit(f'A mark on {screen["evidence"]} must give x, y, w and h as percentages '
                             f'of the whole screenshot that stay inside it: {mark}')
        for block in play.get('code') or []:
            _, _, folder, _ = observation(runs, block.get('run'), block.get('evidence'))
            source = folder / f'{block["evidence"]}.dom.txt'
            page = normal(source.read_text(errors='replace')) if source.is_file() else ''
            for line in block.get('lines') or []:
                if normal(line) not in page:
                    sys.exit(f'The code excerpt "{line[:80]}" is not in the saved page source of '
                             f'{block["evidence"]}. Copy excerpts from {source.name}, do not retype them.')
    for row in narrative.get('also_found') or []:
        if row.get('evidence'):
            observation(runs, row.get('run'), row['evidence'])


def brand_names(narrative):
    """Host → brand name, from every page, so a site is named the same way throughout."""
    names = {}
    for value in (narrative.get('pages') or {}).values():
        names.update(value.get('names') or {})
    return names


def own(record):
    return host((record.get('mission') or {}).get('url'))


def answered(record):
    return {host(s.get('url')): s for s in record.get('sites') or []}


def scoreboard(runs, narrative, esc):
    cards = []
    pages = narrative.get('pages') or {}
    names = brand_names(narrative)
    for run_id, record, _ in runs:
        page = next((v for k, v in pages.items() if run_id.startswith(k)), {})
        me, sites = own(record), answered(record)
        ranked = sorted(record.get('benchmark') or [], key=lambda b: (b.get('rank') is None, b.get('rank') or 0))
        good = [b for b in ranked if sites.get(host(b.get('url')), {}).get('outcome', 'success') == 'success']
        failed = [s for s in record.get('sites') or [] if s.get('outcome') != 'success']
        chips, place = [], None
        for index, entry in enumerate(good, 1):
            name = host(entry.get('url'))
            if name == me:
                place = index
            chips.append(f'<li class="{"us" if name == me else ""}">{esc(names.get(name, name))}</li>')
        for site in failed:
            name = host(site.get('url'))
            chips.append(f'<li class="fail" title="{esc(site.get("outcome"))}">{esc(names.get(name, name))}</li>')
        rank = (f'<b>{ordinal(place)}</b><span>of {len(good)}{" that answered" if failed else ""}</span>'
                if place else '<b>–</b><span>not ranked by the review</span>')
        label = page.get('label') or (record.get('mission') or {}).get('name', 'Benchmark')
        question = page.get('question') or ''
        cards.append(f'''<article class="score">
  <span class="label">{esc(label)}</span>
  <div class="rank">{rank}</div>
  {f'<p>{esc(question)}</p>' if question else ''}
  <ol class="order" aria-label="Ranking, best first">{''.join(chips)}</ol>
</article>''')
    return f'<div class="board">{"".join(cards)}</div>'


def lcp_order(site):
    """Slowest first; a site without a measurement goes last and is never read as zero."""
    lcp = (site.get('metrics') or {}).get('lcp')
    return (0, -lcp) if isinstance(lcp, (int, float)) else (1, 0)


def speed_table(runs, narrative, esc):
    rows, peak = [], 0
    pages = narrative.get('pages') or {}
    names = brand_names(narrative)
    for run_id, record, _ in runs:
        me = own(record)
        measured = [s for s in record.get('sites') or [] if s.get('outcome') == 'success']
        if not measured:
            continue
        label = next((v.get('label') for k, v in pages.items() if run_id.startswith(k)), None) \
            or (record.get('mission') or {}).get('name', '')
        rows.append(('group', label))
        measured.sort(key=lcp_order)
        for site in measured:
            metrics = site.get('metrics') or {}
            if isinstance(metrics.get('lcp'), (int, float)):
                peak = max(peak, metrics['lcp'])
            rows.append(('site', host(site.get('url')) == me, names.get(host(site.get('url')), host(site.get('url'))), metrics))
    if not rows:
        return ''
    scale = max(3, math.ceil(peak / 1000)) * 1000
    body = []
    for row in rows:
        if row[0] == 'group':
            body.append(f'<tr class="group"><td colspan="4">{esc(row[1])}</td></tr>')
            continue
        _, mine, name, metrics = row
        lcp = metrics.get('lcp')
        bar = (f'<div class="track"><span class="fill" style="width:{lcp / scale * 100:.1f}%"></span>'
               f'<span class="limit" style="left:{2500 / scale * 100:.1f}%"></span></div>'
               if isinstance(lcp, (int, float)) else '<span class="na">not recorded</span>')
        body.append(f'<tr class="{"us" if mine else ""}" title="{esc(name)} · LCP {seconds(lcp)} · server {seconds(metrics.get("ttfb_ms"))}">'
                    f'<td class="site">{esc(name)}</td><td>{bar}</td>'
                    f'<td class="num">{seconds(lcp)}</td><td class="num">{seconds(metrics.get("ttfb_ms"))}</td></tr>')
    return f'''<div class="chart">
  <div class="keyline"><span><i class="own"></i>This product</span><span><i class="other"></i>Competitor</span><span><i class="dash"></i>2.5 s “good” limit</span></div>
  <table><thead><tr><th scope="col">Site</th><th scope="col">LCP, 0–{scale // 1000} s</th><th scope="col">LCP</th><th scope="col">Server</th></tr></thead>
  <tbody>{''.join(body)}</tbody></table>
  <p class="muted small">One visit per page, measured by the run. Sites that did not answer the question are left out.</p>
</div>'''


def screen_figure(runs, screen, esc, picture):
    run_id, record, folder, seen = observation(runs, screen.get('run'), screen.get('evidence'))
    shot = picture(folder, screen['evidence'])
    mine = host(seen.get('url')) == own(record)
    marks = []
    for mark in screen.get('marks') or []:
        classes = ' '.join(c for c in ('hl', 'dash' if mark.get('dashed') else '', 'below' if mark.get('below') else '',
                                       'right' if mark.get('right') else '') if c)
        marks.append(f'<span class="{classes}" style="left:{mark["x"]}%;top:{mark["y"]}%;width:{mark["w"]}%;height:{mark["h"]}%">'
                     f'<span>{esc(mark.get("label"))}</span></span>')
    wide = shot['w'] > shot['h']
    return f'''<figure class="shot{' wide' if wide else ''}">
  <span class="who {'us' if mine else 'them'}">{esc(screen.get('who') or host(seen.get('url')))}</span>
  <div class="frame"><div class="screen"><img src="{shot['src']}" width="{shot['w']}" height="{shot['h']}" alt="{esc(screen.get('alt') or screen.get('caption'))}">{''.join(marks)}</div></div>
  <figcaption>{esc(screen.get('caption'))} <span class="where">{esc(seen.get('url'))} · {esc(screen['evidence'])}</span></figcaption>
</figure>'''


def code_block(block, esc):
    lines = '\n'.join(esc(line) for line in block.get('lines') or [])
    return f'<span class="label">{esc(block.get("who"))} · page source</span><pre class="code">{lines}</pre>'


def items(values, esc):
    return ''.join(f'<li>{esc(v)}</li>' for v in values or [])


def plays(runs, narrative, esc, picture):
    cards = []
    for index, play in enumerate(narrative.get('plays') or [], 1):
        impact = play.get('impact') if play.get('impact') in IMPACT else 'medium'
        confidence = CONFIDENCE.get(play.get('confidence'), CONFIDENCE['unverified'])
        copy = f'<span class="tag">Copy: {esc(play["copy_from"])}</span>' if play.get('copy_from') else ''
        strip = ''.join(screen_figure(runs, s, esc, picture) for s in play.get('screens') or [])
        code = [b for b in play.get('code') or []]
        today_code = ''.join(code_block(b, esc) for b in code if b.get('side') == 'today')
        best_code = ''.join(code_block(b, esc) for b in code if b.get('side') != 'today')
        speed = speed_table(runs, narrative, esc) if play.get('speed') else ''
        cards.append(f'''<article class="play">
  <div class="top"><span class="n">{index}</span><h3>{esc(play.get('title'))}</h3>
    <div class="tags"><span class="chip {impact}">{impact.title()} impact</span><span class="tag">{esc(confidence)}</span>{copy}</div></div>
  {f'<div class="strip">{strip}</div>' if strip else ''}
  <div class="trio">
    <div class="col"><span class="label">Today</span>{today_code}<p>{esc(play.get('today'))}</p></div>
    <div class="col copy"><span class="label">Best examples</span>{best_code}{speed}<ul>{items(play.get('best'), esc)}</ul></div>
    <div class="col do"><span class="label">Do this</span><ul>{items(play.get('do'), esc)}</ul></div>
  </div>
</article>''')
    return ''.join(cards)


def also_found(narrative, esc):
    rows = narrative.get('also_found') or []
    if not rows:
        return ''
    body = ''.join(f'<tr><td>{esc(r.get("what"))}</td><td>{esc(r.get("where"))}</td><td>{esc(r.get("basis"))}</td>'
                   f'<td><span class="tag">{esc(CONFIDENCE.get(r.get("confidence"), CONFIDENCE["unverified"]))}</span></td></tr>'
                   for r in rows)
    return f'''<section aria-labelledby="also">
  <div class="intro"><span class="label">Also found</span><h2 id="also">Issues outside the planned questions</h2></div>
  <div class="tablewrap"><table><thead><tr><th>What</th><th>Where</th><th>Evidence</th><th>How sure</th></tr></thead>
  <tbody>{body}</tbody></table></div>
</section>'''


def limits(runs, narrative):
    lines, names = [], brand_names(narrative)
    for run_id, record, _ in runs:
        verdicts = {host(b.get('url')): b for b in record.get('benchmark') or []}
        for site in record.get('sites') or []:
            if site.get('outcome') == 'success':
                continue
            name = host(site.get('url'))
            said = (verdicts.get(name) or {}).get('observed') or site.get('reason') or ''
            lines.append(f'{names.get(name, name)} did not answer in run {run_id[:8]} ({site.get("outcome")}). {said[:180]}'.strip())
    lines += ['Each page was visited once, so speed figures vary between visits.',
              'Rankings are the review AI\'s judgement of what each page showed, not traffic or conversion data.',
              f'The tool masks {MASKED} in screenshots; a filled box over one is not part of the site.',
              'Browsing was read-only: nothing was signed up for, bought or submitted.']
    return lines + list(narrative.get('limits') or [])


def build(runs, narrative, esc, picture, base_style):
    check(narrative, runs)
    first = runs.items[0][1]
    mission = first.get('mission') or {}
    dates = sorted({(record.get('created_at') or '')[:10] for _, record, _ in runs} - {''})
    visits = sum(len(record.get('sites') or []) for _, record, _ in runs)
    calls = sum(record.get('ai_calls') or 0 for _, record, _ in runs)
    network = (first.get('network_snapshot') or {}).get('name') or mission.get('network', '')
    me = own(first)
    title = narrative.get('title') or f'{me} benchmark'
    speed = '' if any(p.get('speed') for p in narrative.get('plays') or []) else speed_table(runs, narrative, esc)
    keep = items(narrative.get('keep'), esc)
    corrections = items(narrative.get('corrections'), esc)
    run_list = ', '.join(f'{run_id[:8]} ({(record.get("mission") or {}).get("name", "")})' for run_id, record, _ in runs)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{base_style}{STYLE}</style></head><body><div class="wrap">

<header>
  <span class="label">Competitor benchmark · {esc(mission.get("viewport", ""))} · signed-out visitor</span>
  <h1>{esc(title)}</h1>
  <p class="lede">{esc(narrative.get("headline"))}</p>
  <div class="meta"><span>{esc(" – ".join(dates[:1] + dates[1:][-1:]))}</span><span>{esc(me)}</span>
    <span>{esc(mission.get("browser", ""))} · {esc(mission.get("viewport", ""))}</span><span>{esc(network)} network</span>
    <span>{len(runs.items)} benchmark{"s" if len(runs.items) != 1 else ""} · {visits} page visits</span><span>read-only</span></div>
</header>

<section aria-labelledby="board">
  <div class="intro"><span class="label">Where it stands</span><h2 id="board">{esc(narrative.get("board_title") or "Rank on each page")}</h2>
  <p class="muted">The review ranked each page on one question, 1 being best. Sites that did not answer are struck through.</p></div>
  {scoreboard(runs, narrative, esc)}
</section>

<section aria-labelledby="plays">
  <div class="intro"><span class="label">The playbook</span><h2 id="plays">{esc(narrative.get("plays_title") or "What to change, and whose fix to copy")}</h2>
  <p class="muted">Each card puts this product's screen beside the competitor screens that show the fix, uncropped, with the element in question outlined. Impact is the report's ranking; any effect on conversion is a hypothesis to test.</p></div>
  <div class="legend"><span><i class="swatch"></i>the element being discussed</span>
    <span><b class="tag">Confirmed</b> an automated check or the page source shows it</span>
    <span><b class="tag">Seen in screenshot</b> visible on the captured screen</span>
    <span><b class="tag">Needs checking</b> read from page text or not yet verified</span></div>
  <div class="plays">{plays(runs, narrative, esc, picture)}</div>
</section>

{f'<section aria-labelledby="speed"><div class="intro"><span class="label">Speed</span><h2 id="speed">Time until the largest element appears</h2></div>{speed}</section>' if speed else ''}

{also_found(narrative, esc)}

<section aria-labelledby="limits">
  <div class="cols">
    {f'<div class="note"><span class="label">Already ahead</span><h3>Keep these</h3><ul>{keep}</ul></div>' if keep else ''}
    <div class="note warn"><span class="label">Read before sharing</span><h3 id="limits">Limits of this benchmark</h3><ul>{items(limits(runs, narrative), esc)}</ul></div>
    {f'<div class="note"><span class="label">Corrections</span><h3>Where a run summary was wrong</h3><ul>{corrections}</ul></div>' if corrections else ''}
  </div>
</section>

<footer><span>Product Excellence benchmark runs {esc(run_list)} · {calls} AI calls.</span>
<span>Evidence stays on the Mac that ran the tests, in each run's artifact folder. Competitor quotes are the sites' own words.</span></footer>

</div></body></html>'''


STYLE = '''
.wrap{max-width:74rem}
.small{font-size:.82rem}
:root{--mark:#FFB020;--mark-ink:#1A1300;--code:#EEF2F5;--bar:#B7C3CE}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--code:#10171E;--bar:#3F4E5C}}
:root[data-theme="dark"]{--code:#10171E;--bar:#3F4E5C}
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1rem}
.score{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.2rem;display:grid;gap:.55rem;align-content:start}
.rank{display:flex;align-items:baseline;gap:.4rem}
.rank b{font:700 2.6rem/1 var(--display);font-variant-numeric:tabular-nums}
.rank span{color:var(--muted)}
.order{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.3rem}
.order li{font:500 .74rem/1 var(--mono);padding:.32rem .45rem;border-radius:5px;background:var(--sunk);color:var(--muted)}
.order li.us{background:var(--accent-soft);color:var(--accent);font-weight:600}
.order li.fail{text-decoration:line-through}
.legend{display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;font-size:.86rem;color:var(--muted);align-items:center}
.legend span{display:inline-flex;gap:.45rem;align-items:center}
.swatch{display:inline-block;width:1.1rem;height:.8rem;border:2px solid var(--mark);border-radius:3px}
.plays{display:grid;gap:1.4rem}
.play{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1.4rem;display:grid;gap:1.3rem}
.play .top{display:grid;grid-template-columns:2.4rem 1fr;gap:.2rem 1rem;align-items:start}
.play .n{font:700 1.6rem/1.05 var(--display);color:var(--muted);font-variant-numeric:tabular-nums}
.play .tags{grid-column:2;display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.35rem}
.trio{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1.2rem;align-items:start}
@media (max-width:900px){.trio{grid-template-columns:1fr}}
.col{display:grid;gap:.6rem;align-content:start;font-size:.93rem}
.col.copy{background:var(--sunk);border-radius:12px;padding:.9rem}
.col.do{background:var(--accent-soft);border-radius:12px;padding:.9rem}
.col.do .label{color:var(--accent)}
.col ul{margin:0;padding-left:1.05rem;display:grid;gap:.35rem}
.col ul:empty{display:none}
.strip{display:flex;flex-wrap:wrap;gap:1.4rem 1.2rem;align-items:start}
.shot{margin:0;display:grid;gap:.45rem;width:16.5rem;max-width:100%}
.shot.wide{width:30rem}
.shot .who{font:600 .78rem/1.2 var(--mono);letter-spacing:.04em;text-transform:uppercase}
.shot .who.us{color:var(--accent)}
.shot .who.them{color:var(--muted)}
.frame{background:var(--phone);border-radius:22px;padding:7px;line-height:0}
.shot.wide .frame{border-radius:12px}
.frame img{display:block;width:100%;height:auto;border-radius:15px}
.shot.wide .frame img{border-radius:6px}
.screen{position:relative}
.hl{position:absolute;border:2.5px solid var(--mark);border-radius:5px;box-shadow:0 0 0 2px rgba(0,0,0,.55);pointer-events:none}
.hl.dash{border-style:dashed}
.hl span{position:absolute;left:-2.5px;bottom:100%;margin-bottom:3px;background:var(--mark);color:var(--mark-ink);font:600 .64rem/1.25 var(--mono);padding:.16rem .34rem;border-radius:4px;white-space:nowrap}
.hl.below span{bottom:auto;top:100%;margin:3px 0 0}
.hl.right span{left:auto;right:-2.5px}
.shot figcaption{font-size:.84rem;line-height:1.45;color:var(--ink);display:grid;gap:.2rem}
pre.code{margin:0;background:var(--code);border:1px solid var(--line);border-radius:10px;padding:.75rem .85rem;font:400 .74rem/1.55 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}
.chart{display:grid;gap:.7rem;overflow-x:auto}
.chart table{min-width:19rem;font-size:.85rem}
.chart th,.chart td{padding:.3rem .4rem;border-bottom:0;background:none}
.chart tr.group td{padding-top:.8rem;font:600 .7rem/1.2 var(--mono);color:var(--muted);letter-spacing:.05em;text-transform:uppercase}
.chart td.site{white-space:nowrap}
.chart tr.us td.site{font-weight:600;color:var(--accent)}
.chart td.num{font:500 .8rem/1 var(--mono);text-align:right;color:var(--muted)}
.track{position:relative;height:14px;min-width:6rem}
.track .fill{position:absolute;left:0;top:2px;height:10px;border-radius:0 4px 4px 0;background:var(--bar)}
.chart tr.us .fill{background:var(--accent)}
.track .limit{position:absolute;top:-6px;bottom:-6px;width:0;border-left:2px dashed var(--medium)}
.na{font:500 .74rem/1 var(--mono);color:var(--muted)}
.keyline{display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.8rem;color:var(--muted)}
.keyline i{display:inline-block;width:.9rem;height:.6rem;border-radius:2px;vertical-align:middle;margin-right:.35rem}
.keyline i.own{background:var(--accent)}
.keyline i.other{background:var(--bar)}
.keyline i.dash{width:0;height:.9rem;border-left:2px dashed var(--medium);border-radius:0}
.note.warn{border-color:var(--medium);background:var(--medium-soft)}
'''
