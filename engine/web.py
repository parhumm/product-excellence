"""A browser page wearing the surface engine/scenario.py already drives on a device.

Method names and return shapes match engine/android.py Device, so one interpreter runs
the same ordered scenario against a native app or a website.
"""
from . import store
from .policy import allowed_url
from .scenario import ScenarioError

# Chromium's own throttling, as download Mbps, upload Mbps and added latency.
# This shapes the browser, not the link: it is configuration evidence, not throughput.
SPEEDS={'gsm':(0.014,0.014,650),'edge':(0.24,0.2,420),'umts':(0.384,0.128,200),'lte':(50,10,20),'full':(0,0,0)}

class Browser:
    def __init__(self,page,context,cdp,profile,run,mission,hide,supplied,tabs,relay=None,faults=None):
        self.page=page;self.context=context;self.cdp=cdp;self.profile=profile
        self.run=run;self.mission=mission;self.hide=hide;self.supplied=supplied;self.tabs=tabs
        # The relay this context was pointed at, and the run's own list of requested faults.
        self.relay=relay;self.faults=faults if faults is not None else []
        # A page belongs to no package; the text oracle's "another app in front" guard never fires.
        self.app={'package':''}

    async def sample(self):
        """One cheap read of what is in front: the page address and its readable text. Never raises."""
        found={'at':store.now(),'activity':self.page.url,'package':'','labels':''}
        try:found['text']=self.hide(await self.page.evaluate('()=>document.body?document.body.innerText.slice(0,14000):""'))
        except Exception as error:found['error']='Page text unavailable: '+str(error)[:200]
        found['activity']=self.page.url
        return found

    def log_cursor(self):
        """Where the collected console stands now, so a later check only sees what followed it."""
        return len(self.run['console'])

    def crash_since(self,cursor):
        """On the web a crash is an uncaught page error; '' when there is none."""
        for entry in self.run['console'][cursor:]:
            if entry.get('kind')=='pageerror':return (entry.get('name','Error')+': '+entry.get('message',''))[:2000]
        return ''

    async def media_state(self):
        """The first media element that has loaded anything, in the shape a MediaSession sample has."""
        return await self.page.evaluate("""()=>{const el=document.querySelector('video,audio');
            if(!el||!el.readyState)return null;
            return {state:el.ended?'stopped':el.paused?'paused':'playing',position:Math.round(el.currentTime*1000),updated:Math.round(performance.now())}}""")

    async def notifications(self):
        """The notifications this page created through the Notification API, recorded by collect.js."""
        recorded=await self.page.evaluate("()=>((window.__pex&&window.__pex.notifications)||[]).map(n=>({title:n.title||'',body:n.body||''}))")
        return [{'key':str(i),'package':'','text':(n['title']+' '+n['body']).strip()} for i,n in enumerate(recorded)]

    async def open_notification(self,text):
        """Click the first recorded notification whose text matches, firing the page's own handler."""
        fired=await self.page.evaluate("""(text)=>{const list=(window.__pex&&window.__pex.notifications)||[];
            const hit=list.find(n=>((n.title||'')+' '+(n.body||'')).includes(text));
            if(!hit)return false;hit.dispatchEvent(new Event('click'));return true}""",text)
        if not fired:raise ScenarioError(f'This page has not created a notification saying "{text[:60]}"')

    def conditions(self,down,up,latency,offline=False):
        return {'offline':offline,'latency':latency,
                'downloadThroughput':down*125000 if down else -1,'uploadThroughput':up*125000 if up else -1}

    async def apply_route(self,route_id,step=None,budget=None):
        """Change the way out mid-run. The context was pointed at the relay, never at a route."""
        if not self.relay:raise ScenarioError('This run was not started with a relay, so it cannot change route')
        # Requested evidence whatever comes of it, so the switch is recorded before it is attempted.
        self.faults.append({'route':route_id})
        return await self.relay.switch(route_id,step,budget)

    async def apply_speed(self,speed='',delay_ms=None,record=True):
        if not self.cdp:raise ScenarioError('Link shaping in the browser needs Chromium')
        down,up,latency=SPEEDS[speed] if speed else (0,0,0)
        if record:self.faults.append({'speed':speed,'delay_ms':delay_ms})
        await self.cdp.send('Network.emulateNetworkConditions',self.conditions(down,up,latency+(delay_ms or 0)))

    async def apply_network(self,mode):
        """offline/restore switch the whole context; wifi and cellular are link shapes."""
        # One operation, one requested fault: the shape a transport switch applies is not a second one.
        self.faults.append({'network':mode})
        if mode=='offline':
            await self.context.set_offline(True)
            if self.cdp:await self.cdp.send('Network.emulateNetworkConditions',self.conditions(0,0,0,offline=True))
            return
        if mode=='restore':
            p=self.profile
            await self.context.set_offline(p['offline'])
            if self.cdp:await self.cdp.send('Network.emulateNetworkConditions',self.conditions(p['down_mbps'],p['up_mbps'],p['latency_ms'],offline=p['offline']))
            return
        await self.apply_speed('full' if mode=='wifi' else 'lte',record=False)

    async def home(self):
        """Another tab in front, so the page goes hidden the way a backgrounded app does."""
        # The runner closes any page it did not open; the None reserves this one before it exists.
        self.tabs.append(None)
        try:other=await self.context.new_page()
        finally:self.tabs.remove(None)
        self.tabs.append(other)
        await other.goto('about:blank');await other.bring_to_front()

    async def background_kill(self):
        """Drop the document: in-memory state is gone, cookies and storage stay."""
        await self.page.goto('about:blank')

    async def relaunch(self):
        await self.page.bring_to_front()
        if self.page.url in ('','about:blank'):await self.page.goto(self.mission['url'],wait_until='domcontentloaded')
        else:await self.page.reload(wait_until='domcontentloaded')

    async def back(self):
        await self.page.go_back(wait_until='domcontentloaded')

    async def open_deep_link(self,url):
        if not allowed_url(url,self.mission):raise ScenarioError('This link is outside the hosts this mission may open: '+url[:120])
        await self.page.goto(url,wait_until='domcontentloaded')

    # ponytail: the web recording is one video per context, so a pause cannot cut it the way
    # an Android screen recording is cut. Move to per-step context video if a secret ever needs hiding.
    async def stop_recording(self):pass
    async def start_recording(self):pass

    async def type_focused(self,value):
        """Type an operator-supplied value into the focused field. `supplied` keeps hide() scrubbing it."""
        self.supplied.append(value)
        await self.page.keyboard.type(value)
