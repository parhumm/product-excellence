"""The relay's own correctness, offline: what arrives at an origin, what an upstream is told,
and what a switch does to connections that were already running.

Every server here is loopback and ephemeral. Nothing in this file touches the internet, a
browser or a device.
"""
import asyncio,base64,socket
from urllib.parse import urlsplit
import h11
import pytest
from engine import relay as module
from engine.relay import Relay,split_authority
from engine.scenario import ScenarioError

PASSWORD=base64.b64encode(b'agent:s3cret').decode()

async def couple(reader,writer,up_reader,up_writer):
    """Both directions until each end stops, the way any of these fakes tunnels bytes."""
    async def one(source,sink):
        try:
            while data:=await source.read(65536):sink.write(data);await sink.drain()
        except Exception:pass
        finally:
            try:sink.close()
            except Exception:pass
    await asyncio.gather(one(reader,up_writer),one(up_reader,writer))

class Service:
    """A loopback server on an ephemeral port that never outlives its test.

    `wait_closed` waits for handlers, and these handlers block on purpose, so stopping cancels
    them first.
    """
    def __init__(self):self.seen=[];self.server=None;self.port=0;self.host='127.0.0.1';self.running=set()

    async def start(self,host='127.0.0.1'):
        self.host=host;self.server=await asyncio.start_server(self._accept,host,0)
        self.port=self.server.sockets[0].getsockname()[1];return self.port

    async def stop(self):
        for task in list(self.running):task.cancel()
        if self.server:
            self.server.close();await self.server.wait_closed();self.server=None

    @property
    def authority(self):return (f'[{self.host}]' if ':' in self.host else self.host)+f':{self.port}'

    @property
    def server_url(self):return f'http://127.0.0.1:{self.port}'

    async def _accept(self,reader,writer):
        self.running.add(asyncio.current_task())
        try:await self._client(reader,writer)
        except (asyncio.CancelledError,ConnectionResetError,asyncio.IncompleteReadError):pass
        finally:
            self.running.discard(asyncio.current_task())
            try:writer.close()
            except Exception:pass

class Origin(Service):
    """An HTTP origin that records what actually reached it.

    `/plain` answers with a length, `/chunked` in two chunks, `/head` states a length it never
    sends, `/echo` counts the upload it read, `/upgrade` switches protocol and echoes in capitals.
    """

    async def _client(self,reader,writer):
        conn=h11.Connection(h11.SERVER)
        request=None;body=b''
        while True:
            event=conn.next_event()
            if event is h11.NEED_DATA:conn.receive_data(await reader.read(65536));continue
            if isinstance(event,h11.Request):request=event
            elif isinstance(event,h11.Data):body+=event.data
            else:break
        if request is None:writer.close();return
        seen={'method':request.method.decode(),'target':request.target.decode(),'body':body,
              'headers':{k.decode():v.decode() for k,v in request.headers}}
        self.seen.append(seen)
        path=seen['target'].split('?')[0]
        if path=='/upgrade':
            writer.write(conn.send(h11.InformationalResponse(status_code=101,headers=[(b'connection',b'upgrade'),(b'upgrade',b'pex')])))
            await writer.drain()
            pending=conn.trailing_data[0]
            while True:
                data=pending or await reader.read(65536)
                pending=b''
                if not data:break
                writer.write(data.upper());await writer.drain()
            writer.close();return
        if path=='/chunked':await self._answer(conn,writer,[(b'transfer-encoding',b'chunked')],[b'first ',b'second'])
        elif path=='/head':await self._answer(conn,writer,[(b'content-length',b'12')],[])
        elif path=='/echo':await self._answer(conn,writer,None,[str(len(body)).encode()])
        else:await self._answer(conn,writer,None,[b'origin plain'])
        writer.close()

    async def _answer(self,conn,writer,headers,chunks):
        body=b''.join(chunks)
        writer.write(conn.send(h11.Response(status_code=200,headers=headers if headers is not None else [(b'content-length',str(len(body)).encode())])))
        for chunk in chunks:writer.write(conn.send(h11.Data(data=chunk)))
        writer.write(conn.send(h11.EndOfMessage()));await writer.drain()

