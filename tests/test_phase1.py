import asyncio,json,re
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from engine import store
from engine.runner import Runner
from engine import presets
from engine.contracts import Mission,NetworkProfile
from engine.outcomes import coverage,gate,sync_findings
from engine.schema_validation import vocabulary,validate_schema
from engine.evaluate import compare_runs
import app as service

@pytest.fixture
def client(monkeypatch,tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'ARTIFACTS',tmp_path/'artifacts');store.ARTIFACTS.mkdir()
    worker=Runner();monkeypatch.setattr(service,'runner',worker)
    async def no_execute():
        await asyncio.Event().wait()
    monkeypatch.setattr(worker,'loop',no_execute)
    with TestClient(service.app,headers={'X-PEX-Request':'1'}) as c:yield c
    engine.dispose()

def mission(client,**kw):
    data={'name':'Fixture','url':'https://example.com','goal':'Audit the homepage','mode':'audit','provider':'none',**kw}
    r=client.post('/api/missions',json=data);assert r.status_code==200,r.text;return r.json()

def test_fresh_seed_and_idempotence(client):
    s=client.get('/api/state').json();assert {n['id'] for n in s['networks']} >= {'baseline','slow-mobile','poor-mobile','offline','netem-poor','unstable'}
    service.seed();assert len(client.get('/api/state').json()['networks'])==len(s['networks'])
    assert len(client.get('/api/missions').json())==len(s['missions'])

def test_every_workspace_starts_with_presets(client):
    seeded={m['template'] for m in client.get('/api/missions').json()}
    assert seeded=={p['template'] for p in presets.GENERIC}
    other=client.post('/api/projects',json={'name':'Other','url':'https://example.org'}).json()
    assert other['presets']==presets.PRESET_VERSION
    pack={m['template'] for m in client.get('/api/state',params={'project':other['id']}).json()['missions']}
    assert pack=={p['template'] for p in presets.GENERIC}
    plain=client.post('/api/projects',json={'name':'Anything','url':'https://example.com'}).json()
    ms=client.get('/api/state',params={'project':plain['id']}).json()['missions']
    assert len(ms)==10 and all(m['allowed_domains']==['example.com'] for m in ms)

def test_deleted_preset_is_not_recreated(client):
    gone=[m for m in client.get('/api/missions').json() if m['template']=='search'][0]
    client.delete('/api/missions/'+gone['id']);service.seed()
    assert 'search' not in {m['template'] for m in client.get('/api/missions').json()}

def test_create_edit_export_import_version(client):
    m=mission(client);m['name']='Changed'
    assert client.put('/api/missions/'+m['id'],json=m).json()['version']==2
    assert len(client.get('/api/missions/'+m['id']+'/versions').json())==1
    y=client.get('/api/missions/'+m['id']+'/export').text
    assert client.post('/api/import',files={'file':('mission.yaml',y,'application/yaml')}).json()['name']=='Changed'
def test_network_validation_and_snapshot(client):
    assert client.post('/api/networks',json={'name':'Bad','loss_pct':1}).status_code==422
    m=mission(client);r=client.post('/api/runs',json={'mission_id':m['id']}).json()
    client.put('/api/networks/baseline',json={'name':'Changed baseline','latency_ms':100})
    assert client.get('/api/runs/'+r['id']).json()['network_snapshot']['latency_ms']==0
    assert client.post('/api/runs',json={'mission_id':m['id'],'network':'missing'}).status_code==404

def test_matrix_rejects_unsupported_browser_before_queueing(client):
    m=mission(client,browser='webkit');assert client.post('/api/missions/'+m['id']+'/matrix').status_code==422
    assert not store.all_records('run')
def test_cancel_queued_and_matrix(client):
    m=mission(client);runs=client.post('/api/missions/'+m['id']+'/matrix').json();assert len(runs)==5
    id=runs[0]['id'];client.post('/api/runs/'+id+'/cancel');assert client.get('/api/runs/'+id).json()['status']=='cancelled'
def test_scheduler_pause_resume_tick(client,monkeypatch):
    m=mission(client);s=client.post('/api/schedules',json={'mission_id':m['id'],'every_minutes':5,'enabled':True}).json()
    assert client.patch('/api/schedules/'+s['id'],json={'enabled':False}).json()['enabled'] is False
    s=client.patch('/api/schedules/'+s['id'],json={'enabled':True}).json();s['next_at']='2000-01-01T00:00:00+00:00';store.save('schedule',s)
    asyncio.run(service.schedule_once());assert len(store.all_records('run'))==1
    s=store.get('schedule',s['id']);s['next_at']='2000-01-01T00:00:00+00:00';store.save('schedule',s)
    asyncio.run(service.schedule_once());assert len(store.all_records('run'))==1

def test_persona_and_proxy_secrets_not_in_state(client):
    p=client.post('/api/personas',files={'file':('session.json',json.dumps({'cookies':[],'origins':[]}),'application/json')}).json()
    assert client.delete('/api/personas/'+p['id']).status_code==200
    e=client.post('/api/egress',json={'name':'Proxy','server':'http://127.0.0.1:9999','username':'u','password':'SECRET_SENTINEL'}).json()
    assert 'SECRET_SENTINEL' not in client.get('/api/state').text
    assert (store.DATA/'secrets'/f"{e['id']}.json").stat().st_mode & 0o777==0o600

def test_mission_password_stored_as_secret(client):
    m=mission(client,login_identifier='test-user@example.invalid',login_password='SECRET_SENTINEL')
    path=store.DATA/'secrets'/f"{m['id']}.json"
    assert path.stat().st_mode & 0o777==0o600 and json.loads(path.read_text())['password']=='SECRET_SENTINEL'
    for text in (client.get('/api/missions').text,client.get('/api/state').text,client.get('/api/missions/'+m['id']+'/export').text):
        assert 'SECRET_SENTINEL' not in text
    # An edit that leaves the password field blank keeps the stored password.
    assert client.put('/api/missions/'+m['id'],json={**m,'name':'Changed'}).status_code==200
    assert json.loads(path.read_text())['password']=='SECRET_SENTINEL'
    assert client.post('/api/missions',json={'name':'No id','url':'https://example.com','goal':'Audit the homepage','mode':'audit','provider':'none','login_password':'x'}).status_code==422
    client.delete('/api/missions/'+m['id']);assert not path.exists()

