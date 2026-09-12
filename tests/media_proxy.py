import asyncio,json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch();ctx=await b.new_context();await ctx.add_init_script(path='engine/collect.js');page=await ctx.new_page()
        await page.goto('http://127.0.0.1:8741/demo')
        await page.evaluate('''async()=>{const canvas=document.createElement('canvas');canvas.width=320;canvas.height=180;const ctx=canvas.getContext('2d');let i=0;setInterval(()=>{ctx.fillStyle=i++%2?'#357451':'#335374';ctx.fillRect(0,0,320,180)},40);const video=document.createElement('video');video.muted=true;video.srcObject=canvas.captureStream(25);document.body.append(video);await new Promise(r=>setTimeout(r,100));await video.play();}''')
        await page.wait_for_timeout(1200);a=await page.evaluate('window.__pexSnapshot()');assert a['video'][0]['startup_ms'] is not None and a['video'][0]['width']==320
        await page.evaluate("document.querySelector('video').dispatchEvent(new Event('waiting'))")
        await page.wait_for_timeout(200);a=await page.evaluate('window.__pexSnapshot()');assert a['video'][0]['stall_ms']>=180 and a['video'][0]['stall_count']==1
        await page.evaluate("document.querySelector('video').pause()")
        a=await page.evaluate('window.__pexSnapshot()');assert a['video'][0]['waiting_at'] is None
        await page.evaluate("dispatchEvent(new CustomEvent('pex:player',{detail:{type:'quality_change',bitrate_kbps:1500,resolution:'320x180'}}))")
        a=await page.evaluate('window.__pexSnapshot()');assert a['player_events'][0]['bitrate_kbps']==1500
        await b.close();print('Real HTML video startup, controlled stall accounting and custom player telemetry passed',flush=True)
    hits=[]
    async def proxy(reader,writer):
        upstream=None
        try:
            head=await reader.readuntil(b'\r\n\r\n');request=head.decode().split('\r\n')[0]
            if request!='CONNECT api.ipify.org:443 HTTP/1.1':writer.write(b'HTTP/1.1 403 Forbidden\r\n\r\n');await writer.drain();return
            hits.append(request);rr,ww=await asyncio.open_connection('api.ipify.org',443);upstream=ww
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n');await writer.drain()
            async def relay(r,w):
                while data:=await r.read(65536):w.write(data);await w.drain()
            ts=[asyncio.create_task(relay(reader,ww)),asyncio.create_task(relay(rr,writer))]
            done,pending=await asyncio.wait(ts,return_when=asyncio.FIRST_COMPLETED)
            for t in pending:t.cancel()
        finally:
            writer.close()
            if upstream:upstream.close()
    server=await asyncio.start_server(proxy,'127.0.0.1',8788)
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8741/api',headers={'X-PEX-Request':'1'},timeout=30) as c:
        r=await c.post('/egress',json={'name':'Temporary verification proxy','server':'http://127.0.0.1:8788'});r.raise_for_status();id=r.json()['id']
        try:
            r=await c.post('/egress/'+id+'/verify');r.raise_for_status();assert r.json()['verified_ip'] and hits
            print('Real HTTP CONNECT proxy and public IP verification passed',flush=True)
        finally:await c.delete('/egress/'+id)
    server.close();await server.wait_closed()
asyncio.run(main())
