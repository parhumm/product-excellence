import re, ipaddress, socket
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

SENSITIVE=re.compile(r'token|secret|password|authorization|cookie|session|api.?key|otp',re.I)
RISKY=re.compile(r'delete|remove account|confirm purchase|pay now|complete purchase|place order|publish|upload|send message|حذف|پرداخت|خرید|ارسال|انتشار|بارگذاری|تایید خرید|تأیید خرید',re.I)
def safe_url(url):
    try:
        u=urlsplit(url)
        return urlunsplit((u.scheme,u.netloc.split('@')[-1],u.path,urlencode([(k,'[REDACTED]' if SENSITIVE.search(k) else v) for k,v in parse_qsl(u.query)]),''))
    except Exception: return '[invalid URL]'
def is_measurement(value):
    # A number or an explicitly missing count; neither can carry a credential.
    return value is None or (isinstance(value,(int,float)) and not isinstance(value,bool))
def redact(value):
    # Counts such as input_tokens survive; an unknown count must not become a string.
    if isinstance(value,dict): return {k:(v if is_measurement(v) else '[REDACTED]') if SENSITIVE.search(k) else redact(v) for k,v in value.items()}
    if isinstance(value,list): return [redact(x) for x in value]
    if isinstance(value,str):
        value=re.sub(r'\bBearer\s+[\w.\-]+','Bearer [REDACTED]',value,flags=re.I)
        value=re.sub(r'([?&](?:token|access_token|session|key|password)=)[^&\s]+',r'\1[REDACTED]',value,flags=re.I)
        return value
    return value

PASSWORD_PLACEHOLDER='{{password}}'

def scrub(value,secret,placeholder=PASSWORD_PLACEHOLDER):
    # Reflections in structured evidence need the same protection as raw captures.
    if not secret:return value
    if isinstance(value,dict):return {k:scrub(v,secret,placeholder) for k,v in value.items()}
    if isinstance(value,list):return [scrub(v,secret,placeholder) for v in value]
    if isinstance(value,str):return value.replace(secret,placeholder)
    return value

def site_hosts(host):
    """A site redirects between its bare and its www host; both name the same site.
    An IP literal or a bare name has no such pair, so it stands alone."""
    h=(host or '').lower()
    if not h or '.' not in h:return {h}-{''}
    try:
        ipaddress.ip_address(h);return {h}
    except ValueError:pass
    bare=h[4:] if h.startswith('www.') else h
    return {bare,'www.'+bare}

def own_hosts(mission):
    """The hosts the mission is about. Findings are recorded only for these."""
    return set().union(*(site_hosts(h) for h in
        {urlsplit(mission['url']).hostname or '',*mission.get('allowed_domains',[])}))

def competitor_hosts(mission):
    # A benchmark opens each competitor's start URL.
    return set().union(set(),*(site_hosts(urlsplit(url).hostname) for url in mission.get('competitors',[])))

def allowed_hosts(mission):
    return own_hosts(mission)|competitor_hosts(mission)

def allowed_url(url, mission):
    try:
        u=urlsplit(url);port=u.port
    except ValueError:return False
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password: return False
    h=u.hostname.lower(); base=urlsplit(mission['url']).hostname.lower()
    if h not in allowed_hosts(mission): return False
    if h in ('localhost','127.0.0.1','::1'):
        return base in ('localhost','127.0.0.1','::1') and port==urlsplit(mission['url']).port and (u.path=='/demo' or u.path.startswith('/demo/'))
    try:
        if not ipaddress.ip_address(h).is_global: return False
    except ValueError: pass
    return True

def mutation_allowed(method, url, mission, operator_supplied=False):
    # A journey operates the website the way a person would, so the website's own form
    # submissions must reach it; so must they for stored sign-in credentials, or once the
    # operator has typed a value into this run. An audit, an exploration and a benchmark stay
    # read-only, and no mode ever lets a third party — analytics included — be written to.
    if method in ('GET','HEAD','OPTIONS'): return True
    own=(mission.get('mode')=='journey' or bool(mission.get('login_identifier')) or operator_supplied)
    return own and allowed_url(url,mission)

def action_allowed(action, mission, target=None, controls=None):
    kind=action.get('type')
    if kind not in ('click','type','focus','select','forward','press','scroll','open','back','reload','wait','ask','choose','finish'): return False,'Unsupported action'
    if kind=='choose':
        # A choice is only a choice when the screen really offers several ways on, each one a
        # control the operator can be shown and the worker can then actuate.
        ids={c['id'] for c in (controls or [])}
        if len({o for o in (action.get('options') or []) if o in ids})<2:
            return False,'choose needs options: the control ids of at least two ways to continue on this screen, such as pex-2 and pex-3'
    if kind=='open':
        # Models put the URL in either field; refuse with the field or host that was wrong.
        url=action.get('value') or action.get('target') or ''
        if not allowed_url(url,mission):
            hosts=', '.join(sorted(h for h in allowed_hosts(mission) if h))
            try:host=urlsplit(url).hostname
            except ValueError:host=''
            return False,(f'Navigation to {host} refused; allowed hosts: {hosts}' if host
                          else 'open needs an absolute http(s) URL in value, on an allowed host: '+hosts)
    if kind=='click' and RISKY.search((target or {}).get('text','')+' '+(target or {}).get('href','')): return False,'Payment, publication or destructive control blocked'
    if kind in ('click','type','focus','select','ask') and not target:return False,'Missing current target: target must be a control id from the current observation, such as pex-2, not a label or a value name'
    if kind=='ask':
        # The operator types the value into this field, so it has to be a field that takes typing.
        tag=target.get('tag') or ''
        if not (tag in ('input','textarea') or tag.endswith('EditText')) or target.get('input_type') in ('file','checkbox','radio','submit','button','image','range','color'):
            return False,'ask needs the text field that takes the value as its target'
    if kind=='type':
        if not target: return False,'Missing target'
        password_field=target.get('input_type')=='password'
        if action.get('value')==PASSWORD_PLACEHOLDER and not password_field:
            return False,PASSWORD_PLACEHOLDER+' may only be typed into a password field'
        if password_field and mission.get('login_identifier'):
            # The engine substitutes the stored password; the AI never handles it.
            if action.get('value')!=PASSWORD_PLACEHOLDER:
                return False,'Type exactly '+PASSWORD_PLACEHOLDER+' into the password field; the stored sign-in password is filled for you'
            return True,''
        if target.get('input_type') in ('password','file') or SENSITIVE.search(target.get('text','')): return False,'Return action ask with this field as target and a short name of the value in value; the operator supplies it. Never invent it.'
    if kind=='press' and action.get('value') not in ('Tab','Escape','ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End'):
        # Enter inside a search box is how many sites run a search, and some expose no submit control.
        if not (action.get('value')=='Enter' and (target or {}).get('input_type')=='search'):
            return False,'Key may submit a form; use an explicitly identified control'
    return True,''
