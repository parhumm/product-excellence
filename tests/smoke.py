import httpx,json,time
from pathlib import Path
base='http://127.0.0.1:8741'
c=httpx.Client(base_url=base,headers={'X-PEX-Request':'1'},timeout=20)
ids=[]
for browser in ['chromium','firefox','webkit']:
 m=c.post('/api/missions',json={'name':f'Fixture defects · {browser}','url':base+'/demo?bug=true','goal':'Audit the local fixture for seeded defects.','mode':'audit','provider':'none','browser':browser,'locale':'en-US'}).json()
 r=c.post('/api/runs',json={'mission_id':m['id']}).json();ids.append(r['id'])
m=c.post('/api/missions',json={'name':'Fixture autonomous discovery','url':base+'/demo','goal':'Open Search movies, then open The Glass River. Finish when movie details are visible.','success_text':'Movie details loaded','mode':'journey','provider':'codex','max_steps':4,'ai_budget':4,'locale':'en-US'}).json()
r=c.post('/api/runs',json={'mission_id':m['id']}).json();ids.append(r['id'])
Path('data/smoke-ids.json').write_text(json.dumps(ids))
print('Queued',ids,flush=True)
while True:
 runs=[c.get('/api/runs/'+id).json() for id in ids]
 print([(r['mission']['name'],r['status'],r.get('error','')[:140],len(r['findings'])) for r in runs],flush=True)
 if all(r['status'] not in ('queued','running') for r in runs):break
 time.sleep(10)
Path('data/smoke-results.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2))