def test_schema_checks():
    types,props=vocabulary();assert 'VideoObject' in types and 'name' in props
    assert not validate_schema(json.dumps({'@context':'https://schema.org','@type':'VideoObject','name':'Trailer','uploadDate':'2026-01-01'}))
    assert any(i['code']=='unknown-type' for i in validate_schema('{"@context":"https://schema.org","@type":"MadeUp"}'))
    assert any(i['code']=='unknown-property' for i in validate_schema('{"@context":"https://schema.org","@type":"Movie","madeUp":1}'))
def test_incomplete_coverage_and_rejected_findings_gate():
    r={'mission':{'pillars':['cro','ux_ui']},'status':'completed','observations':[{'axe':{'error':'failed'}}],'findings':[]}
    r['coverage']=coverage(r);assert gate(r)=='warn'
    r['coverage']={'cro':{'status':'evaluated'}};r['findings']=[{'severity':'P1','verifier_status':'REJECTED'}];assert gate(r)=='pass'
def test_failed_comparison_is_not_resolution():
    a={'id':'a','mission':{},'status':'completed','findings':[{'fingerprint':'one'}]};b={'id':'b','mission':{},'status':'failed','findings':[]}
    c=compare_runs(a,b);assert not c['resolved'] and len(c['not_assessed'])==1

def test_worker_model_and_effort_round_trip(client):
    m=mission(client,provider='claude',model='opus',effort='high',mode='journey',goal='Explore the homepage')
    assert (m['model'],m['effort'],m['provider'])==('opus','high','claude')
    y=client.get('/api/missions/'+m['id']+'/export').text
    back=client.post('/api/import',files={'file':('mission.yaml',y,'application/yaml')}).json()
    assert back['model']=='opus' and back['effort']=='high' and back['provider']=='claude'
    base={'name':'Bad','url':'https://example.com','goal':'Audit this','mode':'audit','provider':'none'}
    assert client.post('/api/missions',json={**base,'model':'opus --dangerous flag'}).status_code==422
    assert client.post('/api/missions',json={**base,'effort':'extreme'}).status_code==422
    assert client.post('/api/missions',json={**base,'model_max':'bad id;'}).status_code==422

def test_dynamic_model_and_its_ceiling_round_trip(client):
    m=mission(client,provider='claude',model='dynamic',model_max='claude-opus-5',mode='journey',goal='Explore the homepage')
    assert (m['model'],m['model_max'])==('dynamic','claude-opus-5')
    y=client.get('/api/missions/'+m['id']+'/export').text
    back=client.post('/api/import',files={'file':('mission.yaml',y,'application/yaml')}).json()
    assert back['model']=='dynamic' and back['model_max']=='claude-opus-5'
    a={'id':'a','mission':{**m,'model_max':''},'findings':[],'observations':[],'coverage':{}}
    b={'id':'b','mission':m,'findings':[],'observations':[],'coverage':{}}
    assert 'model_max' in compare_runs(a,b)['mismatches']

def test_seeded_presets_use_dynamic_worker_selection(client):
    workers={(m['provider'],m['model'],m['effort']) for m in client.get('/api/missions').json()}
    assert workers=={('auto','dynamic','low'),('auto','dynamic','medium')}

def test_invalid_mission_combinations():
    for kw in [{'mode':'journey','provider':'none'},{'ai_budget':0},{'pillars':[]},{'observe_seconds':60,'max_seconds':30}]:
        with pytest.raises(ValueError):Mission(name='Test',url='https://example.com',goal='Test mission',**kw)

def test_project_assignment_and_grouped_triage(client):
    p=client.post('/api/projects',json={'name':'Second project','url':'https://example.com'}).json()
    m=mission(client,project_id=p['id']);assert m['project_id']==p['id']
    for i in range(2):
        store.save('run',{'id':'group-'+str(i),'mission':m,'mission_id':m['id'],'status':'completed','gate':'warn','coverage':{},'findings':[{'id':'f'+str(i),'run_id':'group-'+str(i),'evidence_id':'step-000','fingerprint':'same','title':'Same finding','severity':'P2','verifier_status':'CONFIRMED','status':'open','owner':''}]})
    g=client.get('/api/findings?grouped=true').json();assert len(g)==1 and len(g[0]['occurrences'])==2
    assert g[0]['run_id']=='group-1',g[0]['run_id']
    assert client.patch('/api/findings/group-0/f0',json={'owner':'QA'}).status_code==200
    assert store.get('run','group-0')['findings'][0]['owner']=='QA'
    # The assignment made on the earlier run stays visible after a later run rediscovered the same finding.
    assert client.get('/api/findings?grouped=true').json()[0]['owner']=='QA'
    # One issue has one review state: closing it on one run closes it in every report that recorded it.
    done=client.patch('/api/findings/group-1/f1',json={'status':'resolved','owner':'QA'})
    assert done.status_code==200 and done.json()['synced']==1
    assert store.get('run','group-0')['findings'][0]['status']=='resolved'
    assert client.get('/api/findings?grouped=true').json()[0]['status']=='resolved'

def test_one_issue_has_one_review_state_inside_its_own_run(client):
    """A site-wide defect is recorded once per page. The score charges it once, so closing it closes every record."""
    m=mission(client)
    same=lambda i:{'id':'p'+str(i),'run_id':'pages','evidence_id':'step-00'+str(i),'fingerprint':'repeat','title':'Slow largest contentful paint','rule':'lcp','pillar':'performance','severity':'P2','classification':'defect','verifier_status':'CONFIRMED','status':'open','owner':''}
    store.save('run',{'id':'pages','mission':m,'mission_id':m['id'],'status':'completed','gate':'warn',
                      'coverage':{'performance':{'status':'evaluated'}},'findings':[same(0),same(1),same(2)]})
    assert client.patch('/api/findings/pages/p0',json={'status':'resolved','owner':'QA'}).status_code==200
    saved=store.get('run','pages')['findings']
    assert [f['status'] for f in saved]==['resolved']*3 and [f['owner'] for f in saved]==['QA']*3
    assert saved and store.get('run','pages')['scores']['performance']['score']==100

