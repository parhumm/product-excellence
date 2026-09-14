import asyncio,json,os,re,secrets,uuid,fcntl,hashlib,tempfile
from datetime import datetime,timedelta,timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from pydantic import ValidationError
from fastapi import FastAPI,HTTPException,Request,UploadFile,File,Header
from fastapi.responses import HTMLResponse,FileResponse,Response,JSONResponse
from fastapi.staticfiles import StaticFiles
from engine import store,ai,netem,presets,pricing,hub,views,suggest,targets,android
from engine.contracts import Mission,GoalRequest,RunRequest,ContinueRequest,ContinueStepRequest,SnapshotRequest,DraftRequest,ScenarioText,Step,NetworkProfile,Egress,Schedule,Project,Target
from engine.runner import runner
from engine.evaluate import finding_identity
from engine.outcomes import gate,scores,executive_summary,sync_findings
from engine import VERSION

ROOT=store.ROOT

def required(kind,id):
    v=store.get(kind,id)
    if not v:raise HTTPException(404,'Not found')
    return v

def seed():
    if not store.get('network','unstable'):
        store.save('network',{'id':'unstable',**NetworkProfile(name='Unstable with disconnects',latency_ms=70,down_mbps=8,up_mbps=2,disconnect_every_seconds=15,disconnect_seconds=3).model_dump()})
    if not store.get('network','netem-poor'):
        store.save('network',{'id':'netem-poor',**NetworkProfile(name='Linux loss and jitter',backend='netem',latency_ms=90,jitter_ms=20,loss_pct=2,down_mbps=5,up_mbps=1).model_dump()})
    if True:
        for id,name,lat,down,up,offline in [('baseline','Baseline',0,0,0,False),('slow-mobile','Slow mobile',90,5,1,False),('poor-mobile','Poor mobile',180,1.5,.512,False),('high-latency','High latency',300,20,5,False),('constrained','Constrained bandwidth',150,.75,.25,False),('offline','Offline',0,0,0,True)]:
            if store.get('network',id):continue
            store.save('network',{'id':id,**NetworkProfile(name=name,latency_ms=lat,down_mbps=down,up_mbps=up,offline=offline).model_dump()})
    # Workspaces on this machine are seeded here; a shared one is seeded by the team server that created it.
    projects=store.all_records('project',local=True)
    if not projects and not hub.CONFIG.get('logins'):
        with store.Session.begin() as session:
            projects=[store.save('project',{'id':'default','name':'Example','url':'https://example.com','allowed_domains':['example.com','www.example.com']},session=session,local=True)]
            targets.default_web(projects[0],session)
    for p in projects:presets.seed_project(p)

async def schedule_once():
    runs=await hub.io(store.all_records,'run')
    for s in await hub.io(store.all_records,'schedule'):
        if store.remote('schedule',s) and s.get('origin')!=hub.origin():continue
        if not s.get('enabled') or s['next_at']>store.now():continue
        m=await hub.io(store.get,'mission',s['mission_id'])
        if not m:
            s.update(enabled=False,last_error='Mission no longer exists');await hub.io(store.save,'schedule',s);continue
        busy=any(r['mission_id']==m['id'] and r['status'] in ('queued','running') for r in runs)
        if not busy:
            try:
                run=await runner.submit(m);runs.append(run);s['last_run_id']=run['id'];s.pop('last_error',None)
            except ValueError as e:s['last_error']=str(e)
        s['next_at']=(datetime.now(timezone.utc)+timedelta(minutes=s['every_minutes'])).isoformat();await hub.io(store.save,'schedule',s)

async def scheduler():
    while True:
        await asyncio.sleep(15)
        try:
            if hub.enabled():
                if not runner.ready:await runner.recover()
                await runner.retry_publication()
            await schedule_once()
        except Exception:
            import logging
            logging.exception('Schedule tick failed; scheduler will retry')

@asynccontextmanager
async def lifespan(app):
    with (store.DATA/'runtime.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another local app or import is using this data directory')
        hub.load();store.init(skip=hub.shared);seed();runner.start();task=asyncio.create_task(scheduler())
        try:yield
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True);await runner.close();hub.close()

app=FastAPI(title='Product Excellence',version=VERSION,lifespan=lifespan)
@app.middleware('http')
async def local_boundary(request,call_next):
    if request.url.hostname not in ('127.0.0.1','localhost','::1','testserver'):return JSONResponse({'detail':'Local access only. Use an SSH tunnel for a VPS.'},403)
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-pex-request')!='1':return JSONResponse({'detail':'Missing same-origin request header'},403)
    origin=request.headers.get('origin')
    if origin and origin!=str(request.base_url).rstrip('/'):return JSONResponse({'detail':'Cross-origin request blocked'},403)
    token=hub.WORKSPACE.set(request.headers.get('x-pex-workspace',''))
    # A page the browser reads may fall back to the last copy from the team server; a write may not.
    page=hub.PAGE_READ.set([] if request.method in ('GET','HEAD') else None)
    try:response=await call_next(request)
    finally:hub.WORKSPACE.reset(token);hub.PAGE_READ.reset(page)
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Cache-Control':'no-store'})
    return response

