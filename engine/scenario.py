"""Deterministic execution of one ordered Android scenario.

Everything here is measurement: no AI, no storage and no release policy. The caller
supplies the device, a goal callback, an operator pause callback and one absolute
monotonic deadline that the whole run shares.
"""
import asyncio, time
from . import store

# A hold aims for a sample every two seconds. Hierarchy dumps are slow on a busy device,
# so the real sample times are recorded and a longer blind stretch makes the hold unavailable.
CADENCE=2
GAP_TOLERANCE=6
POLL=1
VERDICT={True:'pass',False:'fail',None:'unavailable'}

class ScenarioError(Exception):
    """The step could not be carried out. That is an execution failure, not an app defect."""

def oracle_kind(oracle):
    for key in ('text','text_absent','activity','playing','notification','no_crash'):
        if oracle.get(key) not in (None,''):return key
    raise ScenarioError('This check states no fact to establish')

def event_kind(event):
    chosen=[k for k in ('network','speed','delay_ms','kill','home','wait','relaunch','deep_link','open_notification') if event.get(k) is not None]
    if 'speed' in chosen and 'delay_ms' in chosen:chosen.remove('delay_ms')
    if not chosen:raise ScenarioError('This event performs no operation')
    return chosen[0]

def step_kind(step):
    for key in ('goal','manual','event','check','hold'):
        if step.get(key) not in (None,''):return key
    raise ScenarioError('This step does nothing')

def quote(value):return '"'+str(value)[:60]+'"'

def required_of(oracle):
    """Whether dependent steps wait on this one. Confirmed expectations are required unless the author said otherwise."""
    if not oracle:return False
    if oracle.get('policy','confirmed')=='unknown':return False
    return bool(oracle.get('required',True))

def requested(step):
    """The fact or action this step asks for, in the reader's words."""
    kind=step_kind(step)
    if kind=='goal':return 'Goal: '+step['goal']
    if kind=='manual':return 'Operator: '+step['manual']
    if kind=='event':
        event=step['event'];name=event_kind(event)
        if name=='network':return {'wifi':'Switch to Wi-Fi','cellular':'Switch to mobile data','offline':'Take the device offline','restore':'Restore the network as it was'}[event['network']]
        if name=='speed':return 'Set the mobile link to '+event['speed']+(f" with {event['delay_ms']} ms added delay" if event.get('delay_ms') else '')
        if name=='delay_ms':return f"Add {event['delay_ms']} ms of network delay"
        if name=='wait':return f"Wait {event['wait']} s"
        if name=='kill':return 'Send the app to the background and let the system kill it'
        if name=='home':return 'Go to the home screen'
        if name=='relaunch':return 'Force-stop and start the app again'
        if name=='deep_link':return 'Open the link '+event['deep_link']
        return 'Open the notification saying '+quote(event['open_notification'])
    oracle=step[kind];name=oracle_kind(oracle)
    fact={'text':lambda:'the screen shows '+quote(oracle['text']),
          'text_absent':lambda:quote(oracle['text_absent'])+' is not on the screen',
          'activity':lambda:'the screen is '+quote(oracle['activity'].get('equals') or oracle['activity'].get('contains')),
          'playing':lambda:'playback is reported as '+('running' if oracle['playing'] else 'stopped'),
          'notification':lambda:'a notification saying '+quote(oracle['notification']['text'])+(' is posted' if oracle['notification'].get('present',True) else ' is gone'),
          'no_crash':lambda:'the app has not crashed'}[name]()
    if kind=='check':return f"Check within {oracle.get('within',10)} s that "+fact
    return f"Hold for {oracle['for']} s that "+fact

async def playback(device,oracle,memo):
    """MediaSession-reported playback. Projection cannot prove progress, so only reported updates do."""
    try:state=await device.media_state()
    except Exception as error:return None,{'observed':'Playback state unavailable: '+str(error)[:200]}
    if not state:return None,{'observed':'No MediaSession is reported for this package'}
    detail={'observed':'MediaSession reports '+state['state'],'media':state}
    if not oracle['playing']:
        # Stopped is a claim about the player, so only the player saying so establishes it.
        if state['state'] in ('paused','stopped'):return True,detail
        return (False,detail) if state['state']=='playing' else (None,detail)
    if state['state'] in ('paused','stopped'):return False,detail
    if state['state']!='playing':return None,detail
    if state['position'] is None or state['updated'] is None:
        return None,{**detail,'observed':'MediaSession reports playing without a position or an update time'}
    first=memo.get('media')
    if not first or first[0] is None or first[1] is None:memo['media']=first=(state['position'],state['updated'])
    if state['updated']>first[1] and state['position']!=first[0]:
        return True,{**detail,'observed':f"MediaSession-reported playback progress: position {first[0]} to {state['position']} over {state['updated']-first[1]} ms of device time"}
    return None,{**detail,'observed':'MediaSession reports playing, but it has reported no position update yet'}

