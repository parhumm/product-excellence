"""Workspace data hub. Run one process behind a trusted HTTPS reverse proxy."""
import hashlib, json, os, re, secrets, tempfile, time, threading, uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import Column, String
from sqlalchemy.exc import IntegrityError
from engine import store, presets, views
from engine.contracts import Project, Mission, Schedule
from engine.hub import HubError, file_path, digest, artifact_names, TERMINAL, ROUTED

class WorkspaceLogin(store.Base):
    __tablename__='workspace_login'
    workspace_id=Column(String,primary_key=True)
    username=Column(String,unique=True,nullable=False)
    password_hash=Column(String,nullable=False)

security=HTTPBasic()
JSON_LIMIT=8*1024*1024
UPLOAD_LIMIT=512*1024*1024
attempts=OrderedDict(); attempt_lock=threading.Lock()

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    h=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return f'scrypt$16384$8$1${salt}${h}'

def verify(password,encoded):
    try:
        algorithm,n,r,p,salt,want=encoded.split('$')
        if (algorithm,n,r,p)!=('scrypt','16384','8','1'):return False
        return secrets.compare_digest(hash_password(password,salt),encoded)
    except (ValueError,TypeError):return False

def throttle(username,source):
    # ponytail: bounded process-local buckets; use an edge limiter before multiple hub workers.
    now=time.monotonic()
    with attempt_lock:
        buckets=[]
        for key in [('account',username),('source',source)]:
            start,count=attempts.get(key,(now,0))
            if now-start>=60:start,count=now,0
            if count>=120:raise HTTPException(429,'Too many authentication attempts. Retry in one minute.',headers={'Retry-After':'60'})
            buckets.append((key,start,count))
        for key,start,count in buckets:
            attempts[key]=(start,count+1);attempts.move_to_end(key)
        while len(attempts)>4096:attempts.popitem(last=False)

def auth_success(username,source):
    with attempt_lock:
        for key in [('account',username),('source',source)]:
            if key in attempts:
                start,count=attempts[key];attempts[key]=(start,max(0,count-1))

def authenticate(request:Request,credentials:HTTPBasicCredentials=Depends(security)):
    username=credentials.username;password=credentials.password
    if len(username)>60 or len(password)>256:raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})
    source=request.client.host if request.client else 'unknown'
    throttle(username,source)
    if username=='admin':
        admin=os.environ.get('PEX_HUB_ADMIN_PASSWORD','')
        if admin and secrets.compare_digest(password.encode(),admin.encode()):
            auth_success(username,source);return 'admin'
    else:
        with store.Session() as s:
            login=s.query(WorkspaceLogin).filter_by(username=username).first()
            if login and verify(password,login.password_hash):
                auth_success(username,source);return login.workspace_id
    raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})

def workspace(who=Depends(authenticate)):
    if who=='admin':raise HTTPException(403,'Use a workspace login for workspace data')
    return who

def admin(who=Depends(authenticate)):
    if who!='admin':raise HTTPException(403,'Admin access required')
    return who

@asynccontextmanager
async def lifespan(app):
    store.init()
    yield
app=FastAPI(title='Product Excellence team server',version='1.3.0',lifespan=lifespan)

@app.exception_handler(HubError)
async def hub_error(request,e):return JSONResponse({'detail':e.detail},e.status)
@app.exception_handler(store.Conflict)
async def conflict(request,e):return JSONResponse({'detail':str(e)},409)
@app.exception_handler(IntegrityError)
async def duplicate(request,e):return JSONResponse({'detail':'Record or username already exists'},409)
@app.exception_handler(ValidationError)
async def invalid(request,e):return JSONResponse({'detail':'Invalid record fields'},422)