@app.get('/')
def index():return FileResponse(ROOT/'static/index.html')

@app.get('/console')
def console():return FileResponse(ROOT/'static/index.html')

@app.get('/intro')
def intro():return HTMLResponse((ROOT/'static/intro.html').read_text().replace('{{version}}',app.version))
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@app.get('/api/health')
async def health():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browsers={b:Path(getattr(p,b).executable_path).exists() for b in ('chromium','firefox','webkit')}
    return {'ok':True,'version':app.version,'database':('PostgreSQL' if 'postgresql' in store.DATABASE_URL else 'SQLite')+(' · shared workspaces on '+hub.CONFIG['url'] if hub.enabled() else ''),'ai':await ai.health(),'browsers':browsers,'android':android.health(),'active':list(runner.active),'network':{'browser':True,'netem':bool((await netem.status()).get('ok')),'real_isp':'Requires a configured proxy endpoint'},'mode':'hybrid' if hub.enabled() else 'local','policy':'Web requests are read-only; Android runs do not intercept app network writes'}

def workspaces():
    """Every workspace this console can open: the ones on this machine, then the shared ones signed in to."""
    values=store.all_records('project',local=True)
    known={p['id'] for p in values}
    return values+[{'id':id,'name':v.get('name',id)} for id,v in hub.CONFIG.get('logins',{}).items() if id not in known]

@app.get('/api/state')
def state(project:str=''):
    """One workspace at a time when a project is given; the run list is capped, so it is filtered first."""
    projects=workspaces();ids=[p['id'] for p in projects]
    globals_={k:store.all_records(kind) for k,kind in [('networks','network'),('egresss','egress'),('personas','persona')]}
    if ids and (project or hub.enabled()):
        if project not in ids:project=ids[0]
        shared=hub.shared(project)
        if shared:
            selected=store.get('project',project,project)
            # During an outage the workspace name from the sign-in stands in for its record.
            if not selected and not hub.OUTAGE:raise HTTPException(404,'Workspace not found')
            if selected:projects=[selected if p['id']==project else p for p in projects]
        runs=store.all_records('run',project,limit=200,summaries=shared)
        # The hub status is read last, so an outage these record reads just met is reported.
        return {'projects':projects,'targets':store.all_records('target',project),'missions':store.all_records('mission',project),'runs':runs if shared else [views.summary(r) for r in runs],'schedules':store.all_records('schedule',project),**globals_,'hub':hub.status()}
    # Nothing selected and nothing shared: the whole local database, as the command line and tests read it.
    records={k:store.all_records(k[:-1],local=True) for k in ('missions','schedules')}
    return {'projects':projects,'targets':store.all_records('target',local=True),**records,'runs':[views.summary(r) for r in store.all_records('run',local=True)[:200]],**globals_,'hub':hub.status()}

@app.post('/api/projects')
def project(p:Project):
    with store.Session.begin() as session:
        value=store.save('project',p.model_dump(),session=session)
        targets.default_web(value,session)
        return presets.seed_project(value,session=session)
@app.put('/api/projects/{id}')
def update_project(id:str,p:Project,revision:int|None=Header(None,alias='X-PEX-Revision')):
    old=required('project',id);check_edit(old,revision)
    if old.get('url') and not p.url and store.get('target',targets.default_id(id),id):raise HTTPException(409,'Remove the default website target first')
    if hub.shared(id):return store.save('project',{**old,**p.model_dump()})
    with store.Session.begin() as session:
        value=store.save('project',{**old,**p.model_dump()},session=session)
        targets.default_web(value,session)
        return value

@app.get('/api/targets')
def target_list():return store.all_records('target')
@app.get('/api/targets/{id}')
def target_get(id:str):return required('target',id)
@app.post('/api/targets')
def target_create(target:Target):
    required('project',target.project_id)
    return store.save('target',target.model_dump())
@app.put('/api/targets/{id}')
def target_update(id:str,target:Target,revision:int|None=Header(None,alias='X-PEX-Revision')):
    old=required('target',id);check_edit(old,revision)
    if hub.shared(old['project_id']) and target.visibility!=old.get('visibility','team'):raise HTTPException(409,'Use Share to publish a local target; published targets cannot be made local')
    if target.project_id!=old['project_id'] or target.type!=old['type'] or (old.get('package') and target.package!=old['package']):raise HTTPException(409,'Target workspace, type and bound package cannot change')
    if id==targets.default_id(old['project_id']) and (target.url!=old.get('url') or target.allowed_domains!=old.get('allowed_domains',[])):raise HTTPException(409,'Edit the default website through workspace settings')
    return store.save('target',{**old,**target.model_dump()})
