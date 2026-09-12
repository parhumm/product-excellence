import asyncio,os
from pathlib import Path
from playwright.async_api import async_playwright
from tests.browser_helpers import open_view
async def main():
 base=os.environ.get('PEX_BASE_URL','http://127.0.0.1:8741')
 output=Path(os.environ.get('PEX_UI_ARTIFACTS','data'));output.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  for route in ['overview','missions','new','runs','findings','benchmark','compare','network','settings']:
   await open_view(page,route,base)
   # Every view belongs to one website, so the workspace picker is always usable.
   assert await page.locator('#workspace option').count()>0,f'Workspace picker is empty on {route}'
   if route=='new':
    # The model catalog and the escape hatch for an unlisted id must both be reachable.
    assert await page.locator('select[name=model] optgroup').count()>0,'Model catalog is empty'
    assert await page.locator('select[name=model] option[value="__custom__"]').count()==1,'Custom model option missing'
    assert await page.locator('.model-custom input').count()==1,'Custom model field missing'
    assert await page.locator('textarea[name=competitors]').count()==1,'Competitor URL field missing'
    # Dynamic is the default choice, so its ceiling shows and the fixed-effort control hides.
    assert await page.locator('select[name=model] option[value=dynamic]').count()==1,'Dynamic model option missing'
    assert await page.locator('select[name=model]').input_value()=='dynamic','Dynamic is not the default model'
    assert await page.locator('select[name=model_max]').is_visible(),'Highest model allowed is hidden'
    assert not await page.locator('select[name=effort]').is_visible(),'Reasoning effort shows next to Dynamic'
    assert not await page.locator('#competitors-field').is_visible(),'Competitor URLs show outside benchmark mode'
    await page.select_option('select[name=model]','claude-opus-5')
    assert await page.locator('select[name=effort]').is_visible(),'Reasoning effort stays hidden for a fixed model'
    assert not await page.locator('select[name=model_max]').is_visible(),'Ceiling shows for a fixed model'
    await page.select_option('select[name=model]','dynamic')
    extras=page.locator('#mission-form details')
    assert await extras.count()==1,'Extra settings section missing'
    assert not await extras.first.get_attribute('open'),'Extra settings open on a new mission'
    assert await page.locator('select[name=mode] option[value=benchmark]').count()==1,'Benchmark mode missing'
   if route=='findings':
    assert await page.locator('#finding-sort').count()==1,'Findings sort control is missing'
    assert await page.locator('#finding-owner').count()==1,'Assignment filter is missing'
    if await page.locator('#finding-list .finding').count():
     assert await page.locator('#finding-list [data-done]').count()>0,'Done checkbox is missing'
     assert await page.locator('#finding-list [data-replay]').count()>0,'Recheck button is missing'
     assert await page.locator('#finding-list details[data-topic]').count()>0,'Topic sections are missing'
   if route=='runs':
    heads=[h.strip() for h in await page.locator('table th').all_inner_texts()]
    assert not heads or 'AI' in heads,f'AI column missing from {heads}'
    assert not heads or 'SCORE' in [h.upper() for h in heads],f'Score column missing from {heads}'
    first=page.locator('table tbody tr td a').first
    if await first.count():
     await first.click();await page.wait_for_selector('h1')
     if await page.locator('video').count():
      assert await page.locator('#video-speed').input_value()=='2','Playback speed does not default to 2x'
      assert await page.evaluate('document.querySelector("video").playbackRate')==2,'Video is not playing at the selected speed'
     await open_view(page,'runs',base)
   if route in ['overview','missions','settings']:await page.screenshot(path=str(output/f'ui-{route}.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844});await open_view(page,'missions',base)
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile overflow'
  assert await page.locator('#workspace').is_visible(),'Workspace picker is hidden on mobile'
  await page.screenshot(path=str(output/'ui-mobile.png'),full_page=True)
  print('UI pages checked. JS errors:',errors)
  assert not errors
  await b.close()
if __name__=='__main__':asyncio.run(main())
