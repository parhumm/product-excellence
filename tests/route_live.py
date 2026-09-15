"""Opt-in live route checks. Never collected by pytest: every mode owns real hardware.

`--android-gate` measures what the installed emulator actually does with `-http-proxy` and
console shaping, one interface at a time, before any Android routing code trusts it. `--web`
and `--android` exercise the shipped feature end to end. Each mode writes its full transcript
and a pass/fail matrix into the artifact folder and returns nonzero unless every advertised
interface passed.

The fixture lives inside the gate proxy itself and answers on 192.0.2.10 (RFC 5737 TEST-NET-1),
which nothing on this machine or the internet routes. An answer is therefore proof the guest's
connection reached this proxy, not proof of general internet reachability.
"""
import argparse,asyncio,json,os,re,statistics,subprocess,sys,time,uuid
from pathlib import Path

SDK=Path(os.environ.get('PEX_ANDROID_SDK') or os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '/opt/homebrew/share/android-commandlinetools')
ADB=SDK/'platform-tools/adb'
EMULATOR=SDK/'emulator/emulator'
FIXTURE_HOST='192.0.2.10'
# 80 and 443 are the ports a proxy is documented to carry; 9101 is the arbitrary-port claim.
FIXTURE_PORTS=(80,443,9101)
BOOT_SECONDS=180

def command(*args,timeout=60,check=False):
    """One host command, captured. Timeouts and non-zero exits are data, not exceptions."""
    try:result=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:return {'ok':False,'out':'','error':f'timed out after {timeout} s'}
    out=(result.stdout or '').strip()
    if check and result.returncode:raise RuntimeError(((result.stderr or result.stdout) or '').strip()[-500:])
    return {'ok':not result.returncode,'out':out,'error':(result.stderr or '').strip()[-500:]}

# --- the gate's own proxy, which is also the only endpoint it will connect anyone to ----------