class Echo(Service):
    """A plain TCP service, for what a CONNECT tunnel carries. Echoes what it is sent, in capitals."""
    async def _client(self,reader,writer):
        try:
            while data:=await reader.read(65536):writer.write(data.upper());await writer.drain()
        except Exception:pass
        writer.close()

class Upstream(Service):
    """A fake HTTP proxy that records every head it was given, and can demand a password or stall.

    Like any proxy it keeps its own hop headers to itself, so whatever reaches the origin is
    what the relay chose to send end to end.
    """
    def __init__(self,tag='A',require=False,stall=False):
        super().__init__();self.tag=tag;self.require=require;self.stall=stall

    async def _client(self,reader,writer):
        head=await reader.readuntil(b'\r\n\r\n')
        text=head.decode('latin1');self.seen.append(text)
        if self.require and ('proxy-authorization: basic '+PASSWORD).lower() not in text.lower():
            writer.write(b'HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 27\r\n'
                         b'Connection: close\r\n\r\nupstream rejected password\n');await writer.drain();writer.close();return
        if self.stall:await asyncio.sleep(3600)
        line,_,rest=head.partition(b'\r\n')
        method,target,version=line.split(b' ')
        if method==b'CONNECT':
            host,port=split_authority(target.decode('latin1'))
            up_reader,up_writer=await asyncio.open_connection(host,port)
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n');await writer.drain()
        else:
            url=urlsplit(target.decode('latin1'))
            up_reader,up_writer=await asyncio.open_connection(url.hostname,url.port or 80)
            origin_form=(url.path or '/')+('?'+url.query if url.query else '')
            onward=b''.join(f+b'\r\n' for f in rest.split(b'\r\n') if not f.lower().startswith(b'proxy-'))
            up_writer.write(method+b' '+origin_form.encode('latin1')+b' '+version+b'\r\n'+onward)
            await up_writer.drain()
        await couple(reader,writer,up_reader,up_writer)

async def raw(relay,request,seconds=10):
    """One request written exactly as given, read back until the relay closes."""
    reader,writer=await asyncio.open_connection('127.0.0.1',relay.port)
    try:
        writer.write(request);await writer.drain()
        return await asyncio.wait_for(reader.read(-1),seconds)
    finally:
        writer.close()

async def opened(relay,routes=None,route=module.DIRECT):
    started=Relay(routes or {});await started.start(route);return started

def get(authority,path='/plain',extra=''):
    return (f'GET http://{authority}{path} HTTP/1.1\r\nHost: {authority}\r\n'
            f'Proxy-Authorization: Basic bogus\r\nAccept: */*\r\n{extra}Connection: keep-alive\r\n\r\n').encode()

# --- ordinary HTTP ----------------------------------------------------------------------------

async def test_direct_request_arrives_cleaned_and_in_origin_form():
    origin=Origin();await origin.start();relay=await opened(None)
    try:
        answer=await raw(relay,get(origin.authority))
        assert b'200 OK' in answer and answer.endswith(b'origin plain')
        seen=origin.seen[0]
        assert seen['target']=='/plain' and seen['headers']['host']==origin.authority
        # The client's own proxy credentials are this hop's business and go no further.
        assert 'proxy-authorization' not in seen['headers'] and 'proxy-connection' not in seen['headers']
        assert seen['headers']['accept']=='*/*'
    finally:
        await relay.stop();await origin.stop()

async def test_upstream_gets_absolute_form_and_only_this_route_credentials():
    origin=Origin();await origin.start();upstream=Upstream(require=True);await upstream.start()
    relay=await opened(None,{'r1':{'name':'Germany','server':upstream.server_url,'username':'agent','password':'s3cret'}},'r1')
    try:
        answer=await raw(relay,get(origin.authority))
        assert answer.endswith(b'origin plain')
        assert upstream.seen[0].startswith(f'GET http://{origin.authority}/plain HTTP/1.1')
        assert 'Basic '+PASSWORD in upstream.seen[0] and 'Basic bogus' not in upstream.seen[0]
        # The password buys the upstream hop only. The origin must never see it.
        assert not any(k.startswith('proxy-') for k in origin.seen[0]['headers'])
        assert PASSWORD not in str(origin.seen[0]['headers'])
    finally:
        await relay.stop();await upstream.stop();await origin.stop()

