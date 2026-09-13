"""Workspace target defaults, mission binding, and bounded APK inspection."""
import hashlib, os, re, subprocess
from pathlib import Path
from urllib.parse import urlsplit
from .contracts import Mission, Target

ID = re.compile(r'^[A-Za-z0-9_-]{1,120}$')
PACKAGE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')

def default_id(project_id):
    return 'web-'+project_id if ID.fullmatch(project_id) and len(project_id)<=116 else 'web-'+hashlib.sha256(project_id.encode()).hexdigest()[:32]

def default_web(project, session, *, sync=True):
    """Create or synchronize the project-owned web target in the caller transaction."""
    from . import store
    if not project.get('url'):return None
    id=default_id(project['id']);row=session.get(store.Record,id)
    if row and (row.kind!='target' or row.workspace!=project['id']):raise store.Conflict('Default target ID collides with another record')
    if row:
        value=store.unpack(row)
        changed=sync and (value.get('url')!=project['url'] or value.get('allowed_domains',[])!=project.get('allowed_domains',[]))
        return store.save('target',{**value,'url':project['url'],'allowed_domains':project.get('allowed_domains',[])},session=session) if changed else value
    value={'id':id,'project_id':project['id'],'type':'web','name':project['name'],'visibility':'team','url':project['url'],'allowed_domains':project.get('allowed_domains',[]),'package':'','builds':[],'created_at':project.get('created_at',store.now())}
    return store.save('target',Target.model_validate(value).model_dump()|{'id':id,'created_at':value['created_at']},session=session,preserve_times=True)

def sdk_root():
    explicit=[(name,os.environ.get(name)) for name in ('PEX_ANDROID_SDK','ANDROID_HOME','ANDROID_SDK_ROOT') if os.environ.get(name)]
    candidates=explicit+[(None,'/opt/homebrew/share/android-commandlinetools'),(None,str(Path.home()/'Library/Android/sdk'))]
    for name,value in candidates:
        root=Path(value)
        if root.is_dir():return root
        if name:raise ValueError(f'{name} points to an unusable Android SDK: {value}')
    raise ValueError('Android SDK not found; set PEX_ANDROID_SDK')

def tool(name):
    root=sdk_root()
    direct={'adb':root/'platform-tools/adb','emulator':root/'emulator/emulator'}.get(name)
    if direct and direct.is_file():return direct
    matches=sorted(root.glob(f'build-tools/*/{name}'),key=lambda p:tuple(int(x) for x in re.findall(r'\d+',p.parent.name)))
    if not matches:raise ValueError(f'Android SDK tool not found: {name}')
    return matches[-1]

def inspect_apk(path):
    try:result=subprocess.run([tool('aapt2'),'dump','badging',path],capture_output=True,text=True,timeout=15)
    except subprocess.TimeoutExpired as error:raise ValueError('APK inspection timed out') from error
    if result.returncode:raise ValueError('Malformed APK: '+(result.stderr or result.stdout)[-500:])
    text=result.stdout
    package=re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'",text,re.M)
    launch=re.search(r"^launchable-activity: name='([^']+)'",text,re.M)
    min_sdk=re.search(r"^sdkVersion:'(\d+)'",text,re.M);target_sdk=re.search(r"^targetSdkVersion:'(\d+)'",text,re.M)
    native=re.search(r"^native-code: (.+)$",text,re.M)
    if not package or not PACKAGE.fullmatch(package[1]):raise ValueError('APK has no valid package metadata')
    if " split='" in (text.splitlines()[0] if text else ''):raise ValueError('Split APKs are not supported; upload a universal/base installable APK')
    if not launch:raise ValueError('APK has no launcher activity')
    size=Path(path).stat().st_size
    with Path(path).open('rb') as source:sha=hashlib.file_digest(source,'sha256').hexdigest()
    return {'package':package[1],'sha256':sha,'version_name':package[3],'version_code':int(package[2]),'min_sdk':int(min_sdk[1]) if min_sdk else 1,'target_sdk':int(target_sdk[1]) if target_sdk else 1,'launch_activity':launch[1],'abis':re.findall(r"'([^']+)'",native[1]) if native else [],'size':size}

def resolve_mission(value, *, session=None):
    """Resolve an explicit target once; absent target_id remains legacy web."""
    from . import store
    raw=dict(value);target_id=raw.get('target_id','')
    if not target_id:return Mission.model_validate({**raw,'platform':'web'}).model_dump(exclude={'login_password'})
    if not ID.fullmatch(target_id):raise ValueError('Invalid target ID')
    target=store.get('target',target_id,raw.get('project_id',''),session=session,metadata=True)
    if not target:raise ValueError('Target not found in this workspace')
    if target.get('visibility')=='local' and raw.get('visibility','team')=='team':raise ValueError('A team mission cannot use a local target')
    raw['platform']=target['type']
    if target['type']=='web':
        raw['url']=raw.get('url') or target['url'];raw['allowed_domains']=raw.get('allowed_domains') or target.get('allowed_domains',[])
        host=urlsplit(raw['url']).hostname or ''
        allowed=set(target.get('allowed_domains',[]))
        if host.lower() not in allowed or not set(raw['allowed_domains'])<=allowed:raise ValueError('Mission URL and domains must stay within the target')
    else:
        raw['allowed_domains']=target.get('allowed_domains',[])
        if raw.get('url') and (urlsplit(raw['url']).hostname or '').lower() not in set(target.get('allowed_domains',[])):raise ValueError('Deep link must use a target domain')
        builds=[b for b in target.get('builds',[]) if not b.get('archived')]
        wanted=raw.get('build','')
        if wanted:build=next((b for b in target.get('builds',[]) if b['sha256']==wanted),None)
        else:build=max(builds,key=lambda b:(b['version_code'],b['uploaded_at'],b['sha256']),default=None)
        if not build:raise ValueError('Upload or select an Android build')
        raw['build']=build['sha256']
    return Mission.model_validate(raw).model_dump(exclude={'login_password'})
