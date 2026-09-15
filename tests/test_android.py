import asyncio, time
from pathlib import Path
import pytest
from engine import android

def test_password_xml_is_structurally_sanitized():
    raw='<hierarchy rotation="0"><node password="true" text="pex-secret-sentinel" content-desc="secret" bounds="[1,2][20,30]"/><node password="false" text="Public" bounds="[0,0][2,2]"/></hierarchy>'
    xml,root,boxes=android.sanitize_xml(raw)
    assert 'pex-secret-sentinel' not in xml and 'content-desc="secret"' not in xml
    assert root[0].get('password')=='true' and root[0].get('text')=='' and boxes==[(1,2,20,30)]

def test_log_blocks_are_attributed_redacted_and_rotated(tmp_path):
    lines=['x AndroidRuntime: FATAL EXCEPTION: main\n','x AndroidRuntime: Process: other.app, PID: 1\n','x AndroidRuntime: password=hunter2\n',
           'x AndroidRuntime: FATAL EXCEPTION: main\n','x AndroidRuntime: Process: dev.pex.app, PID: 2\n','x AndroidRuntime: token=secret\n','x ActivityManager: ANR in dev.pex.app\n']
    scoped=android.scoped_logs(lines,'dev.pex.app')
    text=''.join(scoped)
    assert 'other.app' not in text and 'secret' not in text and '[REDACTED]' in text and 'ANR in dev.pex.app' in text
    names=android.write_log_parts(tmp_path,['x'*11],part_size=5)
    assert names==['logcat.txt','logcat-2.txt','logcat-3.txt'] and b''.join((tmp_path/n).read_bytes() for n in names)==b'x'*11

@pytest.mark.asyncio
async def test_command_timeout_terminates_and_reaps():
    with pytest.raises(asyncio.TimeoutError):await android.run('/bin/sh','-c','sleep 5',timeout=.01)

@pytest.mark.asyncio
async def test_shell_quotes_metacharacters(monkeypatch,tmp_path):
    calls=[]
    async def fake(*args,**kw):calls.append(args);return ''
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1'
    await device.shell('input','text','space $HOME; % ü')
    assert calls[0][-1]=="input text 'space $HOME; % ü'"

def test_bounds_and_package_validation(monkeypatch,tmp_path):
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'));monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    assert android.parse_bounds('[1,2][3,4]')==(1,2,3,4)
    assert android.parse_bounds('bad') is None
    with pytest.raises(android.AndroidError,match='package'):android.Device({'device':'pex-test'},{'package':'bad;rm'},tmp_path,'run')

@pytest.mark.asyncio
async def test_stop_is_idempotent_and_releases_lock(monkeypatch,tmp_path):
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'));monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    lock=tmp_path/'lock';device.lock_file=lock.open('a')
    await device.stop();await device.stop()
    assert device.lock_file is None

@pytest.mark.asyncio
async def test_stop_signals_only_the_owned_device_recorder(monkeypatch,tmp_path):
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'));monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    calls=[]
    async def shell(*args,**kw):calls.append(args);return ''
    class Recorder:
        returncode=None
        async def wait(self):return 0
        def terminate(self):self.returncode=0
    device.serial='emulator-1';device.recorder=Recorder();device.recorder_pid='42';device.shell=shell
    device.record_task=asyncio.create_task(asyncio.sleep(0))
    await device.stop()
    # The owned part is signalled by pid; the survivor check is scoped to this run, and pkill is never used.
    assert ('kill','-2','42') in calls and ('pidof','screenrecord') in calls and not any(call[0]=='pkill' for call in calls)

async def test_focused_app_is_read_from_the_full_window_dump(monkeypatch,tmp_path):
    """API 34 prints the focus only in `dumpsys window`, as mFocusedApp/mCurrentFocus lines."""
    calls=[]
    async def fake(*args,**kw):
        calls.append(args)
        return '  mCurrentFocus=Window{af57e58 u0 com.aparat.filimo/com.bluevod.app.features.vitrine.NewVitrineActivity}\n  mFocusedApp=ActivityRecord{cc4ba81 u0 com.aparat.filimo/com.bluevod.app.features.vitrine.NewVitrineActivity t30}\n' if args[-1]=='dumpsys window' else ''
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'com.aparat.filimo'},tmp_path,'run')
    device.serial='emulator-1'
    assert await device.focused()=='com.aparat.filimo/com.bluevod.app.features.vitrine.NewVitrineActivity'
    assert calls[0][-1]=='dumpsys window'