async def test_empty_credentials_are_valid_and_add_no_header():
    origin=Origin();await origin.start();upstream=Upstream();await upstream.start()
    relay=await opened(None,{'r1':{'name':'Open proxy','server':upstream.server_url,'username':'','password':''}},'r1')
    try:
        assert (await raw(relay,get(origin.authority))).endswith(b'origin plain')
        assert 'Proxy-Authorization' not in upstream.seen[0]
    finally:
        await relay.stop();await upstream.stop();await origin.stop()

async def test_chunked_upload_is_read_and_a_chunked_answer_stays_chunked():
    origin=Origin();await origin.start();relay=await opened(None)
    try:
        body=b'5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n'
        upload=(f'POST http://{origin.authority}/echo HTTP/1.1\r\nHost: {origin.authority}\r\n'
                'Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n').encode()+body
        assert (await raw(relay,upload)).endswith(b'11')
        assert origin.seen[0]['body']==b'hello world'
        answer=await raw(relay,get(origin.authority,'/chunked'))
        head,_,rest=answer.partition(b'\r\n\r\n')
        assert b'transfer-encoding: chunked' in head.lower() and b'first ' in rest and b'second' in rest
    finally:
        await relay.stop();await origin.stop()

async def test_head_keeps_its_length_and_sends_no_body():
    origin=Origin();await origin.start();relay=await opened(None)
    try:
        answer=await raw(relay,get(origin.authority,'/head').replace(b'GET',b'HEAD',1))
        head,_,rest=answer.partition(b'\r\n\r\n')
        assert b'content-length: 12' in head.lower() and rest==b''
    finally:
        await relay.stop();await origin.stop()

async def test_upgrade_becomes_a_tunnel_in_both_directions():
    origin=Origin();await origin.start();relay=await opened(None)
    try:
        reader,writer=await asyncio.open_connection('127.0.0.1',relay.port)
        writer.write(get(origin.authority,'/upgrade',extra='Upgrade: pex\r\n').replace(b'Connection: keep-alive',b'Connection: upgrade'))
        await writer.drain()
        head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10)
        assert b'101' in head and b'upgrade: pex' in head.lower()
        writer.write(b'after the switch');await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(16),10)==b'AFTER THE SWITCH'
        writer.close()
    finally:
        await relay.stop();await origin.stop()

async def test_ipv6_origin_on_a_non_default_port():
    if not socket.has_ipv6:pytest.skip('no IPv6 on this machine')
    origin=Origin()
    try:await origin.start('::1')
    except OSError:pytest.skip('loopback IPv6 is not available')
    relay=await opened(None)
    try:
        assert (await raw(relay,get(origin.authority))).endswith(b'origin plain')
        assert origin.seen[0]['headers']['host']==origin.authority
    finally:
        await relay.stop();await origin.stop()

# --- CONNECT ----------------------------------------------------------------------------------

async def tunnel(relay,authority,payload=b'tunnelled bytes'):
    """Open a CONNECT tunnel and exchange one payload. Returns the open pair and the echo."""
    reader,writer=await asyncio.open_connection('127.0.0.1',relay.port)
    writer.write(f'CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\nProxy-Authorization: Basic bogus\r\n\r\n'.encode())
    await writer.drain()
    head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),10)
    assert b'200' in head,head
    writer.write(payload);await writer.drain()
    return reader,writer,await asyncio.wait_for(reader.readexactly(len(payload)),10)

async def test_connect_tunnels_directly_and_through_an_upstream():
    echo=Echo();await echo.start();upstream=Upstream(require=True);await upstream.start()
    relay=await opened(None)
    try:
        reader,writer,answer=await tunnel(relay,f'127.0.0.1:{echo.port}')
        assert answer==b'TUNNELLED BYTES';writer.close()
        await relay.stop()
        relay=await opened(None,{'r1':{'name':'Germany','server':upstream.server_url,'username':'agent','password':'s3cret'}},'r1')
        reader,writer,answer=await tunnel(relay,f'127.0.0.1:{echo.port}')
        assert answer==b'TUNNELLED BYTES'
        assert upstream.seen[0].startswith(f'CONNECT 127.0.0.1:{echo.port} HTTP/1.1')
        assert f'Host: 127.0.0.1:{echo.port}' in upstream.seen[0]
        assert 'Basic '+PASSWORD in upstream.seen[0] and 'Basic bogus' not in upstream.seen[0]
        writer.close()
    finally:
        await relay.stop();await upstream.stop();await echo.stop()

