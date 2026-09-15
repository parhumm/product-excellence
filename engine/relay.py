"""One run-owned local relay, so a journey can change its way out without a new session.

The listener is loopback and ephemeral: a browser or an owned emulator is pointed at `proxy`
once, and `apply(route_id)` decides which upstream the next connection uses. A switch is a
deliberate disconnect — every connection opened on the previous route is terminated, so
in-flight requests may be interrupted. Nothing is retried and nothing falls back to direct.

Route records and their credentials live in this object only. Credentials are injected on the
upstream hop, never sent to an origin and never logged; inbound proxy credentials are stripped.
What a client is told about a failure is one of a few fixed categories, never upstream text.

A proxy label is operator metadata. Forwarding through it establishes no country, ISP, carrier
or entitlement, and UDP/QUIC never reaches it at all.
"""
import asyncio,base64,ipaddress,ssl
from http import HTTPStatus
from urllib.parse import urlsplit
import h11,httpx
from . import store
from .scenario import ScenarioError

DIRECT='direct'
HEADERS_MAX=65536
CHUNK=65536
DIAL_SECONDS=5
HEAD_SECONDS=10
HANDLERS_MAX=128
SHUTDOWN_SECONDS=5
# Regenerated or hop-by-hop, so never copied across: framing comes back from h11, Host from the
# request target, and an upgrade is re-stated deliberately. Fields named by Connection go too.
DROP={b'host',b'content-length',b'transfer-encoding',b'connection',b'keep-alive',b'proxy-connection',
      b'proxy-authenticate',b'proxy-authorization',b'te',b'trailer',b'upgrade'}
REFUSALS={400:'Malformed request',501:'Unsupported request form',502:'Upstream connection failed',
          503:'Relay connection limit reached',504:'Upstream timed out'}
SWITCH_NOTE=('Switched route and disconnected existing proxied connections. In-flight requests may be '
             'interrupted; new connections use the selected route.')
SETUP_NOTE='Initial route for this run, established before any traffic was proxied.'
EVIDENCE=('Connections exit through this route; observed exit IP recorded per switch. UDP/QUIC not proxied. '
          'DNS is resolved on the host, so CDN/geo may follow the host resolver\'s country rather than the '
          'exit IP. ISP/ASN identity not independently verified.')
# Two independent echoes, tried in order. Each answers with the exit address and nothing else.
PROBES=('https://api.ipify.org','https://icanhazip.com')
PROBE_SECONDS=15

def counters():
    """Per-generation transport diagnostics. The probe's own connection is counted twice: in the
    totals, and again under its own name, so app traffic is never inferred from a probe."""
    return {'accepted':0,'established':0,'bytes':0,'probe_accepted':0,'probe_established':0,'probe_bytes':0}

class _Refuse(Exception):
    """Answer the client with one fixed category and close. Carries no upstream detail."""
    def __init__(self,code):self.code=code

class _Stale(Exception):
    """This connection belongs to a route that has since been switched away from."""

def split_authority(text,default=0):
    """host,port from a CONNECT authority or a URI authority. Anything ambiguous raises."""
    host,port=text,''
    if text.startswith('['):
        host,_,rest=text[1:].partition(']')
        if rest and not rest.startswith(':'):raise ValueError('bad authority')
        port=rest[1:]
    elif text.count(':')==1:host,_,port=text.partition(':')
    elif ':' in text:raise ValueError('bad authority')
    if not host or '@' in host or '/' in host or (port and not port.isdigit()):raise ValueError('bad authority')
    number=int(port) if port else default
    if not 0<number<65536:raise ValueError('bad authority')
    return host,number

def connection_named(headers):
    """The field names a Connection header hands over to this hop, so they are not forwarded."""
    named=set()
    for key,value in headers:
        if key==b'connection':named.update(token.strip().lower() for token in value.split(b',') if token.strip())
    return named

def reason(code):
    """The standard phrase for a status code. An upstream's own wording never reaches a client."""
    try:return HTTPStatus(code).phrase.encode()
    except ValueError:return b''