@app.delete('/api/targets/{id}')
def target_delete(id:str,revision:int|None=Header(None,alias='X-PEX-Revision')):
    target=required('target',id);check_edit(target,revision);ws=target['project_id']
    missions=store.all_records('mission',ws);runs=store.all_records('run',ws)
    if any(m.get('target_id')==id for m in missions) or any(r.get('status') in ('queued','running') and r.get('mission',{}).get('target_id')==id for r in runs):raise HTTPException(409,'Remove dependent missions and active runs first')
    if hub.shared(ws):store.delete('target',id,expected=revision)
    else:
        with store.Session.begin() as session:
            store.delete('target',id,ws,session=session,expected=revision)
            if id==targets.default_id(ws):
                project=store.get('project',ws,ws,session=session)
                store.save('project',{**project,'url':'','allowed_domains':[]},session=session)
    return {'ok':True}

@app.post('/api/targets/{id}/builds')
async def target_upload(id:str,file:UploadFile=File(...),revision:int|None=Header(None,alias='X-PEX-Revision')):
    async with runner.connection_lock:
        target=await hub.io(required,'target',id);check_edit(target,revision)
        if target['type']!='android':raise HTTPException(422,'Builds belong to Android targets')
        apps=store.DATA/'apps';apps.mkdir(exist_ok=True,mode=0o700)
        fd,name=tempfile.mkstemp(dir=apps,prefix='.upload-')
        path=Path(name);size=0
        try:
            with os.fdopen(fd,'wb') as output:
                while chunk:=await file.read(1024*1024):
                    size+=len(chunk)
                    if size>300*1024*1024:raise HTTPException(413,'APK exceeds 300 MiB limit')
                    output.write(chunk)
                output.flush();os.fsync(output.fileno())
            path.chmod(0o600)
            try:build=await hub.io(targets.inspect_apk,path)
            except ValueError as error:raise HTTPException(422,str(error))
            package=build.pop('package')
            if target.get('package') and target['package']!=package:raise HTTPException(422,'APK package does not match this target')
            destination=apps/(build['sha256']+'.apk')
            try:os.link(path,destination);destination.chmod(0o600)
            except FileExistsError:
                with destination.open('rb') as source:
                    if hashlib.file_digest(source,'sha256').hexdigest()!=build['sha256']:raise HTTPException(409,'Stored APK bytes conflict')
            if not any(item['sha256']==build['sha256'] for item in target.get('builds',[])):
                build.update(uploaded_at=store.now(),archived=False)
                target={**target,'package':target.get('package') or package,'builds':target.get('builds',[])+[build]}
                target=await hub.io(store.save,'target',target)
            return target
        finally:path.unlink(missing_ok=True)

@app.delete('/api/targets/{id}/builds/{sha256}')
def archive_build(id:str,sha256:str,revision:int|None=Header(None,alias='X-PEX-Revision')):
    target=required('target',id);check_edit(target,revision);found=False
    for build in target.get('builds',[]):
        if build['sha256']==sha256:build['archived']=True;found=True
    if not found:raise HTTPException(404,'Build not found')
    return store.save('target',target)
@app.delete('/api/targets/{id}/builds/{sha256}/local')
async def remove_local_build(id:str,sha256:str):
    async with runner.connection_lock:
        target=await hub.io(required,'target',id)
        if not any(b['sha256']==sha256 for b in target.get('builds',[])):raise HTTPException(404,'Build not found')
        for mission in await hub.io(store.all_records,'mission',target['project_id']):
            if mission.get('build')==sha256:raise HTTPException(409,'A pinned mission still uses this build')
        for run in await hub.io(store.all_records,'run',target['project_id']):
            if run.get('status') in ('queued','running') and run.get('mission',{}).get('build')==sha256:raise HTTPException(409,'An active run still uses this build')
        for other in await hub.io(store.all_records,'target'):
            if other['id']!=id and any(b['sha256']==sha256 for b in other.get('builds',[])):raise HTTPException(409,'Another target still uses this local APK')
        (store.DATA/'apps'/(sha256+'.apk')).unlink(missing_ok=True)
        return {'ok':True}