@app.middleware('http')
async def boundary(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('x-pex-request')!='1':return JSONResponse({'detail':'Missing same-origin request header'},403)
        if request.headers.get('origin') and request.headers['origin']!=str(request.base_url).rstrip('/'):return JSONResponse({'detail':'Cross-origin request blocked'},403)
        if '/hub/artifacts/' not in request.url.path:
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>JSON_LIMIT:return JSONResponse({'detail':'JSON body too large'},413)
            request._body=bytes(body)
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    return response

@app.get('/hub/health')
def health():return {'ok':True,'version':app.version}
@app.get('/hub/me')
def me(who=Depends(authenticate)):
    if who=='admin':return {'admin':True}
    return required('project',who,who)
@app.get('/')
def landing():return HTMLResponse((store.ROOT/'static/intro.html').read_text().replace('{{version}}',app.version))
@app.get('/console')
def console(ws=Depends(workspace)):return FileResponse(store.ROOT/'static/index.html')
@app.get('/admin')
def admin_page(who=Depends(admin)):return FileResponse(store.ROOT/'static/hub.html')
@app.get('/logout')
def logout():
    # Basic authentication keeps no session: a 401 in the same realm makes the browser forget the credentials.
    return HTMLResponse('<p>Signed out. <a href="/">Back to the landing page</a></p>',401,headers={'WWW-Authenticate':'Basic'})
app.mount('/static',StaticFiles(directory=store.ROOT/'static'),name='static')

# The console reads the signed-in workspace and nothing else. Missions run in a local
# console and publish their results here, so no /api route below writes.
def connection(ws):return {'mode':'server','url':'','logins':{},'admin':False,'origin':'','pending':[],'workspace':ws}

@app.get('/api/hub/status')
def api_connection(ws=Depends(workspace)):return connection(ws)
@app.get('/api/health')
def api_health(ws=Depends(workspace)):
    return {'ok':True,'database':'Team server','ai':{},'browsers':{},'active':[],'mode':'server',
            'network':{'browser':False,'netem':False,'real_isp':'Missions run in your local console'},
            'policy':'Read-only console. Browser execution and AI stay on each teammate\'s machine.'}
@app.get('/api/state')
def api_state(ws=Depends(workspace)):
    return {'projects':[required('project',ws,ws)],'networks':[],'egresss':[],'personas':[],'hub':connection(ws),
            **{k:store.all_records(kind,ws,local=True,metadata=True) for k,kind in [('missions','mission'),('schedules','schedule')]},
            'runs':store.all_records('run',ws,local=True,metadata=True,limit=200,summaries=True)}
@app.get('/api/missions')
def api_missions(ws=Depends(workspace)):return store.all_records('mission',ws,local=True,metadata=True)
@app.get('/api/missions/{id}/versions')
def api_versions(id:str,ws=Depends(workspace)):
    required('mission',id,ws)
    return [v for v in store.all_records('mission_version',ws,local=True,metadata=True) if v['mission_id']==id]
@app.get('/api/runs/{id}')
def api_run(id:str,ws=Depends(workspace)):return views.rated(required('run',id,ws))
@app.get('/api/compare')
def api_compare(baseline:str,candidate:str,ws=Depends(workspace)):
    return views.compare(required('run',baseline,ws),required('run',candidate,ws))
@app.get('/api/findings')
def api_findings(grouped:bool=False,ws=Depends(workspace)):
    return views.findings(store.all_records('run',ws,local=True,metadata=True),grouped)
@app.get('/api/runs/{id}/export')
def api_export(id:str,format:str='md',ws=Depends(workspace)):
    r=required('run',id,ws)
    if format=='json':return Response(json.dumps(r,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="run-{id}.json"'})
    return Response(views.export_markdown(r),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="run-{id}.md"'})
@app.get('/api/runs/{id}/artifacts/{filename}')
def api_artifact(id:str,filename:str,ws=Depends(workspace)):return artifact(id,filename,ws)

def check_kind(kind,id=None):
    if kind not in ROUTED:raise HTTPException(404,'Unknown record kind')
    if id is not None and not re.fullmatch(r'[A-Za-z0-9_-]+',id):raise HTTPException(422,'Invalid record ID')

def required(kind,id,ws,session=None):
    check_kind(kind,id)
    r=store.get(kind,id,ws,local=True,session=session,metadata=True)
    if not r:raise HTTPException(404,'Not found')
    return r

def check_revision(body):
    v=body.get('_revision')
    if type(v)!=int or v<0:raise HTTPException(422,'Expected revision is required')
    return v

def validate(kind,id,body,ws,old,s):
    check_kind(kind,id)
    for key in ('created_at','updated_at'):
        if key in body and (not isinstance(body[key],str) or len(body[key])>64):raise HTTPException(422,'Invalid timestamp')
    if body.get('id')!=id:raise HTTPException(422,'URL and record IDs differ')
    if store.workspace_of(kind,body)!=ws:raise HTTPException(403,'Workspace cannot change')
    for v in (body,body.get('mission',{}),body.get('snapshot',{})):
        if not isinstance(v,dict):raise HTTPException(422,'Invalid snapshot')
        if v.get('project_id',ws)!=ws:raise HTTPException(403,'Workspace cannot change')
    def secrets_check(v):
        if isinstance(v,dict):
            if 'login_password' in v:raise HTTPException(422,'Mission passwords must remain local')
            for item in v.values():secrets_check(item)
        elif isinstance(v,list):
            for item in v:secrets_check(item)
    secrets_check(body)
    if kind=='project':Project.model_validate(body)
    elif kind=='mission':Mission.model_validate(body)
    elif kind=='schedule':Schedule.model_validate(body)
    elif kind=='mission_version':
        if old:raise HTTPException(409,'Historical versions are immutable')
        if not isinstance(body.get('snapshot'),dict):raise HTTPException(422,'A version requires a mission snapshot')
        Mission.model_validate(body['snapshot'])
    elif kind=='run':
        Mission.model_validate(body.get('mission',{}))
        if body.get('status') not in TERMINAL|{'queued','running','importing'}:raise HTTPException(422,'Invalid run status')
        for key in ('observations','actions','events','findings','http','console'):
            if not isinstance(body.get(key),list) or any(not isinstance(item,dict) for item in body[key]):raise HTTPException(422,'Invalid run evidence: '+key)
        if not old and body['status'] not in ('queued','importing'):raise HTTPException(409,'New runs must be queued or importing')
        if old and old['status']=='queued' and body['status'] not in ('queued','interrupted'):raise HTTPException(409,'Use the atomic start/cancel operation')
        if old and old['status'] in TERMINAL and body['status']!=old['status']:raise HTTPException(409,'A finished run cannot be restarted')
        for key in ('mission','mission_id','origin'):
            if old and body.get(key)!=old.get(key):raise HTTPException(409,'Run identity cannot change')
        if body['status'] in TERMINAL:
            manifest=body.get('_artifacts',{})
            if not isinstance(manifest,dict):raise HTTPException(422,'Invalid evidence manifest')
            for name in artifact_names(body)|set(manifest):
                p=file_path(store.ARTIFACTS,id,name)
                if not p.is_file() or manifest.get(name)!=digest(p):raise HTTPException(409,'Evidence is not fully uploaded: '+name)
    if kind in ('run','schedule'):
        if not isinstance(body.get('origin'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',body['origin']):raise HTTPException(422,'An explicit execution origin is required')
        if old and body['origin']!=old.get('origin'):raise HTTPException(409,'Execution origin cannot change')
    refs=[]
    if kind in ('run','schedule','mission_version') and body.get('mission_id'):refs.append(('mission',body['mission_id']))
    if kind=='run':refs.extend(('run',body[k]) for k in ('baseline_id','replay_of') if body.get(k))
    for refkind,refid in refs:
        if not isinstance(refid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',refid):raise HTTPException(422,'Invalid referenced ID')
        exists=store.get(refkind,refid,local=True,session=s,metadata=True)
        if exists and store.workspace_of(refkind,exists)!=ws:raise HTTPException(404,'Referenced record not found')
        if not exists and not (old or kind=='mission_version' or (kind=='run' and body.get('status')=='importing')):raise HTTPException(404,'Referenced record not found')
    if kind!='project':required('project',ws,ws,s)

@app.get('/hub/records/{kind}')
def records(kind:str,ws=Depends(workspace),limit:int=Query(200,ge=1,le=200),offset:int=Query(0,ge=0),summaries:bool=False):
    check_kind(kind)
    return store.all_records(kind,ws,local=True,metadata=True,limit=limit,offset=offset,summaries=summaries and kind=='run')
@app.get('/hub/records/{kind}/{id}')
def record(kind:str,id:str,ws=Depends(workspace)):return required(kind,id,ws)
@app.put('/hub/records/{kind}/{id}')
def put(kind:str,id:str,body:dict,ws=Depends(workspace)):
    check_kind(kind,id);expected=check_revision(body)
    with store.Session.begin() as s:
        collision=s.get(store.Record,id)
        if collision and (collision.workspace!=ws or collision.kind!=kind):raise HTTPException(404,'Not found')
        old=store.get(kind,id,ws,session=s,metadata=True)
        if kind=='project' and not old:raise HTTPException(403,'Only admins create workspaces')
        validate(kind,id,body,ws,old,s)
        if kind=='mission' and old:
            if expected!=old['_revision']:raise store.Conflict('This mission changed. Reload before saving.')
            store.save('mission_version',{'mission_id':id,'project_id':ws,'snapshot':store.clean(old)},session=s)
            body={**body,'version':old.get('version',1)+1}
        return store.save(kind,body,session=s,workspace=ws,expected=expected,preserve_times=True)
@app.delete('/hub/records/{kind}/{id}')
def remove(kind:str,id:str,revision:int,ws=Depends(workspace)):
    if kind in ('project','run','mission_version'):raise HTTPException(403,'This record cannot be deleted')
    with store.Session.begin() as s:
        required(kind,id,ws,s)
        store.delete(kind,id,ws,session=s,expected=revision)
        if kind=='mission':
            for r in store.all_records('schedule',ws,session=s):
                if r.get('mission_id')==id:store.delete('schedule',r['id'],ws,session=s)
    return {'ok':True}
@app.post('/hub/runs/{id}/{action}')
def transition(id:str,action:str,body:dict,ws=Depends(workspace)):
    if action not in ('start','cancel'):raise HTTPException(404,'Unknown operation')
    with store.Session.begin() as s:
        r=required('run',id,ws,s)
        if r['status']!='queued':raise HTTPException(409,'Only queued remote runs can be cancelled or started')
        if action=='start' and body.get('origin')!=r['origin']:raise HTTPException(409,'This run belongs to another machine')
        r.update(status='running' if action=='start' else 'cancelled')
        r['started_at' if action=='start' else 'finished_at']=store.now()
        return store.save('run',r,session=s,workspace=ws,expected=body.get('revision',-1))

@app.put('/hub/artifacts/{id}/{name}')
async def upload(id:str,name:str,request:Request,ws=Depends(workspace)):
    r=required('run',id,ws);p=file_path(store.ARTIFACTS,id,name)
    if name=='run.json':raise HTTPException(409,'run.json is generated from the canonical record')
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.upload-')
    try:
        size=0;h=hashlib.sha256()
        with os.fdopen(fd,'wb') as f:
            async for chunk in request.stream():
                size+=len(chunk)
                if size>UPLOAD_LIMIT:raise HTTPException(413,'Artifact exceeds 512 MiB limit')
                f.write(chunk);h.update(chunk)
            f.flush();os.fsync(f.fileno())
        result={'size':size,'sha256':h.hexdigest()}
        # Hard link is an atomic create-if-absent, including simultaneous uploads.
        try:os.link(tmp,p)
        except FileExistsError:
            if digest(p)!=result:raise HTTPException(409,'An artifact with different bytes already exists')
        return result
    finally:Path(tmp).unlink(missing_ok=True)
@app.get('/hub/artifacts/{id}/{name}')
def artifact(id:str,name:str,ws=Depends(workspace)):
    r=required('run',id,ws)
    p=file_path(store.ARTIFACTS,id,name)
    if name=='run.json':return JSONResponse(store.clean(r),headers={'Content-Disposition':'attachment; filename="run.json"'})
    if not p.is_file():raise HTTPException(404,'Artifact not ready')
    return FileResponse(p,filename=name,media_type='image/png' if p.suffix=='.png' else 'video/webm' if p.suffix=='.webm' else 'application/octet-stream')

def credentials(body,optional=False):
    username=body.get('username','');password=body.get('password','')
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,60}',username) or username=='admin':raise HTTPException(422,'Choose a unique workspace username, other than admin')
    if not isinstance(password,str) or (not optional or password) and not 15<=len(password)<=256:raise HTTPException(422,'Use a password of 15–256 characters')
    return username,password
@app.get('/hub/admin/workspaces')
def workspaces(who=Depends(admin)):
    with store.Session() as s:
        return [required('project',l.workspace_id,l.workspace_id,s)|{'username':l.username} for l in s.query(WorkspaceLogin).all()]
@app.post('/hub/admin/workspaces')
def create_workspace(body:dict,who=Depends(admin)):
    username,password=credentials(body);project=Project.model_validate(body).model_dump()
    project['id']=uuid.uuid4().hex
    with store.Session.begin() as s:
        p=store.save('project',project,session=s)
        s.add(WorkspaceLogin(workspace_id=p['id'],username=username,password_hash=hash_password(password)));s.flush()
        if body.get('seed',True):p=presets.seed_project(p,session=s)
        return p|{'username':username}
@app.put('/hub/admin/workspaces/{id}/login')
def change_login(id:str,body:dict,who=Depends(admin)):
    username,password=credentials(body,optional=True)
    with store.Session.begin() as s:
        login=s.get(WorkspaceLogin,id)
        if not login:raise HTTPException(404,'Workspace not found')
        login.username=username
        if password:login.password_hash=hash_password(password)
    return {'id':id,'username':username}
