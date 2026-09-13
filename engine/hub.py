"""Small synchronous hub client; async callers use io() to keep the browser responsive."""
from contextvars import ContextVar
import asyncio, copy, hashlib, json, os, re, tempfile, uuid, threading
from pathlib import Path
from urllib.parse import urlsplit
import httpx

ROUTED={'project','mission','mission_version','run','schedule'}
TERMINAL={'completed','blocked','failed','cancelled','interrupted'}
# Playwright traces are large and only replayable next to the browser that wrote them.
LOCAL_ONLY={'trace.zip'}
CONFIG={}
WORKSPACE=ContextVar("workspace",default="")
# A list while the browser is reading a page: that read may fall back to the last copy
# this console received, and stops trying a server that already failed once in the same
# request. Publication and reconciliation must never see a stale record, so it stays None.
PAGE_READ=ContextVar("page_read",default=None)
OUTAGE={}
_client=None
PUBLICATION_LOCK=threading.RLock()

class HubError(Exception):
    def __init__(self,status,detail): self.status=status; self.detail=detail; super().__init__(detail)

def data():
    from . import store
    return store.DATA

def atomic(path, value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.write-')
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)

def configure(value):
    global _client
    if CONFIG.get('url')!=value.get('url'):
        if _client:_client.close()
        _client=None
    OUTAGE.clear();CONFIG.clear();CONFIG.update(value)

def load():
    p=data()/'hub.json';configure(json.loads(p.read_text()) if p.exists() else {})

def close():configure({})
def enabled():return bool(CONFIG.get('url') and CONFIG.get('logins'))
def shared(ws):
    """One workspace at a time: its records live on the team server only when this console is signed in to it."""
    return bool(ws) and enabled() and ws in CONFIG.get('logins',{})
def persist_config(value):atomic(data()/'hub.json',value);configure(value)
def origin():
    p=data()/'client-id'
    if not p.exists():
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(uuid.uuid4().hex)
        except FileExistsError:pass
    return p.read_text().strip()

def normalize_url(url):
    try:u=urlsplit(url); port=u.port
    except ValueError:raise HubError(422,'Invalid team server URL')
    if u.username or u.password or u.query or u.fragment or u.path not in ('','/') or not u.hostname:raise HubError(422,'Use the server origin, without a path or credentials')
    if u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('localhost','127.0.0.1','::1')):raise HubError(422,'Team servers require HTTPS; HTTP is only allowed on loopback')
    return f'{u.scheme}://{u.netloc}'.rstrip('/')

def client():
    global _client
    # A team server is reached over the internet, not over loopback: a slow link, a VPN or a
    # mobile connection needs seconds to connect and minutes to send a run's evidence.
    if _client is None:_client=httpx.Client(timeout=httpx.Timeout(60,connect=15),follow_redirects=False,trust_env=False)
    return _client

UNREACHABLE='Team server unreachable. Check the connection and retry.'
def cached_read(path,login,kw):
    """Where the last good copy of one record read is kept, per server, login and query."""
    raw=f"{CONFIG.get('url','')}|{login['username']}|{path}|{sorted((kw.get('params') or {}).items())}"
    return data()/'hub-cache'/'reads'/(hashlib.sha256(raw.encode()).hexdigest()+'.json')

def read_cache(p):
    try:v=json.loads(p.read_text())
    except (OSError,ValueError):return None
    return v if isinstance(v,dict) and 'at' in v and 'body' in v else None

def record_outage(synced_at=None):
    OUTAGE['detail']=UNREACHABLE;OUTAGE.setdefault('since',store_now())
    known=[x for x in (OUTAGE.get('synced_at'),synced_at) if x]
    OUTAGE['synced_at']=min(known) if known else None

def degraded(path,login,kw):
    """What a page read gives back while the server is down: the last copy, else nothing."""
    cached=read_cache(cached_read(path,login,kw))
    if cached is not None:record_outage(cached['at']);return cached['body']
    # This read was never answered before, so the view opens empty beside the alert
    # rather than taking the whole console down with it.
    record_outage();return [] if path.count('/')==3 else None

def request(method,path,login,*,url=None,**kw):
    # Only a workspace record read has a last-good copy worth serving during an outage.
    record_read=method=='GET' and url is None and path.startswith('/hub/records/')
    page=PAGE_READ.get() if record_read else None
    # One dead server answers no faster on the page's other reads; do not wait for each.
    if page:return degraded(path,login,kw)
    # ponytail: a browser read gives up in 20 s; publication keeps the 60 s client default.
    if page is not None:kw.setdefault('timeout',httpx.Timeout(20,connect=10))
    try:r=client().request(method,(url or CONFIG['url'])+path,auth=(login['username'],login['password']),headers={'X-PEX-Request':'1'},**kw)
    except httpx.TransportError as e:
        if page is None:raise HubError(502,UNREACHABLE) from e
        page.append(path);return degraded(path,login,kw)
    if r.status_code>=300:
        if r.status_code==401:raise HubError(401,'Team server rejected the sign-in. Update it in Settings.')
        try:detail=r.json().get('detail','Team server request failed')
        except ValueError:detail='Team server request failed'
        raise HubError(r.status_code,str(detail))
    OUTAGE.clear()
    body=r.json()
    if record_read:
        try:atomic(cached_read(path,login,kw),{'at':store_now(),'body':body})
        except OSError:pass
    return body

