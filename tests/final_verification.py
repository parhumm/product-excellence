import asyncio,json,time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
from tests.browser_helpers import open_view
from engine import pricing
async def main():
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8741/api',headers={'X-PEX-Request':'1'},timeout=30) as c:
  async def submit(**kw):
   r=await c.post('/missions',json={'name':'Verification','url':'http://127.0.0.1:8741/demo','goal':'Audit this test page','mode':'audit','provider':'none','locale':'en-US',**kw});r.raise_for_status()
   r=await c.post('/runs',json={'mission_id':r.json()['id']});r.raise_for_status();return r.json()['id']
  async def wait(id):
   for _ in range(150):
    r=(await c.get('/runs/'+id)).json()
    if r['status'] not in ('queued','running'):return r
    await asyncio.sleep(1)
   raise AssertionError('Run did not finish')
  stop=await submit(name='Phase 1 · active stop',observe_seconds=20)
  await asyncio.sleep(2);await c.post('/runs/'+stop+'/cancel');stopped=await wait(stop);assert stopped['status']=='cancelled'
  await asyncio.sleep(2)
  timed=await submit(name='Phase 1 · deadline',max_seconds=30,observe_seconds=29)
  r=await wait(timed);assert r['status']=='blocked' and 'time budget' in r['error'].lower(),r['error']
  disk=json.loads((Path('data/artifacts')/timed/'run.json').read_text());assert disk['status']==r['status']
  id=await submit(name='Phase 1 · final fixture recording')
  r=await wait(id);assert r['status']=='completed' and r.get('video'),r.get('error')
  v=await c.get(r['video'].removeprefix('/api'));assert v.status_code==200 and len(v.content)>1000
  Path('data/final-verification.json').write_text(json.dumps({'cancel':stop,'deadline':timed,'recording':id,'video_bytes':len(v.content)},indent=2))
  async with async_playwright() as p:
   b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto('http://127.0.0.1:8741/#run/'+id);await page.get_by_role('heading',name='Recorded journey').wait_for()
   await page.locator('video').evaluate('(v)=>v.play()');await page.wait_for_function('document.querySelector("video").currentTime > 0')
   await page.screenshot(path='data/final-run-console.png',full_page=True)
   for route in ['new','network','settings','findings']:
    await open_view(page,route)
    await page.add_script_tag(path='static/vendor/axe-core/axe.min.js')
    violations=await page.evaluate('async()=>(await axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}})).violations')
    assert not violations,[(route,x['id']) for x in violations]
   assert not errors,errors
   await b.close()
  print(pricing.report(r),flush=True)
  print('Active cancellation, deadline persistence, fixture video playback and console accessibility passed',flush=True)
asyncio.run(main())
