import asyncio
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
    await device.stop()
    assert ('kill','-2','42') in calls and not any(call[:1] in (('pidof',),('pkill',)) for call in calls)

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
