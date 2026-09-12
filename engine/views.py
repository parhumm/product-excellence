"""Read-only views of a run, shared by the local console and the team server.

Nothing here executes a mission or touches a browser, so the team server can
import it on a box that has no Playwright installed.
"""
import json
from fastapi import HTTPException
from . import ai, pricing, store
from .pricing import tokens as count
from .evaluate import compare_runs, finding_identity
from .outcomes import BASIS, gate, scores, executive_summary

def rated(r):
    """A finished run is rated from its stored findings when it carries no score, or when its score
    was produced under a superseded rule, so every run stays readable and comparable under today's.
    The stored evidence is never touched; only the rating is recomputed for this response."""
    if r.get('status') in ('queued','running'):return r
    if (r.get('scores') or {}).get('basis')==BASIS:return r
    # The summary quotes the score, so it has to be built from the fresh rating, not the stale one.
    rescored={**r,'scores':scores(r)}
    return {**rescored,'executive_summary':executive_summary(rescored)}

def summary(r):return store.summary(rated(r))

def compare(a,b):
    """Two finished runs, or the reason they cannot be compared."""
    if a['id']==b['id']:raise HTTPException(422,'Select two different runs')
    if any(r['status'] in ('queued','running') for r in (a,b)):raise HTTPException(409,'Both runs must finish before comparison')
    return compare_runs(a,b)

def findings(runs,grouped=False):
    """Every finding in these runs, optionally folded so one issue is one row."""
    out=[]
    for r in runs:
        for f in r.get('findings',[]):out.append({**f,**({'_run_revision':r['_revision']} if '_revision' in r else {}),'project_id':store.workspace_of('run',r),'mission_name':r['mission']['name'],'created_at':r['created_at']})
    if not grouped:return out
    groups={}
    for f in out:
        key=(f['project_id'],finding_identity(f))
        # Runs arrive newest first, so the group keeps the latest evidence; an owner assigned on an earlier run must survive.
        if key not in groups:groups[key]={**f,'occurrences':[]}
        elif f.get('owner') and not groups[key].get('owner'):groups[key]['owner']=f['owner']
        groups[key]['occurrences'].append({'run_id':f['run_id'],'evidence_id':f['evidence_id'],'created_at':f['created_at']})
    return list(groups.values())

