import asyncio,json
from pathlib import Path
import pytest
from engine import runner as runner_module

def native_run(tmp_path):
    mission={'id':'mission','project_id':'ws','platform':'android','target_id':'target','build':'a'*64,'device':'pex-test','visibility':'local','name':'Audit','goal':'Audit the app','url':'','allowed_domains':[],'mode':'audit','competitors':[],'browser':'chromium','viewport':'desktop','network':'baseline','auto_replay':False,'observe_seconds':0,'provider':'none','codex_account':'','model':'','model_max':'','effort':'low','max_steps':2,'max_seconds':60,'ai_budget':0,'locale':'en-US','persona_id':'','login_identifier':'','egress_id':'','release':'1','pillars':['functionality','ux_ui']}
    return {'id':'run','project_id':'ws','platform':'android','visibility':'local','mission_id':'mission','mission':mission,'target':{'id':'target','package':'dev.pex.app'},'app':{'sha256':'a'*64,'launch_activity':'dev.pex.app.MainActivity','min_sdk':23,'target_sdk':34,'abis':[]},'status':'running','observations':[],'actions':[],'events':[],'findings':[],'http':[],'console':[],'coverage':{},'ai_calls':0,'ai_usage':[],'ai_totals':{},'baseline_id':'','replay_of':'','error':'','gate':'not_evaluated'}