@pytest.mark.asyncio
async def test_tap_follows_a_control_whose_bounds_moved(monkeypatch,tmp_path):
    """A carousel shifts between observe and act; the same control at new bounds is still tapped, two copies are not."""
    calls=[]
    async def fake(*args,**kw):
        calls.append(args)
        return 'dumpsys window' not in args[-1] and '' or 'mFocusedApp=ActivityRecord{1 u0 dev.pex.app/.Main t1}'
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1';device.display=(1080,2400)
    device.controls={'pex-1':('dev.pex.app','android.widget.ImageView','dev.pex.app:id/poster','Poster','','[0,0][100,100]')}
    node='<node class="android.widget.ImageView" clickable="true" resource-id="dev.pex.app:id/poster" content-desc="Poster" text="" bounds="%s"/>'
    async def hierarchy():
        xml='<hierarchy>'+node%'[200,0][300,100]'+'</hierarchy>';return xml,android.ElementTree.fromstring(xml),[]
    device._hierarchy=hierarchy
    await device.act({'type':'tap','target':'pex-1'})
    assert calls[-1][-1]=='input tap 250 50'
    async def hierarchy2():
        xml='<hierarchy>'+node%'[200,0][300,100]'+node%'[400,0][500,100]'+'</hierarchy>';return xml,android.ElementTree.fromstring(xml),[]
    device._hierarchy=hierarchy2
    with pytest.raises(android.AndroidError,match='ambiguous'):await device.act({'type':'tap','target':'pex-1'})

@pytest.mark.asyncio
async def test_tap_picks_the_near_twin_when_a_row_of_identical_icons_shifts(monkeypatch,tmp_path):
    """Filimo's detail page puts four icon-only buttons in a row; when the page shifts they differ only by bounds,
    and the one a few pixels from where it was observed is the one that was observed."""
    calls=[]
    async def fake(*args,**kw):
        calls.append(args)
        return 'dumpsys window' not in args[-1] and '' or 'mFocusedApp=ActivityRecord{1 u0 dev.pex.app/.Main t1}'
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1';device.display=(1080,2400)
    device.controls={'pex-5':('dev.pex.app','android.widget.Button','','','','[42,1596][267,1722]')}
    node='<node class="android.widget.Button" clickable="true" resource-id="" content-desc="" text="" bounds="%s"/>'
    async def hierarchy():
        xml='<hierarchy>'+''.join(node%f'[{x},1640][{x+225},1766]' for x in (42,299,556,813))+'</hierarchy>'
        return xml,android.ElementTree.fromstring(xml),[]
    device._hierarchy=hierarchy
    await device.act({'type':'tap','target':'pex-5'})
    assert calls[-1][-1]=='input tap 154 1703'


async def test_tap_ignores_the_unclickable_child_that_shares_the_bounds(monkeypatch,tmp_path):
    """Compose wraps a clickable node around a child with identical bounds; only the clickable one counts as a match."""
    calls=[]
    async def fake(*args,**kw):
        calls.append(args)
        return 'dumpsys window' not in args[-1] and '' or 'mFocusedApp=ActivityRecord{1 u0 dev.pex.app/.Main t1}'
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1';device.display=(1080,2400)
    device.controls={'pex-1':('dev.pex.app','android.view.View','','','','[220,2127][419,2337]')}
    xml='<hierarchy><node class="android.view.View" clickable="true" enabled="true" text="" content-desc="" resource-id="" bounds="[220,2127][419,2337]"><node class="android.view.View" clickable="false" enabled="true" text="" content-desc="" resource-id="" bounds="[220,2127][419,2337]"/></node></hierarchy>'
    async def hierarchy():return xml,android.ElementTree.fromstring(xml),[]
    device._hierarchy=hierarchy
    await device.act({'type':'tap','target':'pex-1'})
    assert calls[-1][-1]=='input tap 319 2232'

def device_for(monkeypatch,tmp_path,run_id='run'):
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'));monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    monkeypatch.setattr(android,'POLL',0)
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,run_id)
    device.serial='emulator-1';return device

