import httpx,json,time
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8741/api',headers={'X-PEX-Request':'1'},timeout=30)
assert c.get('/state').status_code==200
assert httpx.post('http://127.0.0.1:8741/api/missions',json={}).status_code==403
assert c.post('/missions',json={'name':'Invalid','url':'file:///etc/passwd','goal':'Bad URL'}).status_code==422
old=json.loads(Path('data/smoke-ids.json').read_text())[0]
replay=c.post(f'/runs/{old}/replay').json()['id']
ids=[replay]
for network in ['baseline','slow-mobile','poor-mobile','high-latency','constrained','offline']:
 m=c.post('/missions',json={'name':'Network validation · '+network,'url':'http://127.0.0.1:8741/demo','goal':'Audit the fixture under this profile','mode':'audit','provider':'none','network':network,'locale':'en-US','max_seconds':60}).json()
 ids.append(c.post('/runs',json={'mission_id':m['id']}).json()['id'])
Path('data/acceptance-ids.json').write_text(json.dumps(ids));print('Queued acceptance runs',ids,flush=True)
while True:
 runs=[c.get('/runs/'+id).json() for id in ids]
 print([(r['mission']['name'],r['status'],r.get('error','')[:120]) for r in runs],flush=True)
 if all(r['status'] not in ('queued','running') for r in runs):break
 time.sleep(15)
Path('data/acceptance-results.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2))
comparison=c.get('/compare',params={'baseline':old,'candidate':replay}).json();assert comparison['compatible'] and comparison['persisting']
assert c.get('/runs/'+replay+'/export').status_code==200
print('Replay and report export verified',flush=True)
