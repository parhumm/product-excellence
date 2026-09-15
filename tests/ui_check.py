import asyncio,json,os,re,httpx
from pathlib import Path
from playwright.async_api import async_playwright
from tests.browser_helpers import open_view
async def scenario_builder(page):
 """The scenario section: every step kind, both spellings, and an unusable YAML that stays put."""
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
 await page.locator('#scenario-more > summary').click()
 await page.locator('#scenario-presets summary').click()
 await page.wait_for_selector('#preset-body [data-preset]')
 assert await page.locator('#preset-body .preset').count()==12,'The twelve shipped journeys are not listed'
 await page.locator('#preset-body [data-preset]').first.click()
 await page.wait_for_selector('#scenario-steps .step')
 assert await page.locator('#scenario-steps input.ph').count()>0,'Unreplaced placeholders are not marked'
 assert 'steps' in await page.locator('#scenario-summary').inner_text(),'The scenario summary reports no steps'
 assert 'Save and run' in await page.locator('#mission-form [name=run]').inner_text(),'The run button lost its label'
 # Blanks are listed once each, they disable saving, and filling one replaces it everywhere.
 await page.wait_for_selector('#scenario-blanks [data-blank]')
 assert 'blanks left' in await page.locator('#scenario-summary').inner_text(),'The blanks still to fill are not counted'
 assert await page.locator('#mission-form button[type=submit]').first.is_disabled(),'A mission with blanks can still be saved'
 blank=page.locator('#scenario-blanks [data-blank]').first
 name=await blank.get_attribute('data-blank')
 before=await page.locator('#scenario-blanks [data-blank]').count()
 await blank.fill('Filled by the check');await blank.blur()
 await page.wait_for_function("n => document.querySelectorAll('#scenario-blanks [data-blank]').length === n - 1",arg=before)
 assert name not in await page.locator('#scenario-steps').inner_html(),'A filled blank is still in the steps'
 # Every step kind, event operation and oracle is reachable from the first row.
 first=page.locator('#scenario-steps .step').first
 for kind in ['goal','manual','event','check','hold']:
  await first.locator('select[data-act=kind]').select_option(kind)
  assert await page.locator(f'#scenario-steps .step >> nth=0 >> select[data-act=kind]').input_value()==kind,f'Step kind {kind} did not stay selected'
 await first.locator('select[data-act=kind]').select_option('event')
 for operation in ['network','speed','delay_ms','wait','home','kill','back','relaunch','deep_link','open_notification']:
  await first.locator('select[data-act=event-kind]').select_option(operation)
  assert await first.locator('select[data-act=event-kind]').input_value()==operation,f'Event {operation} is not offered'
 await first.locator('select[data-act=kind]').select_option('check')
 for fact in ['text','text_absent','screen','playing','notification','no_crash']:
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
 # The toggle lands after the click, so wait for the steps to leave rather than for text that may be left over.
 await page.wait_for_selector('#scenario-steps',state='hidden')
 await page.wait_for_function("document.querySelector('#scenario-yaml').value.includes('- ')")
 assert not await page.locator('#scenario-lines').is_visible(),'The readable list stays visible while the YAML editor is open'
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
 # The readable list is the same scenario spelled differently, so it never falls behind the rows.
 assert await page.locator('#scenario-lines li').count()==2,'The readable list does not match the rows'
 await page.locator('#edit-steps').click()
 assert await page.locator('#scenario-lines').is_visible(),'Leaving the row editor does not bring the readable list back'
 assert not await page.locator('#scenario-steps').is_visible(),'The rows stay on screen after leaving the editor'