@app.post('/api/{collection}/{id}/share')
async def share_item(collection:str,id:str):
    kinds={'targets':'target','missions':'mission','runs':'run'};kind=kinds.get(collection)
    if not kind:raise HTTPException(404,'Unknown share operation')
    value=await hub.io(store.get,kind,id,local=True,metadata=True)
    if not value:raise HTTPException(404,'Not found')
    ws=store.workspace_of(kind,value)
    if not hub.shared(ws):raise HTTPException(409,'Connect this workspace to its team server first')
    if value.get('visibility')!='local':raise HTTPException(409,'This item is already shared')
    if kind=='mission' and value.get('target_id') and not await hub.io(hub.get,'target',value['target_id'],ws):raise HTTPException(409,'Share the target first: '+value['target_id'])
    if kind=='run':
        if value.get('status') not in hub.TERMINAL:raise HTTPException(409,'Only finished runs can be shared')
        for field,label in [('mission_id','mission'),('baseline_id','baseline run'),('replay_of','replay source')]:
            if value.get(field) and not await hub.io(hub.get,'mission' if field=='mission_id' else 'run',value[field],ws):raise HTTPException(409,f'Share the {label} first: {value[field]}')
    local_revision=value.pop('_revision',None);team={**store.clean(value),'visibility':'team','_revision':0}
    try:
        if kind!='run':ack=await hub.io(hub.save,kind,team,preserve_times=True)
        else:
            terminal=team['status'];team['status']='importing'
            current=await hub.io(hub.get,'run',id,ws)
            if current:
                if current.get('status')!='importing':raise HTTPException(409,'A different team run already uses this ID')
                team={**team,'_revision':current['_revision']}
            staged=await hub.io(hub.save,'run',team,preserve_times=True);manifest=staged.setdefault('_artifacts',{})
            folder=store.ARTIFACTS/id
            for name in hub.evidence_names(value,folder):
                path=hub.file_path(folder.parent,id,name);digest=hub.digest(path)
                if manifest.get(name)!=digest:manifest[name]=await hub.io(hub.put_artifact,id,path,ws,digest)
            staged['status']=terminal;ack=await hub.io(hub.save,'run',staged,preserve_times=True)
    except hub.HubError as error:raise HTTPException(error.status,error.detail)
    await hub.io(store.delete,kind,id,ws,local=True,expected=local_revision)
    return ack

@app.get('/api/missions')
def missions():return store.all_records('mission')
def stash_password(record,password):
    # The password never enters the mission record; a blank edit keeps the stored one.
    path=store.DATA/'secrets'/f"{record['id']}.json"
    if password:
        path.parent.mkdir(exist_ok=True,mode=0o700)
        path.write_text(json.dumps({'password':password}));path.chmod(0o600)
    elif not record.get('login_identifier'):path.unlink(missing_ok=True)
    return record
@app.post('/api/missions')
def create_mission(m:Mission):
    required('project',m.project_id)
    try:value=targets.resolve_mission(m.model_dump())
    except ValueError as error:raise HTTPException(422,str(error))
    return stash_password(store.save('mission',{'version':1,**value}),m.login_password)
@app.put('/api/missions/{id}')
def update_mission(id:str,m:Mission,revision:int|None=Header(None,alias='X-PEX-Revision')):
    required('project',m.project_id)
    old=required('mission',id);check_edit(old,revision)
    if hub.shared(old['project_id']) and m.visibility!=old.get('visibility','team'):raise HTTPException(409,'Use Share to publish a local mission; published missions cannot be made local')
    if not store.remote('mission',old):store.save('mission_version',{'mission_id':id,'project_id':old['project_id'],'visibility':old.get('visibility','team'),'snapshot':old})
    try:value=targets.resolve_mission(m.model_dump())
    except ValueError as error:raise HTTPException(422,str(error))
    return stash_password(store.save('mission',{**old,**value,'version':old.get('version',1)+1}),m.login_password)
@app.delete('/api/missions/{id}')
def delete_mission(id:str,revision:int|None=Header(None,alias='X-PEX-Revision')):
    m=required('mission',id);check_edit(m,revision);store.delete('mission',id,expected=revision);(store.DATA/'secrets'/f'{id}.json').unlink(missing_ok=True)
    # A team server removes the schedules of a mission it deletes; a workspace on this machine does it here.
    if store.remote('mission',m):return {'ok':True}
    for s in store.all_records('schedule',m['project_id']):
        if s['mission_id']==id:store.delete('schedule',s['id'])
    return {'ok':True}
@app.post('/api/missions/suggest')
async def suggest_goal(req:GoalRequest):
    """Two goals for the mission form. Nothing is saved; the user applies one and saves the mission."""
    project=await hub.io(required,'project',req.project_id)
    target=await hub.io(store.get,'target',req.target_id,req.project_id) if req.target_id else None
    if req.target_id and not target:raise HTTPException(404,'Target not found in this workspace')
    if target and target['type']=='android':
        builds=target.get('builds',[]);build=next((b for b in builds if b['sha256']==req.build),None) if req.build else max((b for b in builds if not b.get('archived')),key=lambda b:(b['version_code'],b['uploaded_at'],b['sha256']),default=None)
        if not build:raise HTTPException(422,'Upload or select an Android build')
        project={**project,'_target':target,'_build':build}
    try:return await suggest.suggest(req,project)
    except ValueError as e:raise HTTPException(422,str(e))
    except Exception as e:raise HTTPException(502,'The AI worker could not suggest a goal: '+str(e)[:300])
@app.get('/api/missions/{id}/export')
def mission_export(id:str):
    m=required('mission',id);clean={k:v for k,v in m.items() if k in Mission.model_fields}
    return Response(yaml.safe_dump(clean,allow_unicode=True,sort_keys=False),media_type='application/yaml',headers={'Content-Disposition':f'attachment; filename="mission-{id}.yaml"'})
