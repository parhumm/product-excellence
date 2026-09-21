import asyncio, copy, json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from engine import store, hub
import hub as server

PASSWORD='test workspace password'
ADMIN='test administrator password'
HEADERS={'X-PEX-Request':'1'}

@pytest.fixture
def hub_client(monkeypatch,tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'ARTIFACTS',tmp_path/'artifacts');store.ARTIFACTS.mkdir()
    monkeypatch.setenv('PEX_HUB_ADMIN_PASSWORD',ADMIN);server.attempts.clear();hub.close()
    with TestClient(server.app,headers=HEADERS) as c:yield c
    hub.close();engine.dispose()

def workspace(c,name='fixture',seed=True):
    r=c.post('/hub/admin/workspaces',auth=('admin',ADMIN),json={'name':name,'url':'https://example.com','allowed_domains':['example.com'],'username':name,'password':PASSWORD,'seed':seed})
    assert r.status_code==200,r.text
    return r.json()

def mission(c,p,name='Mission'):
    v={'id':'m-'+p['id'],'project_id':p['id'],'name':name,'goal':'Audit the page','url':'https://example.com','provider':'none','mode':'audit','_revision':0}
    r=c.put('/hub/records/mission/'+v['id'],auth=(p['username'],PASSWORD),json=v)
    assert r.status_code==200,r.text
    return r.json()

def run_record(p,m,id='run-one'):
    return {'id':id,'project_id':p['id'],'mission_id':m['id'],'mission':store.clean(m),'origin':'machine-a','status':'queued','observations':[],'actions':[],'events':[],'findings':[],'http':[],'console':[],'_revision':0}

def test_isolation_versions_conflict_and_admin(hub_client):
    c=hub_client;a=workspace(c);b=workspace(c,'second');auth=(a['username'],PASSWORD)
    assert len(c.get('/hub/records/mission',auth=auth).json())==10
    m=mission(c,a)
    assert c.get('/hub/records/mission/'+m['id'],auth=(b['username'],PASSWORD)).status_code==404
    assert c.get('/hub/records/mission/'+m['id'],auth=(a['username'],'wrong')).status_code==401
    updated=c.put('/hub/records/mission/'+m['id'],auth=auth,json=m|{'name':'Changed'})
    assert updated.status_code==200,updated.text
    assert c.put('/hub/records/mission/'+m['id'],auth=auth,json=m).status_code==409
    versions=c.get('/hub/records/mission_version',auth=auth).json();assert len(versions)==1
    assert versions[0]['snapshot']['name']=='Mission'
    assert c.put('/hub/records/mission/'+m['id'],auth=auth,json=m|{'id':'other'}).status_code==422
    assert c.put('/hub/records/mission/'+m['id'],auth=auth,json=m|{'project_id':b['id']}).status_code==403
    assert c.put('/hub/records/mission/'+m['id'],auth=auth,json=updated.json()|{'login_password':'secret'}).status_code==422
    assert c.post('/hub/admin/workspaces',auth=('admin',ADMIN),json={'name':'Duplicate','url':'https://example.com','username':a['username'],'password':PASSWORD}).status_code==409
    assert len(c.get('/hub/admin/workspaces',auth=('admin',ADMIN)).json())==2
    r=c.put('/hub/admin/workspaces/'+a['id']+'/login',auth=('admin',ADMIN),json={'username':'renamed','password':'new workspace password'})
    assert r.status_code==200
    assert c.get('/hub/me',auth=auth).status_code==401
    assert c.get('/hub/me',auth=('renamed','new workspace password')).status_code==200
    assert 'password_hash' not in c.get('/hub/admin/workspaces',auth=('admin',ADMIN)).text

