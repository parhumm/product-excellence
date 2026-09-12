import asyncio
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:8741'
MISSION='Home page · five-pillar audit'

async def row_worker(page,name):
    # The mode cell carries "provider · model · effort" for the named mission.
    return await page.evaluate('''name=>{const row=[...document.querySelectorAll('tbody tr')].find(r=>r.querySelector('strong')?.textContent===name);return row?row.children[1].querySelector('small').textContent:''}''',name)

async def set_worker(page,mission_id,provider,model,effort):
    await page.goto(f'{BASE}/#edit/{mission_id}');await page.wait_for_selector('#mission-form')
    await page.locator('#provider').select_option(provider)
    field=page.locator('[name=model]')
    await field.fill(model)
    await page.locator('#effort').select_option(effort)
    await page.get_by_role('button',name='Save mission',exact=True).click()
    await page.wait_for_url('**/#missions');await page.wait_for_selector('tbody tr')

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(f'{BASE}/#missions');await page.wait_for_selector('tbody tr')
        mission_id=await page.evaluate('''name=>[...document.querySelectorAll('tbody tr')].find(r=>r.querySelector('strong')?.textContent===name).querySelector('a').getAttribute('href').split('/')[1]''',MISSION)
        original=await row_worker(page,MISSION)

        await set_worker(page,mission_id,'claude','opus','high')
        await page.reload();await page.wait_for_selector('tbody tr')
        switched=await row_worker(page,MISSION)
        assert switched=='claude · opus · high',switched

        await set_worker(page,mission_id,'codex','','low')
        await page.reload();await page.wait_for_selector('tbody tr')
        restored=await row_worker(page,MISSION)
        assert restored=='codex · default model · low',restored

        labels=await page.evaluate('''()=>[...document.querySelectorAll('tbody tr')].map(r=>r.querySelector('strong').textContent+' :: '+r.children[1].querySelector('small').textContent)''')
        assert any(l.startswith(MISSION+' ::') and l.endswith('codex · default model · low') for l in labels)

        await page.goto(f'{BASE}/#settings')
        # Settings renders after its own health request, so wait for the worker row itself.
        await page.get_by_text('claude subscription worker',exact=True).wait_for(state='visible')
        rows=await page.evaluate('''()=>[...document.querySelectorAll('tbody tr')].map(r=>[...r.children].map(c=>c.textContent).join(' | '))''')
        for worker in ('codex','claude'):
            line=next(r for r in rows if r.startswith(worker+' subscription worker'))
            assert 'ready' in line.lower() and 'subscription' in line.lower(),line
            print('Settings:',line)
        assert not errors,errors
        print('Mission worker switched to claude · opus · high and back to',restored)
        print('Console worker, model and effort switching verified')
        await browser.close()

asyncio.run(main())
