"""Shared outcome rules used by the worker, reports and release comparisons."""
# Deductions for the per-pillar rating. They express recorded severity, not measured
# business impact, so the basis text below travels with every score.
WEIGHT={'P0':40,'P1':40,'P2':15,'P3':5,'info':0}
BLOCKED_JOURNEY=30
BASIS=('Each selected pillar starts at 100 and loses points for its open, non-rejected findings '
       '(P0 and P1 cost 40, P2 costs 15, P3 costs 5; a finding an AI critic has not confirmed costs half). '
       'One issue is charged once at its worst severity, however many pages recorded it, so visiting '
       'more pages of the same website cannot by itself lower the score. '
       'A journey that did not reach its goal costs Functionality '+str(BLOCKED_JOURNEY)+'. '
       'A pillar that was not evaluated is not scored, which is different from scoring zero. '
       'This rates the findings recorded in this run. It is not a field measurement or an industry benchmark.')
SEVERITY_ORDER=['P0','P1','P2','P3','info']
# A reader is told what happened to the journey, not the internal status word.
OUTCOME_HEADLINE={'success':'The journey reached its goal','audit_completed':'The audit finished',
                  'blocked':'The journey did not reach its goal','budget_stop':'The run stopped at its budget'}
STATUS_HEADLINE={'completed':'The run finished','blocked':'The journey did not reach its goal',
                 'failed':'The run failed before it finished','cancelled':'The run was stopped',
                 'interrupted':'The run was interrupted by a service restart'}
GATE_WORDS={'block':'blocked by a confirmed serious finding','warn':'review before release',
            'pass':'nothing blocks release','not_evaluated':'not evaluated'}

def plain_headline(run):
    """The one sentence a reader sees first: what happened, in their words."""
    status=str(run.get('status','unknown'))
    # A run that never finished is described by how it ended; anything else by what the journey achieved.
    if status in ('failed','cancelled','interrupted'):return STATUS_HEADLINE[status]
    return OUTCOME_HEADLINE.get(run.get('mission_outcome')) or STATUS_HEADLINE.get(status) or ('Run '+status)

def scenario_coverage(run):
    """What the scenario actually established. Missing, skipped or unreadable evidence is a gap."""
    steps=run.get('scenario') or []
    if not steps:return {}
    gaps=[f"Step {s['number']} {s['status']}: {s.get('reason') or s['requested']}"[:300]
          for s in steps if s['status'] not in ('passed','failed')]
    checks=[s for s in steps if s['kind'] in ('check','hold')]
    passed=sum(1 for s in checks if s['status']=='passed')
    note=f'{passed} of {len(checks)} checks established'+(f'; {len(gaps)} steps left no usable evidence' if gaps else '')
    return {'status':'evaluated' if not gaps else 'partial','steps':len(steps),'checks':len(checks),
            'passed':passed,'failed':sum(1 for s in checks if s['status']=='failed'),'gaps':gaps[:20],'note':note}

def coverage(run):
    ai_done=run.get('ai_evaluation_completed',False)
    observations=run.get('observations',[])
    axe_ok=bool(observations) and all('error' not in o.get('axe',{'error':'not run'}) for o in observations)
    result={}
    if (run.get('platform') or run.get('mission',{}).get('platform'))=='android':
        checks=(observations[-1].get('checks',{}) if observations else {})
        scenario=run.get('scenario_coverage') or {}
        # A device this run left shaped cannot be trusted to have measured itself, or the next run.
        unrestored=[e['setting'] for e in (run.get('network_restore') or []) if not e.get('restored')]
        for pillar in run['mission']['pillars']:
            if pillar=='cro':done=ai_done
            elif pillar=='ux_ui':done=bool(observations) and all(o.get('checks',{}).get('hierarchy',{}).get('status')=='supported' for o in observations)
            elif pillar=='functionality':done=bool(observations) and checks.get('logcat',{}).get('status')=='supported' and run.get('measurements',{}).get('launch_status')=='ok'
            else:done=bool(observations) and any((checks.get(k) or {}).get('status')=='supported' for k in ('gfxinfo','meminfo'))
            unavailable=[k for k,v in checks.items() if v.get('status')!='supported']
            result[pillar]={'status':'evaluated' if done else 'not_evaluated','method':'deterministic + AI' if ai_done else 'deterministic','note':'Android lab checks; unavailable: '+(', '.join(unavailable) if unavailable else 'none')}
            # A scenario reports under Functionality; incomplete scenario evidence leaves that pillar unevaluated.
            if pillar=='functionality' and scenario:
                if scenario['status']!='evaluated':result[pillar]['status']='not_evaluated'
                result[pillar]['note']+=' · Scenario: '+scenario['note']
            if unrestored:
                result[pillar]['status']='not_evaluated'
                result[pillar]['note']+=' · Network settings left changed on the device: '+', '.join(unrestored)
        return result
    for pillar in run['mission']['pillars']:
        done=bool(observations)
        if pillar=='cro':done=ai_done
        if pillar=='ux_ui':done=done and axe_ok
        result[pillar]={'status':'evaluated' if done else 'not_evaluated','method':'deterministic + AI' if ai_done else 'deterministic','note':'Lab measurements only. Video metrics require observed playback.' if pillar=='performance' else 'Hypotheses, not measured conversion effects.' if pillar=='cro' else ''}
    return result

