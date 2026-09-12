import asyncio,json,uuid
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
from engine.ai import call,ACTION_SCHEMA
from engine import pricing
from tests.browser_helpers import open_view

def usage_line(label,usage):
 """Each smoke check names the model the CLI actually answered with and what it cost to estimate."""
 return (f"{label} · {usage.get('model_reported') or usage.get('model_requested') or 'unknown'}"
         f" · {pricing.tokens(usage.get('input_tokens'))} in / {pricing.tokens(usage.get('cached_tokens'))} cached"
         f" / {pricing.tokens(usage.get('output_tokens'))} out · {pricing.money(usage.get('est_cost_usd'))}")

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000})
  await open_view(page,'new')
  name='UI acceptance '+uuid.uuid4().hex[:8]
  await page.locator('[name=name]').fill(name);await page.locator('[name=url]').fill('http://127.0.0.1:8741/demo');await page.locator('[name=goal]').fill('Audit local test page')
  await page.locator('[name=mode]').select_option('audit');await page.locator('[name=provider]').select_option('none');await page.get_by_role('button',name='Save mission',exact=True).click();await page.wait_for_url('**/#missions')
  await page.get_by_text(name,exact=True).wait_for(state='visible')
  await page.add_script_tag(path='static/vendor/axe-core/axe.min.js')
  a=await page.evaluate('async()=>await axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}})')
  print('Console accessibility violations',[(v['id'],v['impact']) for v in a['violations']],flush=True)
  assert not a['violations']
  await browser.close()
 # This tests the alternative subscription adapter on a bounded fixed observation.
 result,usage=await call('claude','Return a finish action with outcome success and reason "adapter smoke test". target and value are empty strings.',ACTION_SCHEMA,timeout=240,model='claude-opus-5',effort='high')
 assert result['type']=='finish' and result['outcome']=='success'
 print(usage_line('Claude Code subscription adapter verified on Opus 5 at high effort',usage),flush=True)
 # Journeys send a screenshot, which uses the CLI's streaming input and output path.
 shot=Path('data/ui-missions.png')
 image,usage=await call('claude','This screenshot shows a local console. Return a finish action with outcome success and a one-sentence reason describing what you see. target and value are empty strings.',ACTION_SCHEMA,image=shot,timeout=240,model='claude-opus-5',effort='high')
 assert image['type']=='finish' and image['reason']
 print(usage_line('Claude Code subscription adapter verified with screenshot input',usage),flush=True)
 print('  Model described the screenshot as:',image['reason'][:120],flush=True)
 # A worker without quota is an account state, not a defect, so report it plainly instead of failing the script.
 try:
  codex,usage=await call('codex','Return a finish action with outcome success and reason "adapter smoke test". target and value are empty strings.',ACTION_SCHEMA,timeout=240,effort='high')
 except RuntimeError as e:
  text=str(e).lower()
  if not any(w in text for w in ('credit','quota','usage limit','rate limit')): raise
  print('Codex subscription adapter NOT verified. The ChatGPT workspace reported:',str(e).strip().splitlines()[-1],flush=True)
 else:
  assert codex['type']=='finish'
  print(usage_line('Codex subscription adapter verified at high effort',usage),flush=True)
asyncio.run(main())