async def posted(device,oracle):
    """Whether this package is showing a matching notification right now."""
    want=oracle['notification'];text=want['text'];expected=want.get('present',True)
    try:active=await device.notifications()
    except Exception as error:return None,{'observed':'Active notifications unavailable: '+str(error)[:200]}
    mine=[n for n in active if text in n['text'] and n['package']==device.app['package']]
    others=[n for n in active if text in n['text'] and n['package']!=device.app['package']]
    detail={'observed':f'{len(mine)} notification(s) from this app match'+(f' and {len(others)} from other apps' if others else ''),
            'matches':[n['key'] for n in mine]}
    return (bool(mine) if expected else not mine),detail

async def read(device,oracle,cursor,memo):
    """One sample of the requested fact: True, False, or None when the evidence does not say."""
    kind=oracle_kind(oracle)
    if kind=='no_crash':
        crash=device.crash_since(cursor)
        if crash is None:return None,{'observed':'No crash evidence is being collected'}
        if crash:return False,{'observed':crash[:2000]}
        return True,{'observed':'No attributable fatal exception or ANR'}
    if kind=='playing':return await playback(device,oracle,memo)
    if kind=='notification':return await posted(device,oracle)
    screen=await device.sample()
    detail={'activity':screen.get('activity','')}
    if screen.get('error'):return None,{**detail,'observed':screen['error']}
    if kind=='activity':
        want=oracle['activity'];found=screen['activity']
        hit=(found==want['equals']) if want.get('equals') else (want['contains'] in found)
        return hit,{**detail,'observed':found}
    # Text lives in the app's own hierarchy. Another app in front means no evidence either way.
    if screen.get('package')!=device.app['package']:
        return None,{**detail,'observed':'Another app was in front: '+(screen.get('activity') or 'unknown')}
    if 'text' not in screen:return None,{**detail,'observed':'The screen hierarchy could not be read'}
    haystack=screen['text']+'\n'+screen.get('labels','')
    wanted=oracle['text'] if kind=='text' else oracle['text_absent']
    present=wanted in haystack
    return (present if kind=='text' else not present),{**detail,'observed':screen['text'][:1500]}

