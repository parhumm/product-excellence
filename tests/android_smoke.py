"""Controlled end-to-end Android fixture run against an isolated local console."""
import argparse,fcntl,json,os,re,subprocess,time
from pathlib import Path
import httpx

from engine.android import avd_dir
from tests.android_spike import ADB,EMULATOR,adb,bounds,hierarchy,playable,wait_boot

PACKAGE='dev.pex.crashapp'

def check(response):
    response.raise_for_status();return response.json()

def serial_for(avd,timeout=120):
    from tests.android_spike import command
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        for line in command(str(ADB),'devices').splitlines()[1:]:
            if '\tdevice' not in line:continue
            serial=line.split()[0]
            name=adb(serial,'emu','avd','name',check=False).splitlines()
            if name and name[0]==avd:return serial
        time.sleep(1)
    raise RuntimeError('The designated AVD is not running after the product run started')

def tap_label(serial,label):
    end=time.monotonic()+20
    while time.monotonic()<end:
        try:
            _,nodes=hierarchy(serial);node=next(node for node in nodes if node.get('content-desc')==label)
            x1,y1,x2,y2=bounds(node);adb(serial,'shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));return
        except (RuntimeError,StopIteration):time.sleep(1)
    raise RuntimeError('Fixture control did not become actionable: '+label)

def reset_fixture(avd):
    """The live harness alone may uninstall its owned fixture package."""
    owned=None
    with (avd_dir(avd)/'.pex.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:serial=serial_for(avd,2)
        except RuntimeError:
            owned=subprocess.Popen([str(EMULATOR),'-avd',avd,'-no-snapshot','-no-audio','-gpu','auto','-no-window'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            serial=serial_for(avd)
        wait_boot(serial)
        installed=adb(serial,'shell','pm','list','packages',PACKAGE,check=False)
        if PACKAGE in installed:
            result=adb(serial,'uninstall',PACKAGE,check=False)
            if 'Success' not in result:raise RuntimeError('Fixture-only uninstall failed: '+result)
    return serial,owned

def wait_run(client,id,terminal=False,timeout=180):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        run=check(client.get('/runs/'+id))
        if terminal and run['status'] not in ('queued','running'):return run
        if not terminal and run['status']=='running':return run
        time.sleep(.5)
    raise RuntimeError('Timed out waiting for Android run '+id)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--avd',default=os.environ.get('PEX_ANDROID_AVD',''))
    parser.add_argument('--artifacts',default=os.environ.get('PEX_UI_ARTIFACTS','data/android-smoke'))
    parser.add_argument('--apk',help='Optional third-party APK is compatibility-only and is never modified')
    parser.add_argument('--url',default=os.environ.get('PEX_BASE_URL','http://127.0.0.1:8741'))
    args=parser.parse_args()
    if not args.avd or args.avd!=os.environ.get('PEX_ANDROID_AVD',args.avd):raise SystemExit('Use the operator-designated PEX_ANDROID_AVD')
    output=Path(args.artifacts).resolve();output.mkdir(parents=True,exist_ok=True)
    fixtures=Path(os.environ.get('PEX_ANDROID_FIXTURES',Path(__file__).parent/'fixtures/crashapp/out'))
    client=httpx.Client(base_url=args.url+'/api',headers={'X-PEX-Request':'1'},timeout=60,trust_env=False)
    report={'avd':args.avd,'checks':{},'sample_apk':{'provided':bool(args.apk),'tested':False}};owned=None
    try:
        serial,owned=reset_fixture(args.avd)
        project=check(client.post('/projects',json={'name':'Android smoke','url':'','allowed_domains':[]}))
        headers={'X-PEX-Workspace':project['id']}
        target=check(client.post('/targets',headers=headers,json={'project_id':project['id'],'type':'android','name':'PEX crash fixture','visibility':'local','url':'','allowed_domains':[],'package':'','builds':[]}))
        with (fixtures/'crashapp-v1.apk').open('rb') as apk:target=check(client.post(f"/targets/{target['id']}/builds",headers=headers,files={'file':('crashapp-v1.apk',apk,'application/vnd.android.package-archive')}))
        v1=target['builds'][-1]
        mission=check(client.post('/missions',headers=headers,json={'project_id':project['id'],'target_id':target['id'],'device':args.avd,'visibility':'local','name':'Fixture crash and ANR','goal':'Observe controlled fixture failures','url':'','mode':'audit','provider':'none','ai_budget':0,'observe_seconds':30,'max_seconds':90,'pillars':['functionality','ux_ui','performance']}))
        run=check(client.post('/runs',headers=headers,json={'mission_id':mission['id']}));wait_run(client,run['id'])
        time.sleep(3);tap_label(serial,'Crash');time.sleep(2)
        adb(serial,'shell','am','start','-W','-n',PACKAGE+'/.MainActivity');tap_label(serial,'Freeze');time.sleep(1);adb(serial,'shell','input','tap','540','500')
        first=wait_run(client,run['id'],terminal=True)
        rules={finding.get('rule') for finding in first.get('findings',[])}
        assert first['status']=='completed' and {'anr'}<=rules and any(rule and rule.startswith('crash-') for rule in rules)
        assert first.get('observations') and first.get('videos') and first.get('logs') and first.get('device',{}).get('api')
        observation=client.get(f"/runs/{first['id']}/artifacts/{first['observations'][0]['id']}.json");observation.raise_for_status()
        assert 'pex-secret-sentinel' not in observation.text
        video=client.get(first['videos'][0].replace('/api',''));video.raise_for_status();video_path=output/'journey.mp4';video_path.write_bytes(video.content)
        decoded_ok,decoded=playable(video_path,output);assert decoded_ok
        logs=''.join(client.get(url.replace('/api','')).text for url in first['logs'])
        assert PACKAGE in logs and not re.search(r'Process: (?!'+re.escape(PACKAGE)+r')',logs)
        report['checks']['v1']={'run_id':first['id'],'rules':sorted(rules),'video':decoded,'measurements':first.get('measurements',{})}
        with (fixtures/'crashapp-v2.apk').open('rb') as apk:target=check(client.post(f"/targets/{target['id']}/builds",headers=headers,files={'file':('crashapp-v2.apk',apk,'application/vnd.android.package-archive')}))
        v2=next(build for build in target['builds'] if build['version_code']==2)
        second=check(client.post('/runs',headers=headers,json={'mission_id':mission['id'],'build':v2['sha256']}));second=wait_run(client,second['id'],terminal=True)
        comparison=check(client.get('/compare',headers=headers,params={'baseline':first['id'],'candidate':second['id']}))
        assert comparison['compatible'] and comparison['build_changed'] and first['app']['sha256']==v1['sha256'] and second['app']['sha256']==v2['sha256']
        report['checks']['comparison']={'baseline':first['id'],'candidate':second['id'],'build_changed':True}
        if args.apk:report['sample_apk']['reason']='Optional third-party compatibility remains in android_spike; this smoke modifies only '+PACKAGE
    finally:
        if owned and owned.poll() is None:adb(serial,'emu','kill',check=False)
        report['finished_at']=time.time();(output/'smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        client.close()

if __name__=='__main__':main()
