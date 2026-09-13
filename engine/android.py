"""Concrete, bounded adb/emulator lifecycle for one designated disposable AVD."""
import asyncio, fcntl, hashlib, json, os, re, shlex, signal, time
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image,ImageDraw
from . import store,targets

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
    if check and process.returncode:raise AndroidError((stderr[0] or stdout[0]).decode(errors='replace')[-1000:])
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

def health():
    avd=os.environ.get('PEX_ANDROID_AVD','');reason=''
    try:
        adb=targets.tool('adb');emulator=targets.tool('emulator')
        if avd:avd_dir(avd)
        else:reason='Set PEX_ANDROID_AVD to a disposable AVD'
        return {'available':bool(avd and not reason),'avd':avd,'adb':str(adb),'emulator':str(emulator),'reason':reason}
    except (ValueError,AndroidError) as error:return {'available':False,'avd':avd,'reason':str(error)}

class Device:
    def __init__(self,mission,app,folder,run_id,*,avd=None):
        self.mission=mission;self.app=app;self.folder=Path(folder);self.run_id=run_id
        self.avd=avd or mission.get('device') or os.environ.get('PEX_ANDROID_AVD','')
        self.adb=targets.tool('adb');self.emulator=targets.tool('emulator');self.serial=''
        self.lock_file=None;self.owned=None;self.log_process=None;self.log_task=None;self.log_lines=[]
        self.recorder=None;self.recorder_pid='';self.remote_video='';self.controls={};self.launched=False;self.stopped=False
        self.warnings=[];self.events=[];self.measurements={};self.videos=[];self.logs=[];self.network_before={};self.display=(1080,2400)
        package=app.get('package','')
        if not PACKAGE.fullmatch(package):raise AndroidError('Invalid Android package')
        if not self.avd or self.avd!=os.environ.get('PEX_ANDROID_AVD',''):raise AndroidError('Choose the designated disposable AVD')

    async def adb_call(self,*args,**kw):
        if not self.serial:raise AndroidError('Device is not ready')
        return await run(self.adb,'-s',self.serial,*args,**kw)

    async def shell(self,*args,**kw):
        if not all(isinstance(x,str) for x in args):raise AndroidError('Invalid shell argument')
        return await self.adb_call('shell',shlex.join(args),**kw)

    async def _find_serial(self):
        devices=await run(self.adb,'devices')
        for line in devices.splitlines()[1:]:
            if '\tdevice' not in line:continue
            serial=line.split()[0]
            name=await run(self.adb,'-s',serial,'emu','avd','name',check=False)
            if name.splitlines() and name.splitlines()[0]==self.avd:return serial
        return ''

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
        cleared=await self.shell('pm','clear',self.app['package'])
        if cleared.strip()!='Success':raise AndroidError('Could not clear this package before the mission')
        network=self.mission.get('network','baseline')
        if network!='baseline':raise AndroidError('Android 1.5 supports only baseline here; verified offline is not configured')
        self.folder.mkdir(parents=True,exist_ok=True)
        self.remote_video=f'/data/local/tmp/pex-{self.run_id}.mp4'
        self.recorder=await asyncio.create_subprocess_exec(str(self.adb),'-s',self.serial,'shell',shlex.join(['screenrecord','--time-limit','180','--bit-rate','4000000',self.remote_video]),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
        for pid in (await self.shell('pidof','screenrecord',check=False)).split():
            command=await self.shell('cat',f'/proc/{pid}/cmdline',check=False) if pid.isdigit() else ''
            if self.remote_video in command:self.recorder_pid=pid;break

    async def _read_logs(self):
        total=0
        while line:=await self.log_process.stdout.readline():
            total+=len(line)
            if total>100*1024*1024:
                self.warnings.append('Android log evidence reached the 100 MiB safety limit');self.log_process.terminate();break
            self.log_lines.append(line.decode(errors='replace'))

    async def launch(self,url=''):
        if self.launched:raise AndroidError('App launch was already measured')
        self.launched=True;before=time.monotonic()
        if url:output=await self.shell('am','start','-W','-a','android.intent.action.VIEW','-d',url,'-p',self.app['package'],timeout=30)
        else:output=await self.shell('am','start','-W','-n',self.app['package']+'/'+self.app['launch_activity'],timeout=30)
        match=re.search(r'^TotalTime: (\d+)',output,re.M)
        self.measurements['launch_ms']=int(match[1]) if match else None
        self.measurements['setup_to_launch_ms']=round((time.monotonic()-before)*1000)
        self.measurements['launch_status']='ok' if 'Status: ok' in output else 'error'
        if self.measurements['launch_status']!='ok':raise AndroidError('App launch failed: '+output[-500:])

    async def _hierarchy(self):
        await self.shell('uiautomator','dump','/data/local/tmp/pex-window.xml',timeout=10)
        raw=await self.adb_call('exec-out','cat','/data/local/tmp/pex-window.xml',timeout=10)
        return sanitize_xml(raw)

    async def observe(self,id):
        xml,root,sensitive=await self._hierarchy();size=await self.shell('wm','size');density=await self.shell('wm','density')
        width,height=map(int,re.findall(r'(\d+)x(\d+)',size)[-1]);dpi=int(re.findall(r'(\d+)',density)[-1]);self.display=(width,height)
        controls=[];self.controls={}
        for node in root.iter('node'):
            box=parse_bounds(node.get('bounds'));enabled=node.get('enabled')=='true'
            actionable=enabled and box and box[2]>box[0] and box[3]>box[1] and (node.get('clickable')=='true' or node.get('class')=='android.widget.EditText')
            if not actionable:continue
            x1,y1,x2,y2=box;x1=max(0,min(width,x1));x2=max(0,min(width,x2));y1=max(0,min(height,y1));y2=max(0,min(height,y2))
            if x2<=x1 or y2<=y1:continue
            raw_identity=(self.app['package'],node.get('class',''),node.get('resource-id',''),node.get('content-desc',''),node.get('text',''),node.get('bounds',''))
            cid='pex-'+str(len(controls)+1);self.controls[cid]=raw_identity
            password=node.get('password')=='true';label='Password field' if password else node.get('content-desc') or node.get('text','')
            controls.append({'id':cid,'tag':node.get('class',''),'role':'textbox' if node.get('class')=='android.widget.EditText' else 'button','text':'' if password else node.get('text',''),'label':label,'labeled':bool(label),'resource_id':node.get('resource-id',''),'input_type':'password' if password else 'text' if node.get('class')=='android.widget.EditText' else '','disabled':False,'checked':node.get('checked')=='true','href':'','options':[],'box':{'x':x1,'y':y1,'width':x2-x1,'height':y2-y1},'identity':hashlib.sha256(repr(raw_identity).encode()).hexdigest()[:24]})
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
        observation={'id':id,'at':store.now(),'url':'android-app://'+self.app['package']+'/'+activity,'title':self.app['package'],'lang':locale,'dir':'ltr','text':'\n'.join(n.get('text','') for n in root.iter('node') if n.get('text')),'viewport':{'width':width,'height':height,'density_dpi':dpi,'rotation':int(root.get('rotation','0'))},'controls':controls,'metrics':{'jank_pct':None,'janky_frames':None,'total_frames':None,'pss_kb':int(pss[1]) if pss else None,'crashes':0},'checks':{'hierarchy':{'status':'supported'},'gfxinfo':{'status':'unavailable'},'meminfo':{'status':'supported' if pss else 'unavailable'},'logcat':{'status':'supported'}},'console_events':[],'hierarchy':xml,'screenshot':'/api/runs/'+self.run_id+'/artifacts/'+screenshot.name if screenshot else '' ,'part':1}
        (self.folder/(id+'.json')).write_text(json.dumps(observation,ensure_ascii=False,indent=2))
        return observation

    async def focused(self):
        """package/activity that owns the focus; `dumpsys window windows` stopped printing it on API 34, so read the full dump."""
        dump=await self.shell('dumpsys','window',check=False)
        found=re.search(r'm(?:FocusedApp|CurrentFocus)=\S+ u\d+ ([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)',dump)
        return found[1] if found else ''

    async def act(self,action):
        kind=action.get('type');target=action.get('target') or ''
        if kind in ('wait',):await asyncio.sleep(2);return
        if kind=='back':await self.shell('input','keyevent','KEYCODE_BACK');return
        if kind=='reload':await self.shell('am','force-stop',self.app['package']);self.launched=False;await self.launch(self.mission.get('url',''));return
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
        if not matches and len(moved)==1:matches=moved
        if len(matches)!=1:raise AndroidError('Control changed or is ambiguous; observe again')
        node=matches[0];box=parse_bounds(node.get('bounds'));x=(box[0]+box[2])//2;y=(box[1]+box[3])//2
        if node.get('password')=='true':raise AndroidError('Android password and OTP entry is not supported')
        if kind=='tap':await self.shell('input','tap',str(x),str(y));return
        if kind in ('type','fill'):
            value=action.get('value','')
            if not value.isascii():raise AndroidError('Unicode input needs a preconfigured ADBKeyboard')
            await self.shell('input','tap',str(x),str(y));await self.shell('input','keycombination','KEYCODE_CTRL_LEFT','KEYCODE_A');await self.shell('input','text',value.replace(' ','%s'));return
        if kind=='press' and action.get('value') in ('Tab','Escape'):await self.shell('input','keyevent','KEYCODE_TAB' if action['value']=='Tab' else 'KEYCODE_ESCAPE');return
        raise AndroidError('Unsupported Android action: '+str(kind))

    async def stop(self):
        if self.stopped:return
        self.stopped=True
        try:
            if self.recorder and self.recorder.returncode is None:
                if self.recorder_pid:await self.shell('kill','-2',self.recorder_pid,check=False)
                else:await self.shell('pkill','-2','-f',self.remote_video,check=False)
                try:await asyncio.wait_for(self.recorder.wait(),8)
                except asyncio.TimeoutError:self.recorder.terminate();await self.recorder.wait()
            if self.serial and self.remote_video:
                local=self.folder/'journey.mp4'
                pulled=await self.adb_call('pull',self.remote_video,str(local),timeout=30,check=False)
                await self.shell('rm',self.remote_video,check=False)
                if local.is_file() and local.stat().st_size:self.videos=['/api/runs/'+self.run_id+'/artifacts/journey.mp4']
        except Exception as error:self.warnings.append('Video finalization failed: '+str(error))
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