async def test_a_failed_restore_still_restores_the_other_setting_and_never_claims_success(monkeypatch,tmp_path):
    """Wi-Fi refuses to come back on. Mobile data still goes back, and the run says which one did not."""
    device=device_for(monkeypatch,tmp_path)
    device.network_before={'wifi':'1','data':'0','console':'','route':'WIFI'};device.network_changed={'wifi','data'}
    async def shell(*args,**kw):return '0' if args[:2]==('settings','get') else ''
    device.shell=shell
    problems=await device.restore_network()
    assert len(problems)==1 and 'Wi-Fi' in problems[0]
    assert device.network_restore==[{'setting':'data','restored':True},{'setting':'wifi','restored':False}]
    assert device.network_changed=={'wifi'} and problems[0] in device.warnings

async def test_a_surviving_recording_refuses_to_pause_for_operator_input(monkeypatch,tmp_path):
    device=device_for(monkeypatch,tmp_path)
    device.record_task=asyncio.create_task(asyncio.sleep(0))
    async def shell(*args,**kw):
        if args[0]=='pidof':return '7'
        if args[0]=='cat':return 'screenrecord\x00/data/local/tmp/pex-run-1.mp4'
        return ''
    device.shell=shell
    with pytest.raises(android.AndroidError,match='still running'):await device.stop_recording()

async def test_recording_rotates_into_parts_and_reports_the_blind_gap(monkeypatch,tmp_path):
    device=device_for(monkeypatch,tmp_path)
    device.video_parts=[{'part':1,'name':'journey.mp4','ended_at':time.monotonic()-3}]
    class Proc:
        returncode=None
        async def wait(self):device.record_stop=True;return 0
    async def spawn(*a,**k):return Proc()
    async def nothing(*args,**kw):return ''
    monkeypatch.setattr(android.asyncio,'create_subprocess_exec',spawn)
    device.shell=nothing;device.adb_call=nothing
    await device._record()
    assert [p['name'] for p in device.video_parts]==['journey.mp4','journey-2.mp4']
    assert device.gaps[0]['after_part']==1 and 2.5<device.gaps[0]['seconds']<4 and not device.videos

STATUS=('Current network status:\n  download speed:          {down} bits/s (0.0 KB/s)\n'
        '  upload speed:            {up} bits/s (0.0 KB/s)\n'
        '  minimum latency:  {lo} ms\n  maximum latency:  {hi} ms\nOK')
UNSHAPED=STATUS.format(down=0,up=0,lo=0,hi=0)

def test_recorded_console_shaping_reads_back_as_console_arguments():
    """The console reports the two directions separately; it takes them back as up:down in kbps."""
    assert android.console_network(UNSHAPED)==('full','none')
    # A link that is slower up than down stays that way, and 14.4 kbit/s does not become 14.
    assert android.console_network(STATUS.format(down=256000,up=14400,lo=150,hi=400))==('14.4:256','150:400')
    # The old symmetric shape of this status is not what the emulator prints, and inventing the
    # missing half would restore the device to a link nobody measured.
    assert android.console_network('download speed: 240000 bits/s\nminimum latency: 150 ms\nmaximum latency: 400 ms') is None

def test_a_stored_profile_becomes_the_same_console_arguments():
    assert android.profile_console({'latency_ms':200,'down_mbps':1,'up_mbps':.5})==('500:1000','200:200')
    assert android.profile_console({'latency_ms':0,'down_mbps':0,'up_mbps':0})==('','')
    # A rate far below one kilobit is still a rate; rounding it away would report shaping that never happened.
    assert android.profile_console({'down_mbps':.0005,'up_mbps':.0005})[0]=='0.5:0.5'

def shaping_device(monkeypatch,tmp_path,wifi='0'):
    """A device on mobile data, recording every console command instead of issuing one."""
    device=device_for(monkeypatch,tmp_path);calls=[]
    async def shell(*args,**kw):
        if args[:3]==('settings','get','global'):return wifi if args[3]=='wifi_on' else '1'
        calls.append(args);return ''
    async def adb_call(*args,**kw):calls.append(args);return UNSHAPED
    device.shell=shell;device.adb_call=adb_call
    return device,calls