def test_review_state_skips_unfinished_runs(client):
    m=mission(client)
    for i,status in enumerate(['completed','running','completed']):
        store.save('run',{'id':'sync-'+str(i),'mission':m,'mission_id':m['id'],'status':status,'gate':'warn','coverage':{},
                          'findings':[{'id':'s'+str(i),'run_id':'sync-'+str(i),'evidence_id':'step-000','fingerprint':'shared','title':'Shared finding','pillar':'seo_aeo','severity':'P2','classification':'defect','verifier_status':'CONFIRMED','status':'open','owner':''}]})
    assert sync_findings(m['project_id'],{'shared':{'status':'resolved'}},('sync-0',))==['sync-2']
    assert store.get('run','sync-2')['findings'][0]['status']=='resolved' and store.get('run','sync-2')['scores']
    # The run that was edited directly is skipped, and a run still in progress is never rewritten.
    assert store.get('run','sync-0')['findings'][0]['status']=='open'
    assert store.get('run','sync-1')['findings'][0]['status']=='open'

def test_comparison_rejects_same_or_unfinished_run(client):
    m=mission(client);r=client.post('/api/runs',json={'mission_id':m['id']}).json()
    assert client.get('/api/compare',params={'baseline':r['id'],'candidate':r['id']}).status_code==422
    other=client.post('/api/runs',json={'mission_id':m['id']}).json()
    assert client.get('/api/compare',params={'baseline':r['id'],'candidate':other['id']}).status_code==409

def test_automatic_replay_is_bounded(client):
    m=mission(client,auto_replay=True)
    r=store.save('run',{'mission':m,'mission_id':m['id'],'status':'completed','findings':[{'severity':'P1','verifier_status':'PROBABLE'}],'replay_of':''})
    asyncio.run(service.runner.after_run(r['id']))
    updated=store.get('run',r['id']);assert updated['automatic_replay_id']
    replay=store.get('run',updated['automatic_replay_id']);assert replay['replay_of']==r['id']
    asyncio.run(service.runner.after_run(r['id']));assert len(store.all_records('run'))==2
    replay['status']='completed';replay['findings']=r['findings'];store.save('run',replay)
    asyncio.run(service.runner.after_run(replay['id']));assert len(store.all_records('run'))==2

@pytest.mark.parametrize('severity,verifier,status,expected',[
    ('P2','CONFIRMED','open',True),('P2','PROBABLE','open',True),
    ('P2','REJECTED','open',False),('P1','CONFIRMED','dismissed',False),
    ('P2','CONFIRMED','resolved',False),('P3','CONFIRMED','open',False)])
def test_replay_threshold_and_triage(client,severity,verifier,status,expected):
    m=mission(client,auto_replay=True)
    r=store.save('run',{'mission':m,'status':'completed','findings':[{'severity':severity,'verifier_status':verifier,'status':status}]})
    asyncio.run(service.runner.after_run(r['id']))
    assert bool(store.get('run',r['id']).get('automatic_replay_id')) is expected

def test_replay_uses_original_network_snapshot(client):
    m=mission(client)
    r=client.post('/api/runs',json={'mission_id':m['id']}).json()
    r['status']='completed';store.save('run',r)
    client.put('/api/networks/baseline',json={'name':'Changed','latency_ms':400})
    replay=client.post('/api/runs/'+r['id']+'/replay')
    assert replay.status_code==200
    assert replay.json()['network_snapshot']==r['network_snapshot']
    assert compare_runs(r,replay.json())['compatible']

def test_replay_error_does_not_fail_finished_parent(client):
    m=mission(client,auto_replay=True,persona_id='removed')
    r=store.save('run',{'mission':m,'status':'completed','findings':[{'severity':'P2'}]})
    asyncio.run(service.runner.after_run(r['id']))
    saved=store.get('run',r['id'])
    assert saved['status']=='completed' and 'persona' in saved['automatic_replay_error']
    assert client.post('/api/runs/'+r['id']+'/replay').status_code==422

def stopped_run(client,**kw):
    """A journey that ran out of budget: evidence recorded, goal not reached."""
    m=mission(client,**{'mode':'journey','provider':'codex','ai_budget':20,'max_steps':20,**kw})
    return store.save('run',{'mission':m,'mission_id':m['id'],'status':'blocked','mission_outcome':'budget_stop',
                             'error':'Mission did not reach success: budget_stop','evaluation_error':'AI budget ended before pillar evaluation',
                             'ai_calls':20,'observations':[{'id':'step-019','url':'https://example.com/last'}],
                             'actions':[{'step':19,'status':'executed'}],'events':[],'findings':[]})

def test_continue_adds_budget_and_keeps_the_same_run(client):
    r=stopped_run(client)
    answer=client.post('/api/runs/'+r['id']+'/continue',json={'ai_calls':20,'steps':10})
    assert answer.status_code==200,answer.text
    queued=answer.json()
    assert queued['id']==r['id'] and queued['status']=='queued' and queued['continuations']==1
    assert queued['mission']['ai_budget']==40 and queued['mission']['max_steps']==30
    # The earlier evidence and its AI usage stay; the stale verdict does not.
    assert queued['ai_calls']==20 and len(queued['observations'])==1
    assert 'evaluation_error' not in queued and not queued['error'] and 'finished_at' not in queued
    assert queued['events'][-1]['message']=='Continuing at action 21: AI budget now 40, step limit now 30'

def test_continue_repeats_the_mission_budget_when_no_amount_is_given(client):
    r=stopped_run(client)
    queued=client.post('/api/runs/'+r['id']+'/continue',json={}).json()
    assert queued['mission']['ai_budget']==40 and queued['mission']['max_steps']==40

