import os,json
from urllib.parse import urlsplit,urlunsplit
import httpx
from .store import DATA

def config():
    path=DATA/'netem.json'
    return json.loads(path.read_text()) if path.exists() else {}
async def status():
    cfg=config()
    if not cfg:return {'ok':False,'reason':'Not configured'}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r=await c.get(cfg['url']+'/health',headers={'Authorization':'Bearer '+cfg['token']});r.raise_for_status();return r.json()
    except Exception as e:return {'ok':False,'reason':str(e)}
async def start(profile,browser,max_seconds):
    cfg=config()
    if not cfg:raise RuntimeError('Linux runner is not configured')
    async with httpx.AsyncClient(timeout=40) as c:
        r=await c.post(cfg['url']+'/start',json={**profile,'browser':browser,'max_seconds':max_seconds},headers={'Authorization':'Bearer '+cfg['token']})
        if not r.is_success:raise RuntimeError(r.text)
        out=r.json();u=urlsplit(out['endpoint']);host=urlsplit(cfg['url']).hostname
        out['endpoint']=urlunsplit(('ws',host+':8753',u.path,u.query,''));return out
async def stop():
    cfg=config()
    if cfg:
        try:
            async with httpx.AsyncClient(timeout=20) as c:await c.post(cfg['url']+'/stop',headers={'Authorization':'Bearer '+cfg['token']})
        except Exception:pass
