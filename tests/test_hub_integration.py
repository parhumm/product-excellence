"""One real hub and two independent local apps; no AI calls or browser missions."""
import json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx
import pytest

ROOT=Path(__file__).resolve().parents[1]
ADMIN='integration admin password'
PASSWORD='integration workspace password'

@pytest.fixture(scope='module')
def cluster(tmp_path_factory):
    root=tmp_path_factory.mktemp('team-cluster');processes=[];clients=[];logs=[]
    def launch(module,name):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        folder=root/name;folder.mkdir();log=(folder/'server.log').open('w');logs.append(log)
        env={**os.environ,'PEX_DATA':str(folder),'DATABASE_URL':'sqlite:///'+str(folder/'records.db'),'PEX_HUB_ADMIN_PASSWORD':ADMIN}
        process=subprocess.Popen([sys.executable,'-m','uvicorn',module+':app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(process)
        client=httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'X-PEX-Request':'1'},timeout=15,trust_env=False);clients.append(client)
        for _ in range(100):
            if process.poll() is not None:raise AssertionError((folder/'server.log').read_text())
            try:
                if client.get('/hub/health' if module=='hub' else '/api/hub/status').status_code==200:break
            except httpx.TransportError:pass
            time.sleep(.05)
        else:raise AssertionError('Server did not start')
        return client,folder,env
    try:yield launch('hub','hub'),launch('app','a'),launch('app','b')
    finally:
        for c in clients:c.close()
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=20)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for f in logs:f.close()

def test_two_clients_modes_edits_import_and_recovery(cluster):
    (server,_,_),(a,folder_a,env_a),(b,folder_b,_)=cluster
    created=server.post('/hub/admin/workspaces',auth=('admin',ADMIN),json={'name':'Shared fixture','url':str(a.base_url)+'/demo','username':'team','password':PASSWORD,'seed':False})
    assert created.status_code==200,created.text
    ws=created.json()['id']
    for c in (a,b):
        r=c.post('/api/hub/login',json={'url':str(server.base_url),'username':'team','password':PASSWORD})
        assert r.status_code==200,r.text
        c.headers['X-PEX-Workspace']=ws
        assert c.get('/api/state',params={'project':ws}).json()['hub']['mode']=='hybrid'
    m=a.post('/api/missions',json={'name':'Shared audit','url':str(a.base_url)+'/demo','goal':'Audit fixture page','mode':'audit','provider':'none','project_id':ws})
    assert m.status_code==200,m.text
    m=m.json();stale=b.get('/api/state',params={'project':ws}).json()['missions'][0]
    edited=a.put('/api/missions/'+m['id'],headers={'X-PEX-Revision':str(m['_revision'])},json=m|{'name':'Edited by A'})
    assert edited.status_code==200,edited.text
    assert b.put('/api/missions/'+m['id'],headers={'X-PEX-Revision':str(stale['_revision'])},json=stale|{'name':'Stale edit'}).status_code==409
    assert len(b.get('/api/missions/'+m['id']+'/versions').json())==1
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        writes=[pool.submit(c.put,'/api/missions/'+m['id'],headers={'X-PEX-Revision':str(edited.json()['_revision'])},json=edited.json()|{'name':name}) for c,name in ((a,'Concurrent A'),(b,'Concurrent B'))]
        assert sorted(f.result().status_code for f in writes)==[200,409]
    assert len(b.get('/api/missions/'+m['id']+'/versions').json())==2
    assert a.post('/api/projects',json={'name':'Not local','url':'https://example.com'}).status_code==403
    before=a.get('/api/hub/status').json()
    assert a.post('/api/hub/login',json={'url':str(server.base_url),'username':'team','password':'wrong'}).status_code==401
    assert a.get('/api/hub/status').json()==before
    # Admin-only sign-in must not switch local mode after the workspace is removed.
    assert a.post('/api/hub/login',json={'url':str(server.base_url),'username':'admin','password':ADMIN}).status_code==200
    assert a.get('/api/hub/admin/workspaces').status_code==200
    assert a.delete('/api/hub/login/'+ws).json()['mode']=='local'
    assert a.get('/api/hub/status').json()['admin'] is True
    # Revoked credentials do not prevent opening connection repair.
    assert server.put('/hub/admin/workspaces/'+ws+'/login',auth=('admin',ADMIN),json={'username':'team','password':'rotated workspace password'}).status_code==200
    assert b.get('/api/state',params={'project':ws}).status_code==401
    assert b.get('/api/hub/status').status_code==200
    assert b.post('/api/hub/login',json={'url':str(server.base_url),'username':'team','password':'rotated workspace password'}).status_code==200
    # Local SDK integration: generated canonical run.json and remote evidence download.
    auth=('team','rotated workspace password')
    record={'id':'artifact-fixture','project_id':ws,'mission_id':m['id'],'mission':{k:v for k,v in m.items() if k!='_revision'},'origin':'fixture-machine','status':'importing','observations':[],'actions':[],'events':[],'findings':[],'http':[],'console':[],'_revision':0}
    r=server.put('/hub/records/run/artifact-fixture',auth=auth,json=record)
    assert r.status_code==200,r.text
    evidence=server.put('/hub/artifacts/artifact-fixture/x.png',auth=auth,content=b'fixture evidence').json()
    r=server.put('/hub/records/run/artifact-fixture',auth=auth,json=r.json()|{'status':'completed','observations':[{'screenshot':'/api/runs/artifact-fixture/artifacts/x.png'}],'_artifacts':{'x.png':evidence}})
    assert r.status_code==200,r.text
    assert b.get('/api/runs/artifact-fixture/artifacts/x.png').content==b'fixture evidence'
    assert b.get('/api/runs/artifact-fixture/artifacts/run.json').json()['status']=='completed'
    # Credential repair remains possible when revoked credentials have left pending evidence.
    pending=folder_b/'pending-publication'/'artifact-fixture.json';pending.parent.mkdir(exist_ok=True)
    pending.write_text(json.dumps({'url':str(server.base_url).rstrip('/'),'workspace':ws,'run':r.json()}))
    assert b.delete('/api/hub/login/'+ws).status_code==409
    assert b.post('/api/hub/login',json={'url':str(server.base_url),'username':'team','password':'rotated workspace password'}).status_code==200
    pending.unlink(missing_ok=True)
    # The import script refuses to touch a live local app.
    command=[sys.executable,'scripts/push-workspace.py','default',ws]
    result=subprocess.run(command,cwd=ROOT,env=env_a,capture_output=True,text=True)
    assert result.returncode==1 and 'Stop the local app' in result.stderr