def test_continue_stops_at_the_highest_limits_a_mission_allows(client):
    r=stopped_run(client)
    r['mission'].update(ai_budget=60,max_steps=40);store.save('run',r)
    answer=client.post('/api/runs/'+r['id']+'/continue',json={'ai_calls':10,'steps':10})
    assert answer.status_code==422 and 'highest limits' in answer.json()['detail']

@pytest.mark.parametrize('change,code,reason',[
    ({'status':'running'},409,'Wait'),
    ({'observations':[]},422,'nothing to continue'),
    ({'status':'completed','mission_outcome':'success'},200,'')])
def test_continue_refuses_what_it_cannot_resume(client,change,code,reason):
    r=stopped_run(client);r.update(change);store.save('run',r)
    answer=client.post('/api/runs/'+r['id']+'/continue',json={'ai_calls':5})
    assert answer.status_code==code,answer.text
    if reason:assert reason in answer.json()['detail']

def test_continue_refuses_a_benchmark(client):
    r=stopped_run(client,mode='benchmark',competitors=['https://rival.example'])
    answer=client.post('/api/runs/'+r['id']+'/continue',json={'ai_calls':5})
    assert answer.status_code==422 and 'benchmark' in answer.json()['detail']

def test_invalid_project_edit_leaves_mission_and_history_unchanged(client):
    m=mission(client)
    assert client.put('/api/missions/'+m['id'],json={**m,'project_id':'missing'}).status_code==404
    assert store.get('mission',m['id'])['project_id']==m['project_id']
    assert client.get('/api/missions/'+m['id']+'/versions').json()==[]

def test_active_cancel_waits_for_finalization_and_is_idempotent(client):
    m=mission(client)
    r=store.save('run',{'mission':m,'status':'running'})
    class Task:
        calls=0
        def cancelling(self):return self.calls
        def cancel(self):self.calls+=1
    task=Task();service.runner.active[r['id']]=task
    asyncio.run(service.runner.cancel(r['id']))
    asyncio.run(service.runner.cancel(r['id']))
    assert task.calls==1
    assert store.get('run',r['id'])['status']=='running'
    service.runner.active.clear()

def test_ai_usage_records_every_attempt_including_the_failed_primary():
    from engine.runner import record_call
    from engine import ai
    r={'ai_usage':[],'ai_totals':{}}
    entry,message=record_call(r,ai.usage_record('codex','','','low'),'action',2500,0,'workspace out of credits')
    # A failed attempt still spent quota; it is listed with unknown counts, never zero.
    assert entry['call']==1 and entry['step']==0 and entry['input_tokens'] is None
    assert 'AI call 1' in message and 'workspace out of credits' in message and 'n/a' in message
    ok=ai.usage_record('claude','sonnet','claude-sonnet-5','low',input_tokens=21930,cached_tokens=0,output_tokens=640)
    entry,message=record_call(r,ok,'action',18200,0)
    assert entry['call']==2 and '21,930 in / 640 out' in message and '18.2 s' in message
    totals=r['ai_totals']
    assert (totals['calls'],totals['models'],totals['cost_partial'])==(2,['claude-sonnet-5'],True)
    assert totals['est_cost_usd']==ok['est_cost_usd']==pytest.approx(0.05026)

def test_new_run_and_export_report_ai_usage(client):
    m=mission(client)
    r=client.post('/api/missions/'+m['id']+'/matrix').json()[0]
    assert r['ai_usage']==[] and r['ai_totals']=={} and r['ai_calls']==0
    report=client.get('/api/runs/'+r['id']+'/export').text
    assert '## AI usage' in report and 'No AI call was made in this run.' in report
    assert 'AI calls:' not in report


def workspace_run(m,run_id,**kw):
    return store.save('run',{'id':run_id,'mission':m,'mission_id':m['id'],'status':'completed','gate':'warn',
        'coverage':{p:{'status':'evaluated'} for p in m['pillars']},
        'findings':[{'id':run_id+'-f','run_id':run_id,'evidence_id':'step-000','fingerprint':run_id,'pillar':'functionality',
                     'title':'Broken step','severity':'P1','classification':'defect','observed':'No results','expected':'Results','recommendation':'Fix search','source':'deterministic','verifier_status':'CONFIRMED','status':'open','owner':''}],**kw})

def test_workspace_filters_state_and_findings(client):
    other=client.post('/api/projects',json={'name':'Other','url':'https://example.org','allowed_domains':['example.org']}).json()
    primary=mission(client);secondary=mission(client,project_id=other['id'],name='Secondary audit')
    workspace_run(primary,'run-primary');workspace_run(secondary,'run-secondary')
    for m,minutes in ((primary,30),(secondary,60)):client.post('/api/schedules',json={'mission_id':m['id'],'every_minutes':minutes})
    s=client.get('/api/state',params={'project':other['id']}).json()
    assert secondary['id'] in [m['id'] for m in s['missions']] and primary['id'] not in [m['id'] for m in s['missions']]
    assert [r['id'] for r in s['runs']]==['run-secondary']
    assert [x['mission_id'] for x in s['schedules']]==[secondary['id']]
    assert {p['id'] for p in s['projects']}>={'default',other['id']} and len(s['networks'])>1
    assert {f['run_id'] for f in client.get('/api/findings',params={'project':other['id']}).json()}=={'run-secondary'}
    assert {r['id'] for r in client.get('/api/state').json()['runs']}=={'run-primary','run-secondary'}

def test_run_carries_scores_and_summary_that_follow_review_decisions(client):
    m=mission(client);workspace_run(m,'scored')
    r=store.get('run','scored');r.update(scores=service.scores(r),executive_summary=service.executive_summary(r));store.save('run',r)
    before=client.get('/api/runs/scored').json()
    assert before['scores']['functionality']['score']==60 and before['scores']['overall']['scored']==5
    assert 'Open findings: 1 P1.' in before['executive_summary']['summary']
    assert client.patch('/api/findings/scored/scored-f',json={'status':'dismissed'}).status_code==200
    after=client.get('/api/runs/scored').json()
    assert after['scores']['functionality']['score']==100 and after['scores']['overall']['score']==100
    assert 'No open findings were recorded.' in after['executive_summary']['summary']
    report=client.get('/api/runs/scored/export').text
    assert '## Executive summary' in report and '## Scores' in report and 'not a field measurement' in report