@app.post('/api/import')
async def import_mission(file:UploadFile=File(...)):
    raw=await file.read(100001)
    if len(raw)>100000:raise HTTPException(413,'Mission file is too large')
    try:m=Mission.model_validate(yaml.safe_load(raw))
    except Exception as e:raise HTTPException(422,str(e))
    return await hub.io(create_mission,m)

@app.post('/api/runs')
async def start_run(req:RunRequest):
    m=await hub.io(required,'mission',req.mission_id)
    if req.visibility:m={**m,'visibility':req.visibility}
    if req.build:m={**m,'build':req.build}
    if req.network:m['network']=(await hub.io(required,'network',req.network))['id']
    if req.baseline_id:await hub.io(required,'run',req.baseline_id)
    try:return await runner.submit(m,req.baseline_id)
    except ValueError as e:raise HTTPException(429 if 'Queue' in str(e) else 422,str(e))
@app.post('/api/missions/{id}/matrix')
async def matrix(id:str):
    m=await hub.io(required,'mission',id)
    if m.get('platform')=='android':raise HTTPException(422,'Android network matrices are not supported')
    if runner.queue.qsize()>15:raise HTTPException(429,'Queue is full')
    if m['browser']!='chromium':raise HTTPException(422,'Standard browser network matrix requires Chromium')
    return [await runner.submit({**m,'network':profile}) for profile in ('baseline','slow-mobile','poor-mobile','high-latency','constrained')]

@app.get('/api/runs/{id}')
def run(id:str):return views.rated(required('run',id))
@app.post('/api/runs/{id}/cancel')
async def cancel(id:str):await hub.io(required,'run',id);await runner.cancel(id);return {'ok':True}
@app.post('/api/runs/{id}/replay')
async def replay(id:str):
    original=await hub.io(required,'run',id)
    if original['status'] in ('queued','running'):raise HTTPException(409,'Wait for the original run to finish')
    try:return await runner.submit(original['mission'],original.get('baseline_id',''),id,network_snapshot=original.get('network_snapshot'))
    except ValueError as e:raise HTTPException(429 if 'Queue' in str(e) else 422,str(e))
@app.post('/api/runs/{id}/continue')
async def continue_run(id:str,req:ContinueRequest):
    r=await hub.io(required,'run',id)
    # Zero means "as much again as the mission asked for", so one click is enough.
    try:return await runner.resume(id,req.ai_calls or r['mission']['ai_budget'],req.steps or r['mission']['max_steps'])
    except ValueError as e:raise HTTPException(429 if 'Queue' in str(e) else 409 if str(e).startswith('Wait') else 422,str(e))
@app.post('/api/runs/{id}/continue-step')
async def continue_step(id:str,req:ContinueStepRequest):
    r=await hub.io(required,'run',id)
    if store.remote('run',r):raise HTTPException(409,'Continue an operator step on the machine running the device')
    if r['status']!='running':raise HTTPException(409,'This run is not waiting for an operator')
    try:return await runner.continue_step(id,req.step,req.token)
    except ValueError as e:raise HTTPException(409,str(e))
@app.get('/api/scenarios')
def scenario_templates():
    """The shipped stateful journeys. Each mission still needs a target, build and device."""
    return presets.scenarios()
def problem(error):
    """The first thing pydantic objected to, in the author's words rather than the validator's."""
    first=error.errors()[0];where='.'.join(str(part) for part in first['loc'] if not isinstance(part,int))
    return (where+': ' if where else '')+first['msg'].replace('Value error, ','')[:300]
def compact(step):
    """The step as an author would write it: nothing that is already implied."""
    row=step.model_dump(by_alias=True,exclude_defaults=True,exclude_none=True)
    for kind in ('check','hold'):
        oracle=row.get(kind)
        # Required is derived from the policy; printing it back only when it was overridden.
        if oracle and oracle.get('required') is (oracle.get('policy','confirmed')=='confirmed'):oracle.pop('required')
    return row
@app.post('/api/scenarios/yaml')
def scenario_yaml(req:ScenarioText):
    """One normalized model, two spellings. Invalid YAML is refused and changes nothing."""
    steps=req.steps
    if req.yaml.strip():
        try:parsed=yaml.safe_load(req.yaml)
        except yaml.YAMLError as e:raise HTTPException(422,'This is not valid YAML: '+str(e).split('\n')[0][:300])
        if not isinstance(parsed,list):raise HTTPException(422,'A scenario is a list of steps, one per dash')
        if len(parsed)>40:raise HTTPException(422,'A scenario holds at most 40 steps')
        steps=[]
        for number,item in enumerate(parsed,1):
            if not isinstance(item,dict):raise HTTPException(422,f'Step {number} is not a step: write one key such as goal, check, hold, event or manual')
            try:steps.append(Step.model_validate(item))
            except ValidationError as e:raise HTTPException(422,f'Step {number}: '+problem(e))
            except ValueError as e:raise HTTPException(422,f'Step {number}: '+str(e)[:300])
    rows=[compact(s) for s in steps]
    return {'steps':rows,'yaml':yaml.safe_dump(rows,allow_unicode=True,sort_keys=False,default_flow_style=False) if rows else ''}
