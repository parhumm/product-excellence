import asyncio,json,os,re,secrets,uuid,fcntl
from datetime import datetime,timedelta,timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from fastapi import FastAPI,HTTPException,Request,UploadFile,File,Header
from fastapi.responses import HTMLResponse,FileResponse,Response,JSONResponse
from fastapi.staticfiles import StaticFiles
from engine import store,ai,netem,presets,pricing,hub,views,suggest
from engine.contracts import Mission,GoalRequest,RunRequest,NetworkProfile,Egress,Schedule,Project
from engine.runner import runner
from engine.evaluate import finding_identity
from engine.outcomes import gate,scores,executive_summary,sync_findings

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
        projects=[store.save('project',{'id':'default','name':'Example','url':'https://example.com','allowed_domains':['example.com','www.example.com']},local=True)]
    for p in projects:presets.seed_project(p)

async def schedule_once():
    runs=await hub.io(store.all_records,'run')
    for s in await hub.io(store.all_records,'schedule'):
        if hub.shared(s['project_id']) and s.get('origin')!=hub.origin():continue
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
        hub.load();store.init();seed();runner.start();task=asyncio.create_task(scheduler())
        try:yield
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True);await runner.close();hub.close()

app=FastAPI(title='Product Excellence',version='1.2.0',lifespan=lifespan)
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
    return {'ok':True,'version':app.version,'database':('PostgreSQL' if 'postgresql' in store.DATABASE_URL else 'SQLite')+(' · shared workspaces on '+hub.CONFIG['url'] if hub.enabled() else ''),'ai':await ai.health(),'browsers':browsers,'active':list(runner.active),'network':{'browser':True,'netem':bool((await netem.status()).get('ok')),'real_isp':'Requires a configured proxy endpoint'},'mode':'hybrid' if hub.enabled() else 'local','policy':'Read-only network methods; no payments or account changes'}

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
        return {'projects':projects,'missions':store.all_records('mission',project),'runs':runs if shared else [views.summary(r) for r in runs],'schedules':store.all_records('schedule',project),**globals_,'hub':hub.status()}
    # Nothing selected and nothing shared: the whole local database, as the command line and tests read it.
    records={k:store.all_records(k[:-1],local=True) for k in ('missions','schedules')}
    return {'projects':projects,**records,'runs':[views.summary(r) for r in store.all_records('run',local=True)[:200]],**globals_,'hub':hub.status()}

@app.post('/api/projects')
def project(p:Project):
    return presets.seed_project(store.save('project',p.model_dump(),local=True))
@app.put('/api/projects/{id}')
def update_project(id:str,p:Project,revision:int|None=Header(None,alias='X-PEX-Revision')):
    old=required('project',id);check_edit(old,revision)
    return store.save('project',{**old,**p.model_dump()})

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
    return stash_password(store.save('mission',{'version':1,**m.model_dump(exclude={'login_password'})}),m.login_password)
@app.put('/api/missions/{id}')
def update_mission(id:str,m:Mission,revision:int|None=Header(None,alias='X-PEX-Revision')):
    required('project',m.project_id)
    old=required('mission',id);check_edit(old,revision)
    if not hub.shared(old['project_id']):store.save('mission_version',{'mission_id':id,'project_id':old['project_id'],'snapshot':old})
    return stash_password(store.save('mission',{**old,**m.model_dump(exclude={'login_password'}),'version':old.get('version',1)+1}),m.login_password)
@app.delete('/api/missions/{id}')
def delete_mission(id:str,revision:int|None=Header(None,alias='X-PEX-Revision')):
    m=required('mission',id);check_edit(m,revision);store.delete('mission',id,expected=revision);(store.DATA/'secrets'/f'{id}.json').unlink(missing_ok=True)
    # A team server removes the schedules of a mission it deletes; a workspace on this machine does it here.
    if hub.shared(m['project_id']):return {'ok':True}
    for s in store.all_records('schedule',m['project_id']):
        if s['mission_id']==id:store.delete('schedule',s['id'])
    return {'ok':True}
@app.post('/api/missions/suggest')
async def suggest_goal(req:GoalRequest):
    """Two goals for the mission form. Nothing is saved; the user applies one and saves the mission."""
    project=await hub.io(required,'project',req.project_id)
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
    if req.network:m['network']=(await hub.io(required,'network',req.network))['id']
    if req.baseline_id:await hub.io(required,'run',req.baseline_id)
    try:return await runner.submit(m,req.baseline_id)
    except ValueError as e:raise HTTPException(429 if 'Queue' in str(e) else 422,str(e))
@app.post('/api/missions/{id}/matrix')
async def matrix(id:str):
    m=await hub.io(required,'mission',id)
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
    if hub.shared(store.workspace_of('run',run)):
        if filename=='run.json':return JSONResponse(store.clean(run))
        p=hub.cached_artifact(id,filename,store.workspace_of('run',run))
        if not p.is_file():p=hub.fetch_artifact(id,filename,store.workspace_of('run',run))
        return FileResponse(p,media_type='image/png' if p.suffix=='.png' else 'video/webm' if p.suffix=='.webm' else 'application/octet-stream')
    p=hub.file_path(store.ARTIFACTS,id,filename)
    if not p.is_file():raise HTTPException(404,'Artifact not ready')
    if p.suffix=='.png':return FileResponse(p,media_type='image/png')
    if p.suffix=='.webm':return FileResponse(p,media_type='video/webm')
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
    return store.save('schedule',{'project_id':mission['project_id'],'origin':hub.origin(),**s.model_dump(),'next_at':(datetime.now(timezone.utc)+timedelta(minutes=s.every_minutes)).isoformat()})
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