def test_intro_page_is_served(client):
    from app import app
    from engine.presets import GENERIC
    r=client.get('/intro');assert r.status_code==200 and 'Product Excellence' in r.text
    # The page prints the running version, so a release cannot leave it behind.
    assert app.version in r.text and '{{version}}' not in r.text
    # It lists the presets by name; renaming one without the page fails here.
    for preset in GENERIC:assert preset['name'] in r.text,preset['name']

def test_benchmark_mission_round_trips_through_yaml(client):
    m=mission(client,name='Pricing benchmark',mode='benchmark',provider='auto',ai_budget=8,
              goal='Compare the subscription plans with the competition',
              competitors=['https://example.org','https://example.net'])
    text=client.get(f"/api/missions/{m['id']}/export").text
    assert 'example.org' in text
    back=client.post('/api/import',files={'file':('mission.yaml',text,'application/yaml')})
    assert back.status_code==200,back.text
    assert back.json()['competitors']==['https://example.org','https://example.net']

def test_benchmark_report_compares_every_site(client):
    m=mission(client,name='Home benchmark',mode='benchmark',provider='auto',ai_budget=8,
              goal='Compare the home pages',competitors=['https://example.org','https://example.net'])
    workspace_run(m,'run-benchmark',mission_outcome='success',
        sites=[{'url':'https://example.com','outcome':'success','reason':'Plans were read','evidence_id':'step-000',
                'metrics':{'lcp':2100.0,'cls':0.02,'inp':None,'ttfb_ms':310.0},'axe_violations':4},
               {'url':'https://example.org','outcome':'blocked','reason':'The page did not load','evidence_id':'step-003',
                'metrics':{'lcp':None,'cls':None,'inp':None,'ttfb_ms':None},'axe_violations':None},
               {'url':'https://example.net','outcome':'not_visited','reason':'The time or AI-call budget ended before this site',
                'evidence_id':None,'metrics':{},'axe_violations':None}],
        benchmark=[{'url':'https://example.com','observed':'Three plans','strengths':'Prices are stated','weaknesses':'Renewal is not mentioned','rank':1}])
    report=client.get('/api/runs/run-benchmark/export').text
    assert '## Benchmark' in report
    for site in ('https://example.com','https://example.org','https://example.net'):assert site in report
    assert 'not_visited' in report and 'Renewal is not mentioned' in report
    # A competitor that never loaded must read as unmeasured, never as a zero.
    assert 'Not measured' in report

def fake_worker(monkeypatch,logged_in=('codex',),suggestions=None):
    """Record what the suggestion call asked for, without running a CLI."""
    from engine import ai,pricing,suggest as goal_suggest
    seen={}
    async def health():
        return {p:{'installed':True,'logged_in':p in logged_in,'subscription':'','models':[]} for p in ('codex','claude')}
    async def call(provider,prompt,schema,image=None,timeout=100,model='',effort='low',codex_account=''):
        seen.update(provider=provider,prompt=prompt,schema=schema,timeout=timeout,model=model,effort=effort,codex_account=codex_account)
        return {'suggestions':suggestions if suggestions is not None else [
            {'title':'Pricing - renewal before payment','why':'Shows what a customer still does not know before paying.',
             'caveat':'','goal':'Find the plans and read the renewal terms. Stop before any payment control.',
             'mode':'journey','pillars':['cro','functionality']},
            {'title':'Pricing against the competition','why':'Shows whether the price reads clearly beside rivals.',
             'caveat':'needs competitor URLs','goal':'Read the plans here and on each competitor, then compare.',
             'mode':'benchmark','pillars':['cro','made-up-pillar']},
            {'title':'Renewal terms survive a reload','why':'Shows whether the terms are there on the second look.',
             'caveat':'','goal':'Open the plans, reload the page and read the renewal terms again.',
             'mode':'journey','pillars':['cro'],'shape':'scenario','journey':'Read the terms, reload, read again.',
             'steps':[{'goal':'Open the plans'},{'check':{'text':'renews','within':10}}]},
            {'title':'Renewal terms on a slow link','why':'Shows whether the terms arrive on a shaped connection.',
             'caveat':'','goal':'Shape the connection, open the plans and read the renewal terms.',
             'mode':'journey','pillars':['cro'],'shape':'scenario','journey':'Slow the link, then read the terms.',
             'steps':[{'event':{'delay_ms':400}},{'goal':'Open the plans'}]}]},ai.usage_record(
                 'codex',model,'gpt-5.6-terra',effort,input_tokens=800,output_tokens=200)
    monkeypatch.setattr(goal_suggest.ai,'health',health);monkeypatch.setattr(goal_suggest.ai,'call',call)
    return seen

def test_goal_suggestions_use_the_house_voice_and_the_standard_model(client,monkeypatch):
    seen=fake_worker(monkeypatch)
    from engine import pricing
    r=client.post('/api/missions/suggest',json={'project_id':'default','goal':'check if the pricing page explains renewal',
                                               'url':'https://example.com/pricing','mode':'audit'})
    assert r.status_code==200,r.text
    body=r.json();four=body['suggestions']
    # Four missions, two of each shape, and every one complete.
    assert len(four)==4 and four[0]['mode']=='journey'
    assert [s['shape'] for s in four].count('goal')==2 and [s['shape'] for s in four].count('scenario')==2
    # A benchmark without competitor URLs cannot be saved, so it is offered as the journey it is.
    assert four[1]['mode']=='journey' and four[1]['caveat']=='needs competitor URLs'
    assert four[1]['pillars']==['cro'] and body['usage']['provider']=='codex'
    # The subscription's standard model, at low effort so the form answers quickly.
    assert seen['model']==pricing.LADDER['codex'][1] and seen['effort']=='low'
    assert seen['codex_account']=='default'
    # The prompt carries the user's words, the workspace facts and the shared goal voice.
    assert 'check if the pricing page explains renewal' in seen['prompt']
    assert 'example.com' in seen['prompt'] and 'Three goals to imitate' in seen['prompt']
    assert '{{password}}' in seen['prompt']
    assert 'Home page · five-pillar audit' in seen['prompt']
    # The prompt asks for the mix and no longer talks the worker out of a scenario.
    assert 'Return four missions' in seen['prompt'] and 'Do not force a scenario' not in seen['prompt']