class GateProxy:
    """A logging HTTP proxy that answers the fixture authority itself and refuses everything else.

    Refusing the rest matters twice: a guest system connection can neither hang against this
    proxy nor be mistaken for fixture evidence. `tag` names this upstream, `generation` advances
    on switch; both are echoed in every fixture reply, so the guest's own bytes say which route
    and which generation carried them.
    """
    def __init__(self,tag='A',exit_ip=''):
        # The address this upstream claims to exit from. Two upstreams answer differently, so the
        # shipped relay's own verification reads back which one carried it, rather than being told.
        self.tag=tag;self.exit_ip=exit_ip
        self.requests=[];self.generation=1;self.live=set();self.server=None;self.port=0

    async def start(self):
        self.server=await asyncio.start_server(self._client,'127.0.0.1',0)
        self.port=self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self):
        if self.server:self.server.close();await self.server.wait_closed();self.server=None
        self.drop()

    def drop(self):
        """Close every tunnel this proxy is carrying. New connections open on the current generation."""
        closed=0
        for writer in list(self.live):
            self.live.discard(writer)
            try:writer.close();closed+=1
            except Exception:pass
        return closed

    def switch(self,tag):
        self.tag=tag;self.generation+=1
        return {'tag':tag,'generation':self.generation,'disconnected':self.drop()}

    def fixture_hits(self,nonce=None):
        return [r for r in self.requests if r['fixture'] and (nonce is None or nonce in r.get('verbs_seen',''))]

    async def _client(self,reader,writer):
        entry={'at':time.time(),'line':'','authority':'','fixture':False,'served':'','verbs_seen':''}
        self.requests.append(entry)
        try:
            head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10)
        except Exception as error:
            entry['served']='no request line: '+type(error).__name__;writer.close();return
        entry['auth']=b'proxy-authorization' in head.lower()
        line=head.decode('latin1').split('\r\n')[0][:300];entry['line']=line
        method,_,rest=line.partition(' ');authority=rest.rsplit(' ',1)[0]
        entry['authority']=authority
        host=authority.rsplit(':',1)[0].lstrip('[').rstrip(']')
        if method!='CONNECT':
            # Port 80 never arrives as CONNECT: the emulator parses it and hands us an absolute-form
            # request instead. Serving it is the same evidence, and the shipped relay owes both forms.
            target=re.match(r'https?://([^/\s]+)(/\S*)?',authority)
            if not target or target.group(1).rsplit(':',1)[0]!=FIXTURE_HOST:
                # Prompt refusal, not silence: a dropping proxy makes the guest hang until its own long timeout.
                entry['served']='refused'
                try:
                    writer.write(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n');await writer.drain()
                except Exception:pass
                writer.close();return
            path=target.group(2) or ''
            nonce=path.rsplit('/',1)[-1][:80]
            entry.update(fixture=True,served='answered',generation=self.generation,tag=self.tag,verbs_seen=nonce+':'+method)
            # `/exit` is this upstream's claimed exit address, in the one form a relay probe accepts.
            # `/bytes/N` is N bytes and nothing else, so a shaped link is measured on the payload alone.
            body=(self.exit_ip+'\n').encode() if path.startswith('/exit') else (
                  b'x'*min(int(nonce or 0),4*1024*1024) if path.startswith('/bytes/') and nonce.isdigit() else
                  f'PEXOK {nonce} {self.tag} {self.generation}\n'.encode())
            try:
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: '
                             +str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);await writer.drain()
            except Exception:pass
            writer.close();return
        if not fixture_host(host):
            entry['served']='refused'
            try:
                writer.write(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n');await writer.drain()
            except Exception:pass
            writer.close();return
        entry['fixture']=True;entry['served']='tunnelled';entry['generation']=self.generation;entry['tag']=self.tag
        # A TLS request carries its nonce in the authority it asks for: the payload is opaque to a
        # proxy, so that is the only place an app's own request can be correlated from. A proxy-aware
        # client can put it in the name; a guest behind `-http-proxy` resolves names itself and hands
        # the proxy an address, so there the nonce is the port.
        entry['verbs_seen']=(host[4:-5] if host!=FIXTURE_HOST else authority.rsplit(':',1)[-1])+':CONNECT'
        self.live.add(writer)
        try:
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n');await writer.drain()
            await self._fixture(reader,writer,entry)
        except Exception as error:entry['served']='tunnel ended: '+type(error).__name__
        finally:
            self.live.discard(writer)
            try:writer.close()
            except Exception:pass

    async def _fixture(self,reader,writer,entry):
        """One line in, one answer out. `PEX <nonce> <verb> [n]` — GET, DOWN n, UP n, HOLD secs."""
        while True:
            raw=await asyncio.wait_for(reader.readline(),60)
            if not raw:return
            parts=raw.decode('latin1',errors='replace').strip().split()
            if len(parts)<3 or parts[0]!='PEX':
                writer.write(b'PEXBAD\n');await writer.drain();return
            nonce,verb=parts[1][:80],parts[2].upper();size=int(parts[3]) if len(parts)>3 and parts[3].isdigit() else 0
            entry['verbs_seen']=(entry['verbs_seen']+' '+nonce+':'+verb).strip()
            stamp=f'PEXOK {nonce} {self.tag} {self.generation}'
            if verb=='UP':
                got=0
                while got<size:
                    chunk=await asyncio.wait_for(reader.read(min(65536,size-got)),60)
                    if not chunk:break
                    got+=len(chunk)
                writer.write(f'{stamp} {got}\n'.encode());await writer.drain();return
            writer.write((stamp+'\n').encode());await writer.drain()
            if verb=='DOWN':
                payload=b'x'*65536
                sent=0
                while sent<size:
                    block=payload[:min(65536,size-sent)];writer.write(block);await writer.drain();sent+=len(block)
                return
            if verb=='HOLD':
                await asyncio.sleep(min(size or 5,120));return
            if verb!='GET':return

def fixture_host(host):
    """The fixture authority, or a `pex-<nonce>.test` name pointed at it for one request."""
    return host==FIXTURE_HOST or (host.startswith('pex-') and host.endswith('.test'))

# --- guest-side fixture calls -----------------------------------------------------------------

def guest_get(nonce,port=9101,wait=15):
    # Port 80 is HTTP to this emulator, not an opaque tunnel, so it is probed as HTTP. The nonce
    # travels in the path, which survives the rewrite into absolute form.
    if port==80:
        head=f'GET /pex/{nonce} HTTP/1.1\r\nHost: {FIXTURE_HOST}\r\nConnection: close\r\n\r\n'
        return f"printf '{head}' | nc -w {wait} {FIXTURE_HOST} {port}"
    return f"echo 'PEX {nonce} GET' | nc -w {wait} {FIXTURE_HOST} {port}"

def guest_down(nonce,size,port=9101,wait=60):
    return f"echo 'PEX {nonce} DOWN {size}' | nc -w {wait} {FIXTURE_HOST} {port} | wc -c"

def guest_up(nonce,size,port=9101,wait=60):
    return f"(echo 'PEX {nonce} UP {size}'; dd if=/dev/zero bs=1024 count={size//1024} 2>/dev/null | tr '\\0' 'x') | nc -w {wait} {FIXTURE_HOST} {port}"

# --- the emulator this gate owns ---------------------------------------------------------------

class OwnedEmulator:
    """One emulator this gate starts, drives by serial and kills. It refuses to adopt a running one."""
    def __init__(self,avd,proxy_port,log_path):
        self.avd=avd;self.proxy_port=proxy_port;self.log_path=Path(log_path)
        self.serial='';self.process=None;self.log=None;self.drain=None;self.args=[]

    def running_avds(self):
        found={}
        for line in command(ADB,'devices')['out'].splitlines()[1:]:
            if not line.strip().endswith('device'):continue
            serial=line.split()[0]
            named=command(ADB,'-s',serial,'emu','avd','name')['out'].splitlines() if serial.startswith('emulator-') else []
            found[serial]=named[0].strip() if named else ''
        return found

    async def start(self):
        already=[s for s,name in (await asyncio.to_thread(self.running_avds)).items() if name==self.avd]
        if already:raise RuntimeError(f'{self.avd} is already running as {already[0]}. This gate owns the emulator it measures; stop that instance first.')
        self.args=[str(EMULATOR),'-avd',self.avd,'-http-proxy',f'http://127.0.0.1:{self.proxy_port}',
                   '-no-snapshot','-no-audio','-gpu','auto','-verbose']
        if os.environ.get('PEX_ANDROID_WINDOW')!='1':self.args.append('-no-window')
        self.log=self.log_path.open('wb')
        self.process=await asyncio.create_subprocess_exec(*self.args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        async def pump():
            while line:=await self.process.stdout.readline():self.log.write(line);self.log.flush()
        self.drain=asyncio.create_task(pump())
        before=set(await asyncio.to_thread(self.running_avds))
        for _ in range(BOOT_SECONDS):
            await asyncio.sleep(1)
            mine=[s for s,name in (await asyncio.to_thread(self.running_avds)).items() if name==self.avd and s not in before]
            if mine:self.serial=mine[0];break
        if not self.serial:raise RuntimeError('The owned emulator never exposed an adb device')
        for _ in range(BOOT_SECONDS):
            if (await self.a_shell('getprop','sys.boot_completed'))['out']=='1':break
            await asyncio.sleep(1)
        else:raise RuntimeError('The owned emulator did not finish booting')
        return self.serial

    def adb(self,*args,**kw):return command(ADB,'-s',self.serial,*args,**kw)
    def shell(self,*args,**kw):return self.adb('shell',*args,**kw)
    # Every guest command the fixture answers must run off the loop: this process is also the
    # proxy, and a blocking subprocess here means the guest's CONNECT is never accepted.
    async def a_adb(self,*args,**kw):return await asyncio.to_thread(self.adb,*args,**kw)
    async def a_shell(self,*args,**kw):return await asyncio.to_thread(self.shell,*args,**kw)

    async def stop(self):
        if self.serial:await self.a_adb('emu','kill')
        for _ in range(30):
            await asyncio.sleep(1)
            if self.avd not in (await asyncio.to_thread(self.running_avds)).values():break
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:await asyncio.wait_for(self.process.wait(),10)
            except asyncio.TimeoutError:self.process.kill();await self.process.wait()
        if self.drain:self.drain.cancel();await asyncio.gather(self.drain,return_exceptions=True)
        if self.log:self.log.close()

# --- measurements ------------------------------------------------------------------------------

async def timed(awaitable):
    began=time.monotonic();result=await awaitable;return result,round((time.monotonic()-began)*1000)

def median_ms(samples):return round(statistics.median(samples)) if samples else None

class Report:
    """Every check this gate performed, in the order it ran, plus the matrix a reader acts on."""
    def __init__(self):self.rows=[];self.notes={}

    def add(self,interface,capability,status,detail,**numbers):
        self.rows.append({'interface':interface,'capability':capability,'status':status,'detail':detail,**numbers})
        mark={'pass':'PASS','fail':'FAIL','absent':'ABSENT','unavailable':'N/A'}[status]
        print(f'  [{mark}] {interface}/{capability}: {detail}',flush=True)
        return status=='pass'

    # `absent` is the console accepting and reading back a setting the traffic then ignores: a
    # measured property of this emulator, recorded to narrow scope, not a failure of the gate.
    def failures(self):return [r for r in self.rows if r['status'] not in ('pass','absent')]
    def absences(self):return [r for r in self.rows if r['status']=='absent']

    def matrix(self):
        interfaces=list(dict.fromkeys(r['interface'] for r in self.rows))
        caps=list(dict.fromkeys(r['capability'] for r in self.rows))
        lines=['| interface | '+' | '.join(caps)+' |','|'+'---|'*(len(caps)+1)]
        for i in interfaces:
            cells=[next((r['status'] for r in self.rows if r['interface']==i and r['capability']==c),'-') for c in caps]
            lines.append(f'| {i} | '+' | '.join(cells)+' |')
        return '\n'.join(lines)

async def measure_interface(emulator,proxy,report,interface):
    """Routing first, then shaping. Shaping is only meaningful where routing already works."""
    wifi,data=('enable','disable') if interface=='wifi' else ('disable','enable')
    await emulator.a_shell('svc','wifi',wifi);await emulator.a_shell('svc','data',data)
    await asyncio.sleep(15)
    route=(await emulator.a_shell('dumpsys','connectivity',timeout=40))['out']
    active=re.search(r'Active default network:\s*(\S{1,40})',route)
    report.notes[interface+'_active_route']=active.group(1) if active else 'not reported'

    routed=True
    for port in FIXTURE_PORTS:
        nonce=uuid.uuid4().hex[:12]
        answer,elapsed=await timed(emulator.a_shell(guest_get(nonce,port),timeout=60))
        seen=any(nonce in r.get('verbs_seen','') for r in proxy.requests)
        ok=seen and f'PEXOK {nonce}' in answer['out']
        routed&=report.add(interface,f'route tcp/{port}','pass' if ok else 'fail',
            (f'guest reply {answer["out"].strip()[:60]!r} correlated with proxy log' if ok else
             f'no correlated fixture request; guest said {answer["out"].strip()[:80]!r}{" / "+answer["error"][:80] if answer["error"] else ""}'),
            ms=elapsed,nonce=nonce)
    if not routed:
        for capability in ('shape delay','shape bandwidth'):
            report.add(interface,capability,'unavailable','not measured: this interface does not route through the proxy')
        return False

    # Delay. Five controlled round trips at baseline, five with the console delay applied.
    async def samples(n=5):
        out=[]
        for _ in range(n):
            nonce=uuid.uuid4().hex[:12]
            answer,elapsed=await timed(emulator.a_shell(guest_get(nonce),timeout=60))
            if f'PEXOK {nonce}' in answer['out']:out.append(elapsed)
        return out
    await emulator.a_adb('emu','network','delay','none');await asyncio.sleep(1)
    warm=await samples();base=median_ms(warm)
    applied=await emulator.a_adb('emu','network','delay','200:200');await asyncio.sleep(1)
    status=(await emulator.a_adb('emu','network','status'))['out']
    delayed=await samples();shaped=median_ms(delayed)
    await emulator.a_adb('emu','network','delay','none')
    readback=re.search(r'minimum latency:\s*(\d+)',status)
    acknowledged=applied['ok'] and 'KO' not in applied['out']
    reads_back=bool(readback and int(readback.group(1))>=100)
    # 200:200 is min:max one-way; a round trip that gains most of it is the setting taking effect.
    shift=shaped-base if (base is not None and shaped is not None) else None
    verdict='pass' if (acknowledged and reads_back and shift is not None and shift>=150) else \
            'absent' if (acknowledged and reads_back) else 'fail'
    report.add(interface,'shape delay',verdict,
        f'baseline median {base} ms, with delay 200:200 median {shaped} ms ({"+" if shift and shift>0 else ""}{shift} ms); '
        f'console readback {"reports "+readback.group(1)+" ms" if readback else "reports nothing"}'
        +('' if verdict!='absent' else ' — accepted and read back, traffic unchanged'),
        baseline_ms=base,shaped_ms=shaped,shift_ms=shift,samples=warm+delayed,console_status=status[:400],command='emu network delay 200:200')

    # Bandwidth, down and up separately, so a symmetric restore cannot hide an asymmetric link.
    async def transfer(size):
        down_nonce=uuid.uuid4().hex[:12];up_nonce=uuid.uuid4().hex[:12]
        down,down_ms=await timed(emulator.a_shell(guest_down(down_nonce,size),timeout=180))
        up,up_ms=await timed(emulator.a_shell(guest_up(up_nonce,size),timeout=180))
        got=int(re.search(r'(\d+)',down['out']).group(1)) if re.search(r'(\d+)',down['out']) else 0
        return {'down_ms':down_ms,'down_bytes':got,'up_ms':up_ms,'up_ok':f'PEXOK {up_nonce}' in up['out'],'up_reply':up['out'].strip()[:80]}
    # 32 KB is one second at the shaped rate and milliseconds unshaped: both ends stay measurable.
    size=32768
    await emulator.a_adb('emu','network','speed','full');await asyncio.sleep(1)
    fast=await transfer(size)
    applied=await emulator.a_adb('emu','network','speed','512:256');await asyncio.sleep(1)
    status=(await emulator.a_adb('emu','network','status'))['out']
    slow=await transfer(size)
    await emulator.a_adb('emu','network','speed','full')
    down_read=re.search(r'download speed:\s*(\d+)',status);up_read=re.search(r'upload speed:\s*(\d+)',status)
    asymmetric=bool(down_read and up_read and down_read.group(1)!=up_read.group(1))
    slower=bool(fast['down_ms'] and slow['down_ms']>fast['down_ms']*1.5)
    rate=lambda run:round(run['down_bytes']*8/run['down_ms']) if run['down_ms'] and run['down_bytes'] else None
    verdict='pass' if (applied['ok'] and asymmetric and slower) else 'absent' if (applied['ok'] and asymmetric) else 'fail'
    report.add(interface,'shape bandwidth',verdict,
        f'{size} B down took {fast["down_ms"]} ms at full ({rate(fast)} kbit/s) and {slow["down_ms"]} ms at 512:256 ({rate(slow)} kbit/s); '
        f'console readback down={down_read.group(1) if down_read else "?"} up={up_read.group(1) if up_read else "?"} bits/s'
        +('' if verdict!='absent' else ' — accepted and read back, traffic unchanged'),
        full=fast,shaped=slow,full_kbit=rate(fast),shaped_kbit=rate(slow),console_status=status[:400],command='emu network speed 512:256')
    return True

async def switch_check(emulator,proxy,report):
    """A long-lived tunnel, dropped at the proxy, and the next request carrying the new route."""
    hold=uuid.uuid4().hex[:12]
    holder=await asyncio.create_subprocess_exec(str(ADB),'-s',emulator.serial,'shell',
        f"echo 'PEX {hold} HOLD 90' | nc -w 120 {FIXTURE_HOST} 9101",
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    for _ in range(30):
        await asyncio.sleep(1)
        if any(hold in r.get('verbs_seen','') for r in proxy.requests):break
    held=any(hold in r.get('verbs_seen','') for r in proxy.requests)
    moved=proxy.switch('B')
    nonce=uuid.uuid4().hex[:12]
    answer=await emulator.a_shell(guest_get(nonce),timeout=60)
    try:holder.kill()
    except ProcessLookupError:pass
    await holder.wait()
    tagged=f'PEXOK {nonce} B {moved["generation"]}' in answer['out']
    report.add('switch','route switch','pass' if (held and tagged) else 'fail',
        (f'long-lived tunnel established, {moved["disconnected"]} connection(s) dropped on switch, '
         f'next guest request answered by upstream B generation {moved["generation"]}') if tagged else
        f'held={held}; guest said {answer["out"].strip()[:100]!r}',
        disconnected=moved['disconnected'],reply=answer['out'].strip()[:200])

async def android_gate(artifacts):
    avd=os.environ.get('PEX_ANDROID_AVD','')
    if not avd:print('Set PEX_ANDROID_AVD to a disposable AVD',file=sys.stderr);return 2
    report=Report();proxy=GateProxy('A');port=await proxy.start()
    emulator=OwnedEmulator(avd,port,artifacts/'emulator.log');before={}
    print(f'Gate proxy on 127.0.0.1:{port}; fixture authority {FIXTURE_HOST}:{FIXTURE_PORTS}',flush=True)
    try:
        await emulator.start()
        version=command(EMULATOR,'-version')['out'].splitlines()[0]
        report.notes.update(emulator=version,serial=emulator.serial,launch_args=' '.join(emulator.args),
                            api=(await emulator.a_shell('getprop','ro.build.version.sdk'))['out'],
                            abi=(await emulator.a_shell('getprop','ro.product.cpu.abi'))['out'])
        print(f'{version} · serial {emulator.serial} · API {report.notes["api"]} {report.notes["abi"]}',flush=True)
        before={'console':(await emulator.a_adb('emu','network','status'))['out'],
                'wifi':(await emulator.a_shell('settings','get','global','wifi_on'))['out'],
                'data':(await emulator.a_shell('settings','get','global','mobile_data'))['out']}
        report.notes['network_before']=before
        # The emulator proxy is host-side; a guest system proxy would be a different, leaky mechanism.
        guest_proxy=(await emulator.a_shell('settings','get','global','http_proxy'))['out']
        report.notes['guest_http_proxy']=guest_proxy
        report.add('device','host-side proxy','pass' if guest_proxy in ('null','') else 'fail',
            f'guest global http_proxy reads {guest_proxy!r}; routing is the host-side Emulator Proxy')
        for interface in ('wifi','cellular'):
            print(f'-- {interface} --',flush=True)
            await measure_interface(emulator,proxy,report,interface)
        await switch_check(emulator,proxy,report)
    except Exception as error:
        report.add('gate','harness','fail',f'{type(error).__name__}: {error}')
    finally:
        try:
            if emulator.serial:
                for service,recorded in (('wifi',before.get('wifi')),('data',before.get('data'))):
                    if recorded in ('0','1'):await emulator.a_shell('svc',service,'enable' if recorded=='1' else 'disable')
                await emulator.a_adb('emu','network','speed','full');await emulator.a_adb('emu','network','delay','none')
        except Exception as error:report.notes['restore_error']=str(error)[:300]
        try:await emulator.stop()
        except Exception as error:report.notes['stop_error']=str(error)[:300]
        await proxy.stop()
        report.notes['proxy_requests']=proxy.requests[-300:]
        (artifacts/'android-gate.json').write_text(json.dumps({'notes':report.notes,'rows':report.rows},ensure_ascii=False,indent=2,default=str))
        (artifacts/'android-gate.md').write_text('# Android transport gate\n\n'+report.matrix()+'\n\n```\n'+json.dumps(report.notes,indent=2,default=str)[:20000]+'\n```\n')
    print('\n'+report.matrix(),flush=True)
    print(f'\nArtifacts: {artifacts}',flush=True)
    absent=report.absences()
    if absent:
        print(f'\n{len(absent)} capability/ies measured as unavailable on this emulator — this narrows what the product may offer:',flush=True)
        for row in absent:print(f"  {row['interface']}/{row['capability']}: {row['detail']}",flush=True)
    failed=report.failures()
    if failed:
        print(f'\n{len(failed)} check(s) did not pass:',flush=True)
        for row in failed:print(f"  {row['interface']}/{row['capability']}: {row['detail']}",flush=True)
        return 1
    print('\nEvery advertised interface was measured; nothing failed.',flush=True)
    return 0

# --- the shipped feature, end to end -----------------------------------------------------------

# Two upstreams that answer differently, and a third address only a direct connection can reach.
ROUTES={'route-a-live-01':('A','203.0.113.11',{}),
        'route-b-live-02':('B','198.51.100.22',{'username':'relay','password':'upstream-only'})}

class LocalEcho:
    """An address reachable only without an upstream: every proxy here refuses anything but the fixture.

    So the address the relay reads back is not something this harness told it. Through a route it can
    only be the fixture's answer, and off every route it can only be this one.
    """
    def __init__(self):self.server=None;self.port=0;self.hits=0

    async def start(self):
        self.server=await asyncio.start_server(self._client,'127.0.0.1',0)
        self.port=self.server.sockets[0].getsockname()[1];return self.port

    async def stop(self):
        if self.server:self.server.close();await self.server.wait_closed();self.server=None

    async def _client(self,reader,writer):
        try:
            await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10);self.hits+=1
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 10\r\n'
                         b'Connection: close\r\n\r\n127.0.0.1\n');await writer.drain()
        except Exception:pass
        try:writer.close()
        except Exception:pass

def upstreams():
    """The two tagged proxies and the relay configuration that names them, unstarted."""
    proxies={id:GateProxy(tag,ip) for id,(tag,ip,_) in ROUTES.items()}
    return proxies,{id:{'name':f'Route {tag}','server':'',**extra} for id,(tag,_,extra) in ROUTES.items()}

async def open_upstreams(artifacts):
    """Both upstreams and the echo listening, the shipped relay in front of them, probing as it ships.

    The probe list is the harness's one substitution: the shipped default is two public echoes, and
    what is measured here is the routing, not the internet. Stated in the transcript, not implied.
    """
    from engine import relay as routing
    proxies,configured=upstreams()
    echo=LocalEcho();await echo.start()
    for id,proxy in proxies.items():
        await proxy.start();configured[id]['server']=f'http://127.0.0.1:{proxy.port}'
    routing.PROBES=(f'http://127.0.0.1:{echo.port}/exit',f'http://{FIXTURE_HOST}/exit')
    return routing.Relay(configured),proxies,echo,routing

def landed(proxy,nonce):
    """The entries this upstream answered for one nonce: the guest's own bytes, not the harness's."""
    return [r for r in proxy.requests if nonce in (r.get('verbs_seen') or '')]

def exit_check(report,interface,check,route_id):
    """One switch, judged on the address the relay read back rather than on the call returning."""
    want='127.0.0.1' if route_id=='direct' else ROUTES[route_id][1]
    return report.add(interface,'route '+route_id,
        'pass' if check.get('observed_ip')==want else 'fail',
        f"{check.get('route_name')} generation {check.get('generation')}: relay read back "
        f"{check.get('observed_ip')!r}, expected {want!r}{'; '+check['error'] if check.get('error') else ''}",
        generation=check.get('generation'),disconnected=check.get('disconnected'))

async def held_tunnel(relay,nonce):
    """A CONNECT tunnel through the shipped relay — the form an HTTPS request takes at a proxy."""
    reader,writer=await asyncio.open_connection(relay.host,relay.port)
    writer.write(f'CONNECT {FIXTURE_HOST}:9101 HTTP/1.1\r\nHost: {FIXTURE_HOST}:9101\r\n\r\n'.encode())
    await writer.drain()
    head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),15)
    writer.write(f'PEX {nonce} HOLD 90\n'.encode());await writer.drain()
    answer=await asyncio.wait_for(reader.readline(),15)
    return reader,writer,head.split(b'\r\n')[0].decode('latin1'),answer.decode('latin1').strip()