# --- idea first ---------------------------------------------------------------
SUGGESTED=[
 {'title':'Offline playback survives a relaunch','why':'Whether a downloaded title still plays with no connection.',
  'caveat':'A downloaded title on the device','mode':'journey','pillars':['functionality','ux_ui'],
  'shape':'scenario','journey':'Download, go offline, relaunch, play.','goal':'As a subscriber, play a downloaded title with the device offline.',
  'steps':[{'goal':'Open the downloads list'},{'manual':'Sign in on the device','ask':'one-time code','timeout':300},
           {'event':{'delay_ms':0}},{'check':{'playing':True,'policy':'confirmed','within':20}}]},
 {'title':'The download finishes on a slow connection','why':'Whether a shaped connection still completes a download.',
  'caveat':'','mode':'journey','pillars':['functionality'],'shape':'goal','journey':'','goal':'As a subscriber, finish a download on a slow connection.','steps':[]},
 {'title':'Downloads survive a reload','why':'Whether the saved list is still there on the second look.',
  'caveat':'','mode':'journey','pillars':['functionality'],'shape':'scenario','journey':'Open the list, reload, look again.',
  'goal':'As a subscriber, find the downloads list again after a reload.',
  'steps':[{'goal':'Open the downloads list'},{'check':{'text':'Downloads','within':10}}]},
 {'title':'The plans page names the renewal','why':'Whether a customer can read the renewal before paying.',
  'caveat':'','mode':'journey','pillars':['cro'],'shape':'goal','journey':'',
  'goal':'As a visitor, find the plans and read the renewal terms. Stop before any payment control.','steps':[]}]
def answered(items,rejected=()):return {'suggestions':items,'rejected':list(rejected),
                                       'usage':{'provider':'codex','model_reported':'gpt-5-mini'}}
async def stub(page,payload,status=200):
 """Deterministic answers for the one endpoint the idea flow calls. No AI quota is spent here."""
 await page.unroute('**/api/missions/suggest')
 await page.route('**/api/missions/suggest',lambda route:asyncio.ensure_future(
  route.fulfill(status=status,content_type='application/json',body=json.dumps(payload))))