def test_goal_suggestions_need_a_signed_in_worker(client,monkeypatch):
    fake_worker(monkeypatch,logged_in=())
    r=client.post('/api/missions/suggest',json={'project_id':'default','goal':'check the pricing page'})
    assert r.status_code==422 and 'Settings' in r.json()['detail']

def test_goal_suggestions_refuse_an_unknown_workspace(client,monkeypatch):
    fake_worker(monkeypatch)
    r=client.post('/api/missions/suggest',json={'project_id':'nope','goal':'check the pricing page'})
    assert r.status_code==404

# --- Whole missions: a goal or a complete scenario, and revising one ---------

SCENARIO={'title':'Downloads - survive going offline','why':'Shows whether a saved title still plays with no network.',
          'caveat':'','goal':'Open the downloads list, start the saved title and keep it playing while the network '
          'drops away and comes back. Report anything that stops playback. Nothing is purchased or deleted.',
          'mode':'audit','pillars':['ux_ui'],'shape':'scenario','journey':'Play a downloaded title offline.',
          'steps':[{'name':'Open downloads','goal':'Open the downloads list and start <Saved title>','until':None,
                    'manual':'','ask':'','timeout':None,'event':None,'check':None,'hold':None},
                   {'name':'Sign in','goal':'','until':None,'manual':'Sign in as the second account','ask':'one-time code',
                    'timeout':120,'event':None,'check':None,'hold':None},
                   {'name':'Go offline','goal':'','until':None,'manual':'','ask':'','timeout':None,
                    'event':{'network':'offline','speed':None,'delay_ms':None,'kill':None,'home':None,'back':None,
                             'wait':None,'relaunch':None,'deep_link':None,'open_notification':None},
                    'check':None,'hold':None},
                   {'name':'Still playing','goal':'','until':None,'manual':'','ask':'','timeout':None,'event':None,
                    'check':None,'hold':{'text':'','text_absent':'','screen':None,'playing':True,'notification':None,
                                         'no_crash':None,'policy':'confirmed','severity':'P1','required':None,'for':20}}]}
GOAL_ONLY={'title':'Pricing - renewal before payment','why':'Shows what a customer still does not know before paying.',
           'caveat':'','goal':'Find the plans and read the renewal terms. Stop before any payment control.',
           'mode':'journey','pillars':['cro'],'shape':'goal','journey':'','steps':[]}

def web_target(project_id='default',url='https://shop.example.net',name='Shop'):
    return store.save('target',{'project_id':project_id,'type':'web','name':name,'url':url,
                                'allowed_domains':['shop.example.net'],'package':'','builds':[],'visibility':'team'})

def android_target(project_id='default'):
    build={'sha256':'a'*64,'version_name':'9.1.0','version_code':91,'min_sdk':26,'target_sdk':34,
           'launch_activity':'.Main','abis':['arm64-v8a'],'size':1024,'uploaded_at':'2026-01-01T00:00:00Z','archived':False}
    return store.save('target',{'project_id':project_id,'type':'android','name':'Player','url':'',
                                'allowed_domains':[],'package':'com.example.player','builds':[build],'visibility':'team'})

def test_a_scenario_suggestion_arrives_complete_and_runnable(client,monkeypatch):
    seen=fake_worker(monkeypatch,suggestions=[SCENARIO,GOAL_ONLY])
    target=web_target()
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':target['id'],
                                               'goal':'does a download still play with no network'})
    assert r.status_code==200,r.text
    scenario,goal=r.json()['suggestions']
    assert scenario['shape']=='scenario' and goal['shape']=='goal' and goal['steps']==[]
    assert scenario['journey']=='Play a downloaded title offline.'
    # A scenario verdict is recorded under Functionality and runs as a journey, whatever the worker said.
    assert scenario['mode']=='journey' and 'functionality' in scenario['pillars'] and 'ux_ui' in scenario['pillars']
    # The steps arrive in order, in the spelling the rows and the runner use.
    kinds=[next(k for k in ('goal','manual','event','check','hold') if s.get(k)) for s in scenario['steps']]
    assert kinds==['goal','manual','event','hold']
    assert scenario['steps'][1]['ask']=='one-time code' and 'password' not in json.dumps(scenario['steps'])
    # Nulls the strict schema forced out of the worker are gone; a real false or zero would not be.
    assert 'until' not in scenario['steps'][0] and scenario['steps'][3]['hold']['playing'] is True
    assert scenario['steps'][3]['hold']['for']==20
    # The mission this workspace holds is the one asked about, not another website in the same workspace.
    assert 'Website: https://shop.example.net' in seen['prompt']
    assert 'Start URL for this mission: https://shop.example.net' in seen['prompt']
    assert 'Website: https://example.com' not in seen['prompt']
    assert 'Rules for steps' in seen['prompt'] and '{{password}}' in seen['prompt']
    assert seen['timeout']==120

def test_a_scenario_suggestion_works_on_android_too(client,monkeypatch):
    seen=fake_worker(monkeypatch,suggestions=[SCENARIO,GOAL_ONLY])
    target=android_target()
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':target['id'],
                                               'goal':'does a download still play with no network'})
    assert r.status_code==200,r.text
    scenario=r.json()['suggestions'][0]
    assert scenario['shape']=='scenario' and len(scenario['steps'])==4
    assert 'seo_aeo' not in scenario['pillars']
    assert 'com.example.player' in seen['prompt'] and '9.1.0' in seen['prompt']
    # An operator may still be asked to sign in during the run; only stored credentials are refused.
    assert 'stop before sign-in' not in seen['prompt']
    assert 'stored credentials' in seen['prompt']