@app.post('/api/scenarios/draft')
async def draft_scenario(req:DraftRequest):
    """Steps suggested from a description. Nothing is saved and no device is touched."""
    project=await hub.io(required,'project',req.project_id)
    target=await hub.io(store.get,'target',req.target_id,req.project_id) if req.target_id else None
    if req.target_id and not target:raise HTTPException(404,'Target not found in this workspace')
    if not target or target['type']!='android':raise HTTPException(422,'Scenarios are drafted against an Android target')
    builds=target.get('builds',[]);build=next((b for b in builds if b['sha256']==req.build),None) if req.build else max((b for b in builds if not b.get('archived')),key=lambda b:(b['version_code'],b['uploaded_at'],b['sha256']),default=None)
    try:return await suggest.draft(req,{**project,'_target':target,'_build':build or {}})
    except ValueError as e:raise HTTPException(422,str(e))
    except Exception as e:raise HTTPException(502,'The AI worker could not draft the steps: '+str(e)[:300])
def designated_avd():
    avd=os.environ.get('PEX_ANDROID_AVD','')
    if not avd:raise HTTPException(422,'Name the designated disposable AVD in PEX_ANDROID_AVD before managing snapshots')
    return avd
@app.get('/api/android/snapshots')
def android_snapshots(project:str=''):
    avd=designated_avd()
    try:return {'avd':avd,'snapshots':android.snapshots(avd,project)}
    except android.AndroidError as e:raise HTTPException(422,str(e))
@app.post('/api/android/snapshots')
async def save_android_snapshot(req:SnapshotRequest):
    avd=designated_avd()
    try:return await android.capture_snapshot(avd,req.name,req.project_id)
    except android.AndroidError as e:raise HTTPException(409 if 'busy' in str(e) else 422,str(e))
@app.delete('/api/android/snapshots/{id}')
async def remove_android_snapshot(id:str,project:str=''):
    avd=designated_avd()
    try:return await android.delete_snapshot(avd,id,project)
    except android.AndroidError as e:raise HTTPException(409 if 'busy' in str(e) else 404 if 'no managed snapshot' in str(e) else 422,str(e))
@app.get('/api/compare')
def compare(baseline:str,candidate:str):
    a=required('run',baseline);b=required('run',candidate)
    if hub.enabled() and store.workspace_of('run',a)!=store.workspace_of('run',b):raise HTTPException(422,'Compare runs within one workspace')
    return views.compare(a,b)
@app.get('/api/findings')
def findings(grouped:bool=False,project:str=''):
    runs=[r for r in store.all_records('run',project) if not project or store.workspace_of('run',r)==project]
    return views.findings(runs,grouped)
@app.patch('/api/findings/{run_id}/{id}')
async def finding_update(run_id:str,id:str,request:Request,revision:int|None=Header(None,alias='X-PEX-Revision')):
    r=await hub.io(required,'run',run_id);check_edit(r,revision)
    if r['status'] in ('running','queued'):raise HTTPException(409,'Review status can be edited after this run finishes')
    body=await request.json()
    if body.get('status','open') not in ('open','accepted','resolved','dismissed'):raise HTTPException(422,'Invalid status')
    target=None
    for f in r['findings']:
        if f['id']==id:
            f.update(status=body.get('status',f['status']),owner=str(body.get('owner',f.get('owner','')))[:100]);target=f
    if not target:raise HTTPException(404,'Finding not found')
    # One issue has one review state inside its own run too: a site-wide defect is recorded once per
    # page that showed it, and the score already charges it once, so closing it closes every record.
    identity=finding_identity(target)
    for f in r['findings']:
        if f is not target and finding_identity(f)==identity:f.update(status=target['status'],owner=target.get('owner',''))
    # A closed or reassigned finding changes the gate, the pillar score and the summary.
    r['gate']=gate(r);r['scores']=scores(r);r['executive_summary']=executive_summary(r)
    saved=await hub.io(store.save,'run',r)
    # The same issue is one issue: every earlier report of it carries the review decision too.
    synced=await hub.io(sync_findings,store.workspace_of('run',r),
                        {finding_identity(target):{'status':target['status'],'owner':target.get('owner','')}},(run_id,))
    return {'ok':True,'synced':len(synced),**({'_revision':saved['_revision']} if '_revision' in saved else {})}