async def dropped(reader):
    """A switch terminates what the previous route carried; an empty read is that termination."""
    try:return not await asyncio.wait_for(reader.read(1),15)
    except (asyncio.TimeoutError,TimeoutError):return False
    except Exception:return True

async def web_live(artifacts):
    """Every claimed engine through the shipped relay, plus shaping where Chromium is claimed."""
    os.environ.setdefault('PEX_DATA',str(artifacts/'data'))
    from playwright.async_api import async_playwright
    from engine import web
    report=Report();relay,proxies,echo,routing=await open_upstreams(artifacts)
    report.notes['probes']=list(routing.PROBES)
    report.notes['probe_substitution']=('The two public exit-IP echoes are replaced by controlled ones. '
        'What is measured is which upstream carried the request, not internet reachability.')
    try:
        await relay.start('route-a-live-01')
        report.notes['relay']=relay.proxy
        exit_check(report,'relay',await relay.verify(),'route-a-live-01')
        async with async_playwright() as play:
            for name in ('chromium','firefox','webkit'):
                print(f'-- {name} --',flush=True)
                await page_journey(play,name,relay,proxies,report,web)
        await switch_evidence(relay,proxies,report)
    except Exception as error:
        report.add('harness','web','fail',f'{type(error).__name__}: {error}')
    finally:
        await relay.stop()
        # Cancelling a run must leave nothing listening: a relay outliving its run is a leaked way out.
        report.add('cleanup','relay closed','pass' if await refused(relay.host,relay.port) else 'fail',
                   f'the relay port {relay.port or "already released"} refuses connections after stop()')
        report.notes['route_traffic']={g:c for g,c in sorted(relay.stats.items())}
        for id,proxy in proxies.items():
            report.notes.setdefault('upstream_requests',{})[id]=proxy.requests[-120:];await proxy.stop()
        await echo.stop()
    return finish(report,artifacts,'web')