def test_run_transition_artifacts_and_deletion(hub_client,tmp_path):
    c=hub_client;p=workspace(c);other=workspace(c,'other');m=mission(c,p);auth=(p['username'],PASSWORD)
    r=c.put('/hub/records/run/run-one',auth=auth,json=run_record(p,m)).json()
    assert c.put('/hub/records/run/run-one',auth=auth,json=r|{'status':'running'}).status_code==409
    started=c.post('/hub/runs/run-one/start',auth=auth,json={'revision':r['_revision'],'origin':'machine-a'})
    assert started.status_code==200,started.text
    assert c.post('/hub/runs/run-one/cancel',auth=auth,json={'revision':r['_revision']}).status_code==409
    r=started.json();r.update(status='completed',video='/api/runs/run-one/artifacts/video.webm')
    assert c.put('/hub/records/run/run-one',auth=auth,json=r).status_code==409
    uploaded=c.put('/hub/artifacts/run-one/video.webm',auth=auth,content=b'video')
    assert uploaded.status_code==200,uploaded.text
    assert c.put('/hub/artifacts/run-one/video.webm',auth=auth,content=b'changed').status_code==409
    assert c.get('/hub/artifacts/run-one/video.webm',auth=(other['username'],PASSWORD)).status_code==404
    r['_artifacts']={'video.webm':uploaded.json()}
    final=c.put('/hub/records/run/run-one',auth=auth,json=r)
    assert final.status_code==200,final.text
    assert c.get('/hub/artifacts/run-one/run.json',auth=auth).json()['status']=='completed'
    assert c.get('/hub/artifacts/run-one/video.webm',auth=auth,headers={'Range':'bytes=0-1'}).status_code==206
    with pytest.raises(hub.HubError):hub.file_path(store.ARTIFACTS,'run-one','..')
    link=store.ARTIFACTS/'run-one'/'escape';link.symlink_to(tmp_path)
    with pytest.raises(hub.HubError):hub.file_path(store.ARTIFACTS,'run-one','escape')
    s={'id':'schedule-one','project_id':p['id'],'mission_id':m['id'],'origin':'machine-a','enabled':True,'every_minutes':5,'next_at':store.now(),'_revision':0}
    assert c.put('/hub/records/schedule/schedule-one',auth=auth,json=s).status_code==200
    assert c.delete('/hub/records/mission/'+m['id'],auth=auth,params={'revision':m['_revision']}).status_code==200
    assert c.get('/hub/records/schedule',auth=auth).json()==[]
    assert c.get('/hub/records/run/run-one',auth=auth).status_code==200

def test_boundary_limits(hub_client,monkeypatch):
    c=hub_client;p=workspace(c)
    assert c.post('/hub/admin/workspaces',auth=('admin',ADMIN),headers={'X-PEX-Request':''},json={}).status_code==403
    assert c.post('/hub/admin/workspaces',auth=('admin',ADMIN),headers={'Origin':'https://hostile.example'},json={}).status_code==403
    monkeypatch.setattr(server,'JSON_LIMIT',10)
    assert c.post('/hub/admin/workspaces',content=b'x'*11).status_code==413
    for _ in range(120):c.get('/hub/me',auth=('missing','wrong'))
    assert c.get('/hub/me',auth=('missing','wrong')).status_code==429
    before=len(server.attempts)
    for n in range(20):assert c.get('/hub/me',auth=('new-'+str(n),'wrong')).status_code==429
    assert len(server.attempts)==before
    for url in ('http://example.com','https://user:password@example.com','https://example.com/path'):
        with pytest.raises(hub.HubError):hub.normalize_url(url)

def test_migration_legacy_backfill(monkeypatch,tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'old.db'))
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'DATA',tmp_path)
    monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False))
    values=[('default','project',{'id':'default'}),('m','mission',{'id':'m'}),('s','schedule',{'id':'s','mission_id':'m'}),('v','mission_version',{'id':'v','mission_id':'m','snapshot':{'project_id':'default'}})]
    with engine.begin() as c:
        c.execute(text('CREATE TABLE records (id VARCHAR PRIMARY KEY, kind VARCHAR NOT NULL, payload JSON NOT NULL)'))
        for id,kind,value in values:c.execute(text('INSERT INTO records VALUES (:id,:kind,:payload)'),{'id':id,'kind':kind,'payload':json.dumps(value)})
    store.init();store.init()
    assert {'workspace','revision'}<={c['name'] for c in inspect(engine).get_columns('records')}
    assert len(store.all_records('schedule','default',local=True))==1
    assert store.get('mission_version','v',local=True)['project_id']=='default'
    engine.dispose()

