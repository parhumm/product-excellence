import asyncio
from engine import netem
from playwright.async_api import async_playwright
async def main():
    assert (await netem.status())['ok']
    profile={'latency_ms':30,'jitter_ms':5,'loss_pct':.5,'up_mbps':10,'down_mbps':0,'offline':False,'reorder_pct':5,'duplicate_pct':1}
    conn=await netem.start(profile,'chromium',60)
    try:
        assert any(q['kind']=='netem' for q in conn['applied']),conn
        async with async_playwright() as p:
            b=await p.chromium.connect(conn['endpoint']);page=await b.new_page();await page.goto('https://example.com',wait_until='domcontentloaded',timeout=45000)
            assert 'example.com' in page.url
            await b.close()
        print('Live Linux loss/jitter/reordering/duplication configuration and browser navigation passed',flush=True)
    finally:await netem.stop()
    assert not (await netem.status())['busy']
asyncio.run(main())
