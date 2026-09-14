import asyncio,os,re,httpx
from pathlib import Path
from playwright.async_api import async_playwright
from tests.browser_helpers import open_view
async def scenario_builder(page):
 """The Android scenario section: every step kind, both spellings, and an unusable YAML that stays put."""
 assert await page.locator('#scenario-section').is_visible(),'The scenario builder is hidden for an Android mission'
 assert await page.locator('input[name=start_state][value=fresh]').is_checked(),'Fresh app data is not the default start state'
 assert not await page.locator('#snapshot-field').is_visible(),'The saved-state picker shows without that start state'
 # The snapshot list is local, so the option is only offered once this Mac has a usable one.
 await page.wait_for_selector('#snapshot-note:not(:empty)',state='attached')
 saved=page.locator('input[name=start_state][value=snapshot]')
 if await saved.is_disabled():assert (await page.locator('#snapshot-note').text_content() or '').strip(),'A disabled saved-state option gives no reason'
 else:
  await saved.check()
  assert await page.locator('#snapshot-field').is_visible(),'The saved-state picker stays hidden after choosing it'
  await page.check('input[name=start_state][value=fresh]')
 # A shipped journey fills the rows, and every placeholder it leaves is visible as one.
 await page.locator('#scenario-presets summary').click()
 await page.wait_for_selector('#preset-body [data-preset]')
 assert await page.locator('#preset-body .preset').count()==5,'The five shipped journeys are not listed'
 await page.locator('#preset-body [data-preset]').first.click()
 await page.wait_for_selector('#scenario-steps .step')
 assert await page.locator('#scenario-steps input.ph').count()>0,'Unreplaced placeholders are not marked'
 assert 'steps' in await page.locator('#scenario-summary').inner_text(),'The scenario summary reports no steps'
 assert 'Save and run' in await page.locator('#mission-form [name=run]').inner_text(),'The run button lost its label'
 # Every step kind, event operation and oracle is reachable from the first row.
 first=page.locator('#scenario-steps .step').first
 for kind in ['goal','manual','event','check','hold']:
  await first.locator('select[data-act=kind]').select_option(kind)
  assert await page.locator(f'#scenario-steps .step >> nth=0 >> select[data-act=kind]').input_value()==kind,f'Step kind {kind} did not stay selected'
 await first.locator('select[data-act=kind]').select_option('event')
 for operation in ['network','speed','delay_ms','wait','home','kill','relaunch','deep_link','open_notification']:
  await first.locator('select[data-act=event-kind]').select_option(operation)
  assert await first.locator('select[data-act=event-kind]').input_value()==operation,f'Event {operation} is not offered'
 await first.locator('select[data-act=kind]').select_option('check')
 for fact in ['text','text_absent','activity','playing','notification','no_crash']:
  await first.locator('select[data-act=oracle-kind]').select_option(fact)
  assert await first.locator('select[data-act=oracle-kind]').input_value()==fact,f'Fact {fact} is not offered'
 await first.locator('select[data-act=oracle-kind]').select_option('text')
 # An unconfirmed expectation can never be required, and the control says so.
 await first.locator('select[data-path="check.policy"]').select_option('unknown')
 assert await first.locator('select[data-path="check.required"]').is_disabled(),'An unknown-policy check can still be made required'
 await first.locator('select[data-path="check.policy"]').select_option('confirmed')
 await first.locator('input[data-path="check.text"]').fill('Now playing')
 steps_before=await page.locator('#scenario-steps .step').count()
 # The rows and the YAML are the same steps; text that does not parse never replaces them.
 await page.locator('#scenario-yaml-box summary').click()
 await page.wait_for_function("document.querySelector('#scenario-yaml').value.includes('- ')")
 assert not await page.locator('#scenario-steps').is_visible(),'The rows stay visible while the YAML editor is open'
 await page.fill('#scenario-yaml','- check: {text: a, playing: true}')
 await page.locator('#yaml-apply').click()
 await page.wait_for_selector('#scenario-yaml-error:not(:empty)')
 assert 'exactly one' in await page.locator('#scenario-yaml-error').inner_text(),'Unusable YAML is not explained'
 assert '- check' in await page.locator('#scenario-yaml').input_value(),'Unusable YAML was discarded instead of kept for editing'
 await page.locator('#scenario-yaml-box summary').click()
 await page.wait_for_function("document.querySelector('#scenario-yaml-error').textContent.includes('not applied')")
 assert await page.locator('#scenario-yaml-box').get_attribute('open') is not None,'Unapplied YAML let the rows come back'
 assert '- check' in await page.locator('#scenario-yaml').input_value(),'Reopening the editor discarded the unapplied edits'
 await page.fill('#scenario-yaml','- goal: Open the downloads list\n- check:\n    playing: true\n    within: 20\n')
 await page.locator('#yaml-apply').click()
 await page.wait_for_function("document.querySelectorAll('#scenario-steps .step').length===2")
 await page.locator('#scenario-yaml-box summary').click()
 await page.wait_for_selector('#scenario-steps',state='visible')
 assert await page.locator('#scenario-steps .step').count()==2,'The applied YAML is not what the rows show'
 assert steps_before>2,'The shipped journey loaded fewer steps than expected'
 # Reordering and removal keep the list honest.
 await page.locator('#scenario-steps .step >> nth=1 >> button[data-act=up]').click()
 assert await page.locator('#scenario-steps .step >> nth=0 >> select[data-act=kind]').input_value()=='check','Moving a step up did not reorder the list'
 await page.locator('#scenario-steps .step >> nth=0 >> button[data-act=del]').click()
 assert await page.locator('#scenario-steps .step').count()==1,'Removing a step did not shorten the list'
 await page.locator('#add-step').click()
 assert await page.locator('#scenario-steps .step').count()==2,'Adding a step did not lengthen the list'

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
    extras=page.locator('#mission-form > details')
    assert await extras.count()==1,'Extra settings section missing'
    assert not await extras.first.get_attribute('open'),'Extra settings open on a new mission'
    assert await page.locator('select[name=mode] option[value=benchmark]').count()==1,'Benchmark mode missing'
    site_option=page.locator('select[name=target_id] option').filter(has_text='Website').first
    if await site_option.count():await page.select_option('select[name=target_id]',await site_option.get_attribute('value'))
    assert not await page.locator('#scenario-section').is_visible(),'The scenario builder shows for a website mission'
    native_option=page.locator('select[name=target_id] option').filter(has_text='Android app').first
    if await native_option.count():
     await page.select_option('select[name=target_id]',await native_option.get_attribute('value'))
     assert await page.locator('select[name=build]').is_visible(),'Android build selector is hidden'
     assert await page.locator('input[name=device]').is_visible(),'Android device selector is hidden'
     assert await page.locator('select[name=browser]').is_disabled(),'Browser remains enabled for an Android mission'
     assert await page.locator('input[name=pillars][value=seo_aeo]').is_disabled(),'SEO/AEO remains enabled for Android'
     await scenario_builder(page)
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
   if route=='settings':
    # The designated device and its saved states are stated whether or not this Mac has one configured.
    section=page.locator('#android-settings')
    assert await section.count()==1,'The Android device section is missing from Settings'
    told=await section.inner_text()
    assert 'manual step' in told,'Settings does not say whether an operator can finish a manual step'
    assert 'entitlement' in told,'Settings does not state what a saved state cannot restore'
    assert await section.locator('#snapshot-form [name=name]').count()==1,'The saved-state name field is missing'
    if not await section.locator('#snapshot-form button').is_disabled():
     await section.locator('#snapshot-form button').click()
     await page.wait_for_selector('#snapshot-form .error:not(:empty)')
     assert 'Name this state' in await section.locator('#snapshot-form .error').inner_text(),'An unnamed save gives no reason'
   if route=='settings' and os.environ.get('PEX_ANDROID_AVD'):
    assert await page.locator('input[data-apk]').count()>0,'APK upload control is missing'
    assert await page.locator('[data-archive-build]').count()>0,'Build archive control is missing'
    assert await page.locator('[data-remove-build]').count()>0,'Local APK removal control is missing'
   if route=='compare' and os.environ.get('PEX_ANDROID_AVD'):
    await page.locator('#compare-form button').click();await page.wait_for_selector('#comparison-result .section')
    basis=await page.locator('#comparison-result').inner_text()
    assert 'Conditions' in basis,'The comparison does not say what conditions it compared'
    assert 'Reproduction' in basis,'The comparison does not say whether it can confirm a reproduction'
   if route in ['overview','missions','settings']:await page.screenshot(path=str(output/f'ui-{route}.png'),full_page=True)
  await page.set_viewport_size({'width':390,'height':844});await open_view(page,'missions',base)
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile overflow'
  assert await page.locator('#workspace').is_visible(),'Workspace picker is hidden on mobile'
  await page.screenshot(path=str(output/'ui-mobile.png'),full_page=True)
  print('UI pages checked. JS errors:',errors)
  assert not errors
  await b.close()
if __name__=='__main__':asyncio.run(main())