async def test_connect_needs_an_explicit_port():
    relay=await opened(None)
    try:assert b'400' in await raw(relay,b'CONNECT example.test HTTP/1.1\r\nHost: example.test\r\n\r\n')
    finally:await relay.stop()

async def test_half_close_lets_the_answer_finish():
    echo=Echo();await echo.start();relay=await opened(None)
    try:
        reader,writer,answer=await tunnel(relay,f'127.0.0.1:{echo.port}',b'last words')
        assert answer==b'LAST WORDS'
        writer.write_eof()
        assert await asyncio.wait_for(reader.read(65536),10)==b''
        writer.close()
    finally:
        await relay.stop();await echo.stop()

# --- what a client is told when something fails -----------------------------------------------

async def test_upstream_failures_never_quote_the_upstream():
    origin=Origin();await origin.start();upstream=Upstream(require=True);await upstream.start()
    relay=await opened(None,{'r1':{'name':'Germany','server':upstream.server_url,'username':'agent','password':'wrong'}},'r1')
    try:
        answer=await raw(relay,get(origin.authority))
        assert b'502' in answer and b'Upstream connection failed' in answer
        assert b'rejected password' not in answer and b'407' not in answer
    finally:
        await relay.stop();await upstream.stop();await origin.stop()

async def test_a_refused_connect_says_only_that_the_upstream_failed():
    echo=Echo();await echo.start();upstream=Upstream(require=True);await upstream.start()
    relay=await opened(None,{'r1':{'name':'Germany','server':upstream.server_url,'username':'agent','password':'wrong'}},'r1')
    try:
        answer=await raw(relay,f'CONNECT 127.0.0.1:{echo.port} HTTP/1.1\r\nHost: 127.0.0.1:{echo.port}\r\n\r\n'.encode())
        assert b'502 Upstream connection failed' in answer and b'407' not in answer and b'password' not in answer
    finally:
        await relay.stop();await upstream.stop();await echo.stop()

async def test_the_handler_limit_refuses_rather_than_queues(monkeypatch):
    monkeypatch.setattr(module,'HANDLERS_MAX',2)
    echo=Echo();await echo.start();relay=await opened(None)
    held=[]
    try:
        for _ in range(2):held.append(await tunnel(relay,f'127.0.0.1:{echo.port}'))
        assert b'503 Relay connection limit reached' in await raw(relay,get(f'127.0.0.1:{echo.port}'))
        # The tunnels already carrying bytes are untouched by the refusal.
        reader,writer,_=held[0]
        writer.write(b'still mine');await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(10),10)==b'STILL MINE'
    finally:
        for _,writer,_ in held:writer.close()
        await relay.stop();await echo.stop()

async def test_a_dead_upstream_a_bad_request_and_an_origin_form_each_get_their_category():
    spare=socket.socket();spare.bind(('127.0.0.1',0));closed=spare.getsockname()[1];spare.close()
    relay=await opened(None,{'r1':{'name':'Gone','server':f'http://127.0.0.1:{closed}'}},'r1')
    try:
        assert b'502' in await raw(relay,get('127.0.0.1:1/plain'))
        await relay.apply(module.DIRECT)
        assert b'400' in await raw(relay,b'NOT-A-REQUEST\r\nHost: x\r\n\r\n')
        assert b'501' in await raw(relay,b'GET /plain HTTP/1.1\r\nHost: example.test\r\n\r\n')
    finally:
        await relay.stop()

async def test_untrusted_upstream_tls_is_one_category():
    # A plain server answering a TLS handshake fails exactly where an untrusted certificate does.
    origin=Origin();await origin.start()
    relay=await opened(None,{'r1':{'name':'TLS proxy','server':f'https://127.0.0.1:{origin.port}'}},'r1')
    try:
        answer=await raw(relay,get('example.test:80'))
        assert b'502' in answer and b'certificate' not in answer.lower()
    finally:
        await relay.stop();await origin.stop()