async def mission_ideas(page):
 """Idea, suggestions, application, revision and undo, with the worker's answers stubbed."""
 assert await page.locator('#idea-box').get_attribute('open') is not None,'A new mission does not open on the idea'
 assert not await page.locator('#draft-section').is_visible(),'A new mission shows a draft before there is one'
 assert not await page.locator('#mission-suggestions').is_visible(),'The suggestion panel shows before anything was asked'
 # The starters come from the shipped journeys already loaded for the builder.
 await page.wait_for_selector('#idea-starters [data-starter]')
 await page.locator('#idea-starters [data-starter]').first.click()
 assert (await page.locator('#mission-idea').input_value()).strip(),'A starter left the idea box empty'
 # Writing it yourself is always reachable, worker or no worker.
 await page.locator('#idea-manual').click()
 assert await page.locator('#draft-section').is_visible(),'Write it yourself does not reveal the mission'
 assert await page.locator('#scenario-section').is_visible(),'Write it yourself does not reveal the steps'
 assert await page.locator('#idea-box').get_attribute('open') is None,'The idea stays open once the mission is on screen'
 # Everything a run is configured with lives behind one disclosure; open it and leave it open.
 await page.locator('#run-settings > summary').click()
 assert await page.locator('select[name=browser]').is_visible(),'Run settings do not open on their disclosure'
 # A budget the person already raised is never cut back by an applied suggestion.
 await page.fill('#mission-form [name=max_steps]','30')
 await page.fill('#mission-form [name=max_seconds]','900')
 await page.select_option('#mission-form [name=browser]','firefox')
 await stub(page,answered(SUGGESTED,['Mission 5: step 2: a step holds one instruction']))
 await page.locator('#idea-box > summary').click()
 await page.fill('#mission-idea','Does a downloaded title still play when the phone loses its connection?')
 await page.locator('#idea-suggest').click()
 await page.wait_for_selector('#mission-suggestions .suggestion')
 assert await page.locator('#mission-suggestions .suggestion').count()==4,'Four missions were not offered'
 # Goals and scenarios arrive under their own headings, goals first.
 headings=await page.locator('#mission-suggestions .suggesthead').all_inner_texts()
 assert headings==['Let the worker find its own way','Run these exact steps'],f'The groups are wrong: {headings}'
 # A mission the worker got wrong is named beside the ones that survived, not instead of them.
 panel=await page.locator('#mission-suggestions').inner_text()
 assert 'did not fit the contract' in panel and 'step 2' in panel,'A dropped mission is not reported'
 # Two goals come first, then the two scenarios, whatever order the worker sent them in.
 cards=page.locator('#mission-suggestions .suggestion')
 offline=cards.nth(2)
 assert await offline.locator('.steplines li').count()==4,'A card hides some of the steps it would apply'
 first=await offline.inner_text()
 assert 'Chromium' in first,'A shaped step gives no Chromium notice'
 assert 'operator' in first,'A manual step gives no operator notice'
 assert 'Needs first' in first,'The card drops the precondition the worker named'
 assert 'Use this scenario' in first,'A scenario card does not say what it applies'
 goalcard=await cards.nth(0).inner_text()
 assert 'No steps' in goalcard,'A goal-only suggestion pretends to have steps'
 assert 'Use this goal' in goalcard,'A goal card does not say what it applies'
 await offline.locator('[data-apply]').click()
 await page.wait_for_selector('#scenario-lines li')
 assert await page.locator('#mission-form [name=name]').input_value()=='Offline playback survives a relaunch','The title did not become the mission name'
 assert 'downloaded title' in await page.locator('#mission-form [name=goal]').input_value(),'The goal did not arrive'
 assert await page.locator('#mission-form [name=mode]').input_value()=='journey','The mode did not arrive'
 assert await page.locator('input[name=pillars][value=functionality]').is_checked(),'Functionality is not selected for a scenario'
 assert await page.locator('#mission-form [name=browser]').input_value()=='chromium','A zero-delay step did not select Chromium'
 assert await page.locator('#mission-form [name=max_steps]').input_value()=='30','An applied suggestion lowered a larger action budget'
 assert await page.locator('#scenario-lines li').count()==4,'The applied steps are not the steps the card showed'
 lines=await page.locator('#scenario-lines').inner_text()
 assert 'asks for one-time code' in lines,'The value an operator supplies is not named in the readable list'
 summary=await page.locator('#run-summary').inner_text()
 assert 'chromium' in summary and '15 min' in summary and '30 actions' in summary,f'The run settings summary is wrong: {summary}'
 # One slot of undo, and it puts back every field the suggestion touched.
 await page.locator('#undo-ai').click()
 assert await page.locator('#mission-form [name=browser]').input_value()=='firefox','Undo did not put the browser back'
 assert await page.locator('#scenario-lines li.nosteps').count()==1,'Undo did not put the empty scenario back'
 assert await page.locator('#undo-ai').is_hidden(),'Undo stays offered after it was used'
 await offline.locator('[data-apply]').click()
 await page.wait_for_selector('#scenario-lines li:not(.nosteps)')
 # A revision returns one whole mission, and Undo reaches back to the one before it.
 await stub(page,answered([{**SUGGESTED[0],'title':'Offline playback survives two relaunches','mode':'explore',
   'pillars':['functionality'],'steps':SUGGESTED[0]['steps'][:2]}]))
 await page.fill('#mission-revise','Relaunch the app twice instead of once.')
 await page.locator('#revise-go').click()
 await page.wait_for_selector('#mission-suggestions .suggestion [data-apply]')
 assert await page.locator('#mission-suggestions .suggestion').count()==1,'A revision offered more than one mission'
 await page.locator('#mission-suggestions [data-apply]').first.click()
 await page.wait_for_function("document.querySelectorAll('#scenario-lines li').length===2")
 assert await page.locator('#mission-form [name=mode]').input_value()=='explore','The revision did not carry its mode'
 await page.locator('#undo-ai').click()
 assert await page.locator('#scenario-lines li').count()==4,'Undo did not restore the mission the revision replaced'
 assert await page.locator('#mission-form [name=mode]').input_value()=='journey','Undo did not restore the mode'
 # A failed revision changes nothing and keeps what the person typed.
 await stub(page,{'detail':'The AI worker could not suggest a mission'},status=502)
 await page.fill('#mission-revise','Add a check that the title still plays.')
 await page.locator('#revise-go').click()
 await page.wait_for_selector('#revise-error:not(:empty)')
 assert await page.locator('#scenario-lines li').count()==4,'A failed revision changed the mission anyway'
 assert await page.locator('#mission-revise').input_value()=='Add a check that the title still plays.','A failed revision discarded the instruction'
 assert not await page.locator('#mission-form button[type=submit]').first.is_disabled(),'Saving stays blocked after a failed revision'
 # Text that is not applied is not a scenario, so nothing may replace the steps while it sits there.
 await stub(page,answered([SUGGESTED[0]]))
 await page.locator('#scenario-more > summary').click()
 await page.locator('#scenario-yaml-box summary').click()
 await page.wait_for_selector('#scenario-steps',state='hidden')
 await page.wait_for_function("document.querySelector('#scenario-yaml').value.includes('- ')")
 await page.fill('#scenario-yaml','- goal: Not applied yet')
 await page.locator('#revise-go').click()
 await page.wait_for_selector('#revise-error:not(:empty)')
 assert 'Apply your YAML' in await page.locator('#revise-error').inner_text(),'Unapplied YAML did not stop the revision'
 assert await page.locator('#mission-form button[type=submit]').first.is_disabled(),'A mission with unapplied YAML can still be saved'
 await page.locator('#yaml-apply').click()
 await page.wait_for_function("document.querySelectorAll('#scenario-steps .step').length===1")
 await page.locator('#scenario-yaml-box summary').click()
 await page.locator('#scenario-more > summary').click()
 assert not await page.locator('#mission-form button[type=submit]').first.is_disabled(),'Applied YAML still blocks saving'
 # Nothing on this page may answer twice to the same id or name.
 ids=await page.evaluate("[...document.querySelectorAll('#mission-form [id]')].map(e=>e.id)")
 assert len(ids)==len(set(ids)),'The mission form repeats an element id'
 await page.unroute('**/api/missions/suggest')

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
  for route in ['overview','missions','journeys','new','runs','findings','benchmark','compare','network','settings']:
   await open_view(page,route,base)
   # Every view belongs to one website, so the workspace picker is always usable.
   assert await page.locator('#workspace option').count()>0,f'Workspace picker is empty on {route}'
   if route=='journeys':
    await page.wait_for_selector('.journey')
    assert await page.locator('.journey').count()==12,'The journey gallery does not list the twelve shipped journeys'
    assert await page.locator('.journey .toolbar a[href^="#new/"]').count()==12,'A journey card has no way to open it'
    await page.fill('#journey-search','checkout')
    await page.wait_for_function("document.querySelectorAll('.journey:not([hidden])').length < 12")
    assert await page.locator('.journey:not([hidden])').count()>0,'Searching hid every journey'
    await page.fill('#journey-search','')
    # A journey link opens the mission already drafted, so there is no idea to write first.
    link=await page.locator('.journey .toolbar a[href^="#new/"]').first.get_attribute('href')
    await page.goto(base.rstrip('/')+'/'+link)
    await page.wait_for_selector('#scenario-steps .step')
    assert await page.locator('#draft-section').is_visible(),'A journey link does not open its mission'
    assert await page.locator('#idea-box').get_attribute('open') is None,'A journey link opens on the idea instead of the mission'
    assert (await page.locator('#mission-form [name=goal]').input_value()).strip(),'A journey link left the goal empty'
    await open_view(page,'journeys',base)
   if route=='new':
    # The idea comes first, so everything else on this form is reached through it.
    site_option=page.locator('select[name=target_id] option').filter(has_text='Website').first
    if await site_option.count():await page.select_option('select[name=target_id]',await site_option.get_attribute('value'))
    await mission_ideas(page)
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
    extras=page.locator('#draft-section > details:not(#run-settings)')
    assert await extras.count()==1,'Extra settings section missing'
    assert not await extras.first.get_attribute('open'),'Extra settings open on a new mission'
    assert await page.locator('select[name=mode] option[value=benchmark]').count()==1,'Benchmark mode missing'
    # One vocabulary, two targets: the builder shows for a website too, minus the saved device state.
    assert await page.locator('#scenario-section').is_visible(),'The scenario builder is hidden for a website mission'
    assert not await page.locator('#start-snapshot').is_visible(),'A saved device state is offered for a website mission'
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
  # The narrowest phone still in use, on the view with the most controls.
  await page.set_viewport_size({'width':320,'height':640});await open_view(page,'new',base)
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'The mission form overflows a 320px screen'
  await page.set_viewport_size({'width':390,'height':844});await open_view(page,'missions',base)
  await page.screenshot(path=str(output/'ui-mobile.png'),full_page=True)
  print('UI pages checked. JS errors:',errors)
  assert not errors
  await b.close()
if __name__=='__main__':asyncio.run(main())