def test_client_publication_recovery(hub_client,monkeypatch):
    c=hub_client;p=workspace(c);m=mission(c,p)
    hub.configure({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}})
    monkeypatch.setattr(hub,'_client',c)
    r=hub.save('run',run_record(p,m));r=hub.transition(r,'start') if r['origin']==hub.origin() else c.post('/hub/runs/run-one/start',auth=(p['username'],PASSWORD),json={'revision':r['_revision'],'origin':'machine-a'}).json()
    folder=store.ARTIFACTS/r['id'];folder.mkdir();(folder/'s.png').write_bytes(b'png')
    r.update(status='completed',observations=[{'screenshot':'/api/runs/run-one/artifacts/s.png'}])
    original=hub.put_artifact
    def fail(*a,**kw):raise hub.HubError(502,'offline')
    monkeypatch.setattr(hub,'put_artifact',fail)
    with pytest.raises(hub.HubError):hub.publish(r)
    assert len(hub.pending())==1
    assert hub.get('run',r['id'],p['id'])['status']=='running'
    monkeypatch.setattr(hub,'put_artifact',original)
    hub.retry_pending()
    assert not hub.pending()
    assert hub.get('run',r['id'],p['id'])['status']=='completed'
    monkeypatch.setattr(hub,'_client',None)

@pytest.mark.asyncio
async def test_io_drains_cancelled_write():
    events=[]
    def slow():time.sleep(.08);events.append('committed')
    task=asyncio.create_task(hub.io(slow));await asyncio.sleep(.01);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert events==['committed']


def test_lost_response_reconciliation_never_overwrites_newer_edit(hub_client,monkeypatch):
    c=hub_client;p=workspace(c);m=mission(c,p)
    hub.configure({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}});monkeypatch.setattr(hub,'_client',c)
    request=hub.request;lost=[]
    def response_lost(method,path,login,**kw):
        result=request(method,path,login,**kw)
        if method=='PUT' and not lost:lost.append(True);raise hub.HubError(502,'Response lost after commit')
        return result
    monkeypatch.setattr(hub,'request',response_lost)
    r=hub.save('run',run_record(p,m));assert r['_revision']==1
    monkeypatch.setattr(hub,'request',request);lost.clear()
    def intervening_edit(method,path,login,**kw):
        result=request(method,path,login,**kw)
        if method=='PUT' and not lost:
            lost.append(True)
            request('PUT',path,login,json=result|{'name':'Teammate edit'})
            raise hub.HubError(502,'Response lost after another edit')
        return result
    monkeypatch.setattr(hub,'request',intervening_edit)
    with pytest.raises(hub.HubError,match='Reload'):hub.save('mission',m|{'name':'My edit'})
    assert hub.get('mission',m['id'],p['id'])['name']=='Teammate edit'
    monkeypatch.setattr(hub,'_client',None)

@pytest.mark.asyncio
async def test_recovery_respects_ownership_and_outage_keeps_consumer(hub_client,monkeypatch):
    from engine.runner import Runner
    c=hub_client;p=workspace(c);m=mission(c,p)
    hub.configure({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}});monkeypatch.setattr(hub,'_client',c)
    for id,origin in [('mine',hub.origin()),('theirs','other-machine')]:hub.save('run',run_record(p,m,id)|{'origin':origin})
    legacy=run_record(p,m,'unowned');legacy.pop('origin');store.save('run',legacy,local=True)
    worker=Runner();await worker.recover()
    assert hub.get('run','mine',p['id'])['status']=='interrupted'
    assert hub.get('run','theirs',p['id'])['status']=='queued'
    assert hub.get('run','unowned',p['id'])['status']=='queued'
    def offline(*args,**kwargs):raise hub.HubError(502,'offline')
    monkeypatch.setattr(hub,'all_records',offline)
    worker=Runner();worker.start();await worker.recovery
    assert not worker.task.done() and not worker.ready
    await worker.close();monkeypatch.setattr(hub,'_client',None)

