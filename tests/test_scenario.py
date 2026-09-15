import re, time
import pytest
import yaml
from engine import scenario as engine
from engine.contracts import Mission, Step
from engine.presets import scenarios

PACKAGE='dev.pex.app'

def mission(**extra):
    base=dict(platform='android',name='Scenario',goal='Play a downloaded movie',target_id='t',build='b'*64,
              device='pex-test',mode='audit',provider='none',ai_budget=0,pillars=['functionality'])
    return Mission(**{**base,**extra})

class Stub:
    """A device that answers samples from a script and never touches adb."""
    def __init__(self,samples,crash=''):
        self.app={'package':PACKAGE};self.samples=list(samples);self.crash=crash;self.cursors=[]
    async def sample(self):
        return self.samples.pop(0) if len(self.samples)>1 else self.samples[0]
    def log_cursor(self):self.cursors.append(len(self.cursors));return len(self.cursors)-1
    def crash_since(self,cursor):
        self.asked=cursor;return self.crash

async def quiet(message,kind='info'):pass

def screen(text='Now playing',package=PACKAGE,**extra):
    return {'at':'now','activity':package+'/Player','package':package,'text':text,'labels':'',**extra}

async def play(steps,device):
    script=engine.Scenario([Step.model_validate(s).model_dump() for s in steps],device,notify=quiet,goal=None,
                           deadline=time.monotonic()+30)
    return await script.run()

# --- contract ---------------------------------------------------------------

def test_a_scenario_rejects_placeholders_unknown_keys_and_impossible_time():
    for bad,words in [([{'check':{'text':'<Movie title>'}}],'Fill in 1 blank: <Movie title>'),
                      ([{'check':{'text':'a','after':3}}],'Extra inputs'),
                      ([{'event':{'wait':600}},{'event':{'wait':600}}],'already need 1200 s')]:
        with pytest.raises(ValueError,match=words):mission(scenario=bad,max_seconds=600)

def web(**extra):
    base=dict(platform='web',url='https://example.com',name='Scenario',goal='Play a downloaded movie',
              mode='audit',provider='none',ai_budget=0,pillars=['functionality'])
    return Mission(**{**base,**extra})

def test_the_same_scenario_vocabulary_saves_against_a_website():
    bound=web(scenario=[{'manual':'Sign in, then continue'},
                        {'check':{'notification':{'text':'Saved'},'within':5}},
                        {'event':{'kill':True}},
                        {'event':{'relaunch':True}},
                        {'check':{'screen':{'contains':'/library'},'within':5}},
                        {'event':{'network':'offline'}},
                        {'event':{'back':True}},
                        {'check':{'no_crash':True,'within':5}}])
    assert [s.kind for s in bound.scenario][:3]==['manual','check','event']

def test_a_website_scenario_refuses_a_snapshot_and_needs_chromium_to_shape_the_link():
    with pytest.raises(ValueError,match='through a persona'):web(snapshot='a'*12)
    with pytest.raises(ValueError,match='Step 2: link shaping in the browser needs Chromium'):
        web(browser='firefox',scenario=[{'event':{'network':'offline'}},{'event':{'speed':'edge'}}])
    # Offline and restore need no shaping, so they run on any browser.
    assert web(browser='firefox',scenario=[{'event':{'network':'offline'}},{'event':{'network':'restore'}}]).scenario

def test_blanks_are_listed_once_each_in_the_order_a_reader_meets_them():
    unbound=Mission.model_construct(name='<Movie title> on <Device>',goal='Play <Movie title>',
                                    scenario=[Step.model_validate({'check':{'text':'<Text shown while playing>'}}),
                                              Step.model_validate({'check':{'text':'<Movie title>'}})])
    assert unbound.blanks()==['<Movie title>','<Device>','<Text shown while playing>']

def test_the_screen_fact_replaced_the_android_activity_name():
    with pytest.raises(ValueError,match='Extra inputs'):mission(scenario=[{'check':{'activity':{'contains':'Player'}}}])
    assert mission(scenario=[{'check':{'screen':{'contains':'Player'},'within':5}}]).scenario

def test_a_hold_keeps_its_yaml_spelling_and_an_unknown_expectation_cannot_be_required():
    held=Step.model_validate({'hold':{'playing':True,'for':20,'policy':'unknown'}}).model_dump()
    assert held['hold']['for']==20 and held['hold']['required'] is False
    assert Step.model_validate({'check':{'text':'Downloads'}}).model_dump()['check']['required'] is True

# --- eventually versus throughout -------------------------------------------

async def test_a_check_passes_on_the_first_valid_sample_after_a_transient_miss():
    device=Stub([screen('Loading'),screen('Now playing')])
    result=(await play([{'check':{'text':'Now playing','within':5}}],device))[0]
    assert result['status']=='passed' and len(result['samples'])==2