@pytest.mark.asyncio
async def test_native_audit_final_log_changes_gate(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    saved=[]
    async def write(kind,value):saved.append(value.copy());return value
    monkeypatch.setattr(runner_module,'write',write)
    class FakeDevice:
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[];self.video_parts=[];self.gaps=[];self.faults=[];self.network_restore=[]
        async def start(self):pass
        async def launch(self,url):self.measurements={'launch_ms':400,'launch_status':'ok','api':34,'abi':'arm64-v8a','renderer':'auto'}
        async def observe(self,id):
            (self.folder/(id+'.png')).write_bytes(b'png')
            return {'id':id,'url':'android-app://dev.pex.app/Main','title':'App','lang':'en-US','dir':'ltr','text':'Home','viewport':{'width':1080,'height':2400,'density_dpi':420,'rotation':0},'controls':[],'metrics':{},'checks':{'hierarchy':{'status':'supported'},'gfxinfo':{'status':'unavailable'},'meminfo':{'status':'supported'},'logcat':{'status':'supported'}},'console_events':[],'screenshot':'/api/runs/run/artifacts/step-000.png','part':1}
        async def stop(self):
            text='x AndroidRuntime: FATAL EXCEPTION: main\nx AndroidRuntime: Process: dev.pex.app, PID: 2\nx AndroidRuntime: java.lang.IllegalStateException: late\n'
            (self.folder/'logcat.txt').write_text(text);self.logs=['/api/runs/run/artifacts/logcat.txt']
    monkeypatch.setattr(runner_module.android,'Device',FakeDevice)
    worker=runner_module.Runner();run=native_run(tmp_path)
    await worker.execute_android('run',run)
    assert run['status']=='completed' and any(f['rule']=='crash-illegalstateexception' for f in run['findings'])
    assert run['gate']=='warn' and saved[-1]['status']=='completed'  # first sighting; replay must reproduce before blocking

@pytest.mark.asyncio
async def test_android_continue_is_refused(monkeypatch,tmp_path):
    run=native_run(tmp_path);run['status']='completed'
    async def read(kind,id,workspace=''):return run
    monkeypatch.setattr(runner_module,'read',read)
    with pytest.raises(ValueError,match='cannot be continued'):await runner_module.Runner().resume('run',1,1)

@pytest.mark.asyncio
async def test_stop_failure_still_publishes_terminal(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path);saved=[]
    async def write(kind,value):saved.append(value.copy());return value
    monkeypatch.setattr(runner_module,'write',write)
    class Broken:
        def __init__(self,*a,**k):self.measurements={};self.videos=[];self.logs=[];self.warnings=[];self.video_parts=[];self.gaps=[];self.faults=[];self.network_restore=[]
        async def start(self):raise ValueError('setup failed')
        async def stop(self):raise ValueError('cleanup failed')
    monkeypatch.setattr(runner_module.android,'Device',Broken)
    run=native_run(tmp_path);await runner_module.Runner().execute_android('run',run)
    assert run['status']=='failed' and 'cleanup failed' in run['artifact_warnings'][0] and saved[-1]['status']=='failed'

@pytest.mark.asyncio
async def test_native_journey_resolves_dynamic_model_before_the_cli_call(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    class FakeDevice:
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[];self.video_parts=[];self.gaps=[];self.faults=[];self.network_restore=[]
        async def start(self):pass
        async def launch(self,url):pass
        async def observe(self,id):
            (self.folder/(id+'.png')).write_bytes(b'png')
            return {'id':id,'url':'android-app://dev.pex.app/Main','title':'App','lang':'en-US','dir':'ltr','text':'Home','viewport':{'width':1080,'height':2400,'density_dpi':420,'rotation':0},'controls':[],'metrics':{},'checks':{},'console_events':[],'screenshot':'/api/runs/run/artifacts/step-000.png','part':1}
        async def stop(self):pass
    monkeypatch.setattr(runner_module.android,'Device',FakeDevice)
    calls=[]
    async def call(provider,prompt,schema,image=None,timeout=100,model='',effort='low',codex_account=''):
        calls.append((provider,model,effort))
        return {'type':'finish','target':'','value':'','reason':'done','outcome':'success'},runner_module.ai.usage_record(provider,model,model,effort)
    monkeypatch.setattr(runner_module.ai,'call',call)
    run=native_run(tmp_path);run['mission'].update(mode='journey',provider='codex',model='dynamic',model_max='gpt-5.6-sol',max_steps=1,ai_budget=1)
    await runner_module.Runner().execute_android('run',run)
    assert run['status']=='completed' and calls==[('codex','gpt-5.6-luna','low')]  # the sentinel never reaches the CLI
    assert (run['ai_model'],run['ai_model_max'])==('dynamic','gpt-5.6-sol')


async def test_native_journey_refuses_a_blocked_finish_before_any_tap(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    class FakeDevice:
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[];self.video_parts=[];self.gaps=[];self.faults=[];self.network_restore=[];self.taps=[]
        async def start(self):pass
        async def launch(self,url):pass
        async def observe(self,id):
            (self.folder/(id+'.png')).write_bytes(b'png')
            return {'id':id,'url':'android-app://dev.pex.app/Main','title':'App','lang':'en-US','dir':'ltr','text':'','viewport':{'width':1080,'height':2400,'density_dpi':420,'rotation':0},'controls':[{'id':'pex-1','tag':'android.view.View','role':'button','text':'','label':'','labeled':False,'box':{'x':220,'y':2127,'width':199,'height':210},'identity':'x'}],'metrics':{},'checks':{},'console_events':[],'screenshot':'','part':1}
        async def act(self,action):self.taps.append(action['target'])
        async def stop(self):pass
    monkeypatch.setattr(runner_module.android,'Device',FakeDevice)
    answers=[{'type':'finish','target':'','value':'','reason':'no actionable controls','outcome':'blocked'},{'type':'click','target':'pex-1','value':'','reason':'search tab'},{'type':'finish','target':'','value':'','reason':'done','outcome':'success'}]
    prompts=[]
    async def call(provider,prompt,schema,image=None,timeout=100,model='',effort='low',codex_account=''):
        prompts.append(prompt);return answers.pop(0),runner_module.ai.usage_record(provider,model,model,effort)
    monkeypatch.setattr(runner_module.ai,'call',call)
    run=native_run(tmp_path);run['mission'].update(mode='journey',provider='codex',max_steps=5,ai_budget=5)
    await runner_module.Runner().execute_android('run',run)
    assert [a['status'] for a in run['actions']]==['failed','executed','executed'] and run['mission_outcome']=='success'
    assert [e['message'][:8] for e in run['events'] if e['message'].startswith('Action')]==['Action 1','Action 2','Action 3']  # each action is logged as it happens
    assert 'Refused: no control has been tried yet' in prompts[1]  # the second prompt carries the refusal as action history


class ScenarioDevice:
    """A device that answers the scenario interpreter without adb, used by both scenario runs below."""
    text='Now playing'
    def __init__(self,*a,**k):
        self.folder=Path(a[2]);self.measurements={'start_state':'fresh'};self.videos=[];self.logs=[];self.warnings=[];self.video_parts=[];self.gaps=[];self.faults=[];self.network_restore=[]
        self.app={'package':'dev.pex.app'};self.homed=0;self.recording=True
    async def start(self):pass
    async def launch(self,url):self.measurements.update(launch_ms=400,launch_status='ok',api=34,abi='arm64-v8a',renderer='auto')
    async def observe(self,id):
        (self.folder/(id+'.png')).write_bytes(b'png')
        return {'id':id,'url':'android-app://dev.pex.app/Player','title':'App','lang':'en-US','dir':'ltr','text':self.text,'viewport':{'width':1080,'height':2400,'density_dpi':420,'rotation':0},'controls':[],'metrics':{},'checks':{'hierarchy':{'status':'supported'},'gfxinfo':{'status':'unavailable'},'meminfo':{'status':'supported'},'logcat':{'status':'supported'}},'console_events':[],'screenshot':'/api/runs/run/artifacts/'+id+'.png','part':1}
    async def sample(self):return {'at':'now','activity':'dev.pex.app/Player','package':'dev.pex.app','text':self.text,'labels':''}
    def log_cursor(self):return 0
    def crash_since(self,cursor):return ''
    async def home(self):self.homed+=1
    async def stop_recording(self):self.recording=False
    async def start_recording(self):self.recording=True
    async def stop(self):pass

async def scenario_run(monkeypatch,tmp_path,steps):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    monkeypatch.setattr(runner_module.android,'Device',ScenarioDevice)
    run=native_run(tmp_path);run['mission']['scenario']=steps
    await runner_module.Runner().execute_android('run',run)
    return run

@pytest.mark.asyncio
async def test_scenario_verdicts_become_findings_coverage_gaps_and_skipped_steps(monkeypatch,tmp_path):
    run=await scenario_run(monkeypatch,tmp_path,[{'event':{'home':True}},{'hold':{'no_crash':True,'for':1}},
                                                 {'check':{'text':'Downloads','within':1}},{'check':{'text':'Now playing','within':1}}])
    assert [s['status'] for s in run['scenario']]==['passed','passed','failed','skipped']
    finding=next(f for f in run['findings'] if f['rule'].startswith('scenario-'))
    assert finding['severity']=='P2' and finding['classification']=='defect' and finding['verifier_status']=='CONFIRMED'
    assert run['mission_outcome']=='blocked' and run['status']=='blocked' and run['gate']=='warn'
    assert run['scenario_coverage']['status']=='partial' and run['coverage']['functionality']['status']=='not_evaluated'
    assert run['scenario_digest'] and finding['rule'].endswith('-3-text')  # rule names the scenario, the step and the oracle

@pytest.mark.asyncio
async def test_an_unknown_expectation_is_recorded_without_blocking_or_deducting(monkeypatch,tmp_path):
    run=await scenario_run(monkeypatch,tmp_path,[{'hold':{'text':'Downloads','for':1,'policy':'unknown'}}])
    finding=next(f for f in run['findings'] if f['rule'].startswith('scenario-'))
    assert finding['severity']=='info' and finding['classification']=='observation'
    assert run['mission_outcome']=='success' and run['gate']=='warn' and run['scores']['functionality']['score']==100

@pytest.mark.asyncio
async def test_an_operator_step_stops_recording_and_only_the_issued_token_releases_it(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    devices=[]
    class Recorded(ScenarioDevice):
        def __init__(self,*a,**k):super().__init__(*a,**k);devices.append(self)
    monkeypatch.setattr(runner_module.android,'Device',Recorded)
    run=native_run(tmp_path)
    run['mission']['scenario']=[{'manual':'Sign in as the test account','timeout':30},{'check':{'text':'Now playing','within':1}}]
    worker=runner_module.Runner();task=asyncio.create_task(worker.execute_android('run',run))
    for _ in range(400):
        await asyncio.sleep(0.01)
        if run.get('waiting_for'):break
    waiting=run['waiting_for']
    assert waiting['step']==1 and waiting['instruction'].startswith('Sign in') and devices[0].recording is False
    assert run['scenario'][0]['status']=='waiting'
    for step,token in ((2,waiting['token']),(1,'0'*32)):
        with pytest.raises(ValueError,match='not waiting'):await worker.continue_step('run',step,token)
    await worker.continue_step('run',1,waiting['token'])
    with pytest.raises(ValueError,match='not waiting'):await worker.continue_step('run',1,waiting['token'])
    await task
    assert [s['status'] for s in run['scenario']]==['passed','passed'] and run['scenario'][0]['reason'].startswith('The operator')
    assert run['waiting_for'] is None and devices[0].recording is True and 'run' not in worker.pauses

@pytest.mark.asyncio
async def test_an_operator_step_that_nobody_answers_ends_the_scenario(monkeypatch,tmp_path):
    run=await scenario_run(monkeypatch,tmp_path,[{'manual':'Sign in as the test account','timeout':1},{'check':{'text':'Now playing','within':1}}])
    assert [s['status'] for s in run['scenario']]==['error','skipped']
    assert 'No operator confirmed' in run['scenario'][0]['reason'] and run['mission_outcome']=='blocked'

@pytest.mark.asyncio
async def test_an_ask_step_types_the_operator_value_and_keeps_it_out_of_the_run(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    typed=[]
    class Typing(ScenarioDevice):
        async def type_focused(self,value):assert self.recording is False;typed.append(value)
    monkeypatch.setattr(runner_module.android,'Device',Typing)
    run=native_run(tmp_path)
    run['mission']['scenario']=[{'manual':'Enter the code from the SMS','ask':'SMS code','timeout':30},{'check':{'text':'Now playing','within':1}}]
    worker=runner_module.Runner();task=asyncio.create_task(worker.execute_android('run',run))
    for _ in range(400):
        await asyncio.sleep(0.01)
        if run.get('waiting_for'):break
    waiting=run['waiting_for'];assert waiting['ask']=='SMS code'
    await worker.continue_step('run',1,waiting['token'],'482913')
    await task
    assert typed==['482913'] and run['scenario'][0]['reason']=='The operator supplied SMS code'
    assert '482913' not in json.dumps(run)

@pytest.mark.asyncio
async def test_an_ask_step_released_with_no_value_means_the_operator_did_it_themselves(monkeypatch,tmp_path):
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    typed=[]
    class Typing(ScenarioDevice):
        async def type_focused(self,value):typed.append(value)
    monkeypatch.setattr(runner_module.android,'Device',Typing)
    run=native_run(tmp_path)
    run['mission']['scenario']=[{'manual':'Enter the code from the SMS','ask':'SMS code','timeout':30},{'check':{'text':'Now playing','within':1}}]
    worker=runner_module.Runner();task=asyncio.create_task(worker.execute_android('run',run))
    for _ in range(400):
        await asyncio.sleep(0.01)
        if run.get('waiting_for'):break
    await worker.continue_step('run',1,run['waiting_for']['token'])
    await task
    assert typed==[] and run['scenario'][0]['reason']=='The operator confirmed this step'
    assert [s['status'] for s in run['scenario']]==['passed','passed']


class AskingDevice(ScenarioDevice):
    """A device whose screen has one text field, for the AI journey that needs a value for it."""
    def __init__(self,*a,**k):super().__init__(*a,**k);self.taps=[];self.typed=[]
    async def observe(self,id):
        screen=await super().observe(id)
        screen['controls']=[{'id':'pex-1','tag':'android.widget.EditText','role':'textbox','text':'','label':'Mobile number',
                             'labeled':True,'input_type':'text','box':{'x':0,'y':0,'width':100,'height':40},'identity':'x'}]
        return screen
    async def act(self,action):self.taps.append((action['type'],action['target']))
    async def type_focused(self,value):assert self.recording is False;self.typed.append(value)

async def ask_journey(monkeypatch,tmp_path,answer):
    """Run a plain AI journey whose first action asks the operator, and release the pause with `answer`."""
    monkeypatch.setattr(runner_module,'ARTIFACTS',tmp_path)
    async def write(kind,value):return value
    monkeypatch.setattr(runner_module,'write',write)
    devices=[]
    class Recorded(AskingDevice):
        def __init__(self,*a,**k):super().__init__(*a,**k);devices.append(self)
    monkeypatch.setattr(runner_module.android,'Device',Recorded)
    planned=[{'type':'ask','target':'pex-1','value':'SMS code','reason':'the app needs the code','outcome':'continue'},
             {'type':'finish','target':'','value':'','reason':'signed in','outcome':'success'}]
    prompts=[]
    async def call(provider,prompt,schema,image=None,timeout=100,model='',effort='low',codex_account=''):
        prompts.append(prompt);return planned.pop(0),runner_module.ai.usage_record(provider,model,model,effort)
    monkeypatch.setattr(runner_module.ai,'call',call)
    run=native_run(tmp_path);run['mission'].update(mode='journey',provider='codex',max_steps=4,ai_budget=4)
    worker=runner_module.Runner();task=asyncio.create_task(worker.execute_android('run',run))
    for _ in range(400):
        await asyncio.sleep(0.01)
        if run.get('waiting_for'):break
    waiting=dict(run['waiting_for'])
    await worker.continue_step('run',waiting['step'],waiting['token'],**answer)
    await task
    return run,waiting,devices[0],prompts,worker

@pytest.mark.asyncio
async def test_an_ai_journey_asks_the_operator_and_types_what_they_supply(monkeypatch,tmp_path):
    run,waiting,device,_,worker=await ask_journey(monkeypatch,tmp_path,{'value':'482913'})
    assert waiting['kind']=='ask' and waiting['ask']=='SMS code' and waiting['needs_value'] is False
    # The field is focused first, so the supplied value lands in it, and nothing records while it is typed.
    assert device.taps==[('tap','pex-1')] and device.typed==['482913'] and device.recording is True
    assert [a['status'] for a in run['actions']]==['executed','executed'] and run['mission_outcome']=='success'
    assert '482913' not in json.dumps(run) and run['waiting_for'] is None and 'run' not in worker.pauses

@pytest.mark.asyncio
async def test_a_skipped_ask_lets_the_ai_journey_carry_on_without_the_value(monkeypatch,tmp_path):
    run,_,device,prompts,_=await ask_journey(monkeypatch,tmp_path,{'skip':True})
    assert device.typed==[] and [a['status'] for a in run['actions']]==['skipped','executed']
    assert run['actions'][0]['error']=='The operator skipped: SMS code'
    assert 'The operator skipped: SMS code' in prompts[1]  # the AI sees the skip and chooses what to do next


@pytest.mark.asyncio
async def test_observe_hides_a_supplied_value_from_the_screen_the_hierarchy_and_the_prompt(monkeypatch,tmp_path):
    """A value the operator typed is as sensitive as a password: black box, {{supplied}} everywhere."""
    from io import BytesIO
    from PIL import Image
    from engine import android
    monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run',avd='pex-test')
    device.supplied.append('0912 345 6789')
    xml=('<hierarchy rotation="0"><node class="android.widget.EditText" bounds="[0,0][100,40]" enabled="true" '
         'clickable="true" text="0912 345 6789" resource-id="" content-desc="" password="false" checked="false"/>'
         '<node class="android.widget.TextView" bounds="[0,60][300,100]" enabled="true" clickable="false" '
         'text="Code sent to 0912 345 6789" resource-id="" content-desc="" password="false" checked="false"/></hierarchy>')
    async def hierarchy():return android.sanitize_xml(xml)
    async def shell(*args,**kw):
        return {('wm','size'):'Physical size: 1080x2400',('wm','density'):'Physical density: 420'}.get(args[:2],'')
    buffer=BytesIO();Image.new('RGB',(1080,2400),'white').save(buffer,'PNG')
    async def adb_call(*args,**kw):return buffer.getvalue()
    monkeypatch.setattr(device,'_hierarchy',hierarchy)
    monkeypatch.setattr(device,'shell',shell)
    monkeypatch.setattr(device,'adb_call',adb_call)

    screen=await device.observe('step-000')
    control=screen['controls'][0]
    assert control['text']=='{{supplied}}' and control['label']=='{{supplied}}' and control['filled'] is True
    assert screen['text']=='{{supplied}}\nCode sent to {{supplied}}'
    assert '0912 345 6789' not in json.dumps(screen) and '{{supplied}}' in screen['hierarchy']
    painted=Image.open(tmp_path/'step-000.png').convert('RGB')
    # Both the field and the line echoing it are covered.
    assert painted.getpixel((50,20))==(0,0,0) and painted.getpixel((150,80))==(0,0,0)