async def refused(host,port):
    if not port:return True
    try:
        reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port),5)
        writer.close();return False
    except Exception:return True

async def page_journey(play,name,relay,proxies,report,web):
    """One engine: a page through route A, the shipped switch, then the same page through route B."""
    a,b=proxies['route-a-live-01'],proxies['route-b-live-02']
    # Every engine is measured on the same sequence, so each one starts from route A whatever the
    # engine before it left behind. The reset is a switch like any other and is recorded as one.
    if relay.route_id!='route-a-live-01':await relay.apply('route-a-live-01')
    browser=await getattr(play,name).launch()
    try:
        context=await browser.new_context(proxy={'server':relay.proxy})
        page=await context.new_page()
        first=uuid.uuid4().hex[:12]
        await page.goto(f'http://{FIXTURE_HOST}/page/{first}',wait_until='domcontentloaded',timeout=30000)
        body=await page.inner_text('body')
        report.add(name,'page on route A','pass' if f'PEXOK {first} A' in body and landed(a,first) and not landed(b,first) else 'fail',
                   f'the page read {body.strip()[:80]!r} and upstream A logged {len(landed(a,first))} request(s) for this nonce')
        cdp=await context.new_cdp_session(page) if name=='chromium' else None
        shipped=web.Browser(page,context,cdp,{'offline':False,'latency_ms':0,'down_mbps':0,'up_mbps':0},
                            {'console':[],'scenario':[]},{'url':f'http://{FIXTURE_HOST}/'},str,[],[],relay)
        established=await shipped.apply_route('route-b-live-02',1,30)
        report.add(name,'switch','pass' if '198.51.100.22' in established else 'fail',established[:160])
        second=uuid.uuid4().hex[:12]
        await page.goto(f'http://{FIXTURE_HOST}/page/{second}',wait_until='domcontentloaded',timeout=30000)
        body=await page.inner_text('body')
        # The claim is not that the switch was accepted; it is that the target's own request moved.
        report.add(name,'page on route B','pass' if f'PEXOK {second} B' in body and landed(b,second) and not landed(a,second) else 'fail',
                   f'the page read {body.strip()[:80]!r} and upstream B logged {len(landed(b,second))} request(s) for this nonce')
        report.add(name,'credentials upstream only',
                   'pass' if all(r.get('auth') for r in landed(b,second)) and not any(r.get('auth') for r in landed(a,first)) else 'fail',
                   'route B carries Proxy-Authorization to its upstream; route A, which has no credentials, carries none')
        if name=='chromium':await shaped_route(page,shipped,report,relay,proxies)
        await context.close()
    finally:await browser.close()