async def test_a_check_fails_only_on_a_measured_contradiction():
    result=(await play([{'check':{'text':'Now playing','within':1}}],Stub([screen('Paused')])))[0]
    assert result['status']=='failed' and 'Paused' in result['reason']

async def test_an_unreadable_screen_is_unavailable_and_never_a_failure():
    device=Stub([{'at':'now','activity':'','package':'','error':'No window reported focus'}])
    result=(await play([{'check':{'text':'Now playing','within':1}}],device))[0]
    assert result['status']=='unavailable' and 'No window reported focus' in result['reason']

async def test_absence_cannot_be_proven_while_another_app_is_in_front():
    device=Stub([screen('Home',package='com.android.launcher')])
    result=(await play([{'check':{'text_absent':'Ali','within':1}}],device))[0]
    assert result['status']=='unavailable' and 'Another app was in front' in result['samples'][0]['observed']

async def test_a_hold_fails_at_the_first_contradiction_and_keeps_that_sample():
    device=Stub([screen('Now playing'),screen('Connection lost')])
    result=(await play([{'hold':{'text':'Now playing','for':6}}],device))[0]
    assert result['status']=='failed' and 'Connection lost' in result['reason'] and result['samples'][-1]['verdict']=='fail'

async def test_a_hold_reports_how_many_samples_it_measured():
    result=(await play([{'hold':{'text':'Now playing','for':2}}],Stub([screen()])))[0]
    assert result['status']=='passed' and result['reason'].startswith('Passed across ') and ' samples over ' in result['reason']

async def test_a_hold_with_no_usable_sample_is_unavailable():
    device=Stub([{'at':'now','activity':'','package':'','error':'Screen hierarchy unavailable: timeout'}])
    result=(await play([{'hold':{'text':'Now playing','for':1}}],device))[0]
    assert result['status']=='unavailable' and 'No usable sample' in result['reason']

# --- crash cursor and stopping ----------------------------------------------

async def test_checks_do_not_advance_the_crash_cursor():
    device=Stub([screen()],crash='FATAL EXCEPTION: main\njava.lang.IllegalStateException: late')
    results=await play([{'check':{'text':'Now playing','within':1}},{'check':{'no_crash':True,'within':1}}],device)
    assert results[1]['status']=='failed' and device.asked==0  # the cursor still points before the scenario started

async def test_a_required_failure_skips_the_steps_that_depend_on_it():
    results=await play([{'check':{'text':'Downloads','within':1}},{'check':{'text':'Now playing','within':1}}],Stub([screen('Nothing here')]))
    assert [r['status'] for r in results]==['failed','skipped'] and 'required step failed' in results[1]['reason']

async def test_an_optional_failure_lets_the_scenario_continue():
    device=Stub([screen('Nothing here'),screen('Now playing')])
    results=await play([{'check':{'text':'Downloads','within':1,'required':False}},{'check':{'text':'Now playing','within':2}}],device)
    assert [r['status'] for r in results]==['failed','passed']

# --- replay eligibility ------------------------------------------------------

def android_run(**extra):
    base={'id':'r1','platform':'android','mission':{'platform':'android','project_id':'default','scenario':[]},
          'app':{'sha256':'a'*64},'measurements':{'start_state':'fresh'},'device':{},'findings':[],'coverage':{},
          'status':'completed','target':{'package':PACKAGE},'faults':[],'network_applied':{}}
    return {**base,**extra}

def test_a_replay_confirms_a_reproduction_only_on_the_same_build_and_established_conditions():
    from engine.evaluate import compare_runs
    a=android_run();b=android_run(id='r2')
    assert compare_runs(a,b)['reproduction']=={'eligible':True,'reason':''}
    other=android_run(id='r2',app={'sha256':'b'*64})
    assert compare_runs(a,other)['reproduction']['eligible'] is False and 'different build' in compare_runs(a,other)['reproduction']['reason']
    kept=android_run(id='r2',measurements={'start_state':'kept'})
    assert compare_runs(a,kept)['reproduction']['eligible'] is False and 'kept whatever' in compare_runs(a,kept)['reproduction']['reason']

def test_an_operator_step_or_a_missing_measurement_leaves_a_replay_unable_to_confirm():
    from engine.evaluate import compare_runs
    a=android_run()
    manual=android_run(id='r2',scenario=[{'number':1,'kind':'manual','status':'passed','required':False}])
    assert 'operator' in compare_runs(a,manual)['reproduction']['reason']
    gap=android_run(id='r2',scenario=[{'number':2,'kind':'check','status':'unavailable','required':True}])
    assert compare_runs(a,gap)['reproduction']['eligible'] is False and 'Step 2' in compare_runs(a,gap)['reproduction']['reason']