async def test_a_slow_head_and_an_endless_head_are_bounded(monkeypatch):
    monkeypatch.setattr(module,'HEAD_SECONDS',0.3)
    relay=await opened(None)
    try:
        assert b'504' in await raw(relay,b'GET http://example.test/ HTTP/1.1\r\n')
        assert b'400' in await raw(relay,b'GET http://example.test/ HTTP/1.1\r\nX: '+b'a'*70000+b'\r\n')
    finally:
        await relay.stop()

async def test_unknown_and_unsupported_routes_are_refused_before_anything_moves():
    relay=await opened(None,{'r1':{'name':'Socks','server':'socks5://127.0.0.1:1080'}})
    try:
        with pytest.raises(ScenarioError):await relay.apply('missing')
        with pytest.raises(ScenarioError):await relay.apply('r1')
        assert relay.generation==1 and relay.route_id==module.DIRECT
    finally:
        await relay.stop()

# --- switching ---------------------------------------------------------------------------------

async def test_a_switch_disconnects_the_old_route_and_the_next_request_uses_the_new_one():
    echo=Echo();await echo.start();origin=Origin();await origin.start()
    first=Upstream('A');await first.start();second=Upstream('B');await second.start()
    routes={'a':{'name':'A','server':first.server_url},'b':{'name':'B','server':second.server_url}}
    relay=await opened(None,routes,'a')
    try:
        reader,writer,answer=await tunnel(relay,f'127.0.0.1:{echo.port}')
        assert answer==b'TUNNELLED BYTES'
        switched=await relay.apply('b')
        assert switched['disconnected']==1 and switched['generation']==2 and switched['route_name']=='B'
        assert 'may be interrupted' in switched['note']
        # The tunnel is gone, not paused: nothing it writes can resume on the new route.
        writer.write(b'still here');await asyncio.sleep(0)
        assert await asyncio.wait_for(reader.read(65536),10)==b''
        assert (await raw(relay,get(origin.authority))).endswith(b'origin plain')
        assert len(second.seen)==1 and len(first.seen)==1
        # Switching to the same route again is still a fresh start.
        again=await relay.apply('b')
        assert again['generation']==3 and again['disconnected']==0
        assert not relay.live
    finally:
        await relay.stop();await first.stop();await second.stop();await origin.stop();await echo.stop()

async def test_a_switch_during_a_stalled_handshake_leaves_nothing_behind():
    stalling=Upstream('A',stall=True);await stalling.start();origin=Origin();await origin.start()
    relay=await opened(None,{'a':{'name':'A','server':stalling.server_url}},'a')
    try:
        pending=asyncio.create_task(raw(relay,get(origin.authority)))
        for _ in range(100):
            if stalling.seen:break
            await asyncio.sleep(0.02)
        assert stalling.seen,'the relay never reached the stalling upstream'
        assert (await relay.apply(module.DIRECT))['disconnected']==1
        assert await asyncio.wait_for(pending,10)==b''
        assert not relay.live
        assert (await raw(relay,get(origin.authority))).endswith(b'origin plain')
    finally:
        await relay.stop();await stalling.stop();await origin.stop()

async def test_stop_is_idempotent_and_keeps_its_counters():
    origin=Origin();await origin.start();relay=await opened(None)
    try:
        await raw(relay,get(origin.authority))
        port=relay.port
        await relay.stop();await relay.stop()
        assert not relay.live and relay.server is None
        with pytest.raises(ScenarioError):relay.proxy
        with pytest.raises(OSError):await asyncio.open_connection('127.0.0.1',port)
        assert relay.stats[1]['accepted']==1 and relay.stats[1]['established']==1
    finally:
        await origin.stop()

def test_authority_parsing_refuses_what_it_cannot_resolve():
    assert split_authority('127.0.0.1:8080')==('127.0.0.1',8080)
    assert split_authority('[::1]:9101')==('::1',9101)
    assert split_authority('example.test',80)==('example.test',80)
    for bad in ('example.test','[::1]','[::1]x:80','a:b','host:0','host:70000','user@host:80','host/x:80',':80'):
        with pytest.raises(ValueError):split_authority(bad)