def test_import_interruption_resume_and_restore(cluster,monkeypatch,tmp_path):
    import importlib.util
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from engine import store,hub
    from engine.contracts import Mission
    server=cluster[0][0]
    target=server.post('/hub/admin/workspaces',auth=('admin',ADMIN),json={'name':'Import fixture','url':'https://example.com','username':'importer','password':PASSWORD,'seed':False}).json()
    engine=create_engine('sqlite:///'+str(tmp_path/'source.db'))
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False));monkeypatch.setattr(store,'DATA',tmp_path);monkeypatch.setattr(store,'ARTIFACTS',tmp_path/'artifacts');store.ARTIFACTS.mkdir()
    hub.close();store.init()
    source=store.save('project',{'id':'source','name':'Source','url':'https://example.com'},local=True)
    m=store.save('mission',{'id':'import-mission',**Mission(project_id='source',name='Imported mission',url='https://example.com',goal='Audit the fixture',mode='audit',provider='none').model_dump(exclude={'login_password'})},local=True)
    store.save('mission_version',{'id':'import-version','mission_id':m['id'],'project_id':'source','snapshot':m},local=True)
    store.save('schedule',{'id':'import-schedule','project_id':'source','mission_id':m['id'],'enabled':True,'every_minutes':5,'next_at':store.now()},local=True)
    r=store.save('run',{'id':'import-run','project_id':'source','mission_id':m['id'],'mission':m,'status':'completed','observations':[{'screenshot':'/api/runs/import-run/artifacts/x.png'}],'actions':[],'events':[],'findings':[],'http':[],'console':[]},local=True)
    folder=store.ARTIFACTS/r['id'];folder.mkdir();(folder/'x.png').write_bytes(b'preserved screenshot')
    hub.atomic(tmp_path/'hub.json',{'url':str(server.base_url).rstrip('/'),'logins':{target['id']:{'username':'importer','password':PASSWORD}}})
    spec=importlib.util.spec_from_file_location('push_workspace',ROOT/'scripts/push-workspace.py');script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)
    script.main(['source',target['id']])
    original=hub.save;calls=[]
    def interrupted(kind,value,**kwargs):
        calls.append(kind)
        if len(calls)==2:raise hub.HubError(502,'Simulated interruption')
        return original(kind,value,**kwargs)
    monkeypatch.setattr(hub,'save',interrupted)
    with pytest.raises(hub.HubError):script.main(['source',target['id'],'--apply'])
    monkeypatch.setattr(hub,'save',original)
    script.main(['source',target['id'],'--apply']);script.main(['source',target['id'],'--apply'])
    schedules=hub.all_records('schedule',target['id']);assert len(schedules)==1 and schedules[0]['enabled'] is False
    assert len(hub.all_records('mission_version',target['id']))==1
    remote=hub.get('run','import-run',target['id']);assert remote['status']=='completed' and remote['mission']['project_id']==target['id']
    assert remote['created_at']==r['created_at'] and remote['updated_at']==r['updated_at']
    # Exercise restoring the backed-up source records into a separate, empty SQLite database.
    backup=json.loads(next((tmp_path/'imports').glob('*.backup.json')).read_text())
    restored=create_engine('sqlite:///'+str(tmp_path/'restored.db'));store.Base.metadata.create_all(restored)
    with sessionmaker(restored).begin() as session:
        store.save('project',backup['source_project'],session=session,preserve_times=True)
        for item in backup['source_records']:store.save(item['kind'],item['record'],session=session,preserve_times=True)
    with sessionmaker(restored)() as session:
        assert store.get('run','import-run',session=session)['mission']['project_id']=='source'
    changed=hub.get('mission','import-mission',target['id']);hub.save('mission',changed|{'name':'Teammate edit'})
    with pytest.raises(ValueError,match='Target (was edited|contains records outside)'):script.main(['source',target['id'],'--apply'])
    hub.close();restored.dispose();engine.dispose()
