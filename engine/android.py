"""Concrete, bounded adb/emulator lifecycle for one designated disposable AVD."""
import asyncio, contextlib, fcntl, hashlib, json, os, re, shlex, shutil, signal, time, uuid
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image,ImageDraw
from . import store,targets
from .policy import scrub

PACKAGE=re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')
TOKEN=re.compile(r'^[A-Za-z0-9_.:-]+$')
BOUNDS=re.compile(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$')

class AndroidError(ValueError):pass

async def run(*args,timeout=30,limit=2*1024*1024,binary=False,check=True):
    process=await asyncio.create_subprocess_exec(*(str(x) for x in args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    async def read(stream):
        kept=bytearray();total=0
        while chunk:=await stream.read(65536):
            total+=len(chunk)
            if len(kept)<limit:kept.extend(chunk[:limit-len(kept)])
        return bytes(kept),total
    readers=[asyncio.create_task(read(process.stdout)),asyncio.create_task(read(process.stderr))]
    try:await asyncio.wait_for(process.wait(),timeout)
    except (asyncio.TimeoutError,asyncio.CancelledError):
        process.terminate()
        try:await asyncio.wait_for(process.wait(),3)
        except asyncio.TimeoutError:process.kill();await process.wait()
        await asyncio.gather(*readers,return_exceptions=True)
        raise
    stdout,stderr=await asyncio.gather(*readers)
    if stdout[1]>limit or stderr[1]>limit:raise AndroidError('Android command output exceeded its safety limit')
    if check and process.returncode:
        msg=(stderr[0] or stdout[0]).decode(errors='replace')[-1000:].strip()
        raise AndroidError(msg or f'{args[0]} exited with code {process.returncode}')
    return stdout[0] if binary else stdout[0].decode(errors='replace').strip()

def avd_dir(name):
    if not TOKEN.fullmatch(name):raise AndroidError('Invalid AVD name')
    home=Path(os.environ.get('ANDROID_AVD_HOME',Path.home()/'.android/avd')).resolve()
    ini=home/(name+'.ini')
    if ini.is_file():
        match=re.search(r'^path=(.+)$',ini.read_text(),re.M)
        if match:return Path(match[1]).expanduser().resolve()
    path=home/(name+'.avd')
    if not path.is_dir():raise AndroidError('Designated AVD does not exist: '+name)
    return path.resolve()

def parse_bounds(value):
    match=BOUNDS.fullmatch(value or '')
    return tuple(map(int,match.groups())) if match else None

# MediaSession reports its own clock. `updated` is device uptime in ms, so only its movement,
# never arithmetic on the host clock, says whether the reported position actually advanced.
PLAY_STATES={'0':'none','1':'stopped','2':'paused','3':'playing','6':'buffering','7':'error',
             'NONE':'none','STOPPED':'stopped','PAUSED':'paused','PLAYING':'playing','BUFFERING':'buffering','ERROR':'error'}
SESSION_STATE=re.compile(r'PlaybackState\s*\{([^}]*)\}')
# Sections that follow the active list. Everything after them is history or configuration, never posted now.
# They are headings, so they are anchored: a record's own fields carry 'mLights=false', and a bare
# substring search cut the list at the very first record.
AFTER_ACTIVE=re.compile(r'^\s{0,4}(?:Historical Notifications|Notification Statistics|Ranking Config|Zen Mode|Lights)\b',re.M)
# The value runs to the end of its line: a film title carries its own brackets, as in
# 'android.text=String ( x (240p) به گالری آفلاین اضافه شد)', so the first ')' is not the end.
RECORD_TEXT=re.compile(r'android\.(?:title|text|bigText|subText|summaryText)=\w*\s*\((.*)\)\s*$',re.M)

def parse_media(dump,package):
    """The package's own MediaSession sample, or None when the dump names no session for it."""
    best=None
    for match in re.finditer(r'package=\s*'+re.escape(package)+r'\b',dump):
        rest=dump[match.end():];nxt=re.search(r'\n\s*package=',rest)
        found=SESSION_STATE.search(rest[:nxt.start()] if nxt else rest)
        if not found:continue
        fields=found.group(1)
        code=re.search(r'state=(\w+)',fields);position=re.search(r'position=(-?\d+)',fields)
        updated=re.search(r'updated=(\d+)',fields);speed=re.search(r'speed=(-?[\d.]+)',fields)
        best={'state':PLAY_STATES.get(code.group(1) if code else '','unknown'),
              'position':int(position.group(1)) if position else None,
              'updated':int(updated.group(1)) if updated else None,
              'speed':float(speed.group(1)) if speed else None,'raw':fields.strip()[:300]}
    return best

def parse_notifications(dump):
    """Only what is posted right now: the active list, cut before history and statistics."""
    start=dump.find('Notification List:')
    body=dump[start:] if start>=0 else dump
    cut=AFTER_ACTIVE.search(body)
    if cut and cut.start()>0:body=body[:cut.start()]
    posted=[]
    for record in body.split('NotificationRecord(')[1:]:
        package=re.search(r'pkg=(\S+)',record);key=re.search(r'key=(\S+?)[:\s)]',record)
        if not package:continue
        posted.append({'package':package.group(1),'key':key.group(1) if key else '',
                       'text':'\n'.join(RECORD_TEXT.findall(record))})
    return posted

def redact_log(line):
    return re.sub(r'(?i)\b(authorization|password|token|cookie)\s*[:=]\s*\S+',r'\1=[REDACTED]',line)

def sanitize_xml(raw):
    root=ElementTree.fromstring(raw);sensitive=[]
    for node in root.iter('node'):
        if node.get('password')=='true':
            sensitive.append(parse_bounds(node.get('bounds')));node.set('text','');node.set('content-desc','Password field')
    return ElementTree.tostring(root,encoding='unicode'),root,[box for box in sensitive if box]

def scoped_logs(lines,package):
    """Keep package lines and complete AndroidRuntime blocks attributed to it."""
    kept=[];i=0
    while i<len(lines):
        line=lines[i]
        if 'FATAL EXCEPTION' in line:
            block=[line];i+=1
            while i<len(lines) and 'AndroidRuntime' in lines[i] and 'FATAL EXCEPTION' not in lines[i]:block.append(lines[i]);i+=1
            if any(('Process: '+package) in item or package in item for item in block):kept.extend(block)
            continue
        if package in line:kept.append(line)
        i+=1
    return [redact_log(line) for line in kept]

def write_log_parts(folder,lines,part_size=5*1024*1024):
    data=''.join(lines).encode();names=[]
    for offset in range(0,len(data),part_size):
        number=offset//part_size+1;name='logcat.txt' if number==1 else f'logcat-{number}.txt'
        (folder/name).write_bytes(data[offset:offset+part_size]);names.append(name)
    return names

SNAPSHOT_ID=re.compile(r'^[a-z0-9]{8,64}$')

async def find_serial(adb,avd):
    devices=await run(adb,'devices')
    for line in devices.splitlines()[1:]:
        if '\tdevice' not in line:continue
        serial=line.split()[0]
        name=await run(adb,'-s',serial,'emu','avd','name',check=False)
        if name.splitlines() and name.splitlines()[0]==avd:return serial
    return ''

def snapshot_root(avd):return avd_dir(avd)/'snapshots'
def manifest_path(avd):return avd_dir(avd)/'pex-snapshots.json'

def read_manifest(avd):
    try:entries=json.loads(manifest_path(avd).read_text())
    except (OSError,ValueError):return []
    return entries if isinstance(entries,list) else []

def state_identity(avd,id):
    """Digest of the saved state files: names, sizes and modification times.

    It catches a replaced, truncated, restored-from-elsewhere or missing snapshot. It is not a
    content hash, so it does not detect silent bit rot inside an otherwise untouched image.
    """
    # ponytail: metadata digest; hash contents if a tampered same-size image ever has to be caught
    if not SNAPSHOT_ID.fullmatch(id or ''):raise AndroidError('Invalid snapshot id')
    folder=snapshot_root(avd)/id
    if not folder.is_dir():return '',0,0
    digest=hashlib.sha256();files=0;total=0
    for path in sorted(p for p in folder.rglob('*') if p.is_file()):
        info=path.stat();files+=1;total+=info.st_size
        digest.update(f'{path.relative_to(folder)}|{info.st_size}|{info.st_mtime_ns}\n'.encode())
    return digest.hexdigest()[:32],files,total

@contextlib.contextmanager
def avd_lock(avd):
    """The exclusive lock a run holds, so snapshot work never touches a device mid-mission."""
    handle=(avd_dir(avd)/'.pex.lock').open('a')
    try:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise AndroidError('The designated AVD is busy with a run') from error
        yield
    finally:
        fcntl.flock(handle,fcntl.LOCK_UN);handle.close()

def snapshots(avd,project=''):
    """Managed snapshots this workspace may use, each with what is actually on disk now."""
    found=[]
    for entry in read_manifest(avd):
        if project and entry.get('project_id') and entry['project_id']!=project:continue
        try:identity,files,total=state_identity(avd,entry.get('id',''))
        except AndroidError:continue
        usable=bool(identity) and identity==entry.get('identity')
        found.append({**entry,'available':usable,'bytes_now':total,'files_now':files,
                      'note':'' if usable else ('The saved state files are missing' if not identity else
                             'The saved state files changed since capture, so this snapshot can no longer be loaded')})
    return found

async def capture_snapshot(avd,name,project=''):
    """Save the running device's state under a new managed ID. Existing snapshots are never overwritten."""
    name=(name or '').strip()
    if not name:raise AndroidError('Name this snapshot so you can recognise it later')
    adb=targets.tool('adb')
    with avd_lock(avd):
        serial=await find_serial(adb,avd)
        if not serial:raise AndroidError('Start the designated AVD and prepare the state you want to save first')
        id=uuid.uuid4().hex[:16]
        answer=await run(adb,'-s',serial,'emu','avd','snapshot','save',id,timeout=600,check=False)
        identity,files,total=state_identity(avd,id)
        if not identity:raise AndroidError('The emulator saved no snapshot files: '+answer.strip()[-300:])
        props={}
        for key,prop in (('api','ro.build.version.sdk'),('abi','ro.product.cpu.abi'),('fingerprint','ro.build.fingerprint')):
            props[key]=(await run(adb,'-s',serial,'shell','getprop '+prop,check=False)).strip()
        entry={'id':id,'name':name[:100],'avd':avd,'project_id':project,'created_at':store.now(),
               'identity':identity,'files':files,'bytes':total,'result':answer.strip()[-300:] or 'saved',**props}
        manifest_path(avd).write_text(json.dumps(read_manifest(avd)+[entry],ensure_ascii=False,indent=2))
        return entry

async def delete_snapshot(avd,id,project=''):
    if not SNAPSHOT_ID.fullmatch(id or ''):raise AndroidError('Invalid snapshot id')
    with avd_lock(avd):
        entries=read_manifest(avd)
        entry=next((e for e in entries if e.get('id')==id and (not project or not e.get('project_id') or e['project_id']==project)),None)
        if not entry:raise AndroidError('This workspace has no managed snapshot with that id')
        shutil.rmtree(snapshot_root(avd)/id,ignore_errors=True)
        manifest_path(avd).write_text(json.dumps([e for e in entries if e.get('id')!=id],ensure_ascii=False,indent=2))
        return {'ok':True,'id':id,'name':entry.get('name','')}

# Transports as the device reports them: (Wi-Fi on, mobile data on).
TRANSPORTS={'wifi':(True,False),'cellular':(False,True),'offline':(False,False)}
PART_SECONDS=180
MAX_PARTS=40
POLL=1

def console_network(status):
    """The emulator shaping recorded before any fault, as arguments the console accepts again."""
    down=re.search(r'download speed:\s*(\d+)',status);low=re.search(r'minimum latency:\s*(\d+)',status)
    high=re.search(r'maximum latency:\s*(\d+)',status)
    kbits=int(down.group(1))//1000 if down else 0
    lo=int(low.group(1)) if low else 0;hi=int(high.group(1)) if high else lo
    return ('full' if not kbits else f'{kbits}:{kbits}'),('none' if not (lo or hi) else f'{lo}:{hi}')

def health():
    avd=os.environ.get('PEX_ANDROID_AVD','');reason=''
    # Only an emulator this console starts itself is known to have a window; one already running may have none.
    window=os.environ.get('PEX_ANDROID_WINDOW')=='1'
    try:
        adb=targets.tool('adb');emulator=targets.tool('emulator')
        if avd:avd_dir(avd)
        else:reason='Set PEX_ANDROID_AVD to a disposable AVD'
        return {'available':bool(avd and not reason),'avd':avd,'adb':str(adb),'emulator':str(emulator),'reason':reason,'window':window}
    except (ValueError,AndroidError) as error:return {'available':False,'avd':avd,'reason':str(error),'window':window}

class Device:
    def __init__(self,mission,app,folder,run_id,*,avd=None):
        self.mission=mission;self.app=app;self.folder=Path(folder);self.run_id=run_id
        self.avd=avd or mission.get('device') or os.environ.get('PEX_ANDROID_AVD','')
        self.adb=targets.tool('adb');self.emulator=targets.tool('emulator');self.serial=''
        self.lock_file=None;self.owned=None;self.log_process=None;self.log_task=None;self.log_lines=[]
        self.recorder=None;self.recorder_pid='';self.remote_video='';self.controls={};self.launched=False;self.stopped=False
        self.warnings=[];self.events=[];self.measurements={};self.videos=[];self.logs=[];self.network_before={};self.display=(1080,2400)
        self.record_task=None;self.record_stop=False;self.video_parts=[];self.gaps=[]
        self.network_changed=set();self.network_restore=[];self.faults=[]
        # Operator-supplied values never reach evidence, a prompt or the run record.
        self.supplied=[]
        package=app.get('package','')
        if not PACKAGE.fullmatch(package):raise AndroidError('Invalid Android package')
        if not self.avd or self.avd!=os.environ.get('PEX_ANDROID_AVD',''):raise AndroidError('Choose the designated disposable AVD')

    async def adb_call(self,*args,**kw):
        if not self.serial:raise AndroidError('Device is not ready')
        return await run(self.adb,'-s',self.serial,*args,**kw)

    async def shell(self,*args,**kw):
        if not all(isinstance(x,str) for x in args):raise AndroidError('Invalid shell argument')
        return await self.adb_call('shell',shlex.join(args),**kw)

    async def _find_serial(self):return await find_serial(self.adb,self.avd)

    async def start(self):
        path=avd_dir(self.avd);self.lock_file=(path/'.pex.lock').open('a')
        try:fcntl.flock(self.lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise AndroidError('Designated AVD is already in use by another run') from error
        self.serial=await self._find_serial()
        if not self.serial:
            args=[self.emulator,'-avd',self.avd,'-no-snapshot','-no-audio','-gpu','auto']
            if os.environ.get('PEX_ANDROID_WINDOW')!='1':args.append('-no-window')
            self.owned=await asyncio.create_subprocess_exec(*(str(x) for x in args),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            for _ in range(90):
                await asyncio.sleep(1);self.serial=await self._find_serial()
                if self.serial:break
        if not self.serial:raise AndroidError('AVD did not expose an adb device')
        for _ in range(90):
            if await self.shell('getprop','sys.boot_completed',check=False)=='1':break
            await asyncio.sleep(1)
        else:raise AndroidError('AVD boot exceeded 90 seconds')
        api=int(await self.shell('getprop','ro.build.version.sdk'));abi=await self.shell('getprop','ro.product.cpu.abi')
        if api<self.app['min_sdk']:raise AndroidError(f'APK needs API {self.app["min_sdk"]}; device is API {api}')
        if self.app.get('abis') and abi not in self.app['abis']:raise AndroidError(f'APK ABIs {self.app["abis"]} do not include device {abi}')
        renderer=await self.shell('getprop','ro.hardware.egl',check=False)
        self.measurements.update(api=api,abi=abi,renderer=renderer or 'auto',avd=self.avd)
        if self.mission.get('snapshot'):await self.load_snapshot(self.mission['snapshot'])
        # Android's one-time "swipe down to exit full screen" hint is a system window the app cannot dismiss; confirm it up front.
        await self.shell('settings','put','secure','immersive_mode_confirmations','confirmed',check=False)
        self.log_process=await asyncio.create_subprocess_exec(str(self.adb),'-s',self.serial,'logcat','-v','threadtime',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        self.log_task=asyncio.create_task(self._read_logs())
        apk=store.DATA/'apps'/(self.app['sha256']+'.apk')
        if not apk.is_file():raise AndroidError('Upload this exact build on this console: '+self.app['sha256'])
        with apk.open('rb') as source:
            if hashlib.file_digest(source,'sha256').hexdigest()!=self.app['sha256']:raise AndroidError('Local APK checksum differs from build metadata')
        try:await self.adb_call('install','-r',str(apk),timeout=90)
        except AndroidError as error:raise AndroidError('APK install failed; resolve signature, downgrade or split requirements: '+str(error)[-500:]) from error
        if self.mission.get('snapshot'):pass  # load_snapshot already recorded where this run started
        elif self.mission.get('reset','fresh')=='keep':self.measurements['start_state']='kept'
        else:
            cleared=await self.shell('pm','clear',self.app['package'])
            if cleared.strip()!='Success':raise AndroidError('Could not clear this package before the mission')
            self.measurements['start_state']='fresh'
        network=self.mission.get('network','baseline')
        if network!='baseline':raise AndroidError('Android 1.5 supports only baseline here; verified offline is not configured')
        self.folder.mkdir(parents=True,exist_ok=True)
        await self.capture_network()
        await self.start_recording()

    async def _read_logs(self):
        total=0
        while line:=await self.log_process.stdout.readline():
            total+=len(line)
            if total>100*1024*1024:
                self.warnings.append('Android log evidence reached the 100 MiB safety limit');self.log_process.terminate();break
            self.log_lines.append(line.decode(errors='replace'))

    async def launch(self,url=''):
        """Start the app. A scenario may start it again later; the first launch stays the measured one."""
        first=not self.launched;self.launched=True;before=time.monotonic()
        if url:output=await self.shell('am','start','-W','-a','android.intent.action.VIEW','-d',url,'-p',self.app['package'],timeout=30)
        else:output=await self.shell('am','start','-W','-n',self.app['package']+'/'+self.app['launch_activity'],timeout=30)
        status='ok' if 'Status: ok' in output else 'error'
        if first:
            match=re.search(r'^TotalTime: (\d+)',output,re.M)
            self.measurements['launch_ms']=int(match[1]) if match else None
            self.measurements['setup_to_launch_ms']=round((time.monotonic()-before)*1000)
            self.measurements['launch_status']=status
        if status!='ok':raise AndroidError('App launch failed: '+output[-500:])

    def log_cursor(self):
        """Where the collected log stands now, so a later check only sees what followed it."""
        return len(self.log_lines)

    def crash_since(self,cursor):
        """Attributable crash or ANR text after `cursor`; '' when there is none, None when no evidence is being collected."""
        if not self.log_process or self.log_process.returncode is not None:return None
        text=''.join(scoped_logs(self.log_lines[cursor:],self.app['package']))
        found=[]
        if 'FATAL EXCEPTION' in text:found.append(text[text.index('FATAL EXCEPTION'):][:2000])
        anr=re.search(r'ANR in '+re.escape(self.app['package'])+r'[^\n]*',text)
        if anr:found.append(anr.group(0))
        return '\n'.join(found)

    async def sample(self):
        """One cheap read of what is in front: focused activity and readable screen text. Never raises."""
        found={'at':store.now(),'activity':'','package':''}
        try:activity=await self.focused()
        except Exception as error:found['error']='Focused activity unavailable: '+str(error)[:200];return found
        if not activity:found['error']='No window reported focus';return found
        found.update(activity=activity,package=activity.split('/')[0])
        try:_,root,_=await self._hierarchy()
        except Exception as error:found['error']='Screen hierarchy unavailable: '+str(error)[:200];return found
        found['text']='\n'.join(n.get('text','') for n in root.iter('node') if n.get('text'))
        found['labels']='\n'.join(n.get('content-desc','') for n in root.iter('node') if n.get('content-desc'))
        return found

    async def media_state(self):
        """One MediaSession sample for this package, or None when no session is reported for it."""
        dump=await self.shell('dumpsys','media_session',check=False,timeout=15)
        return parse_media(dump,self.app['package']) if dump else None

    async def notifications(self):
        """What the device is showing right now. Raises when the dump cannot be read at all."""
        dump=await self.shell('dumpsys','notification','--noredact',check=False,timeout=15)
        # --noredact is rejected on older platforms; the plain dump still lists the same records.
        if 'Notification List' not in dump:dump=await self.shell('dumpsys','notification',check=False,timeout=15)
        if 'Notification List' not in dump:raise AndroidError('Active notifications could not be read: '+(dump or 'empty dump')[:200])
        return parse_notifications(dump)

    async def open_notification(self,text):
        """Open the one notification this package posted with that text, and prove where it landed."""
        posted=await self.notifications()
        mine=[n for n in posted if text in n['text'] and n['package']==self.app['package']]
        others=[n for n in posted if text in n['text'] and n['package']!=self.app['package']]
        # Tapping shade text that another app also posted would test that app, so refuse instead.
        if others:raise AndroidError(f'{len(others)} notification(s) from another app also say "{text[:60]}"; the text does not identify one')
        if not mine:raise AndroidError(f'No notification from {self.app["package"]} says "{text[:60]}" right now')
        if len(mine)>1:raise AndroidError(f'{len(mine)} notifications from this app say "{text[:60]}"; the text does not identify one')
        await self.shell('cmd','statusbar','expand-notifications')
        try:
            await asyncio.sleep(2)
            _,root,_=await self._hierarchy()
            rows=[parse_bounds(node.get('bounds')) for node in root.iter('node') if text in node.get('text','')]
            rows=[box for box in rows if box]
            if not rows:raise AndroidError('The notification is posted but its text is not visible in the shade')
            box=rows[0];await self.shell('input','tap',str((box[0]+box[2])//2),str((box[1]+box[3])//2))
            for _ in range(10):
                await asyncio.sleep(POLL)
                focus=await self.focused()
                if focus.startswith(self.app['package']+'/'):return focus
            raise AndroidError('Opening the notification did not bring '+self.app['package']+' to the front')
        finally:
            await self.shell('cmd','statusbar','collapse',check=False)

    async def processes(self):
        return (await self.shell('pidof',self.app['package'],check=False)).split()

    async def home(self):
        await self.shell('input','keyevent','KEYCODE_HOME')

    async def background_kill(self):
        """Approximate the system reclaiming a backgrounded app. A foreground service can refuse this."""
        await self.home();await asyncio.sleep(1)
        await self.shell('am','kill',self.app['package'],check=False)
        for _ in range(5):
            if not await self.processes():return
            await asyncio.sleep(1)
        raise AndroidError('Package processes stayed alive after am kill; a foreground service may be holding them')

    async def relaunch(self):
        await self.shell('am','force-stop',self.app['package'])
        await self.launch('')

    async def open_deep_link(self,url):
        output=await self.shell('am','start','-W','-a','android.intent.action.VIEW','-d',url,'-p',self.app['package'],timeout=30)
        if 'Status: ok' not in output and 'Activity not started' not in output:raise AndroidError('The deep link did not start an activity: '+output[-300:])
        return output

    async def load_snapshot(self,id):
        """Restore a saved local device state, refusing anything that is not the state that was captured."""
        entry=next((e for e in read_manifest(self.avd) if e.get('id')==id),None)
        if not entry:raise AndroidError('This machine has no managed snapshot called '+id)
        project=self.mission.get('project_id','')
        if entry.get('project_id') and project and entry['project_id']!=project:raise AndroidError('That snapshot belongs to another workspace')
        if entry.get('avd') and entry['avd']!=self.avd:raise AndroidError('That snapshot was captured on a different AVD')
        identity,files,total=state_identity(self.avd,id)
        if not identity:raise AndroidError('The saved state files for this snapshot are missing')
        if identity!=entry.get('identity'):raise AndroidError('The saved state files changed since capture; this snapshot can no longer be loaded')
        answer=await self.adb_call('emu','avd','snapshot','load',id,timeout=600,check=False)
        if 'OK' not in answer.upper():raise AndroidError('The emulator refused to load the snapshot: '+answer.strip()[-300:])
        for _ in range(90):
            if await self.shell('getprop','sys.boot_completed',check=False)=='1':break
            await asyncio.sleep(1)
        else:raise AndroidError('The device did not come back after loading the snapshot')
        api=(await self.shell('getprop','ro.build.version.sdk')).strip()
        if entry.get('api') and api!=str(entry['api']):raise AndroidError(f"This snapshot was captured on API {entry['api']}; the device is now API {api}")
        # Local device state only: account, entitlement and server data are still whatever the backend says now.
        self.measurements['start_state']='snapshot'
        self.measurements['snapshot']={'id':id,'name':entry.get('name',''),'identity':identity,'captured_at':entry.get('created_at','')}
        return entry

    async def capture_network(self):
        """What the network looked like before any fault, so restoration targets the real values."""
        self.network_before={'wifi':(await self.shell('settings','get','global','wifi_on',check=False)).strip(),
                             'data':(await self.shell('settings','get','global','mobile_data',check=False)).strip(),
                             'console':await self.adb_call('emu','network','status',check=False),
                             'route':await self.active_route()}
        self.measurements['network_before']=dict(self.network_before)
        if self.network_before['wifi']=='0' and self.network_before['data']=='0':
            self.warnings.append('This device started with both Wi-Fi and mobile data off; an earlier run may have left it that way')
        return self.network_before

    async def active_route(self):
        """The transport the device actually routes through, or '' when the dump does not say."""
        try:dump=await self.shell('dumpsys','connectivity',check=False,timeout=20,limit=400*1024)
        except Exception:return ''
        for pattern in (r'Active default network:\s*(\S{1,60})',r'Default network:\s*(\S{1,60})',
                        r'NetworkAgentInfo\{[^}]{0,300}?type:\s*(WIFI|MOBILE)'):
            found=re.search(pattern,dump)
            if found:return found.group(1)
        return ''

    async def _settled(self,label,key,want):
        for _ in range(6):
            value=(await self.shell('settings','get','global',key,check=False)).strip()
            if value in ('0','1') and (value=='1')==want:return
            await asyncio.sleep(POLL)
        raise AndroidError(f'{label} did not become {"on" if want else "off"}; the device still reports '+(value or 'nothing'))

    async def apply_network(self,mode):
        """Switch transports and prove the switch happened. `restore` puts back only what this run changed."""
        if mode=='restore':
            problems=await self.restore_network()
            if problems:raise AndroidError('; '.join(problems))
            return
        if mode not in TRANSPORTS:raise AndroidError('Unsupported network mode: '+str(mode))
        wifi,data=TRANSPORTS[mode]
        for label,key,service,want in (('Wi-Fi','wifi_on','wifi',wifi),('Mobile data','mobile_data','data',data)):
            # Record the intent before the command runs: a command can change state and still fail.
            self.network_changed.add(service)
            await self.shell('svc',service,'enable' if want else 'disable')
        for label,key,service,want in (('Wi-Fi','wifi_on','wifi',wifi),('Mobile data','mobile_data','data',data)):
            await self._settled(label,key,want)
        self.faults.append({'network':mode})

    async def apply_speed(self,speed='',delay_ms=None):
        """Shape the emulator link. The console acknowledgement is configuration evidence, not app throughput."""
        if speed:
            self.network_changed.add('speed');await self.adb_call('emu','network','speed',speed)
        if delay_ms is not None:
            value=max(0,min(5000,int(delay_ms)));self.network_changed.add('delay')
            await self.adb_call('emu','network','delay',f'{value}:{value}')
        self.faults.append({'speed':speed,'delay_ms':delay_ms})

    async def restore_network(self):
        """Put back only what this run changed, one setting at a time, reporting each failure."""
        problems=[];touched=sorted(self.network_changed)
        for label,key,service in (('Wi-Fi','wifi_on','wifi'),('Mobile data','mobile_data','data')):
            if service not in self.network_changed:continue
            recorded=self.network_before.get('wifi' if service=='wifi' else 'data','')
            if recorded not in ('0','1'):problems.append(f'No recorded {label} state to restore');continue
            try:
                await self.shell('svc',service,'enable' if recorded=='1' else 'disable')
                await self._settled(label,key,recorded=='1');self.network_changed.discard(service)
            except Exception as error:problems.append(f'Could not restore {label}: '+str(error)[:200])
        speed,delay=console_network(self.network_before.get('console',''))
        for name,command,value in (('speed',('speed',),speed),('delay',('delay',),delay)):
            if name not in self.network_changed:continue
            try:
                await self.adb_call('emu','network',*command,value);self.network_changed.discard(name)
            except Exception as error:problems.append(f'Could not restore the emulator {name}: '+str(error)[:200])
        self.network_restore=[{'setting':name,'restored':name not in self.network_changed} for name in touched]
        for problem in problems:self.warnings.append(problem)
        return problems

    async def _screenrecord_pids(self,marker):
        found=[]
        for pid in (await self.shell('pidof','screenrecord',check=False)).split():
            if not pid.isdigit():continue
            if marker in (await self.shell('cat',f'/proc/{pid}/cmdline',check=False)):found.append(pid)
        return found

    async def start_recording(self):
        """Record in parts and restart after each one. Gaps between parts are reported, never smoothed over."""
        if self.record_task and not self.record_task.done():return
        self.record_stop=False;self.record_task=asyncio.create_task(self._record())

    async def _record(self):
        while not self.record_stop:
            part=len(self.video_parts)+1
            if part>MAX_PARTS:self.warnings.append(f'Recording stopped after {MAX_PARTS} parts');return
            remote=f'/data/local/tmp/pex-{self.run_id}-{part}.mp4'
            if self.video_parts:
                blind=time.monotonic()-self.video_parts[-1]['ended_at']
                if blind>=1:self.gaps.append({'after_part':part-1,'seconds':round(blind,1)})
            began=time.monotonic()
            self.recorder=await asyncio.create_subprocess_exec(str(self.adb),'-s',self.serial,'shell',
                shlex.join(['screenrecord','--time-limit',str(PART_SECONDS),'--bit-rate','4000000',remote]),
                stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
            self.remote_video=remote;self.recorder_pid=(await self._screenrecord_pids(remote) or [''])[0]
            await self.recorder.wait()
            name='journey.mp4' if part==1 else f'journey-{part}.mp4'
            entry={'part':part,'name':name,'at':store.now(),'seconds':round(time.monotonic()-began,1),'ended_at':time.monotonic()}
            self.video_parts.append(entry)
            local=self.folder/name
            await self.adb_call('pull',remote,str(local),timeout=60,check=False)
            await self.shell('rm',remote,check=False)
            entry['saved']=local.is_file() and bool(local.stat().st_size)
            if entry['saved']:self.videos.append('/api/runs/'+self.run_id+'/artifacts/'+name)

    async def _interrupt_recorder(self):
        if self.recorder_pid:await self.shell('kill','-2',self.recorder_pid,check=False)
        elif self.remote_video:await self.shell('pkill','-2','-f',self.remote_video,check=False)
        if self.recorder and self.recorder.returncode is None:
            try:await asyncio.wait_for(self.recorder.wait(),8)
            except asyncio.TimeoutError:self.recorder.terminate();await self.recorder.wait()

    async def stop_recording(self):
        """Stop and prove it stopped: nothing may still be recording while an operator types credentials."""
        self.record_stop=True
        if not self.record_task:return
        await self._interrupt_recorder()
        await asyncio.gather(self.record_task,return_exceptions=True);self.record_task=None
        for _ in range(5):
            if not await self._screenrecord_pids(f'pex-{self.run_id}-'):return
            await asyncio.sleep(POLL)
        raise AndroidError('A screen recording for this run is still running; not pausing for input yet')

    async def _hierarchy(self):
        # uiautomator writes a good dump and still exits non-zero while a screen animates, and a
        # half-written file parses as nothing, so trust the XML rather than the exit code, and retry once.
        for attempt in (0,1):
            await self.shell('uiautomator','dump','/data/local/tmp/pex-window.xml',timeout=20,check=False)
            raw=await self.adb_call('exec-out','cat','/data/local/tmp/pex-window.xml',timeout=10,check=False)
            try:return sanitize_xml(raw)
            except ElementTree.ParseError as error:
                if attempt:raise AndroidError('The device did not produce a readable window dump: '+raw.strip()[:200]) from error
                await asyncio.sleep(1)

    def _hide(self,value):
        """Replace every operator-supplied value wherever the device reflects it back."""
        for given in self.supplied:value=scrub(value,given,'{{supplied}}')
        return value

    async def observe(self,id):
        xml,root,sensitive=await self._hierarchy();size=await self.shell('wm','size');density=await self.shell('wm','density')
        width,height=map(int,re.findall(r'(\d+)x(\d+)',size)[-1]);dpi=int(re.findall(r'(\d+)',density)[-1]);self.display=(width,height)
        controls=[];self.controls={}
        for node in root.iter('node'):
            box=parse_bounds(node.get('bounds'));enabled=node.get('enabled')=='true'
            # A node holding a value the operator typed is as sensitive as a password field.
            holds=any(given in (node.get('text') or '') for given in self.supplied)
            if holds and box:sensitive.append(box)
            actionable=enabled and box and box[2]>box[0] and box[3]>box[1] and (node.get('clickable')=='true' or node.get('class')=='android.widget.EditText')
            if not actionable:continue
            x1,y1,x2,y2=box;x1=max(0,min(width,x1));x2=max(0,min(width,x2));y1=max(0,min(height,y1));y2=max(0,min(height,y2))
            if x2<=x1 or y2<=y1:continue
            raw_identity=(self.app['package'],node.get('class',''),node.get('resource-id',''),node.get('content-desc',''),node.get('text',''),node.get('bounds',''))
            cid='pex-'+str(len(controls)+1);self.controls[cid]=raw_identity
            password=node.get('password')=='true'
            label='Password field' if password else self._hide(node.get('content-desc') or node.get('text',''))
            controls.append({'id':cid,'tag':node.get('class',''),'role':'textbox' if node.get('class')=='android.widget.EditText' else 'button','text':'' if password else self._hide(node.get('text','')),'label':label,'labeled':bool(label),'filled':holds,'resource_id':node.get('resource-id',''),'input_type':'password' if password else 'text' if node.get('class')=='android.widget.EditText' else '','disabled':False,'checked':node.get('checked')=='true','href':'','options':[],'box':{'x':x1,'y':y1,'width':x2-x1,'height':y2-y1},'identity':hashlib.sha256(repr(raw_identity).encode()).hexdigest()[:24]})
        png=await self.adb_call('exec-out','screencap','-p',binary=True,limit=20*1024*1024)
        screenshot=self.folder/(id+'.png');screenshot.write_bytes(png)
        if sensitive:
            try:
                image=Image.open(screenshot);draw=ImageDraw.Draw(image)
                for box in sensitive:draw.rectangle(box,fill='black')
                image.save(screenshot)
            except Exception as error:screenshot.unlink(missing_ok=True);self.warnings.append('Sensitive screenshot omitted: '+str(error));screenshot=None
        mem=await self.shell('dumpsys','meminfo',self.app['package'],check=False)
        pss=re.search(r'^\s*TOTAL\s+(\d+)',mem,re.M)
        activity=await self.focused()
        locale=await self.shell('getprop','persist.sys.locale',check=False) or await self.shell('getprop','ro.product.locale',check=False)
        self.measurements.update(display=f'{width}x{height}',density_dpi=dpi,rotation=int(root.get('rotation','0')),locale=locale,pss_kb=int(pss[1]) if pss else None,jank_pct=None)
        observation={'id':id,'at':store.now(),'url':'android-app://'+self.app['package']+'/'+activity,'title':self.app['package'],'lang':locale,'dir':'ltr','text':self._hide('\n'.join(n.get('text','') for n in root.iter('node') if n.get('text'))),'viewport':{'width':width,'height':height,'density_dpi':dpi,'rotation':int(root.get('rotation','0'))},'controls':controls,'metrics':{'jank_pct':None,'janky_frames':None,'total_frames':None,'pss_kb':int(pss[1]) if pss else None,'crashes':0},'checks':{'hierarchy':{'status':'supported'},'gfxinfo':{'status':'unavailable'},'meminfo':{'status':'supported' if pss else 'unavailable'},'logcat':{'status':'supported'}},'console_events':[],'hierarchy':self._hide(xml),'screenshot':'/api/runs/'+self.run_id+'/artifacts/'+screenshot.name if screenshot else '' ,'part':1}
        (self.folder/(id+'.json')).write_text(json.dumps(observation,ensure_ascii=False,indent=2))
        return observation

    async def focused(self):
        """package/activity that owns the focus; `dumpsys window windows` stopped printing it on API 34, so read the full dump."""
        dump=await self.shell('dumpsys','window',check=False)
        found=re.search(r'm(?:FocusedApp|CurrentFocus)=\S+ u\d+ ([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)',dump)
        return found[1] if found else ''

    async def type_focused(self,value):
        """Type an operator-supplied value (a mobile number, an SMS code) into the focused text field.
        The password refusal in act() is for AI-chosen values; a person answering a pause is the point here."""
        _,root,_=await self._hierarchy()
        fields=[n for n in root.iter('node') if n.get('class')=='android.widget.EditText']
        focused=[n for n in fields if n.get('focused')=='true'] or (fields if len(fields)==1 else [])
        if len(focused)!=1:raise AndroidError('No text field is focused on the device')
        box=parse_bounds(focused[0].get('bounds'));x=(box[0]+box[2])//2;y=(box[1]+box[3])//2
        self.supplied.append(value)
        await self.shell('input','tap',str(x),str(y));await self.shell('input','keycombination','KEYCODE_CTRL_LEFT','KEYCODE_A');await self.shell('input','text',value.replace(' ','%s'))
    async def act(self,action):
        kind=action.get('type');target=action.get('target') or ''
        if kind in ('wait',):await asyncio.sleep(2);return
        if kind=='back':await self.shell('input','keyevent','KEYCODE_BACK');return
        if kind=='reload':await self.shell('am','force-stop',self.app['package']);await self.launch(self.mission.get('url',''));return
        if kind=='scroll':
            width,height=self.display;start,end=(str(height*3//4),str(height//4)) if action.get('value','down')=='down' else (str(height//4),str(height*3//4))
            await self.shell('input','swipe',str(width//2),start,str(width//2),end,'400');return
        if not (await self.focused()).startswith(self.app['package']+'/'):raise AndroidError('Target app is not in the foreground; action refused')
        xml,root,_=await self._hierarchy();identity=self.controls.get(target)
        matches=[];moved=[]
        for node in root.iter('node'):
            # Compose wraps a clickable node around a decorative child with identical bounds; observe() listed only the clickable one.
            if not (node.get('clickable')=='true' or node.get('class')=='android.widget.EditText'):continue
            candidate=(self.app['package'],node.get('class',''),node.get('resource-id',''),node.get('content-desc',''),node.get('text',''),node.get('bounds',''))
            if candidate==identity:matches.append(node)
            elif identity and candidate[:-1]==identity[:-1]:moved.append(node)
        # Carousels and lists shift between observe and act; the same control at new bounds is still that control.
        # A row of icon-only buttons is identical once bounds are dropped, so take the nearest of several
        # only when it is clearly the nearest: within a third of the distance to the runner-up.
        if not matches and moved and parse_bounds(identity[-1]):
            want=parse_bounds(identity[-1]);wx,wy=(want[0]+want[2])//2,(want[1]+want[3])//2
            near=sorted((((lambda b:((b[0]+b[2])//2-wx)**2+((b[1]+b[3])//2-wy)**2)(parse_bounds(node.get('bounds')) or want)),index,node) for index,node in enumerate(moved))
            if len(near)==1 or near[0][0]*9<=near[1][0]:matches=[near[0][2]]
        if len(matches)!=1:raise AndroidError('Control changed or is ambiguous; observe again')
        node=matches[0];box=parse_bounds(node.get('bounds'));x=(box[0]+box[2])//2;y=(box[1]+box[3])//2
        if kind=='tap':await self.shell('input','tap',str(x),str(y));return
        if kind in ('type','fill'):
            # A tap may focus a password field so an operator can type into it; the AI still may not.
            if node.get('password')=='true':raise AndroidError('Android password and OTP entry is not supported')
            value=action.get('value','')
            if not value.isascii():raise AndroidError('Unicode input needs a preconfigured ADBKeyboard')
            await self.shell('input','tap',str(x),str(y));await self.shell('input','keycombination','KEYCODE_CTRL_LEFT','KEYCODE_A');await self.shell('input','text',value.replace(' ','%s'));return
        if kind=='press' and action.get('value') in ('Tab','Escape'):await self.shell('input','keyevent','KEYCODE_TAB' if action['value']=='Tab' else 'KEYCODE_ESCAPE');return
        raise AndroidError('Unsupported Android action: '+str(kind))

    async def stop(self):
        if self.stopped:return
        self.stopped=True
        try:await self.stop_recording()
        except Exception as error:self.warnings.append('Video finalization failed: '+str(error))
        # The lock is still held here, so the next run never starts on a device this one left shaped.
        try:await self.restore_network()
        except Exception as error:self.warnings.append('Network restoration failed: '+str(error))
        try:
            if self.log_process and self.log_process.returncode is None:self.log_process.terminate();await asyncio.wait_for(self.log_process.wait(),5)
            if self.log_task:await asyncio.gather(self.log_task,return_exceptions=True)
            logs=scoped_logs(self.log_lines,self.app['package'])
            self.logs=['/api/runs/'+self.run_id+'/artifacts/'+name for name in write_log_parts(self.folder,logs)]
        except Exception as error:self.warnings.append('Log finalization failed: '+str(error))
        finally:
            try:await self.close_owned()
            except Exception as error:self.warnings.append('Owned emulator cleanup failed: '+str(error))
            if self.lock_file:
                fcntl.flock(self.lock_file,fcntl.LOCK_UN);self.lock_file.close();self.lock_file=None

    async def close_owned(self):
        if self.owned and self.owned.returncode is None:
            if self.serial:await self.adb_call('emu','kill',check=False)
            else:self.owned.terminate();await self.owned.wait()