async def shaped_route(page,shipped,report,relay,proxies):
    """A route and the link speed it is to be measured under: one event, applied in that order."""
    from engine import scenario as steps
    size=32768
    quick=(await timed(page.goto(f'http://{FIXTURE_HOST}/bytes/{size}',wait_until='load',timeout=30000)))[1]
    journey=steps.Scenario([],shipped,notify=None,goal='',deadline=time.monotonic()+60)
    await journey.apply({'route':'route-a-live-01','speed':'edge'},2)
    slow=(await timed(page.goto(f'http://{FIXTURE_HOST}/bytes/{size}',wait_until='load',timeout=60000)))[1]
    on_a=[f for f in shipped.faults if f.get('route')]
    report.add('chromium','route with speed','pass' if slow>quick*3 and on_a and relay.route_id=='route-a-live-01' else 'fail',
               f'{size} B took {quick} ms on the unshaped route and {slow} ms after the same event moved back to '
               f'route A at edge; the run recorded {shipped.faults}',unshaped_ms=quick,shaped_ms=slow)
    await shipped.apply_speed('full')

async def switch_evidence(relay,proxies,report):
    """What a switch costs and what `direct` proves, measured once rather than per engine."""
    nonce=uuid.uuid4().hex[:12]
    reader,writer,line,answer=await held_tunnel(relay,nonce)
    report.add('relay','long-lived tunnel','pass' if '200' in line and 'PEXOK' in answer else 'fail',
               f'CONNECT answered {line.strip()!r} and the fixture said {answer!r}')
    check=await relay.apply('direct',3)
    gone=await dropped(reader)
    try:writer.close()
    except Exception:pass
    report.add('relay','switch disconnects','pass' if gone and check['disconnected'] else 'fail',
               f"{check['disconnected']} connection(s) terminated by the switch; the held tunnel {'ended' if gone else 'stayed open'}")
    exit_check(report,'relay',await relay.verify(check),'direct')
    # TEST-NET-1 is routed by nothing, so reaching the fixture without an upstream must fail.
    unreachable=uuid.uuid4().hex[:12]
    before=sum(len(p.requests) for p in proxies.values())
    try:
        reader2,writer2,line2,_=await held_tunnel(relay,unreachable)
        writer2.close();refused_direct='502' in line2 or '504' in line2
        detail=f'the relay answered {line2.strip()!r} with no upstream configured'
    except Exception as error:refused_direct=True;detail=f'the connection failed as {type(error).__name__}'
    after=sum(len(p.requests) for p in proxies.values())
    report.add('relay','direct reaches no upstream','pass' if refused_direct and after==before else 'fail',
               detail+f'; upstream request count went {before} to {after}')

