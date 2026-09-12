import argparse,asyncio
from pathlib import Path
from playwright.async_api import async_playwright
p=argparse.ArgumentParser();p.add_argument('--url',default='https://example.com');p.add_argument('--output',default='data/test-session.json');a=p.parse_args()
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=False);c=await b.new_context();page=await c.new_page();await page.goto(a.url)
  await asyncio.to_thread(input,'Sign into your TEST account in this browser, then press Enter here to save the session. ')
  path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);await c.storage_state(path=str(path));path.chmod(0o600);await b.close()
  print('Import this JSON through Settings > Test personas:',path.resolve())
asyncio.run(main())
