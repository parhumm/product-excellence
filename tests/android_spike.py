"""Bounded live feasibility check for the disposable PEX Android fixture AVD."""
import argparse, json, os, re, subprocess, time
from pathlib import Path
from xml.etree import ElementTree

SDK = Path(os.environ.get('PEX_ANDROID_SDK') or os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '/opt/homebrew/share/android-commandlinetools')
ADB = SDK / 'platform-tools/adb'
EMULATOR = SDK / 'emulator/emulator'
PACKAGE = 'dev.pex.crashapp'

def command(*args, timeout=30, binary=False, check=True):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if check and result.returncode: raise RuntimeError((result.stderr or result.stdout).decode(errors='replace')[-2000:])
    return result.stdout if binary else result.stdout.decode(errors='replace').strip()

def adb(serial, *args, **kw): return command(str(ADB), '-s', serial, *args, **kw)

def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    return tuple(map(int, match.groups())) if match else None

def hierarchy(serial):
    adb(serial, 'shell', 'uiautomator', 'dump', '/data/local/tmp/pex-window.xml')
    raw = adb(serial, 'exec-out', 'cat', '/data/local/tmp/pex-window.xml')
    root = ElementTree.fromstring(raw)
    return raw, [node.attrib for node in root.iter('node')]

def tap(serial, node):
    x1, y1, x2, y2 = bounds(node)
    adb(serial, 'shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))

def wait_boot(serial):
    for _ in range(90):
        if adb(serial, 'shell', 'getprop', 'sys.boot_completed', check=False) == '1': return
        time.sleep(1)
    raise RuntimeError('AVD did not become ready within 90 seconds')

def playable(video, artifacts):
    from playwright.sync_api import sync_playwright
    page_path = artifacts / 'video-check.html'
    page_path.write_text('<video id="v" controls></video>')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_path.as_uri())
        result = page.locator('#v').evaluate("v => new Promise((ok, no) => { const timer=setTimeout(()=>no('decode timeout'),10000); v.onloadedmetadata=()=>{v.onseeked=()=>{clearTimeout(timer);ok({duration:v.duration,time:v.currentTime})};v.currentTime=Math.min(1,v.duration/2)};v.onerror=()=>no(v.error?.message||'decode failed');v.src='journey.mp4' })")
        browser.close()
    return result['duration'] > 0 and result['time'] > 0, result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--avd', default=os.environ.get('PEX_ANDROID_AVD', ''))
    parser.add_argument('--artifacts', default=os.environ.get('PEX_UI_ARTIFACTS', 'data/android-spike'))
    parser.add_argument('--apk')
    args = parser.parse_args()
    if not args.avd: raise SystemExit('Set PEX_ANDROID_AVD or pass --avd')
    if args.avd != os.environ.get('PEX_ANDROID_AVD', args.avd): raise SystemExit('Only the designated AVD may be used')
    artifacts = Path(args.artifacts).resolve(); artifacts.mkdir(parents=True, exist_ok=True)
    fixtures = Path(os.environ.get('PEX_ANDROID_FIXTURES', Path(__file__).parent/'fixtures/crashapp/out'))
    report = {'avd': args.avd, 'started_at': time.time(), 'checks': {}, 'capabilities': {}}
    serial = ''
    owned = None
    try:
        devices = command(str(ADB), 'devices')
        for line in devices.splitlines()[1:]:
            if '\tdevice' in line and adb(line.split()[0], 'emu', 'avd', 'name', check=False).splitlines()[0] == args.avd:
                serial = line.split()[0]; break
        if not serial:
            owned = subprocess.Popen([str(EMULATOR), '-avd', args.avd, '-no-snapshot', '-no-audio', '-gpu', 'auto', '-no-window'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(30):
                time.sleep(1)
                lines = command(str(ADB), 'devices').splitlines()[1:]
                if lines: serial = lines[0].split()[0]; break
        if not serial: raise RuntimeError('Designated AVD did not expose an adb serial')
        wait_boot(serial)
        report['checks']['boot'] = {'supported': True, 'serial': serial, 'api': adb(serial, 'shell', 'getprop', 'ro.build.version.sdk'), 'abi': adb(serial, 'shell', 'getprop', 'ro.product.cpu.abi')}
        # Fixture-only cleanup. No production path may copy this uninstall behavior.
        installed = adb(serial, 'shell', 'pm', 'list', 'packages', PACKAGE, check=False)
        cleanup = adb(serial, 'uninstall', PACKAGE, check=False) if PACKAGE in installed else 'not_installed'
        report['checks']['fixture_cleanup'] = {'supported': True, 'package': PACKAGE, 'result': cleanup}
        apk = fixtures/'crashapp-v1.apk'
        adb(serial, 'install', str(apk), timeout=60)
        time.sleep(1)
        started = adb(serial, 'shell', 'am', 'start', '-W', '-n', PACKAGE+'/.MainActivity', timeout=60)
        report['checks']['launch'] = {'supported': 'Status: ok' in started, 'result': started}
        before = time.monotonic(); raw, nodes = hierarchy(serial); latency = time.monotonic()-before
        controls = [n for n in nodes if n.get('clickable') == 'true' or n.get('class') == 'android.widget.EditText']
        password = next(n for n in controls if n.get('password') == 'true')
        plain = next(n for n in controls if n.get('content-desc') == 'Plain text input')
        change = next(n for n in controls if n.get('content-desc') == 'Change screen')
        tap(serial, plain); adb(serial, 'shell', 'input', 'text', 'pex_fixture'); tap(serial, change); time.sleep(.5)
        changed_raw, _ = hierarchy(serial)
        report['checks']['hierarchy_actions'] = {'supported': bool(controls) and 'Changed screen' in changed_raw, 'latency_ms': round(latency*1000), 'controls': len(controls), 'password_flag': password.get('password') == 'true', 'sentinel_absent': 'pex-secret-sentinel' not in raw}
        size = adb(serial, 'shell', 'wm', 'size'); density = adb(serial, 'shell', 'wm', 'density')
        locale = adb(serial, 'shell', 'getprop', 'persist.sys.locale') or adb(serial, 'shell', 'getprop', 'ro.product.locale')
        report['capabilities']['display'] = {'size': size, 'density': density, 'rotation': adb(serial, 'shell', 'settings', 'get', 'system', 'user_rotation'), 'locale': locale}
        report['capabilities']['gfxinfo'] = {'supported': 'Draw' in adb(serial, 'shell', 'dumpsys', 'gfxinfo', PACKAGE, check=False)}
        report['capabilities']['meminfo'] = {'supported': 'TOTAL' in adb(serial, 'shell', 'dumpsys', 'meminfo', PACKAGE, check=False)}
        remote = '/data/local/tmp/pex-spike.mp4'; video = artifacts/'journey.mp4'
        recorder = subprocess.Popen([str(ADB), '-s', serial, 'shell', 'screenrecord', '--time-limit', '30', '--bit-rate', '4000000', remote], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        recorder.wait(timeout=40)
        adb(serial, 'pull', remote, str(video), timeout=30); adb(serial, 'shell', 'rm', remote)
        ok, decoded = playable(video, artifacts)
        report['checks']['recording'] = {'supported': ok, **decoded, 'size': video.stat().st_size}
        log = subprocess.Popen([str(ADB), '-s', serial, 'logcat', '-v', 'threadtime'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        adb(serial, 'shell', 'am', 'force-stop', PACKAGE); adb(serial, 'shell', 'am', 'start', '-W', '-n', PACKAGE+'/.MainActivity')
        _, nodes = hierarchy(serial); tap(serial, next(n for n in nodes if n.get('content-desc') == 'Crash')); time.sleep(2)
        adb(serial, 'shell', 'am', 'start', '-W', '-n', PACKAGE+'/.MainActivity')
        _, nodes = hierarchy(serial); tap(serial, next(n for n in nodes if n.get('content-desc') == 'Freeze')); time.sleep(1); adb(serial, 'shell', 'input', 'tap', '540', '500'); time.sleep(12)
        log.terminate(); output, _ = log.communicate(timeout=5)
        output += '\n' + adb(serial, 'logcat', '-d', '-v', 'threadtime', timeout=15)
        relevant = '\n'.join(line for line in output.splitlines() if PACKAGE in line or 'FATAL EXCEPTION' in line or 'IllegalStateException: PEX fixture crash' in line or ('ANR in ' in line and PACKAGE in line))
        (artifacts/'logcat.txt').write_text(relevant)
        report['checks']['logs'] = {'supported': 'PEX fixture crash' in relevant and ('ANR in '+PACKAGE in relevant or 'ANR in dev.pex.crashapp' in relevant), 'java_crash': 'PEX fixture crash' in relevant, 'anr': 'ANR in ' in relevant, 'persisted_unrelated_package': any('com.android.' in line for line in relevant.splitlines())}
        report['capabilities']['network'] = {'baseline': True, 'offline': False, 'probe': 'not_configured' if not os.environ.get('PEX_ANDROID_PROBE_URL') else 'configured_not_run'}
        report['capabilities']['shaping'] = {'supported': False, 'reason': 'not verified'}
        if args.apk:
            report['capabilities']['sample_apk'] = {'supported': Path(args.apk).is_file(), 'tested': False, 'reason': 'optional compatibility run not requested by required fixture checks'}
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        if serial:
            adb(serial, 'shell', 'am', 'force-stop', PACKAGE, check=False)
            adb(serial, 'shell', 'rm', '/data/local/tmp/pex-spike.mp4', check=False)
        if owned:
            adb(serial, 'emu', 'kill', check=False) if serial else owned.terminate()
        report['finished_at'] = time.time()
        (artifacts/'capabilities.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    required = ('boot', 'launch', 'hierarchy_actions', 'recording', 'logs', 'fixture_cleanup')
    if report.get('error') or not all(report['checks'].get(name, {}).get('supported') for name in required): raise SystemExit(1)

if __name__ == '__main__': main()