def login_for(ws):
    v=CONFIG.get('logins',{}).get(ws)
    if not v:raise HubError(403,'Not signed in to this workspace')
    return v

def me(url,username,password):return request('GET','/hub/me',{'username':username,'password':password},url=normalize_url(url))
def admin(method,path,body=None):
    if not re.fullmatch(r'workspaces(?:/[\w-]+/login)?',path) or (method,path.count('/')) not in {('GET',0),('POST',0),('PUT',2)}:raise HubError(404,'Unknown admin operation')
    if not CONFIG.get('admin_password'):raise HubError(403,'Sign in as admin first')
    return request(method,'/hub/admin/'+path,{'username':'admin','password':CONFIG['admin_password']},json=body)

def get(kind,id,workspace=''):
    workspace=workspace or WORKSPACE.get()
    if not id:return None
    if not re.fullmatch(r'[\w-]+',id):raise HubError(422,'Invalid record ID')
    for ws in ([workspace] if workspace else CONFIG.get('logins',{})):
        try:return request('GET',f'/hub/records/{kind}/{id}',login_for(ws))
        except HubError as e:
            if e.status!=404:raise
    return None

def all_records(kind,workspace='',limit=None,summaries=False):
    values=[]
    for ws in ([workspace] if workspace else CONFIG.get('logins',{})):
        offset=0
        while True:
            count=min(200,limit-len(values)) if limit is not None else 200
            if count<=0:break
            page=request('GET',f'/hub/records/{kind}',login_for(ws),params={'offset':offset,'limit':count,'summaries':str(summaries).lower()})
            values.extend(page);offset+=len(page)
            if len(page)<count:break
    return sorted(values,key=lambda r:r.get('created_at',''),reverse=True)

def save(kind,value,*,preserve_times=False):
    from . import store
    value=copy.deepcopy(value);value.setdefault('id',uuid.uuid4().hex);value.setdefault('created_at',store.now())
    if not preserve_times:value['updated_at']=store.now()
    ws=store.workspace_of(kind,value);login=login_for(ws)
    value.setdefault('_revision',0)
    path=f'/hub/records/{kind}/{value["id"]}'
    try:return request('PUT',path,login,json=value)
    except HubError as e:
        if e.status!=502:raise
        # A lost response may have committed. Reconcile exactly, never overwrite a newer revision.
        current=get(kind,value['id'],ws)
        same=lambda x:{k:v for k,v in x.items() if k!='_revision'}
        if current and current['_revision']==value['_revision']+1 and same(current)==same(value):return current
        if (current or {}).get('_revision',0)==value['_revision']:return request('PUT',path,login,json=value)
        raise HubError(409,'Save outcome changed on the server. Reload before retrying.') from e

def delete(kind,id,workspace='',expected=None):
    r=get(kind,id,workspace)
    if not r:raise HubError(404,'Not found')
    from .store import workspace_of
    return request('DELETE',f'/hub/records/{kind}/{id}',login_for(workspace_of(kind,r)),params={'revision':expected if expected is not None else r['_revision']})

def transition(run,action):
    from .store import workspace_of
    return request('POST',f'/hub/runs/{run["id"]}/{action}',login_for(workspace_of('run',run)),json={'revision':run['_revision'],'origin':origin()})

def file_path(root,run_id,name):
    if not isinstance(run_id,str) or not isinstance(name,str):raise HubError(422,'Invalid artifact path')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id) or not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name in ('.','..'):raise HubError(422,'Invalid artifact path')
    base=root.resolve();p=root/run_id/name
    if p.parent.is_symlink() or p.is_symlink() or not p.resolve().is_relative_to(base):raise HubError(422,'Invalid artifact path')
    return p

def digest(path):
    with path.open('rb') as f:return {'size':path.stat().st_size,'sha256':hashlib.file_digest(f,'sha256').hexdigest()}

def artifact_names(run):
    prefix=f'/api/runs/{run["id"]}/artifacts/'
    names=set()
    def visit(v):
        if isinstance(v,str) and v.startswith(prefix):names.add(v[len(prefix):])
        elif isinstance(v,dict):
            for k,x in v.items():
                if k!='_artifacts':visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(run);names.discard('run.json');return names

def shareable(run):
    """The copy a server receives: links to evidence that never leaves this machine are dropped."""
    prefix=f'/api/runs/{run["id"]}/artifacts/'
    def strip(v):
        if isinstance(v,dict):return {k:strip(x) for k,x in v.items() if not (isinstance(x,str) and x.startswith(prefix) and x[len(prefix):] in LOCAL_ONLY)}
        if isinstance(v,list):return [strip(x) for x in v]
        return v
    return strip(run)