def framing(headers):
    """b'chunked', a Content-Length value, or None for a message with no body.

    h11 has already refused both headers at once, so at most one of them is here.
    """
    for key,value in headers:
        if key==b'transfer-encoding':return b'chunked'
    for key,value in headers:
        if key==b'content-length':return value
    return None

def restate(headers,extra=()):
    """End-to-end headers only, spelled as they arrived, plus whatever this hop states itself."""
    named=connection_named(headers)
    raw=headers.raw_items() if hasattr(headers,'raw_items') else headers
    return [(k,v) for k,v in raw if k.lower() not in DROP and k.lower() not in named]+list(extra)

class _Conn:
    """One accepted client connection, its upstream, and the route generation it belongs to."""
    __slots__=('generation','reader','client','upstream','task','answered','probe')
    def __init__(self,generation,reader,client,task):
        self.generation=generation;self.reader=reader;self.client=client
        self.upstream=None;self.task=task;self.answered=False;self.probe=False

    def terminate(self,cancel=True):
        """Drop both sockets now. A switch means these bytes stop, not that they are recalled."""
        if cancel and self.task and self.task is not asyncio.current_task():self.task.cancel()
        for writer in (self.client,self.upstream):
            if writer is None:continue
            try:writer.close()
            except Exception:pass

    async def refuse(self,code):
        if self.answered:return
        self.answered=True
        body=REFUSALS[code].encode()
        try:
            self.client.write(f'HTTP/1.1 {code} {REFUSALS[code]}\r\nContent-Type: text/plain\r\n'
                              f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()+body)
            await self.client.drain()
            if self.client.can_write_eof():self.client.write_eof()
            # Closing on bytes this side never read resets the answer away before the client sees it.
            async with asyncio.timeout(1):
                while await self.reader.read(CHUNK):pass
        except Exception:pass

