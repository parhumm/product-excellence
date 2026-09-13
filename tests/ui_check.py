import asyncio,os,re,httpx
from pathlib import Path
from playwright.async_api import async_playwright
from tests.browser_helpers import open_view
async def main():
 base=os.environ.get('PEX_BASE_URL','http://127.0.0.1:8741')
 output=Path(os.environ.get('PEX_UI_ARTIFACTS','data'));output.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  if os.environ.get('PEX_ANDROID_AVD'):
   snapshot=httpx.get(base+'/api/state',timeout=10).json();native=next((t for t in snapshot.get('targets',[]) if t.get('type')=='android'),None)
   assert native,'Android smoke data is missing before the UI check'
   await page.goto(base);await page.evaluate("id => localStorage.setItem('pex.workspace', id)",native['project_id'])
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
    native_option=page.locator('select[name=target_id] option').filter(has_text='Android app').first
    if await native_option.count():
     await page.select_option('select[name=target_id]',await native_option.get_attribute('value'))
     assert await page.locator('select[name=build]').is_visible(),'Android build selector is hidden'
     assert await page.locator('input[name=device]').is_visible(),'Android device selector is hidden'
     assert await page.locator('select[name=browser]').is_disabled(),'Browser remains enabled for an Android mission'
     assert await page.locator('input[name=pillars][value=seo_aeo]').is_disabled(),'SEO/AEO remains enabled for Android'
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
     if 'Android' in await page.locator('.pagehead').inner_text():
      assert await page.get_by_role('heading',name='App evidence').count()==1,'Android run is labeled as browser evidence'
      for label in ['Launch time','Jank','Memory (PSS)','Crashes and errors']:
       assert await page.get_by_text(label,exact=True).count()>0,f'{label} is missing from Android evidence'
      assert await page.get_by_role('link',name=re.compile('App log')).count()>0,'Android log evidence is missing'
     if await page.locator('video').count():
      assert await page.locator('#video-speed').input_value()=='2','Playback speed does not default to 2x'
      assert await page.evaluate('document.querySelector("video").playbackRate')==2,'Video is not playing at the selected speed'
     await open_view(page,'runs',base)
   if route=='settings' and os.environ.get('PEX_ANDROID_AVD'):
    assert await page.locator('input[data-apk]').count()>0,'APK upload control is missing'
    assert await page.locator('[data-archive-build]').count()>0,'Build archive control is missing'
    assert await page.locator('[data-remove-build]').count()>0,'Local APK removal control is missing'
   if route=='compare' and os.environ.get('PEX_ANDROID_AVD'):
    await page.locator('#compare-form button').click();await page.wait_for_selector('#comparison-result .notice')
    assert 'App build changed' in await page.locator('#comparison-result').inner_text(),'Android build change is not labeled'
   if route in ['overview','missions','settings']:await page.screenshot(path=str(output/f'ui-{route}.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844});await open_view(page,'missions',base)
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile overflow'
  assert await page.locator('#workspace').is_visible(),'Workspace picker is hidden on mobile'
  await page.screenshot(path=str(output/'ui-mobile.png'),full_page=True)
  print('UI pages checked. JS errors:',errors)
  assert not errors
  await b.close()
if __name__=='__main__':asyncio.run(main())