async def test_the_mission_link_is_the_condition_this_run_ran_under_not_a_fault_in_it(monkeypatch,tmp_path):
    device,calls=shaping_device(monkeypatch,tmp_path)
    device.profile={'name':'Poor mobile','latency_ms':200,'down_mbps':1,'up_mbps':.5}
    await device.apply_baseline()
    # Shaping reaches the radio, so the baseline takes the device there before it shapes anything.
    assert ('svc','data','enable') in calls and ('svc','wifi','disable') in calls
    assert calls[-3:]==[('emu','network','speed','500:1000'),('emu','network','delay','200:200'),('emu','network','status')]
    assert device.faults==[] and device.network_changed=={'wifi','data','speed','delay'}
    assert device.network_applied['applied']=={'speed':'500:1000','delay':'200:200'}
    assert device.network_applied['readback']==UNSHAPED and 'mobile radio only' in device.network_applied['scope']

async def test_an_unshaped_profile_touches_nothing_and_says_so(monkeypatch,tmp_path):
    device,calls=shaping_device(monkeypatch,tmp_path)
    device.profile={'name':'Baseline'}
    await device.apply_baseline()
    assert not calls and not device.network_changed
    assert device.network_applied['verification']=='Nothing applied'

async def test_shaping_a_wifi_link_is_refused_because_the_console_cannot_change_it(monkeypatch,tmp_path):
    """Measured on emulator 36.6.11.0: over Wi-Fi the console accepts the command, reads the new
    value back, and the traffic is unchanged. Applying it there would report a link that is not real."""
    device,calls=shaping_device(monkeypatch,tmp_path,wifi='1')
    with pytest.raises(android.AndroidError,match='mobile radio only'):await device.apply_speed('edge')
    assert not calls and device.faults==[]

async def test_a_step_restore_goes_back_to_the_mission_link_and_the_final_one_to_the_device(monkeypatch,tmp_path):
    """Two restoration targets. `network: restore` undoes the scenario's faults and leaves the run
    standing on its own profile; only the final cleanup puts the device back where it was found."""
    device,calls=shaping_device(monkeypatch,tmp_path)
    device.profile={'name':'Poor mobile','latency_ms':200,'down_mbps':1,'up_mbps':.5}
    device.network_before={'wifi':'0','data':'1','console':STATUS.format(down=8000,up=8000,lo=5,hi=5),'route':'MOBILE'}
    device.network_changed={'speed','delay'}
    await device.apply_network('restore')
    assert [c for c in calls if c[:2]==('emu','network')][:4]==[
        ('emu','network','speed','8:8'),('emu','network','delay','5:5'),
        ('emu','network','speed','500:1000'),('emu','network','delay','200:200')]
    assert device.faults==[{'network':'restore'}]
    calls.clear()
    problems=await device.restore_network()
    assert not problems and [c for c in calls if c[:2]==('emu','network')]==[
        ('emu','network','speed','8:8'),('emu','network','delay','5:5')]

async def test_an_unreadable_capture_never_restores_the_device_to_an_invented_default(monkeypatch,tmp_path):
    device,calls=shaping_device(monkeypatch,tmp_path)
    device.network_before={'wifi':'1','data':'1','console':'error: device offline','route':''}
    device.network_changed={'speed','delay'}
    problems=await device.restore_network()
    assert not calls and len(problems)==2 and all('No recorded emulator' in problem for problem in problems)
    assert device.network_restore==[{'setting':'delay','restored':False},{'setting':'speed','restored':False}]

def fake_avd(monkeypatch,tmp_path,name='pex-test'):
    home=tmp_path/'avd';(home/(name+'.avd')).mkdir(parents=True)
    monkeypatch.setenv('ANDROID_AVD_HOME',str(home));monkeypatch.setenv('PEX_ANDROID_AVD',name)
    monkeypatch.setattr(android.targets,'tool',lambda n:Path('/bin/true'))
    return name

class Relayed:
    """Stands in for the run's relay: all a device needs from it is the address to launch against."""
    proxy='http://127.0.0.1:54321'

async def test_an_emulator_that_routes_is_one_this_run_started_against_the_relay(monkeypatch,tmp_path):
    fake_avd(monkeypatch,tmp_path)
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run',relay=Relayed())
    launched=[]
    class Stop(Exception):pass
    async def spawn(*args,**kw):launched.extend(args);raise Stop
    async def none(self=None):return ''
    monkeypatch.setattr(android.asyncio,'create_subprocess_exec',spawn)
    device._find_serial=none
    with pytest.raises(Stop):await device.start()
    # Host-side, so the guest keeps no proxy setting of its own and no app can opt out of it.
    assert launched[launched.index('-http-proxy')+1]==Relayed.proxy and '-no-snapshot' in launched