def actionable(run):
    """Findings a reader still has to act on: not rejected by the critic, not closed by a reviewer."""
    return [f for f in run.get('findings',[]) if f.get('verifier_status')!='REJECTED' and f.get('status') not in ('dismissed','resolved')]

def gate(run):
    open_findings=actionable(run)
    if any(f['severity'] in ('P0','P1') and f.get('verifier_status')=='CONFIRMED' and f.get('reproduced') for f in open_findings):return 'block'
    incomplete=any(v['status']!='evaluated' for v in run.get('coverage',{}).values())
    return 'warn' if open_findings or incomplete or run.get('status')!='completed' or run.get('evaluation_error') or run.get('policy_blocked_requests') else 'pass'

def scores(run):
    """0-100 per selected pillar, with the deductions that produced each number."""
    cov=run.get('coverage') or {}
    open_findings=actionable(run)
    pillars=run['mission']['pillars']
    result={}
    for pillar in pillars:
        if (cov.get(pillar) or {}).get('status')!='evaluated':
            result[pillar]={'score':None,'deductions':[],
                'reason':'CRO needs an AI review; this run completed none' if pillar=='cro' else 'This pillar was not evaluated in this run'}
            continue
        # One recurring issue is one deduction. A site-wide defect is recorded against every page
        # that showed it, so charging each record would make a deeper crawl score lower than a
        # shallow one for the same website. The group keeps its worst-severity record.
        groups={}
        for f in open_findings:
            if f.get('pillar')!=pillar:continue
            points=WEIGHT.get(f.get('severity'),WEIGHT['P2'])
            # An AI claim no critic confirmed is evidence of a risk, not of a defect.
            if f.get('verifier_status')=='UNCONFIRMED':points=points/2
            if not points:continue
            worst={'finding_id':f.get('id'),'title':f.get('title'),'severity':f.get('severity'),'verifier_status':f.get('verifier_status'),'points':points}
            key=f.get('rule') or f.get('issue_key') or f.get('title')
            if key in groups:
                groups[key]['pages']+=1
                if points>groups[key]['points']:groups[key].update(worst)
            else:groups[key]={**worst,'pages':1}
        deductions=list(groups.values())
        if pillar=='functionality' and run.get('mission_outcome')=='blocked':
            deductions.append({'finding_id':None,'title':'The journey did not reach its goal','severity':'P1','verifier_status':'CONFIRMED','points':BLOCKED_JOURNEY,'pages':1})
        result[pillar]={'score':max(0,round(100-sum(d['points'] for d in deductions))),'reason':'','deductions':deductions}
    scored=[v['score'] for v in result.values() if v['score'] is not None]
    result['overall']={'score':round(sum(scored)/len(scored)) if scored else None,'scored':len(scored),'of':len(pillars)}
    result['basis']=BASIS
    return result

def visits(run):
    """How many times the browser ran for this run: one, plus each continuation."""
    n=run.get('continuations') or 0
    return 'Continued '+('once' if n==1 else str(n)+' times')+', in '+str(n+1)+' visits'