def test_a_changed_scenario_is_not_the_same_configuration():
    from engine.evaluate import compare_runs
    a=android_run();a['mission']['scenario']=[{'check':{'text':'Downloads'}}]
    b=android_run(id='r2');b['mission']['scenario']=[{'check':{'text':'Search'}}]
    assert 'scenario' in compare_runs(a,b)['mismatches'] and not compare_runs(a,b)['compatible']

# --- playback and notification oracles ---------------------------------------

class Player(Stub):
    """A device whose MediaSession and notification dumps are scripted."""
    def __init__(self,media=(),notes=(),fails=''):
        super().__init__([screen()]);self.media=list(media);self.notes=list(notes);self.fails=fails
    async def media_state(self):
        if self.fails:raise RuntimeError(self.fails)
        return self.media.pop(0) if len(self.media)>1 else (self.media[0] if self.media else None)
    async def notifications(self):
        if self.fails:raise RuntimeError(self.fails)
        return self.notes

def session(state='playing',position=1000,updated=5000):
    return {'state':state,'position':position,'updated':updated,'speed':1.0,'raw':''}

@pytest.mark.asyncio
async def test_reported_playback_needs_an_actual_position_update_to_pass():
    frozen=await play([{'check':{'playing':True,'within':2}}],Player([session()]))
    assert frozen[0]['status']=='unavailable' and 'no position update' in frozen[0]['reason']
    moving=await play([{'check':{'playing':True,'within':4}}],
                      Player([session(),session(position=3000,updated=7000)]))
    assert moving[0]['status']=='passed' and 'playback progress' in moving[0]['samples'][-1]['observed']

@pytest.mark.asyncio
async def test_a_paused_player_fails_a_playing_check_and_passes_a_stopped_one():
    assert (await play([{'check':{'playing':True,'within':2}}],Player([session('paused')])))[0]['status']=='failed'
    assert (await play([{'check':{'playing':False,'within':2}}],Player([session('paused')])))[0]['status']=='passed'
    # No session at all says nothing about the player, so it can neither pass nor fail.
    for want in (True,False):
        assert (await play([{'check':{'playing':want,'within':1}}],Player([])))[0]['status']=='unavailable'

@pytest.mark.asyncio
async def test_a_notification_check_reads_only_this_package_and_survives_a_failed_dump():
    notes=[{'package':PACKAGE,'key':'k1','text':'Download finished\nMovie X'},
           {'package':'com.other','key':'k2','text':'Download finished'}]
    assert (await play([{'check':{'notification':{'text':'Download finished'},'within':2}}],Player(notes=notes)))[0]['status']=='passed'
    assert (await play([{'check':{'notification':{'text':'Nothing here'},'within':1}}],Player(notes=notes)))[0]['status']=='failed'
    assert (await play([{'check':{'notification':{'text':'Nothing here','present':False},'within':1}}],Player(notes=notes)))[0]['status']=='passed'
    broken=await play([{'check':{'notification':{'text':'Download finished'},'within':1}}],Player(notes=notes,fails='dumpsys died'))
    assert broken[0]['status']=='unavailable' and 'dumpsys died' in broken[0]['reason']

# --- shipped presets ----------------------------------------------------------

def resolve(value):
    """Stand in for the operator binding a preset: every <placeholder> gets a real value."""
    if isinstance(value,str):
        return re.sub(r'<[^<>]+>','Real value',re.sub(r'<[^<>]*link[^<>]*>','https://example.com/title/1',value,flags=re.I))
    if isinstance(value,dict):return {k:resolve(v) for k,v in value.items()}
    if isinstance(value,list):return [resolve(v) for v in value]
    return value

def test_every_shipped_preset_binds_to_a_mission_on_either_platform_and_survives_yaml():
    shipped=scenarios()
    assert [p['id'] for p in shipped][:2]==['entitlement-switch','weak-network-download'] and len(shipped)==12
    for preset in shipped:
        # A blank is an instruction to the author, so it is never one bare word.
        assert preset['blanks'] and all(' ' in blank for blank in preset['blanks']),preset['id']
        # Unbound, the blanks are exactly what stops it being saved by accident.
        with pytest.raises(ValueError,match='Fill in'):
            Mission(**preset['mission'],target_id='t',build='b'*64,device='pex-test')
        for platform,rest in (('android',{'target_id':'t','build':'b'*64,'device':'pex-test'}),
                              ('web',{'url':'https://example.com'})):
            bound=Mission(**resolve(preset['mission']),platform=platform,**rest)
            again=Mission.model_validate(yaml.safe_load(yaml.safe_dump(bound.model_dump(by_alias=True),allow_unicode=True)))
            assert again.model_dump()==bound.model_dump(),preset['id']
            assert bound.platform==platform and bound.pillars==['functionality'] and bound.scenario