async def test_an_emulator_already_running_is_refused_before_this_run_touches_it(monkeypatch,tmp_path):
    fake_avd(monkeypatch,tmp_path)
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run',relay=Relayed())
    touched=[]
    async def running(self=None):return 'emulator-5554'
    async def shell(*args,**kw):touched.append(args);return ''
    device._find_serial=running;device.shell=shell
    with pytest.raises(android.AndroidError,match='stop the designated AVD first'):await device.start()
    assert not touched

async def test_a_device_without_a_relay_cannot_change_route(monkeypatch,tmp_path):
    device=device_for(monkeypatch,tmp_path)
    with pytest.raises(android.AndroidError,match='not started with a relay'):await device.apply_route('direct')

def saving_emulator(avd):
    async def fake_run(*args,**kw):
        if 'devices' in args:return 'List of devices\nemulator-1\tdevice\n'
        if 'name' in args:return avd+'\n'
        if 'save' in args:
            folder=android.snapshot_root(avd)/args[-1];folder.mkdir(parents=True)
            (folder/'ram.img').write_bytes(b'state');return 'OK'
        return '34'
    return fake_run

async def test_a_managed_snapshot_is_identified_by_its_files_and_never_by_its_name(monkeypatch,tmp_path):
    avd=fake_avd(monkeypatch,tmp_path);monkeypatch.setattr(android,'run',saving_emulator(avd))
    one=await android.capture_snapshot(avd,'Signed in as A','p1')
    two=await android.capture_snapshot(avd,'Signed in as A','p1')
    assert one['id']!=two['id'] and one['identity']!='' # the same display name overwrites nothing
    assert [s['available'] for s in android.snapshots(avd,'p1')]==[True,True]
    assert android.snapshots(avd,'other')==[]  # another workspace cannot see this authenticated state
    (android.snapshot_root(avd)/one['id']/'ram.img').write_bytes(b'tampered state')
    changed=next(s for s in android.snapshots(avd,'p1') if s['id']==one['id'])
    assert changed['available'] is False and 'changed' in changed['note']
    await android.delete_snapshot(avd,two['id'],'p1')
    assert [s['id'] for s in android.snapshots(avd,'p1')]==[one['id']]

async def test_snapshot_work_refuses_while_a_run_owns_the_device(monkeypatch,tmp_path):
    avd=fake_avd(monkeypatch,tmp_path)
    held=(android.avd_dir(avd)/'.pex.lock').open('a');android.fcntl.flock(held,android.fcntl.LOCK_EX|android.fcntl.LOCK_NB)
    for call in (android.capture_snapshot(avd,'x','p1'),android.delete_snapshot(avd,'a'*16,'p1')):
        with pytest.raises(android.AndroidError,match='busy'):await call
    held.close()

