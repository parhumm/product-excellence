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

def test_recorded_console_shaping_reads_back_as_console_arguments():
    assert android.console_network('download speed: 0 bits/s\nminimum latency: 0 ms\nmaximum latency: 0 ms')==('full','none')
    assert android.console_network('download speed: 240000 bits/s\nminimum latency: 150 ms\nmaximum latency: 400 ms')==('240:240','150:400')

def fake_avd(monkeypatch,tmp_path,name='pex-test'):
    home=tmp_path/'avd';(home/(name+'.avd')).mkdir(parents=True)
    monkeypatch.setenv('ANDROID_AVD_HOME',str(home));monkeypatch.setenv('PEX_ANDROID_AVD',name)
    monkeypatch.setattr(android.targets,'tool',lambda n:Path('/bin/true'))
    return name

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
      extras={
        android.title=String (Download finished)
        android.text=String (Movie X)
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
    assert posted[0]['text']=='Download finished\nMovie X'

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