def test_console_is_public_landing_private_data_and_read_only(hub_client):
    """The landing page is public; the console shows one workspace and refuses every write."""
    c=hub_client;a=workspace(c);b=workspace(c,'second');auth=(a['username'],PASSWORD);other=(b['username'],PASSWORD)
    landing=c.get('/')
    assert landing.status_code==200 and 'Product Excellence' in landing.text
    assert server.app.version in landing.text and '{{version}}' not in landing.text
    for path in ('/console','/api/state','/api/findings','/api/health'):
        assert c.get(path).status_code==401,path
        assert 'Basic' in c.get(path).headers.get('www-authenticate','')
    assert c.get('/console',auth=auth).status_code==200
    assert c.get('/admin',auth=auth).status_code==403
    assert c.get('/admin',auth=('admin',ADMIN)).status_code==200
    assert c.get('/console',auth=('admin',ADMIN)).status_code==403

    m=mission(c,a);r=run_record(a,m)
    assert c.put('/hub/records/run/'+r['id'],auth=auth,json=r).status_code==200
    state=c.get('/api/state',auth=auth).json()
    assert [p['id'] for p in state['projects']]==[a['id']]
    assert state['hub']['mode']=='server' and state['hub']['workspace']==a['id']
    assert {x['id'] for x in state['missions']}=={x['id'] for x in c.get('/api/missions',auth=auth).json()}
    assert [x['id'] for x in state['runs']]==[r['id']] and 'observations' not in state['runs'][0]
    assert c.get('/api/health',auth=auth).json()['mode']=='server'

    # A workspace sees only its own records, and the console never offers a write route.
    assert c.get('/api/runs/'+r['id'],auth=auth).status_code==200
    assert c.get('/api/runs/'+r['id'],auth=other).status_code==404
    assert c.get('/api/state',auth=other).json()['runs']==[]
    assert c.get('/api/missions/'+m['id']+'/versions',auth=other).status_code==404
    assert c.get('/api/findings',auth=auth).json()==[]
    for method,path in [('post','/api/runs'),('post','/api/missions'),('patch','/api/findings/'+r['id']+'/x'),('delete','/api/missions/'+m['id'])]:
        assert c.request(method.upper(),path,auth=auth).status_code in (404,405),f'{method} {path} must not exist'

    # Basic authentication has no session, so the console signs out with a 401 in the same realm.
    signed_out=c.get('/logout')
    assert signed_out.status_code==401 and 'Basic' in signed_out.headers.get('www-authenticate','')

def test_unreachable_server_serves_the_last_copy_to_a_page_but_never_to_publication(hub_client,monkeypatch):
    """A browser read falls back to the copy it already had; background writes still fail loudly."""
    c=hub_client;p=workspace(c);m=mission(c,p)
    hub.configure({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}})
    monkeypatch.setattr(hub,'_client',c)
    live=hub.all_records('mission',p['id']);one=hub.get('mission',m['id'],p['id'])
    assert any(x['id']==m['id'] for x in live) and hub.status()['outage'] is None

    class Down:
        def request(self,*a,**kw):raise httpx.ConnectError('down')
        def stream(self,*a,**kw):raise httpx.ConnectError('down')
        def close(self):pass
    monkeypatch.setattr(hub,'_client',Down())
    token=hub.PAGE_READ.set([])
    try:
        assert hub.all_records('mission',p['id'])==live
        assert hub.get('mission',m['id'],p['id'])==one
        outage=hub.status()['outage']
        assert outage['detail']==hub.UNREACHABLE and outage['synced_at'] and outage['since']
    finally:hub.PAGE_READ.reset(token)
    # A page whose records were never received opens empty rather than failing the whole console.
    hub.OUTAGE.clear();token=hub.PAGE_READ.set([])
    try:
        assert hub.all_records('schedule',p['id'])==[] and hub.get('schedule','never',p['id']) is None
        cold=hub.status()['outage']
        assert cold['detail']==hub.UNREACHABLE and cold['since'] and cold['synced_at'] is None
    finally:hub.PAGE_READ.reset(token)
    with pytest.raises(hub.HubError) as offline:hub.all_records('mission',p['id'])
    assert offline.value.status==502
    with pytest.raises(hub.HubError):hub.save('mission',dict(m,name='Edited while offline'))

    monkeypatch.setattr(hub,'_client',c)
    assert hub.all_records('mission',p['id']) and hub.status()['outage'] is None
    monkeypatch.setattr(hub,'_client',None)