def test_an_android_suggestion_needs_a_build(client,monkeypatch):
    fake_worker(monkeypatch,suggestions=[SCENARIO,GOAL_ONLY])
    target=store.save('target',{'project_id':'default','type':'android','name':'Player','url':'','allowed_domains':[],
                                'package':'com.example.player','builds':[],'visibility':'team'})
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':target['id'],'goal':'play something'})
    assert r.status_code==422 and 'build' in r.json()['detail']

def broken(**changes):
    return {**SCENARIO,**changes}

@pytest.mark.parametrize('bad,why',[
    (broken(steps=[{'goal':'Open the downloads list','check':{'text':'Now playing','within':10}}]),'two kinds in one step'),
    (broken(steps=[SCENARIO['steps'][0],{'check':{'text':'a','playing':True,'within':10}}]),'one valid step and one not'),
    (broken(steps=[]),'a scenario with no steps'),
    (broken(steps=[dict(SCENARIO['steps'][0])]*41),'more than forty steps'),
    (broken(steps=['not a step']),'a step that is not an object'),
    (broken(steps={'goal':'x'}),'steps that are not a list'),
    ({**GOAL_ONLY,'steps':[SCENARIO['steps'][0]]},'a goal carrying steps'),
])
def test_a_broken_candidate_is_rejected_whole(client,monkeypatch,bad,why):
    """A partial scenario would hand the person a mission missing its prerequisite and call it ready.

    The broken one costs its own card and is named; the missions beside it still arrive.
    """
    fake_worker(monkeypatch,suggestions=[bad,GOAL_ONLY])
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],'goal':'try it'})
    assert r.status_code==200,why
    body=r.json()
    assert [s['title'] for s in body['suggestions']]==[GOAL_ONLY['title']],why
    assert body['rejected'] and body['rejected'][0].startswith('Mission 1:'),why
    # Nothing truncated reached a card: no returned scenario is a shortened version of the broken input.
    assert not [s for s in body['suggestions'] if s['shape']=='scenario'],why

def test_extra_candidates_are_accepted_and_a_thin_answer_still_answers(client,monkeypatch):
    fake_worker(monkeypatch,suggestions=[GOAL_ONLY,SCENARIO,GOAL_ONLY,SCENARIO,GOAL_ONLY,SCENARIO])
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],'goal':'try it'})
    assert r.status_code==200
    shapes=[s['shape'] for s in r.json()['suggestions']]
    assert len(shapes)==4 and shapes.count('goal')==2 and shapes.count('scenario')==2
    # One usable mission is still an answer, not a minute of waiting thrown away.
    fake_worker(monkeypatch,suggestions=[GOAL_ONLY])
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],'goal':'try it'})
    assert r.status_code==200 and len(r.json()['suggestions'])==1

def test_no_usable_candidate_is_the_only_failure_left(client,monkeypatch):
    fake_worker(monkeypatch,suggestions=[{**GOAL_ONLY,'goal':''},'not a mission'])
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],'goal':'try it'})
    assert r.status_code==502 and 'no usable mission' in r.json()['detail']

def test_a_malformed_response_container_fails_in_a_controlled_way(client,monkeypatch):
    from engine import ai,suggest as goal_suggest
    async def health():return {p:{'installed':True,'logged_in':p=='codex','subscription':'','models':[]} for p in ('codex','claude')}
    async def call(*a,**kw):return {'suggestions':'two of them'},ai.usage_record('codex','m','m','low',input_tokens=1,output_tokens=1)
    monkeypatch.setattr(goal_suggest.ai,'health',health);monkeypatch.setattr(goal_suggest.ai,'call',call)
    r=client.post('/api/missions/suggest',json={'project_id':'default','goal':'try it'})
    assert r.status_code==502 and 'no list of missions' in r.json()['detail']

def test_a_revision_returns_one_whole_mission(client,monkeypatch):
    seen=fake_worker(monkeypatch,suggestions=[{**SCENARIO,'title':'Downloads - survive a relaunch too'}])
    current={'name':'Downloads - survive going offline','goal':'Play the saved title with the network away.',
             'mode':'journey','pillars':['functionality','ux_ui'],'steps':[{'goal':'Open the downloads list'}]}
    r=client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],
                                               'goal':'kill the app and relaunch it before the check','revise':True,'current':current})
    assert r.status_code==200,r.text
    body=r.json()['suggestions']
    assert len(body)==1 and body[0]['title']=='Downloads - survive a relaunch too'
    # The mission being changed travels as data, distinct from the instruction in the person's words.
    assert 'Open the downloads list' in seen['prompt'] and 'kill the app and relaunch it' in seen['prompt']
    assert '"mode": "journey"' in seen['prompt'] and 'ux_ui' in seen['prompt']
    assert 'exactly one mission' in seen['prompt']

def test_a_revision_needs_the_mission_it_is_changing(client,monkeypatch):
    fake_worker(monkeypatch,suggestions=[GOAL_ONLY])
    r=client.post('/api/missions/suggest',json={'project_id':'default','goal':'make it shorter','revise':True})
    assert r.status_code==422 and 'needs the mission' in r.text
    r=client.post('/api/missions/suggest',json={'project_id':'default','goal':'an idea','current':{'goal':'x'}})
    assert r.status_code==422 and 'Only a revision' in r.text

def test_an_invalid_revision_never_reaches_the_worker(client,monkeypatch):
    seen=fake_worker(monkeypatch,suggestions=[GOAL_ONLY])
    body={'project_id':'default','goal':'make it shorter','revise':True,
          'current':{'goal':'x','steps':[{'goal':'Open the list','check':{'text':'a','within':10}}]}}
    assert client.post('/api/missions/suggest',json=body).status_code==422
    body['current']={'goal':'x','steps':[{'goal':'Open the downloads list'}]*41}
    assert client.post('/api/missions/suggest',json=body).status_code==422
    body['current']={'goal':'x','mode':'invented'}
    assert client.post('/api/missions/suggest',json=body).status_code==422
    assert client.post('/api/missions/suggest',json={'project_id':'default','goal':'hi','revise':True,
                                                    'current':{'goal':'x'}}).status_code==422
    assert not seen,'A malformed request still asked the worker'