def finish(report,artifacts,mode):
    """The same transcript, matrix and exit rule every mode in this harness answers to."""
    (artifacts/f'route-live-{mode}.json').write_text(json.dumps({'notes':report.notes,'rows':report.rows},
                                                                ensure_ascii=False,indent=2,default=str))
    (artifacts/f'route-live-{mode}.md').write_text(f'# Live route acceptance: {mode}\n\n'+report.matrix()
                                                   +'\n\n```\n'+json.dumps(report.notes,indent=2,default=str)[:20000]+'\n```\n')
    print('\n'+report.matrix(),flush=True)
    print(f'\nArtifacts: {artifacts}',flush=True)
    failed=report.failures()
    if failed:
        print(f'\n{len(failed)} check(s) did not pass:',flush=True)
        for row in failed:print(f"  {row['interface']}/{row['capability']}: {row['detail']}",flush=True)
        return 1
    print(f'\nEvery advertised {mode} capability passed.',flush=True)
    return 0

async def android_live(artifacts):
    """The shipped Device, launched against the shipped relay, with the app making its own requests."""
    avd=os.environ.get('PEX_ANDROID_AVD','')
    if not avd:print('Set PEX_ANDROID_AVD to a disposable AVD',file=sys.stderr);return 2
    data=artifacts/'data';(data/'apps').mkdir(parents=True,exist_ok=True)
    os.environ['PEX_DATA']=str(data)
    from engine import android,targets
    apk=Path(__file__).parent/'fixtures/crashapp/out/crashapp-v1.apk'
    build=targets.inspect_apk(str(apk));(data/'apps'/(build['sha256']+'.apk')).write_bytes(apk.read_bytes())
    report=Report();relay,proxies,echo,routing=await open_upstreams(artifacts)
    a,b=proxies['route-a-live-01'],proxies['route-b-live-02']
    report.notes.update(probes=list(routing.PROBES),build=build)
    device=android.Device({'device':avd,'reset':'fresh'},build,artifacts/'device','route-live',relay=relay)
    try:
        await relay.start('route-a-live-01')
        exit_check(report,'relay',await relay.verify(),'route-a-live-01')
        await device.start()
        report.notes['serial']=device.serial
        # The proxy is host-side: a guest setting would be a different mechanism, and one an app can opt out of.
        guest=await device.shell('settings','get','global','http_proxy',check=False)
        report.add('device','host-side proxy','pass' if guest.strip() in ('null','') else 'fail',
                   f'guest global http_proxy reads {guest.strip()!r} while the emulator was launched against {relay.proxy}')
        first=await app_request(device,report,'app on route A',a,b)
        established=await device.apply_route('route-b-live-02',1,30)
        report.add('switch','switch','pass' if '198.51.100.22' in established else 'fail',established[:160])
        await app_request(device,report,'app on route B',b,a)
        check=await relay.apply('direct',2)
        exit_check(report,'switch',await relay.verify(check),'direct')
        before=sum(len(p.requests) for p in proxies.values())
        await app_request(device,report,'app off every route',None,None)
        report.add('switch','direct reaches no upstream','pass' if sum(len(p.requests) for p in proxies.values())==before else 'fail',
                   'no upstream saw the app\'s request once the run was switched to a direct connection')
    except Exception as error:
        report.add('harness','android','fail',f'{type(error).__name__}: {error}')
    finally:
        try:await device.stop()
        except Exception as error:report.notes['stop_error']=str(error)[:300]
        try:await device.close_owned()
        except Exception as error:report.notes['close_error']=str(error)[:300]
        report.notes['network_restore']=device.network_restore
        await relay.stop()
        report.add('cleanup','relay closed','pass' if await refused(relay.host,relay.port) else 'fail',
                   f'the relay port {relay.port or "already released"} refuses connections after stop()')
        report.notes['route_traffic']={g:c for g,c in sorted(relay.stats.items())}
        for id,proxy in proxies.items():
            report.notes.setdefault('upstream_requests',{})[id]=proxy.requests[-120:];await proxy.stop()
        await echo.stop()
    return finish(report,artifacts,'android')