def _severity_rank(f):
    severity=f.get('severity')
    return SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else len(SEVERITY_ORDER)

def executive_summary(run):
    """A reader-level report. Facts are deterministic; only the narrative may come from AI."""
    narrative=run.get('ai_summary') or {}
    rating=run.get('scores') or scores(run)
    overall=rating.get('overall') or {}
    open_findings=actionable(run)
    counts={s:sum(1 for f in open_findings if f.get('severity')==s) for s in SEVERITY_ORDER}
    counts={k:v for k,v in counts.items() if v}
    gaps=[p for p,v in (run.get('coverage') or {}).items() if v.get('status')!='evaluated']
    release=str(run.get('gate','not_evaluated'))
    facts=['Run '+str(run.get('status','unknown'))+'. Release check: '+GATE_WORDS.get(release,release)+'.']
    if run.get('mission_outcome'):facts.append('Journey outcome: '+str(run['mission_outcome'])+'.')
    # A continued run is one report over several visits; say so before any count is read as a single sitting.
    if run.get('continuations'):facts.append(visits(run)+': the report covers every visit.')
    facts.append('Overall score '+str(overall['score'])+' of 100 across '+str(overall.get('scored',0))+' of '+str(overall.get('of',0))+' selected pillars.' if overall.get('score') is not None else 'No pillar could be scored in this run.')
    facts.append('Open findings: '+', '.join(str(v)+' '+k for k,v in counts.items())+'.' if counts else 'No open findings were recorded.')
    if gaps:facts.append('Not evaluated: '+', '.join(gaps)+'.')
    if run.get('evaluation_error'):facts.append('AI evaluation incomplete: '+str(run['evaluation_error']))
    if run.get('policy_blocked_requests'):facts.append(str(run['policy_blocked_requests'])+' mutating requests were blocked by the read-only policy.')
    steps=[str(s).strip() for s in (narrative.get('next_steps') or []) if str(s).strip()][:5]
    if not steps:
        if any(f.get('verifier_status') in ('UNCONFIRMED','PROBABLE') for f in open_findings):steps.append('Replay this run to confirm the findings a critic has not confirmed.')
        if any(not f.get('owner') for f in open_findings):steps.append('Assign an owner to each open finding.')
        if gaps:steps.append('Evaluate the remaining pillars: '+', '.join(gaps)+'.')
        if run.get('evaluation_error'):steps.append('Read the AI evaluation error, then rerun the evaluation.')
        steps=steps or ['No follow-up is outstanding from this run.']
    return {'headline':str(narrative.get('headline') or plain_headline(run))[:200],
            'summary':str(narrative.get('summary') or ' '.join(facts))[:2000],
            'facts':facts,
            'top_findings':[{'id':f.get('id'),'title':f.get('title'),'severity':f.get('severity'),'pillar':f.get('pillar'),'verifier_status':f.get('verifier_status'),'evidence_id':f.get('evidence_id')} for f in sorted(open_findings,key=_severity_rank)[:5]],
            'coverage_gaps':gaps,'next_steps':steps,
            'source':'AI narrative with deterministic facts' if narrative.get('summary') else 'Deterministic; no AI narrative in this run'}

def sync_findings(project_id,updates,skip=()):
    """One issue has one review state. Write it to every finished run of the workspace that recorded it.

    `updates` maps a finding identity to the fields to apply. Returns the ids of the runs that changed."""
    from . import store,hub
    from .evaluate import finding_identity
    changed=[]
    for r in store.all_records('run',project_id):
        if r['id'] in skip or r.get('status') in ('queued','running'):continue
        edited=False
        for f in r.get('findings',[]):
            fields=updates.get(finding_identity(f))
            if fields and any(f.get(k)!=v for k,v in fields.items()):f.update(fields);edited=True
        if not edited:continue
        r['gate']=gate(r);r['scores']=scores(r);r['executive_summary']=executive_summary(r)
        # A teammate editing the same run at this moment must not stop the remaining reports from being updated.
        try:store.save('run',r);changed.append(r['id'])
        except (store.Conflict,hub.HubError):pass
    return changed