def test_the_console_page_opens_when_its_team_server_is_down(hub_client,monkeypatch):
    """No workspace record was ever received, so the page answers with empty lists and the alert."""
    from engine.runner import Runner
    import app as console
    c=hub_client;p=workspace(c)
    hub.persist_config({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}})
    class Down:
        def request(self,*a,**kw):raise httpx.ConnectError('down')
        def stream(self,*a,**kw):raise httpx.ConnectError('down')
        def close(self):pass
    worker=Runner();monkeypatch.setattr(console,'runner',worker)
    async def idle():await asyncio.Event().wait()
    monkeypatch.setattr(worker,'loop',idle)
    with TestClient(console.app,headers=HEADERS) as k:
        monkeypatch.setattr(hub,'_client',Down())
        page=k.get('/api/state',params={'project':p['id']})
        assert page.status_code==200,page.text
        body=page.json()
        assert [x['id'] for x in body['projects']]==[p['id']] and body['missions']==[] and body['runs']==[]
        assert body['hub']['outage']['detail']==hub.UNREACHABLE and body['hub']['outage']['synced_at'] is None
        assert k.get('/').status_code==200
    monkeypatch.setattr(hub,'_client',None)

def test_traces_stay_on_the_machine_that_ran_the_mission(hub_client,tmp_path):
    """A published run keeps its screenshots and drops its Playwright trace."""
    r=run_record({'id':'p'},{'id':'m','name':'m'})
    r['trace']=f'/api/runs/{r["id"]}/artifacts/trace-2.zip'
    # A continued run carries one trace per visit, and every part stays behind.
    r['traces']=[f'/api/runs/{r["id"]}/artifacts/trace.zip',f'/api/runs/{r["id"]}/artifacts/trace-2.zip']
    r['videos']=[f'/api/runs/{r["id"]}/artifacts/journey.webm']
    r['observations']=[{'screenshot':f'/api/runs/{r["id"]}/artifacts/s.png'}]
    folder=store.ARTIFACTS/r['id'];folder.mkdir()
    # The cached report narrative is raw model text, redacted only when a report page is rendered from it.
    for name in ('trace.zip','trace-2.zip','s.png','journey.webm','run.json','report-narrative.json'):(folder/name).write_bytes(b'x')
    shared=hub.shareable(r)
    assert 'trace' not in shared and shared['traces']==[] and shared['observations']==r['observations']
    assert shared['videos']==r['videos']
    assert hub.evidence_names(shared,folder)=={'s.png','journey.webm'}

@pytest.mark.asyncio
async def test_a_workspace_on_this_machine_keeps_its_runs_while_another_is_shared(hub_client,monkeypatch):
    """Signing in to one workspace shares that one only; the rest stay on this machine with every feature."""
    from engine.runner import Runner
    c=hub_client;p=workspace(c)
    hub.configure({'url':'http://testserver','logins':{p['id']:{'username':p['username'],'password':PASSWORD}}})
    monkeypatch.setattr(hub,'_client',c)
    assert hub.shared(p['id']) and not hub.shared('mine')
    store.save('project',{'id':'mine','name':'On this machine','url':'https://example.com','allowed_domains':['example.com']},local=True)
    local_mission=store.save('mission',{'id':'m-mine','project_id':'mine','name':'Local audit','goal':'Audit the page','url':'https://example.com','provider':'none','mode':'audit'})
    assert store.get('mission','m-mine',local=True)
    assert c.get('/hub/records/mission/m-mine',auth=(p['username'],PASSWORD)).status_code==404
    profile={'id':'offline','name':'Offline','down_mbps':0,'up_mbps':0,'latency_ms':0,'backend':'browser'}
    run=await Runner().submit(local_mission,network_snapshot=profile)
    assert run['hub_url']=='' and run['project_id']=='mine'
    assert store.get('run',run['id'],local=True)
    assert not hub.pending()
    assert c.get('/hub/records/run',auth=(p['username'],PASSWORD)).json()==[]
    monkeypatch.setattr(hub,'_client',None)