async def app_request(device,report,capability,expected,other):
    """The fixture app's own HTTP stack, pointed at an address that carries this request's nonce.

    `check no_crash` proves nothing about routing; only the app's own bytes arriving at an upstream
    does. The guest resolves names itself, so a made-up hostname never leaves it and the port is the
    only part of the authority this run can choose: one unused port per request is the nonce. The
    fixture answers a line protocol rather than TLS, so the app's own handshake fails; what is being
    measured is which upstream was asked to carry it.
    """
    nonce=str(9200+uuid.uuid4().int%700)
    await device.shell('am','force-stop',device.app['package'])
    await device.shell('am','start','-n',device.app['package']+'/'+device.app['launch_activity'],
                       '-e','probe_url',f'https://{FIXTURE_HOST}:{nonce}/')
    await asyncio.sleep(3)
    observation=await device.observe('probe-'+nonce)
    control=next((c for c in observation['controls'] if 'HTTPS probe' in (c.get('label') or '')),None)
    if not control:
        return report.add('app',capability,'fail','the fixture app never offered its probe control')
    await device.act({'type':'tap','target':control['id']})
    if expected is None:
        # Nothing to wait for: the run is on a direct connection and the request must reach no upstream.
        # Give it the same room a routed request gets before the count is read.
        await asyncio.sleep(20)
        return report.add('app',capability,'pass','the app was asked for a request no upstream should carry')
    for _ in range(20):
        await asyncio.sleep(1)
        if landed(expected,nonce):break
    return report.add('app',capability,'pass' if landed(expected,nonce) and not landed(other,nonce) else 'fail',
        f"upstream {expected.tag} logged {len(landed(expected,nonce))} request(s) for this app's own nonce "
        f"and upstream {other.tag} logged {len(landed(other,nonce))}",nonce=nonce)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android-gate',action='store_true',help='measure emulator transport before implementing its integration')
    parser.add_argument('--web',action='store_true',help='live web route switching against the shipped engine')
    parser.add_argument('--android',action='store_true',help='live Android route switching against the shipped engine')
    parser.add_argument('--artifacts',default=os.environ.get('PEX_LIVE_ARTIFACTS',''),help='where transcripts are written')
    args=parser.parse_args()
    if not (args.android_gate or args.web or args.android):parser.error('Choose --android-gate, --web or --android')
    artifacts=Path(args.artifacts or f'artifacts/route-live-{time.strftime("%Y%m%d-%H%M%S")}')
    artifacts.mkdir(parents=True,exist_ok=True)
    code=0
    if args.android_gate:code|=asyncio.run(android_gate(artifacts))
    if args.web:code|=asyncio.run(web_live(artifacts))
    if args.android:code|=asyncio.run(android_live(artifacts))
    return code

if __name__=='__main__':sys.exit(main())
