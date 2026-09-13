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
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[]
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
        def __init__(self,*a,**k):self.measurements={};self.videos=[];self.logs=[];self.warnings=[]
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
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[]
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
        def __init__(self,*a,**k):self.folder=Path(a[2]);self.measurements={};self.videos=[];self.logs=[];self.warnings=[];self.taps=[]
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