class Relay:
    """`routes` is already resolved: {id: {'name','server','username','password'}}. `direct` is implicit."""
    def __init__(self,routes=None,host='127.0.0.1'):
        self.routes=dict(routes or {});self.host=host;self.port=0;self.server=None
        self.generation=0;self.route=None;self.route_id='';self.live=set();self.stats={}
        self.checks=[];self.expected_probe=None

    @property
    def proxy(self):
        if not self.port:raise ScenarioError('The relay is not listening')
        return f'http://{self.host}:{self.port}'

    def resolve(self,route_id):
        if route_id in (DIRECT,'',None):return {'id':DIRECT,'name':'Direct connection','server':''}
        route=self.routes.get(route_id)
        if not route:raise ScenarioError('This route is not configured for this run: '+str(route_id)[:60])
        if urlsplit(route['server']).scheme not in ('http','https'):
            raise ScenarioError('The relay forwards through HTTP or HTTPS proxies only: '+route['name'])
        return {'id':route_id,**route}

    def _check(self,route,step,note):
        """Evidence for one route change, appended before the change is attempted.

        A switch that is cancelled or never verified still leaves this record behind, so the run
        says which route it asked for and what it could establish about it.
        """
        check={'generation':self.generation+1,'route_id':route['id'],'route_name':route['name'],'step':step,
               'requested_at':store.now(),'finished_at':'','status':'requested','probe':'','observed_ip':None,
               'error':'','disconnected':None,'note':note,'verification':EVIDENCE}
        self.checks.append(check);return check

    async def start(self,route_id=DIRECT):
        self.route=self.resolve(route_id);self.route_id=self.route['id']
        check=self._check(self.route,None,SETUP_NOTE)
        self.generation=1;self.stats[1]=counters()
        self.server=await asyncio.start_server(self._accept,self.host,0,limit=HEADERS_MAX)
        self.port=self.server.sockets[0].getsockname()[1]
        check.update(status='switched',disconnected=0,finished_at=store.now())
        return self.proxy

    async def apply(self,route_id,step=None):
        """Validate the route first, advance the generation, then retire everything older."""
        route=self.resolve(route_id)
        if not self.server:raise ScenarioError('The relay is not listening')
        check=self._check(route,step,SWITCH_NOTE)
        self.generation+=1;self.route=route;self.route_id=route['id']
        self.stats[self.generation]=counters()
        # Switching to the same route still retires: the operator asked for a fresh connection.
        check.update(status='switched',disconnected=await self._retire(lambda c:c.generation!=self.generation),
                     finished_at=store.now())
        return check

    async def verify(self,check=None,budget=None):
        """Probe this relay through itself and record the address this generation exits from.

        Both endpoints failing means the route is unverified, not that it is dead: the caller stops
        the run as an infrastructure failure rather than calling it an app defect or falling back.
        """
        check=check if check is not None else self.checks[-1]
        try:
            async with asyncio.timeout(max(1,min(PROBE_SECONDS,budget if budget is not None else PROBE_SECONDS))):
                for url in PROBES:
                    check['probe']=url
                    try:
                        check.update(observed_ip=await self._probe(url),status='verified',error='')
                        break
                    except asyncio.CancelledError:raise
                    except Exception as error:check['error']=str(error)[:200] or type(error).__name__
        except asyncio.CancelledError:
            check.update(status='cancelled',finished_at=store.now());raise
        except (asyncio.TimeoutError,TimeoutError):check['error']='Route verification timed out'
        if check['status']!='verified':check.update(status='unavailable',error=check['error'] or 'No probe answered')
        check['finished_at']=store.now()
        return check

    async def _probe(self,url):
        """This relay's own exit address, read through this relay. An unparseable answer is no answer."""
        split=urlsplit(url)
        self.expected_probe=split_authority(split.netloc,443 if split.scheme=='https' else 80)
        try:
            async with httpx.AsyncClient(proxy=self.proxy,trust_env=False,follow_redirects=False,
                                         timeout=PROBE_SECONDS) as client:
                answer=await client.get(url)
            answer.raise_for_status()
            return str(ipaddress.ip_address(answer.text.strip()))
        finally:
            self.expected_probe=None

    async def stop(self):
        server,self.server=self.server,None
        self.port=0
        if server:server.close()
        # Retire first: waiting for handlers that are about to be terminated only delays the run.
        await self._retire(lambda c:True)
        if server:
            try:await asyncio.wait_for(server.wait_closed(),SHUTDOWN_SECONDS)
            except Exception:pass

    async def _retire(self,stale):
        """Terminate the matching connections and wait, bounded, for their handlers to finish."""
        going=[c for c in self.live if stale(c)]
        for conn in going:conn.terminate()
        tasks=[c.task for c in going if c.task and c.task is not asyncio.current_task() and not c.task.done()]
        if tasks:await asyncio.wait(tasks,timeout=SHUTDOWN_SECONDS)
        return len(going)

    def _count(self,key,generation,amount=1,probe=False):
        stat=self.stats.setdefault(generation,counters())
        stat[key]+=amount
        if probe:stat['probe_'+key]+=amount

    def _claim(self,conn,host,port):
        """The probe's own connection, claimed once. Later app traffic to that host is not the probe."""
        if self.expected_probe!=(host,port):return
        self.expected_probe=None;conn.probe=True;self._count('probe_accepted',conn.generation)

    def _fresh(self,conn):
        if conn.generation!=self.generation or not self.server:raise _Stale()

    def _credentials(self,route):
        """This route's Basic credentials, for the upstream hop only. Empty credentials are valid."""
        user=route.get('username') or '';password=route.get('password') or ''
        if not user and not password:return []
        return [(b'Proxy-Authorization',b'Basic '+base64.b64encode(f'{user}:{password}'.encode()))]

    async def _accept(self,reader,writer):
        # Registered before the first await, so a switch one instruction later still finds it.
        conn=_Conn(self.generation,reader,writer,asyncio.current_task())
        self.live.add(conn);self._count('accepted',conn.generation)
        try:
            if len(self.live)>HANDLERS_MAX:raise _Refuse(503)
            await self._serve(reader,writer,conn)
        except _Stale:pass
        except asyncio.CancelledError:raise
        except _Refuse as refusal:await conn.refuse(refusal.code)
        except asyncio.TimeoutError:await conn.refuse(504)
        except (h11.RemoteProtocolError,h11.LocalProtocolError,ValueError,asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,UnicodeDecodeError):await conn.refuse(400)
        except Exception:await conn.refuse(502)
        finally:
            self.live.discard(conn);conn.terminate(cancel=False)

    async def _serve(self,reader,writer,conn):
        head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),HEAD_SECONDS)
        parts=head.split(b'\r\n',1)[0].split(b' ')
        if parts[0].upper()==b'CONNECT':
            if len(parts)!=3:raise ValueError('bad request line')
            return await self._tunnel(reader,writer,conn,parts[1].decode('latin1'))
        return await self._forward(reader,writer,conn,head)

    async def _dial(self,host,port,context=None):
        try:
            return await asyncio.wait_for(asyncio.open_connection(
                host,port,ssl=context,server_hostname=host if context else None,limit=HEADERS_MAX),DIAL_SECONDS)
        except asyncio.TimeoutError:raise _Refuse(504)
        except asyncio.CancelledError:raise
        # Refused, unresolved, or an upstream certificate this machine does not trust: one category.
        except Exception:raise _Refuse(502)

    async def _dial_route(self,route,host,port):
        """The socket this generation forwards over: the upstream proxy, or the target itself."""
        if not route['server']:return await self._dial(host,port)
        upstream=urlsplit(route['server'])
        return await self._dial(upstream.hostname,upstream.port or (443 if upstream.scheme=='https' else 80),
                                ssl.create_default_context() if upstream.scheme=='https' else None)

    async def _tunnel(self,reader,writer,conn,target):
        """CONNECT. The client's own proxy headers are dropped; only this route's travel with it."""
        host,port=split_authority(target)
        self._claim(conn,host,port)
        route=self.route
        up_reader,up_writer=await self._dial_route(route,host,port)
        conn.upstream=up_writer
        if route['server']:
            # The authority reaches the upstream unchanged, and is its own Host.
            head=f'CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n'.encode('latin1')
            head+=b''.join(k+b': '+v+b'\r\n' for k,v in self._credentials(route))+b'\r\n'
            up_writer.write(head);await up_writer.drain()
            answer=await asyncio.wait_for(up_reader.readuntil(b'\r\n\r\n'),HEAD_SECONDS)
            status=answer.split(b'\r\n',1)[0].split(b' ')
            # 407, 502 or anything else upstream says stays upstream: the client learns the category.
            if len(status)<2 or not status[1].startswith(b'2'):raise _Refuse(502)
        self._fresh(conn)
        writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n');conn.answered=True;await writer.drain()
        self._count('established',conn.generation,probe=conn.probe)
        # Bytes either side sent behind its head are already buffered in its reader, so they travel too.
        await self._both(reader,writer,up_reader,up_writer,conn)

    async def _forward(self,reader,writer,conn,head):
        """Ordinary proxied HTTP: absolute-form in, framing decoded and re-encoded by h11."""
        server=h11.Connection(h11.SERVER,max_incomplete_event_size=HEADERS_MAX)
        server.receive_data(head)
        request=server.next_event()
        while request is h11.NEED_DATA:
            server.receive_data(await asyncio.wait_for(reader.read(CHUNK),HEAD_SECONDS))
            request=server.next_event()
        if not isinstance(request,h11.Request):raise ValueError('not a request')
        url=urlsplit(request.target.decode('latin1'))
        # Origin-form means this was not addressed to a proxy; https absolute-form would need
        # interception, which this relay does not do.
        if url.scheme!='http' or not url.netloc:raise _Refuse(501)
        host,port=split_authority(url.netloc,80)
        self._claim(conn,host,port)
        upgrade=[(b'Upgrade',v) for k,v in request.headers if k==b'upgrade'] if b'upgrade' in connection_named(request.headers) else []
        hop=[(b'Connection',b'upgrade')]+upgrade if upgrade else [(b'Connection',b'close')]
        body=framing(request.headers)
        if body==b'chunked':hop.append((b'Transfer-Encoding',b'chunked'))
        elif body is not None:hop.append((b'Content-Length',body))
        route=self.route
        up_reader,up_writer=await self._dial_route(route,host,port)
        conn.upstream=up_writer
        self._fresh(conn)
        client=h11.Connection(h11.CLIENT,max_incomplete_event_size=HEADERS_MAX)
        target=request.target if route['server'] else ((url.path or '/')+('?'+url.query if url.query else '')).encode('latin1')
        up_writer.write(client.send(h11.Request(method=request.method,target=target,headers=restate(
            request.headers,[(b'Host',url.netloc.encode('latin1'))]+hop+self._credentials(route)))))
        await up_writer.drain()
        async for event in self._events(server,reader):
            if isinstance(event,h11.Data):
                up_writer.write(client.send(event));await up_writer.drain()
                self._count('bytes',conn.generation,len(event.data),conn.probe)
            elif isinstance(event,h11.EndOfMessage):
                up_writer.write(client.send(h11.EndOfMessage(headers=event.headers if body==b'chunked' else [])))
                await up_writer.drain()
        await self._answer(reader,writer,up_reader,up_writer,conn,client,server)

    async def _answer(self,reader,writer,up_reader,up_writer,conn,client,server):
        """The response, its informational lead-in, and the tunnel a 101 turns this into."""
        try:await self._events_to_client(reader,writer,up_reader,up_writer,conn,client,server)
        # An upstream that answers nonsense, or nothing, failed as an upstream; the client is not at fault.
        except h11.RemoteProtocolError:raise _Refuse(502)

    async def _events_to_client(self,reader,writer,up_reader,up_writer,conn,client,server):
        established=False
        async for event in self._events(client,up_reader,HEAD_SECONDS):
            if isinstance(event,(h11.Response,h11.InformationalResponse)):
                self._fresh(conn)
                # The upstream's own authentication is between it and this relay. A client never
                # learns that a proxy asked for a password, let alone which realm asked.
                if event.status_code==407:raise _Refuse(502)
                framed=framing(event.headers)
                hop=[(b'Connection',b'close')]
                if event.status_code==101:hop=[(b'Connection',b'upgrade')]+[(b'Upgrade',v) for k,v in event.headers if k==b'upgrade']
                elif framed==b'chunked':hop.append((b'Transfer-Encoding',b'chunked'))
                elif framed is not None:hop.append((b'Content-Length',framed))
                writer.write(server.send(type(event)(status_code=event.status_code,
                    headers=restate(event.headers,hop),reason=reason(event.status_code))));conn.answered=True
                await writer.drain()
                if not established:established=True;self._count('established',conn.generation,probe=conn.probe)
                if event.status_code==101:
                    # h11 stops parsing at the switch; whatever it had already read is the new protocol's.
                    for source,sink in ((client,writer),(server,up_writer)):
                        pending=source.trailing_data[0]
                        if pending:sink.write(pending);await sink.drain()
                    return await self._both(reader,writer,up_reader,up_writer,conn)
            elif isinstance(event,h11.Data):
                writer.write(server.send(event));await writer.drain()
                self._count('bytes',conn.generation,len(event.data),conn.probe)
            elif isinstance(event,h11.EndOfMessage):
                writer.write(server.send(h11.EndOfMessage()));await writer.drain()
        if not established:raise _Refuse(502)

    async def _events(self,connection,reader,timeout=None):
        """h11 events off a socket. `timeout` bounds the wait for the head, not the body."""
        while True:
            event=connection.next_event()
            if event is h11.NEED_DATA:
                read=reader.read(CHUNK)
                connection.receive_data(await (asyncio.wait_for(read,timeout) if timeout else read))
                continue
            if event is h11.PAUSED:return
            yield event
            timeout=None
            if isinstance(event,(h11.EndOfMessage,h11.ConnectionClosed)):return

    async def _both(self,reader,writer,up_reader,up_writer,conn):
        """Both directions until each says it is done. A half-close is passed on where it can be."""
        tasks=[asyncio.create_task(self._pump(reader,up_writer,conn)),
               asyncio.create_task(self._pump(up_reader,writer,conn))]
        try:await asyncio.gather(*tasks)
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)

    async def _pump(self,reader,writer,conn):
        try:
            while data:=await reader.read(CHUNK):
                writer.write(data);await writer.drain()
                self._count('bytes',conn.generation,len(data),conn.probe)
        except (OSError,ssl.SSLError):pass
        finally:
            # TLS has no half-close to hand over; closing ends the sibling instead of stranding it.
            try:
                if writer.can_write_eof():writer.write_eof()
                else:writer.close()
            except Exception:pass
