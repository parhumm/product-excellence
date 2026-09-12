import httpx,json,time
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8741/api',headers={'X-PEX-Request':'1'},timeout=20)
ids=[]
def queue(**kw):
    m=c.post('/missions',json={'name':'Phase 1 verification','url':'http://127.0.0.1:8741/demo','goal':'Audit local fixture','mode':'audit','provider':'none','locale':'en-US',**kw});m.raise_for_status()
    r=c.post('/runs',json={'mission_id':m.json()['id']});r.raise_for_status();ids.append(r.json()['id'])
queue(name='Phase 1 · final-action completion',goal='Open the featured movie detail page.',mode='journey',provider='codex',max_steps=1,success_text='Movie details loaded',ai_budget=3)
queue(name='Phase 1 · disconnect and recording',network='unstable',observe_seconds=20)
queue(name='Phase 1 · WebKit metric availability',browser='webkit')
Path('data/review-run-ids.json').write_text(json.dumps(ids));print('Queued',ids,flush=True)
previous=None
while True:
    runs=[c.get('/runs/'+id).json() for id in ids];states=[(r['mission']['name'],r['status'],r.get('mission_outcome'),r.get('error','')[:150]) for r in runs]
    if states!=previous:print(states,flush=True);previous=states
    if all(r['status'] not in ('queued','running') for r in runs):break
    time.sleep(10)
for r in runs:
    assert r.get('finished_at'),('No finished_at on first terminal read',r['mission']['name'])
    assert r['status']=='cancelled' or r.get('duration_seconds') is not None,r['mission']['name']
    if r['mission']['browser']=='chromium' and r['status']!='cancelled':assert r.get('video'),('Video missing on first terminal read',r['mission']['name'])
Path('data/review-results.json').write_text(json.dumps(runs,ensure_ascii=False,indent=2))
for r in runs:print(r['mission']['name'],r['status'],'video',bool(r.get('video')),'coverage',r['coverage'],flush=True)