def ai_usage_lines(r):
    """The AI usage block for a markdown export: settings, totals, then one line per call."""
    totals=r.get('ai_totals') or {};usage=r.get('ai_usage') or []
    if r.get('ai_model')==ai.DYNAMIC:
        requested='Dynamic, up to '+(r.get('ai_model_max') or 'the strongest listed model')
        effort='chosen per call'
    else:
        requested=r.get('ai_model') or 'CLI default';effort=r.get('ai_effort') or 'low'
    header=f"Calls: {r.get('ai_calls',0)} | Provider: {r.get('provider') or 'none'} | Requested model: {requested} | Effort: {effort}"
    lines=['## AI usage',header]
    if not usage:
        lines.append('No AI call was made in this run.');return lines
    lines.append('Models used: '+(', '.join(totals.get('models') or []) or 'unknown'))
    lines.append(f"Tokens: {count(totals.get('input_tokens'))} input | {count(totals.get('cached_tokens'))} cached | {count(totals.get('output_tokens'))} output")
    lines.append('Input counts fresh prompt tokens plus tokens written to the prompt cache; cached counts cache hits.')
    lines.append('Estimated cost: '+pricing.money(totals.get('est_cost_usd'))+(' (partial: some calls could not be priced)' if totals.get('cost_partial') else ''))
    rows=['| # | Purpose | Model | Effort | Input | Cached | Output | Time | Estimate |',
          '| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for e in usage:
        purpose=e.get('purpose') or 'reasoning'
        if e.get('step') is not None:purpose+=f" {e['step']+1}"
        if e.get('error'):purpose+=' (failed)'
        cells=[str(e.get('call')),purpose,e.get('model_reported') or e.get('model_requested') or 'unknown',
               e.get('effort') or '',count(pricing.input_total(e)),count(e.get('cached_tokens')),
               count(e.get('output_tokens')),f"{round((e.get('wall_ms') or 0)/1000,1)} s",pricing.money(e.get('est_cost_usd'))]
        rows.append('| '+' | '.join(cells)+' |')
    lines.append('\n'.join(rows))
    lines.append(pricing.DISCLAIMER+f' Prices published {pricing.PRICE_DATE}.')
    return lines

def action_lines(r):
    """What the journey actually did: one line per attempted action."""
    actions=r.get('actions') or []
    if not actions:return ['## Actions','No browser action was attempted in this run.']
    lines=['## Actions']
    for a in actions:
        summary=a.get('summary') or f"{a.get('type')} {a.get('target') or a.get('value') or ''}".strip()
        result=a.get('error') or ('page changed' if a.get('state_changed') else 'no visible change' if a.get('evidence_after') else '')
        lines.append(f"{(a.get('step') or 0)+1}. {summary} · {a.get('status','pending')}"+(f" · {result}" if result else ''))
        if a.get('reason'):lines.append(f"   Reason: {a['reason']}")
    return ['\n'.join(lines)]

def summary_lines(r):
    """The executive summary block of a markdown export."""
    s=r.get('executive_summary') or executive_summary(r)
    lines=['## Executive summary','### '+s['headline'],s['summary']]
    # A deterministic summary is already the fact list read as a sentence.
    if s['source'].startswith('AI'):lines+=['Recorded facts:']+['- '+f for f in s['facts']]
    if s['top_findings']:lines+=['Most severe open findings:']+[f"- {f['severity']} · {f['title']} ({f['pillar']}, evidence {f['evidence_id']})" for f in s['top_findings']]
    lines+=['Next steps:']+[f'{i+1}. {step}' for i,step in enumerate(s['next_steps'])]+['Source: '+s['source']]
    return ['\n'.join(lines)]

def benchmark_lines(r):
    """The site-by-site comparison of a benchmark run."""
    sites=r.get('sites') or []
    if not sites:return []
    judged={str(b.get('url','')):b for b in (r.get('benchmark') or [])}
    rows=['## Benchmark','| Site | Outcome | Rank | LCP ms | CLS | TTFB ms | Axe violations |','| --- | --- | --- | --- | --- | --- | --- |']
    def cell(value,digits=0):return 'Not measured' if value is None else (f'{value:.{digits}f}' if isinstance(value,(int,float)) else str(value))
    for s in sites:
        m=s.get('metrics') or {};rank=(judged.get(s['url']) or {}).get('rank')
        rows.append(f"| {s['url']} | {s['outcome']} | {rank if rank is not None else 'Not ranked'} | {cell(m.get('lcp'))} | {cell(m.get('cls'),3)} | {cell(m.get('ttfb_ms'))} | {cell(s.get('axe_violations'))} |")
    lines=['\n'.join(rows)]
    for s in sites:
        b=judged.get(s['url']) or {}
        detail=[f"### {s['url']}",f"Outcome: {s['outcome']} · {s.get('reason') or 'No reason recorded'}"]
        if s.get('evidence_id'):detail.append(f"Screenshot: /api/runs/{r['id']}/artifacts/{s['evidence_id']}.png")
        if b.get('observed'):detail.append('Observed: '+b['observed'])
        if b.get('strengths'):detail.append('Strengths: '+b['strengths'])
        if b.get('weaknesses'):detail.append('Weaknesses: '+b['weaknesses'])
        lines.append('\n'.join(detail))
    return lines

def score_lines(r):
    """The score table of a markdown export, with the deductions that produced each number."""
    s=r.get('scores') or scores(r)
    overall=s.get('overall') or {}
    rows=['## Scores','| Pillar | Score | Detail |','| --- | --- | --- |']
    for pillar,value in s.items():
        if pillar in ('overall','basis'):continue
        detail='; '.join(f"{d['title']} −{d['points']:g}" for d in value['deductions']) or value['reason'] or 'No open findings'
        rows.append(f"| {pillar} | {value['score'] if value['score'] is not None else 'Not scored'} | {detail} |")
    rows.append(f"| **Overall** | {overall.get('score') if overall.get('score') is not None else 'Not scored'} | {overall.get('scored',0)} of {overall.get('of',0)} pillars scored |")
    return ['\n'.join(rows),s.get('basis','')]

def console_lines(r):
    """Console and JavaScript errors with the detail needed to debug them."""
    events=[e for e in r.get('console',[]) if e.get('kind') in ('pageerror','error','warning')]
    if not events:return []
    lines=[f'## Console and JavaScript errors ({len(events)})']
    for e in events:
        lines.append('\n'.join([f"### {e.get('kind')} · {(e.get('name') or '').strip() or 'console'}",
            str(e.get('message','')),
            f"Source: {e.get('source') or 'Not reported'} | Page: {e.get('page_url') or 'Unknown'} | Step: {(e['step']+1) if isinstance(e.get('step'),int) else 'n/a'} | At: {e.get('at','')}",
            (f"```\n{e['stack']}\n```" if e.get('stack') else '')]).strip())
    return lines

def export_markdown(r):
    """One run as a self-contained report a stakeholder can read without the console."""
    id=r['id']
    lines=[f"# {r['mission']['name']}",f"Status: {r['status']} | Release gate: {r['gate']}",f"URL: {r['mission']['url']}",f"Run: {id}",f"Browser: {r['mission']['browser']} | Viewport: {r['mission']['viewport']}",f"Network: {json.dumps(r.get('network_applied'),ensure_ascii=False)}",f"Egress: {json.dumps(r.get('egress'),ensure_ascii=False)}",f"Error: {r.get('error') or 'None'}"]+summary_lines(r)+benchmark_lines(r)+score_lines(r)+action_lines(r)+ai_usage_lines(r)+['## Findings']
    for f in r['findings']:
        lines.extend([f"### {f['severity']} · {f['title']}",f"{f['pillar']} · {f['classification']} · {f['verifier_status']}",f"Observed: {f['observed']}",f"Expected: {f['expected']}",f"Recommendation: {f['recommendation']}",f"Evidence: {f['evidence_id']} | Source: {f['source']}",f"Screenshot: /api/runs/{id}/artifacts/{f['evidence_id']}.png",f"Review status: {f.get('status','open')} | Owner: {f.get('owner') or 'Unassigned'}"])
    lines+=console_lines(r)+['## Coverage',json.dumps(r.get('coverage',{}),ensure_ascii=False,indent=2),'## Limitations','Lab observations do not establish field Core Web Vitals or causal conversion impact. AI findings require review. An unconfigured or blocked capability is not a pass. Raw browser traces and page snapshots may contain account data; keep evidence local.']
    return '\n\n'.join(lines)+'\n'