@app.get('/api/runs/{id}/artifacts/{filename}')
def artifact(id:str,filename:str):
    run=required('run',id)
    if store.remote('run',run):
        if filename=='run.json':return JSONResponse(store.clean(run))
        p=hub.cached_artifact(id,filename,store.workspace_of('run',run))
        if not p.is_file():p=hub.fetch_artifact(id,filename,store.workspace_of('run',run))
        return FileResponse(p,media_type={'.png':'image/png','.webm':'video/webm','.mp4':'video/mp4','.txt':'text/plain'}.get(p.suffix,'application/octet-stream'))
    p=hub.file_path(store.ARTIFACTS,id,filename)
    if not p.is_file():raise HTTPException(404,'Artifact not ready')
    if p.suffix=='.png':return FileResponse(p,media_type='image/png')
    if p.suffix=='.webm':return FileResponse(p,media_type='video/webm')
    if p.suffix=='.mp4':return FileResponse(p,media_type='video/mp4')
    if p.suffix=='.txt':return FileResponse(p,media_type='text/plain')
    return FileResponse(p,filename=filename,media_type='application/octet-stream')

@app.get('/api/runs/{id}/export')
def export(id:str,format:str='md'):
    r=required('run',id)
    if format=='json':return Response(json.dumps(r,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="run-{id}.json"'})
    return Response(views.export_markdown(r),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="run-{id}.md"'})

@app.post('/api/networks')
def network(p:NetworkProfile):return store.save('network',p.model_dump())
@app.post('/api/egress')
def egress(p:Egress):
    d=p.model_dump();sec={k:d.pop(k) for k in ('username','password')};v=store.save('egress',d)
    folder=store.DATA/'secrets';folder.mkdir(exist_ok=True,mode=0o700)
    path=folder/f"{v['id']}.json";path.write_text(json.dumps(sec));path.chmod(0o600)
    return v
@app.delete('/api/egress/{id}')
def delete_egress(id:str):
    required('egress',id);store.delete('egress',id);(store.DATA/'secrets'/f'{id}.json').unlink(missing_ok=True);return {'ok':True}
@app.post('/api/personas')
async def persona(file:UploadFile=File(...)):
    data=await file.read(2_000_001)
    if len(data)>2_000_000:raise HTTPException(413,'Session file too large')
    try:
        state=json.loads(data)
        if not isinstance(state.get('cookies'),list) or not isinstance(state.get('origins'),list):raise ValueError('Expected Playwright storage state with cookies and origins')
    except Exception as e:raise HTTPException(422,str(e))
    v=await hub.io(store.save,'persona',{'name':(file.filename or 'Test session')[:100]});folder=store.DATA/'personas';folder.mkdir(exist_ok=True,mode=0o700)
    p=folder/f"{v['id']}.json";p.write_bytes(data);p.chmod(0o600);return v
@app.post('/api/schedules')
def schedule(s:Schedule):
    mission=required('mission',s.mission_id)
    return store.save('schedule',{'project_id':mission['project_id'],'visibility':mission.get('visibility','team'),'origin':hub.origin(),**s.model_dump(),'next_at':(datetime.now(timezone.utc)+timedelta(minutes=s.every_minutes)).isoformat()})
@app.delete('/api/schedules/{id}')
def delete_schedule(id:str,revision:int|None=Header(None,alias='X-PEX-Revision')):
    check_edit(required('schedule',id),revision);store.delete('schedule',id,expected=revision);return {'ok':True}

@app.put('/api/networks/{id}')
def update_network(id:str,p:NetworkProfile):
    old=required('network',id)
    return store.save('network',{**old,**p.model_dump()})

@app.patch('/api/schedules/{id}')
async def toggle_schedule(id:str,request:Request,revision:int|None=Header(None,alias='X-PEX-Revision')):
    s=await hub.io(required,'schedule',id);check_edit(s,revision);body=await request.json()
    if not isinstance(body.get('enabled'),bool):raise HTTPException(422,'enabled must be boolean')
    s['enabled']=body['enabled'];s['next_at']=(datetime.now(timezone.utc)+timedelta(minutes=s['every_minutes'])).isoformat()
    return await hub.io(store.save,'schedule',s)

@app.delete('/api/personas/{id}')
def delete_persona(id:str):
    required('persona',id);store.delete('persona',id);(store.DATA/'personas'/f'{id}.json').unlink(missing_ok=True)
    return {'ok':True}

@app.get('/api/missions/{id}/versions')
def versions(id:str):
    mission=required('mission',id)
    return [v for v in store.all_records('mission_version',mission['project_id']) if v['mission_id']==id]

@app.post('/api/egress/{id}/verify')
async def verify_egress(id:str):
    from playwright.async_api import async_playwright
    e=await hub.io(required,'egress',id)
    sec=json.loads((store.DATA/'secrets'/f'{id}.json').read_text())
    try:
        async with async_playwright() as p:
            ctx=await p.request.new_context(proxy={'server':e['server'],**{k:v for k,v in sec.items() if v}})
            try:
                resp=await ctx.get('https://api.ipify.org?format=json',timeout=15000)
                if not resp.ok:raise ValueError('Egress probe returned HTTP '+str(resp.status))
                data=await resp.json()
                import ipaddress
                ip=str(ipaddress.ip_address(data['ip']))
                e['verified_ip']=ip;e['verified_at']=store.now();e['verification']='Public IP observed through proxy; ISP ownership is not certified'
            finally:await ctx.dispose()
        return await hub.io(store.save,'egress',e)
    except Exception as ex:raise HTTPException(422,'Proxy verification failed: '+str(ex)[:250])

@app.get('/demo',response_class=HTMLResponse)
def demo(bug:bool=False,page:str='home'):
    title='' if bug else 'Cinema Fixture | Product Excellence'
    search='<h2>Search results</h2><a href="/demo?page=movie">The Glass River</a>' if page=='search' else ''
    movie='<h2>The Glass River</h2><p>Movie details loaded. A family mystery, 2026.</p><button onclick="document.querySelector(\'#result\').textContent=\'Playback ready\'">Play trailer</button>' if page=='movie' else ''
    defects='<img src="/demo/missing-image"><div style="width:2000px">Overflow fixture</div><script>setTimeout(()=>{throw new Error("Seeded fixture error")},100)</script><script type="application/ld+json">{invalid}</script>' if bug else ''
    return f'''<!doctype html><html lang="en"><head><title>{title}</title><meta name="description" content="Local fixture for validating the product excellence engine."><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{{font:18px system-ui;max-width:900px;margin:40px auto;padding:20px;color:#25332b;background:#f8faf8}}a,button{{display:inline-block;padding:14px;margin:8px;background:#e0ebe3;color:#163d29}}input{{font:inherit;padding:12px}}h1{{font-size:40px}}</style></head><body><main><h1>Cinema Fixture</h1><p>Local test site. Findings here are test evidence only.</p><a href="/demo?page=search">Search movies</a><a href="/demo?page=movie">Featured movie</a><button onclick="document.querySelector('#result').textContent='DO NOT EXECUTE'">Delete account</button>{search}{movie}<p id="result" role="status"></p>{defects}</main></body></html>'''
@app.get('/demo/missing-image')
def missing():raise HTTPException(500,'Seeded image server failure')


@app.exception_handler(hub.HubError)
async def hub_failure(request,e):return JSONResponse({'detail':e.detail},e.status)
@app.exception_handler(store.Conflict)
async def edit_conflict(request,e):return JSONResponse({'detail':str(e)},409)

def check_edit(record,revision):
    # Only a shared record carries a revision; a workspace on this machine has no concurrent writer.
    if record.get('_revision') is not None and revision!=record['_revision']:
        raise HTTPException(409,'This record changed or its revision is missing. Reload before saving; your changes were not applied.')

@app.get('/api/hub/status')
def hub_status():return hub.status()

def connection_blockers():
    queued=list(runner.owned)
    return sorted(set(queued+list(runner.active)+hub.status()['pending']))

@app.post('/api/hub/login')
async def hub_login(body:dict):
    async with runner.connection_lock:
        blockers=connection_blockers()
        url=hub.normalize_url(body.get('url',''))
        username=body.get('username','');password=body.get('password','')
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>60 or len(password)>256:raise HTTPException(422,'Invalid credentials')
        identity=await hub.io(hub.me,url,username,password)
        replacement=url==hub.CONFIG.get('url') and (identity.get('admin') or identity.get('id') in hub.CONFIG.get('logins',{}))
        if blockers and not replacement:raise HTTPException(409,'Finish queued/active runs and publish pending results first: '+', '.join(blockers))
        config=json.loads(json.dumps(hub.CONFIG)) if url==hub.CONFIG.get('url') else {'url':url,'logins':{}}
        if identity.get('admin'):config['admin_password']=password
        else:config.setdefault('logins',{})[identity['id']]={'username':username,'password':password,'name':identity['name']}
        hub.persist_config(config);runner.ready=False;runner.recovered.clear()
        if not hub.enabled():await hub.io(seed)
        return hub.status()

@app.delete('/api/hub/login/{workspace}')
async def hub_logout(workspace:str):
    async with runner.connection_lock:
        blockers=connection_blockers()
        if blockers:raise HTTPException(409,'Finish queued/active runs and publish pending results first: '+', '.join(blockers))
        config=json.loads(json.dumps(hub.CONFIG))
        if workspace=='admin':config.pop('admin_password',None)
        else:config.get('logins',{}).pop(workspace,None)
        hub.persist_config(config);runner.ready=False;runner.recovered.clear()
        if not hub.enabled():await hub.io(seed)
        return hub.status()

@app.api_route('/api/hub/admin/{path:path}',methods=['GET','POST','PUT'])
async def hub_admin(path:str,request:Request):
    return await hub.io(hub.admin,request.method,path,await request.json() if request.method!='GET' else None)

@app.post('/api/hub/retry')
async def hub_retry():
    return {'published':len(await runner.retry_publication())}