def test_the_expanded_schema_stays_inside_the_strict_limitations(client,monkeypatch):
    seen=fake_worker(monkeypatch,suggestions=[SCENARIO,GOAL_ONLY])
    client.post('/api/missions/suggest',json={'project_id':'default','target_id':web_target()['id'],'goal':'try it'})
    schema=seen['schema'];item=schema['properties']['suggestions']['items']
    from engine.suggest import UNSUPPORTED
    steps=json.dumps({'steps':item['properties']['steps'],'defs':schema['$defs']})
    for keyword in UNSUPPORTED:assert f'"{keyword}":' not in steps,f'{keyword} survives in the strict schema'
    # Every reference the step schema carries resolves from the root of the response schema.
    for ref in set(re.findall(r'"#/\$defs/([A-Za-z]+)"',json.dumps(schema))):assert ref in schema['$defs'],f'{ref} does not resolve'
    assert set(item['required'])=={'title','why','caveat','goal','journey','mode','shape','pillars','steps'}
    assert item['additionalProperties'] is False

# --- routes a scenario switches to -------------------------------------------

def egress(client,name='Route A',server='http://127.0.0.1:9001'):
    r=client.post('/api/egress',json={'name':name,'server':server,'username':'u','password':'SECRET_SENTINEL'})
    assert r.status_code==200,r.text;return r.json()

def routed(client,*route_ids,**kw):
    steps=[{'name':'Switch','event':{'route':id}} for id in route_ids]
    return mission(client,pillars=['functionality'],scenario=steps,**kw)

def test_a_run_snapshots_every_route_its_scenario_switches_to(client):
    a=egress(client);b=egress(client,'Route B','http://127.0.0.1:9002')
    m=routed(client,a['id'],b['id'],'direct',egress_id=a['id'])
    r=client.post('/api/runs',json={'mission_id':m['id']})
    assert r.status_code==200,r.text
    # The starting route and each switched-to route, once each, without their secrets.
    assert r.json()['routes']==[{'id':a['id'],'name':'Route A','server':'http://127.0.0.1:9001'},
                               {'id':b['id'],'name':'Route B','server':'http://127.0.0.1:9002'}]
    assert 'SECRET_SENTINEL' not in r.text
    # A mission with no route steps keeps its native proxy path and snapshots nothing.
    plain=mission(client,egress_id=a['id'])
    assert client.post('/api/runs',json={'mission_id':plain['id']}).json()['routes']==[]

def test_a_route_a_run_cannot_take_is_refused_before_it_is_queued(client):
    a=egress(client);socks=egress(client,'Socks','socks5://127.0.0.1:1080')
    gone=egress(client,'Deleted');assert client.delete('/api/egress/'+gone['id']).status_code==200
    for id,message in ((gone['id'],'does not exist'),(socks['id'],'HTTP or HTTPS')):
        m=routed(client,id)
        answer=client.post('/api/runs',json={'mission_id':m['id']})
        assert answer.status_code==422 and message in answer.json()['detail'],answer.text
    # The record survives its credentials being removed from this machine; the run does not.
    (store.DATA/'secrets'/f"{a['id']}.json").unlink()
    m=routed(client,a['id'])
    answer=client.post('/api/runs',json={'mission_id':m['id']})
    assert answer.status_code==422 and 'Configure proxy credentials' in answer.json()['detail']
    assert not store.all_records('run')

def test_route_switching_needs_a_browser_on_this_machine(client):
    a=egress(client)
    m=routed(client,a['id'])
    answer=client.post('/api/runs',json={'mission_id':m['id'],'network':'netem-poor'})
    assert answer.status_code==422 and 'netem' in answer.json()['detail']

def test_android_route_steps_are_refused_until_android_can_route(client):
    target=android_target()
    # Asking for direct is still asking for a route: it needs the same relay Android has no way to use.
    for route in ('a'*32,'direct'):
        m=mission(client,platform='android',target_id=target['id'],build='a'*64,url='',pillars=['functionality'],
                  scenario=[{'name':'Switch','event':{'route':route}}])
        answer=client.post('/api/runs',json={'mission_id':m['id']})
        assert answer.status_code==422 and 'not available on Android' in answer.json()['detail']

def test_a_replay_matches_on_the_routes_it_used_not_on_what_it_observed():
    a={'id':'a','mission':{},'status':'completed','findings':[],'observations':[],'coverage':{},
       'routes':[{'id':'r1','name':'Route A','server':'http://127.0.0.1:9001'}],
       'route_checks':[{'status':'verified','observed_ip':'203.0.113.7','generation':1}]}
    b={**a,'id':'b','routes':[{'id':'r1','name':'Renamed since','server':'http://127.0.0.1:9001'}],
       'route_checks':[{'status':'verified','observed_ip':'198.51.100.4','generation':1}]}
    # A rotated exit address and a re-typed label are not new conditions.
    assert compare_runs(a,b)['compatible']
    moved={**b,'routes':[{'id':'r1','name':'Route A','server':'http://127.0.0.1:9999'}]}
    assert 'routes' in compare_runs(a,moved)['mismatches']
    swapped={**b,'routes':[{'id':'r2','name':'Route A','server':'http://127.0.0.1:9001'}]}
    assert 'routes' in compare_runs(a,swapped)['mismatches']

def test_an_unverified_route_assesses_nothing_as_resolved():
    a={'id':'a','mission':{},'status':'completed','coverage':{},'observations':[],
       'routes':[{'id':'r1','server':'http://127.0.0.1:9001'}],'route_checks':[{'status':'verified'}],
       'findings':[{'fingerprint':'one','source':'engine'}]}
    b={**a,'id':'b','findings':[]}
    assert compare_runs(a,b)['resolved'] and not compare_runs(a,b)['not_assessed']
    # The same run, unable to establish the route it switched to, resolves nothing.
    for unverified in ({'status':'unavailable'},):
        assert not compare_runs(a,{**b,'route_checks':[unverified]})['resolved']
    # A run configured with routes that recorded no check at all never verified them either.
    assert not compare_runs(a,{**b,'route_checks':[]})['resolved']
