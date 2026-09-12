"""Explicit real-browser smoke check, isolated loopback fixtures, no AI calls."""
import asyncio, json, tempfile, time
from pathlib import Path
from playwright.async_api import async_playwright
from tests.test_hub_integration import cluster,ADMIN,PASSWORD
from tests.browser_helpers import open_view

class Folders:
    def mktemp(self,name):return Path(tempfile.mkdtemp(prefix=name+'-'))

async def check(servers,output):
    (server,_,_),(a,_,_),(b,_,_)=servers
    auth=('admin',ADMIN)
    p=server.post('/hub/admin/workspaces',auth=auth,json={'name':'Browser fixture','url':str(a.base_url)+'/demo','username':'smoke','password':PASSWORD,'seed':False}).json()
    for c in (a,b):
        r=c.post('/api/hub/login',json={'url':str(server.base_url),'username':'smoke','password':PASSWORD});assert r.status_code==200,r.text
        c.headers['X-PEX-Workspace']=p['id']
    m=a.post('/api/missions',json={'name':'Shared browser audit','url':str(a.base_url)+'/demo','goal':'Audit the local demo','project_id':p['id'],'mode':'audit','provider':'none','max_seconds':60}).json()
    started=a.post('/api/runs',json={'mission_id':m['id']});assert started.status_code==200,started.text
    id=started.json()['id']
    for _ in range(120):
        r=await asyncio.to_thread(b.get,'/api/runs/'+id)
        assert r.status_code==200,r.text
        run=r.json()
        if run['status'] not in ('running','queued'):break
        await asyncio.sleep(.5)
    else:raise AssertionError('Run did not finish: '+json.dumps(a.get('/api/hub/status').json()))
    assert run['status']=='completed',json.dumps(run,ensure_ascii=False)[-4000:]
    # The trace stays with the browser that wrote it; everything else reaches the second client.
    assert run['observations'] and run.get('video') and 'trace' not in run,json.dumps(run)[-2000:]
    assert not a.get('/api/hub/status').json()['pending']
    for path in [run['observations'][0]['screenshot'],run['video']]:
        response=b.get(path);assert response.status_code==200 and response.content,path
    assert b.get('/api/runs/'+id+'/artifacts/run.json').json()['status']=='completed'
    errors=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        page=await browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(str(b.base_url)+'/#run/'+id);await page.wait_for_selector('video')
        await page.screenshot(path=str(output/'shared-run.png'),full_page=True)
        await page.goto(str(b.base_url)+'/#settings');await page.wait_for_selector('[data-hub-login]')
        # Sign in as admin through the local Settings form, then create through its shared renderer.
        form=page.locator('[data-hub-login]');await form.locator('[name=username]').fill('admin');await form.locator('[name=password]').fill(ADMIN);await form.locator('button[type=submit]').click()
        await page.wait_for_selector('[data-create]',state='attached')
        await page.locator('[data-create]').locator('..').locator('summary').click()
        create=page.locator('[data-create]')
        for name,value in [('name','Created in local Settings'),('url','https://example.com'),('username','settings-fixture'),('password',PASSWORD)]:await create.locator('[name='+name+']').fill(value)
        await create.locator('button[type=submit]').click();await page.get_by_text('Created in local Settings · settings-fixture',exact=True).wait_for()
        await page.screenshot(path=str(output/'team-settings.png'),full_page=True)
        admin_context=await browser.new_context(http_credentials={'username':'admin','password':ADMIN})
        admin_page=await admin_context.new_page();admin_page.on('pageerror',lambda e:errors.append(str(e)))
        await admin_page.goto(str(server.base_url));await admin_page.get_by_text('Created in local Settings · settings-fixture',exact=True).wait_for()
        row=admin_page.locator('details').filter(has=admin_page.get_by_text('Created in local Settings · settings-fixture',exact=True));await row.locator('summary').click()
        await row.locator('[name=password]').fill('a rotated browser password');await row.locator('button[type=submit]').click()
        await admin_page.screenshot(path=str(output/'hub-admin.png'),full_page=True)
        # Revocation still permits opening and operating Settings, including on mobile.
        server.put('/hub/admin/workspaces/'+p['id']+'/login',auth=auth,json={'username':'smoke','password':'changed smoke password'})
        await page.reload();await page.wait_for_selector('[data-hub-login]')
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile Settings overflow'
        await page.screenshot(path=str(output/'connection-repair-mobile.png'),full_page=True)
        server.put('/hub/admin/workspaces/'+p['id']+'/login',auth=auth,json={'username':'smoke','password':PASSWORD})
        assert not errors,errors
        await browser.close()
    return {'run_id':id,'status':run['status'],'observations':len(run['observations']),'trace':'local only','video':bool(run['video']),'js_errors':errors}

def main():
    output=Path(tempfile.mkdtemp(prefix='pex-hub-smoke-'));generator=cluster.__wrapped__(Folders())
    try:
        servers=next(generator);result=asyncio.run(check(servers,output))
        # Run the existing UI regression on client A while the isolated servers are alive.
        import os,subprocess,sys
        r=subprocess.run([sys.executable,'-m','tests.ui_check'],env={**os.environ,'PEX_BASE_URL':str(servers[1][0].base_url),'PEX_UI_ARTIFACTS':str(output)},capture_output=True,text=True)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)
        result['ui_check']=r.stdout.strip();result['artifacts']=str(output)
        (output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    finally:
        try:next(generator)
        except StopIteration:pass
if __name__=='__main__':main()