class Scenario:
    def __init__(self,steps,device,*,notify,goal,deadline,pause=None):
        self.steps=steps;self.device=device;self.notify=notify;self.goal=goal;self.deadline=deadline;self.pause=pause
        self.results=[];self.cursor=device.log_cursor();self.stopped=''

    def remaining(self):return self.deadline-time.monotonic()

    async def sleep(self,seconds):
        left=self.remaining()
        if seconds>left:
            await asyncio.sleep(max(0,left));raise ScenarioError('The run time limit arrived during this wait')
        await asyncio.sleep(seconds)

    async def run(self):
        for index,step in enumerate(self.steps):
            kind=step_kind(step);oracle=step.get(kind) if kind in ('check','hold') else None
            result={'index':index,'number':index+1,'name':step.get('name',''),'kind':kind,'requested':requested(step),
                    'oracle':oracle_kind(oracle) if oracle else '','policy':(oracle or {}).get('policy','confirmed'),
                    'severity':(oracle or {}).get('severity','P2'),'required':required_of(oracle),
                    'status':'pending','reason':'','samples':[],'evidence':[],'started_at':'','finished_at':'','elapsed_s':0}
            self.results.append(result)
            if self.stopped:result.update(status='skipped',reason=self.stopped);continue
            if self.remaining()<=0:
                self.stopped='The run reached its time limit';result.update(status='skipped',reason=self.stopped);continue
            result.update(status='running',started_at=store.now());began=time.monotonic()
            await self.notify(f"Step {index+1} · {result['requested']}")
            try:await self.dispatch(step,kind,result)
            except asyncio.CancelledError:
                result.update(status='skipped',reason='The run was stopped');raise
            except Exception as error:
                result.update(status='error',reason=str(error)[:500]);self.stopped='An earlier step could not be carried out'
            result.update(finished_at=store.now(),elapsed_s=round(time.monotonic()-began,1))
            if result['status'] in ('failed','unavailable') and result['required']:
                self.stopped='A required step '+('failed' if result['status']=='failed' else 'could not be established')
            await self.notify(f"Step {index+1} · {result['status']} · {result['reason']}",
                              'warning' if result['status'] in ('failed','error','unavailable') else 'info')
        return self.results

    async def dispatch(self,step,kind,result):
        if kind=='goal':
            # A crash inside a goal must still be visible to a later no_crash check.
            self.cursor=self.device.log_cursor()
            outcome,reason,evidence=await self.goal(step['goal'],(step.get('until') or {}).get('text',''))
            result['evidence']=evidence;result['reason']=reason
            result['status']='passed' if outcome=='success' else 'failed'
            if outcome!='success':self.stopped='An earlier goal did not reach its outcome'
            return
        if kind=='manual':
            if not self.pause:raise ScenarioError('Operator continuation is not configured on this console')
            await self.pause(result,step['manual'],step.get('timeout') or 300,step.get('ask',''))
            return
        if kind=='event':
            self.cursor=self.device.log_cursor()
            await self.apply(step['event']);result.update(status='passed',reason='Applied')
            return
        oracle=step[kind]
        if kind=='check':status,reason=await self.establish(oracle,oracle.get('within',10),result)
        else:status,reason=await self.maintain(oracle,oracle['for'],result)
        result.update(status=status,reason=reason)

    async def apply(self,event):
        name=event_kind(event)
        if name=='network':await self.device.apply_network(event['network'])
        elif name=='speed':await self.device.apply_speed(event['speed'],event.get('delay_ms'))
        elif name=='delay_ms':await self.device.apply_speed('',event['delay_ms'])
        elif name=='home':await self.device.home()
        elif name=='wait':await self.sleep(event['wait'])
        elif name=='relaunch':await self.device.relaunch()
        elif name=='kill':await self.device.background_kill()
        elif name=='deep_link':await self.device.open_deep_link(event['deep_link'])
        else:await self.device.open_notification(event['open_notification'])

    def record(self,result,verdict,sample,elapsed):
        entry={'at':sample.get('at') or store.now(),'t':round(elapsed,1),'verdict':VERDICT[verdict],**sample}
        result['samples'].append(entry);return entry

    async def establish(self,oracle,window,result):
        """Eventually: one valid passing sample settles it; only a measured contradiction can fail it."""
        began=time.monotonic();end=began+min(window,max(0,self.remaining()));contradicted=None;memo={}
        while True:
            verdict,sample=await read(self.device,oracle,self.cursor,memo)
            entry=self.record(result,verdict,sample,time.monotonic()-began)
            if verdict is True:return 'passed',f'Established after {entry["t"]:.0f} s'
            if verdict is False:contradicted=entry
            left=end-time.monotonic()
            if left<=0 or self.remaining()<=0:break
            await asyncio.sleep(min(POLL,left))
        if contradicted:return 'failed',f'Measured {contradicted["observed"][:200]} and it had not changed after {window} s'
        return 'unavailable','No sample could establish this within '+str(window)+' s: '+result['samples'][-1]['observed'][:200]

    async def maintain(self,oracle,seconds,result):
        """Throughout: any valid contradiction fails, and blind stretches make it unavailable."""
        began=time.monotonic();end=began+seconds;valid=[];memo={}
        while True:
            verdict,sample=await read(self.device,oracle,self.cursor,memo)
            elapsed=time.monotonic()-began;entry=self.record(result,verdict,sample,elapsed)
            if verdict is False:return 'failed',f'Contradicted after {entry["t"]:.0f} s: {entry["observed"][:200]}'
            if verdict is True:valid.append(elapsed)
            left=end-time.monotonic()
            if left<=0 or self.remaining()<=0:break
            await asyncio.sleep(min(CADENCE,left))
        elapsed=time.monotonic()-began
        if not valid:return 'unavailable',f'No usable sample was captured across {elapsed:.0f} s: '+result['samples'][-1]['observed'][:200]
        if elapsed<seconds-1:return 'unavailable',f'Only {elapsed:.0f} s of the {seconds} s could be measured before the run time limit'
        marks=[0.0]+valid+[elapsed];gap=max(b-a for a,b in zip(marks,marks[1:]))
        if gap>GAP_TOLERANCE:return 'unavailable',f'Evidence was missing for {gap:.0f} s of the {seconds} s'
        return 'passed',f'Passed across {len(valid)} samples over {elapsed:.0f} s'