async def test_a_changed_or_missing_snapshot_never_loads_the_current_state_silently(monkeypatch,tmp_path):
    avd=fake_avd(monkeypatch,tmp_path);monkeypatch.setattr(android,'run',saving_emulator(avd))
    entry=await android.capture_snapshot(avd,'Signed in as A','p1')
    device=android.Device({'device':avd,'project_id':'p1','snapshot':entry['id']},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1'
    with pytest.raises(android.AndroidError,match='no managed snapshot|has no managed'):await device.load_snapshot('b'*16)
    (android.snapshot_root(avd)/entry['id']/'ram.img').write_bytes(b'tampered state')
    with pytest.raises(android.AndroidError,match='changed since capture'):await device.load_snapshot(entry['id'])
    other=android.Device({'device':avd,'project_id':'p2','snapshot':entry['id']},{'package':'dev.pex.app'},tmp_path,'run')
    with pytest.raises(android.AndroidError,match='another workspace'):await other.load_snapshot(entry['id'])

# --- playback and notification evidence --------------------------------------

MEDIA_DUMP='''Sessions Stack - have 2 sessions:
  dev.pex.app/Playback (userId=0)
    ownerPid=900
    package=dev.pex.app
    state=PlaybackState {state=3, position=4200, buffered position=0, speed=1.0, updated=88000, actions=5}
  com.other/Music (userId=0)
    package=com.other
    state=PlaybackState {state=2, position=0, speed=0.0, updated=10}
'''

NOTIFICATION_DUMP='''Current Notification Manager state:
  Notification List:
    NotificationRecord(0xa: pkg=dev.pex.app user=0 id=1 key=0|dev.pex.app|1|null|10123: importance=3)
      channel=NotificationChannel{mSound=null, mLights=false, mLightColor=0, mShowBadge=true}
      extras={
        android.title=String (Download finished)
        android.text=String (Movie X (240p) added)
      }
    NotificationRecord(0xb: pkg=com.other user=0 id=2 key=0|com.other|2|null|10500: importance=3)
        android.title=String (Download finished)
  Historical Notifications:
    NotificationRecord(0xc: pkg=dev.pex.app user=0 id=7 key=0|dev.pex.app|7|null|10123: old)
        android.title=String (Download finished)
'''

def test_playback_and_notification_dumps_are_read_per_package_and_exclude_history():
    mine=android.parse_media(MEDIA_DUMP,'dev.pex.app')
    assert mine['state']=='playing' and mine['position']==4200 and mine['updated']==88000
    assert android.parse_media(MEDIA_DUMP,'com.other')['state']=='paused'
    assert android.parse_media(MEDIA_DUMP,'dev.pex.absent') is None
    posted=android.parse_notifications(NOTIFICATION_DUMP)
    # The archived copy of the same notification must not read as still showing.
    assert [n['key'] for n in posted]==['0|dev.pex.app|1|null|10123','0|com.other|2|null|10500']
    # A record's own 'mLights=false' is not the 'Lights' section, and a title carries its own brackets.
    assert posted[0]['text']=='Download finished\nMovie X (240p) added'

async def test_a_notification_shared_with_another_app_is_never_opened_by_text(monkeypatch,tmp_path):
    device=device_for(monkeypatch,tmp_path);calls=[]
    async def shell(*args,**kw):
        calls.append(args)
        return NOTIFICATION_DUMP if args[0]=='dumpsys' and args[1]=='notification' else ''
    device.shell=shell
    with pytest.raises(android.AndroidError,match='another app'):await device.open_notification('Download finished')
    assert not any(call[0]=='input' for call in calls)
    # Text only this app posted resolves to one record, and the shade is closed either way.
    calls.clear();device._hierarchy=lambda:_shade()
    focus=iter(['','dev.pex.app/Player']);device.focused=lambda:_value(next(focus))
    assert await device.open_notification('Movie X')=='dev.pex.app/Player'
    assert ('input','tap','50','120') in calls and ('cmd','statusbar','collapse') in calls

async def _value(v):return v
async def _shade():
    xml='<hierarchy rotation="0"><node text="Movie X" bounds="[0,100][100,140]" /></hierarchy>'
    return android.sanitize_xml(xml)


@pytest.mark.asyncio
async def test_a_window_dump_is_judged_by_its_xml_not_by_the_exit_code(monkeypatch,tmp_path):
    """uiautomator exits non-zero mid-animation and can leave a half-written file; one retry recovers."""
    monkeypatch.setattr(android.targets,'tool',lambda name:Path('/bin/true'))
    slept=asyncio.sleep
    monkeypatch.setattr(android.asyncio,'sleep',lambda seconds:slept(0))
    reads=['UI hierchary dumped to: /data/local/tmp/pex-window.xml','<hierarchy><node bounds="[0,0][1,1]"/></hierarchy>']
    async def fake(*args,**kw):
        assert kw.get('check') is False
        return reads.pop(0) if 'cat' in args else 'UI hierchary dumped to: /data/local/tmp/pex-window.xml'
    monkeypatch.setattr(android,'run',fake);monkeypatch.setenv('PEX_ANDROID_AVD','pex-test')
    device=android.Device({'device':'pex-test'},{'package':'dev.pex.app'},tmp_path,'run')
    device.serial='emulator-1'
    xml,root,sensitive=await device._hierarchy()
    assert root.find('node') is not None and sensitive==[]
    reads[:]=['not xml','still not xml']
    with pytest.raises(android.AndroidError,match='readable window dump'):await device._hierarchy()