def evidence_names(run,folder):
    """Every file a finished run ships: the ones it links plus the rest of its folder, minus local-only evidence."""
    names=artifact_names(run)|{p.name for p in folder.glob('*') if p.is_file() and not p.name.startswith('.') and p.name!='run.json'}
    return names-LOCAL_ONLY

def put_artifact(run_id,path,workspace,expected=None):
    with path.open('rb') as f:
        result=request('PUT',f'/hub/artifacts/{run_id}/{path.name}',login_for(workspace),content=f)
    if result!=(expected or digest(path)):raise HubError(502,'Artifact checksum mismatch')
    return result

def cached_artifact(run_id,name,workspace):
    namespace=hashlib.sha256((CONFIG['url']+'|'+workspace).encode()).hexdigest()
    return file_path(data()/'hub-cache'/namespace,run_id,name)

def fetch_artifact(run_id,name,workspace):
    p=cached_artifact(run_id,name,workspace);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.download-')
    try:
        with os.fdopen(fd,'wb') as out:
            login=login_for(workspace)
            with client().stream('GET',CONFIG['url']+f'/hub/artifacts/{run_id}/{name}',auth=(login['username'],login['password'])) as r:
                if r.status_code!=200:raise HubError(r.status_code,'Artifact unavailable on the team server')
                total=0
                for chunk in r.iter_bytes():
                    total+=len(chunk)
                    if total>512*1024*1024:raise HubError(413,'Artifact exceeds download limit')
                    out.write(chunk)
            out.flush();os.fsync(out.fileno())
        os.replace(tmp,p);return p
    except httpx.TransportError as e:raise HubError(502,'Artifact download interrupted; retry it') from e
    finally:Path(tmp).unlink(missing_ok=True)

def pending():
    return sorted((data()/'pending-publication').glob('*.json'))

def status():
    return {'url':CONFIG.get('url',''),'mode':'hybrid' if enabled() else 'local','logins':{k:{'username':v['username'],'name':v.get('name',k)} for k,v in CONFIG.get('logins',{}).items()},'admin':bool(CONFIG.get('admin_password')),'origin':origin(),'pending':[json.loads(p.read_text())['run']['id'] for p in pending()],'outage':dict(OUTAGE) or None}

def publish(run):
    # ponytail: one local worker; a global publication lock also serializes manual recovery.
    with PUBLICATION_LOCK:return _publish(run)

def _publish(run):
    """One durable latest snapshot per run, serially written by its owning worker."""
    from . import store
    r=shareable(run);ws=store.workspace_of('run',r)
    path=data()/'pending-publication'/f'{r["id"]}.json'
    item={'url':CONFIG['url'],'workspace':ws,'run':r}
    atomic(path,item)
    manifest=r.setdefault('_artifacts',{})
    for name in LOCAL_ONLY:manifest.pop(name,None)  # a snapshot written before this rule must not ask the server for it
    names=evidence_names(r,store.ARTIFACTS/r['id']) if r['status'] in TERMINAL else artifact_names(r)
    for name in names:
        p=file_path(store.ARTIFACTS,r['id'],name)
        if not p.is_file():raise HubError(409,'Evidence missing locally: '+name)
        d=digest(p)
        if manifest.get(name)!=d:
            manifest[name]=put_artifact(r['id'],p,ws,d)
            atomic(path,item)
    result=save('run',r)
    path.unlink(missing_ok=True)
    return result

def retry_pending(active=(),workspace=''):
    with PUBLICATION_LOCK:return _retry_pending(active,workspace)

def _retry_pending(active,workspace):
    results=[]
    for p in pending():
        item=json.loads(p.read_text());r=item['run']
        if r['id'] in active or (workspace and item['workspace']!=workspace):continue
        if item['url']!=CONFIG.get('url'):raise HubError(409,'Pending results belong to another server')
        current=get('run',r['id'],item['workspace'])
        if current and current['_revision']!=r.get('_revision',0):
            same=lambda x:{k:v for k,v in x.items() if k not in ('_revision','updated_at')}
            if current['_revision']==r.get('_revision',0)+1 and same(current)==same(r):
                p.unlink();results.append(current);continue
            raise HubError(409,'Pending publication conflicts with a newer run: '+r['id'])
        if r['status'] in ('queued','running'):
            r.update(status='interrupted',finished_at=store_now(),error='Service restarted. Collected evidence retained.')
        results.append(publish(r))
    return results

def store_now():
    from .store import now
    return now()

async def io(fn,*args,**kwargs):
    """Drain the bounded request before propagating cancellation; threads cannot be cancelled."""
    task=asyncio.create_task(asyncio.to_thread(fn,*args,**kwargs))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:await asyncio.shield(task)
            except asyncio.CancelledError:continue
            except Exception:break
        if not task.cancelled():task.exception()
        raise
