import json,hashlib,re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .policy import safe_url
from .schema_validation import validate_schema

def normalized_url(url):
    """Keep page identity, but discard fragments and common tracking parameters."""
    u=urlsplit(safe_url(url))
    host=(u.hostname or '').lower()
    port=u.port
    authority=host if port is None or (u.scheme,port) in (('http',80),('https',443)) else f'{host}:{port}'
    query=urlencode(sorted((k,v) for k,v in parse_qsl(u.query,keep_blank_values=True)
                           if not k.lower().startswith('utm_') and k.lower() not in ('gclid','fbclid')))
    return urlunsplit((u.scheme.lower(),authority,u.path or '/',query,''))

def fingerprint(f):
    key=f.get('rule') or f.get('issue_key') or f['title']
    return hashlib.sha256((f['pillar']+'|'+key+'|'+normalized_url(f.get('url',''))).encode()).hexdigest()[:24]

def finding_identity(f):
    # Recompute legacy deterministic records without modifying their evidence.
    if f.get('source')=='ai' and not f.get('issue_key'):
        return fingerprint({**f,'issue_key':'legacy-'+f['fingerprint']})
    return fingerprint(f) if f.get('rule') or f.get('issue_key') else f['fingerprint']

def js_detail(event):
    """Everything a developer needs to locate a page error, from the recorded event."""
    lines=[(event.get('name')+': ' if event.get('name') else '')+str(event.get('message',''))]
    for key,title in (('source','Source'),('page_url','Page')):
        if event.get(key):lines.append(title+': '+str(event[key]))
    if event.get('step') is not None:lines.append('Observation step: '+str(event['step']+1))
    frames=[l.strip() for l in str(event.get('stack') or '').splitlines() if l.strip().startswith('at ')][:6]
    if frames:lines+=['Stack:']+frames
    return '\n'.join(lines)

def evaluate(observation, http_events, console, audit):
    result=[]; oid=observation['id']; url=observation['url']
    def add(rule,pillar,title,observed,expected,recommendation,severity='P2',classification='defect'):
        f=dict(rule=rule,pillar=pillar,title=title,observed=str(observed),expected=expected,recommendation=recommendation,severity=severity,classification=classification,evidence_id=oid,url=url,verifier_status='CONFIRMED',source='deterministic',confidence=1.0)
        f['fingerprint']=fingerprint(f);result.append(f)
    md=observation['metadata']; metrics=observation.get('metrics',{})
    for k,label in [('title','Page title'),('description','Meta description')]:
        v=observation.get(k) if k=='title' else md.get(k)
        if not v:add('missing-'+k,'seo_aeo',label+' is missing','Empty '+k,'A descriptive value for this page','Add a page-specific '+k,'P3')
    if 'noindex' in md.get('robots','').lower():add('noindex','seo_aeo','Page asks search engines not to index it',md['robots'],'Indexable public content when intended','Confirm whether noindex is intentional','P2','risk')
    if not md.get('canonical'):add('canonical','seo_aeo','No canonical link found','No link rel=canonical','Canonical strategy appropriate for this URL','Review duplicate-URL handling','P3','observation')
    for i,x in enumerate(md.get('jsonld',[])):
        for issue in validate_schema(x):
            add('schema-'+issue['code']+'-'+str(i)+'-'+issue['path'],'seo_aeo','Structured data needs review',issue['message']+' at '+issue['path'],'Valid JSON-LD and appropriate Schema.org types and properties','Correct the structured data or confirm intentional extension usage','P2' if issue['code']=='json-syntax' else 'P3','defect' if issue['code']=='json-syntax' else 'risk')
    if md.get('overflow'):add('overflow','ux_ui','Page overflows the viewport horizontally','Document width exceeds viewport width','Content fits the selected viewport','Inspect overflowing elements at this viewport')
    for v in audit.get('violations',[]):
        if v.get('impact') in ('critical','serious','moderate','minor'):
            add('axe-'+v['id'],'ux_ui',v['help'],json.dumps([{'target':n.get('target'),'summary':n.get('failureSummary')} for n in v['nodes'][:4]],ensure_ascii=False),v.get('description','Accessibility rule passes'),v.get('helpUrl','Review accessible markup'),'P2' if v.get('impact') in ('critical','serious') else 'P3')
    for e in http_events:
        if e.get('status',0)>=500:add('http-'+str(e['status'])+'-'+urlsplit(e['url']).path,'functionality','Server error during the journey',f"{e['status']} {e['url']}",'Successful response','Reproduce the request and inspect server logs')
    for e in console:
        if e.get('kind')=='pageerror':add('js-'+e['message'][:80],'functionality','Unhandled JavaScript error',js_detail(e),'No unhandled runtime errors','Reproduce at the source location; the complete stack trace is kept in the observation JSON')
    if metrics.get('lcp') and metrics['lcp']>2500:add('lcp','performance','Slow largest contentful paint in this visit',f"{metrics['lcp']:.0f} ms",'Lab target ≤2500 ms','Inspect LCP resource and rendering work; confirm over repeated runs','P2','risk')
    if (metrics.get('cls') or 0)>0.1:add('cls','performance','Layout shifts exceed the lab threshold',metrics['cls'],'CLS ≤0.1','Reserve layout space and inspect shifting content','P2','risk')
    for v in metrics.get('video',[]):
        if v.get('error'):add('video-error','functionality','Video element reported a playback error',v['error'],'Playback without an HTML media error','Inspect player/network events and repeat playback')
        if v.get('stall_count',0)>0:add('video-stall','performance','Playback stalled during this visit',f"{v['stall_count']} stalls, {v.get('stall_ms',0):.0f} ms completed stalls",'Continuous playback under the selected profile','Repeat with baseline network and compare QoE','P2','risk')
    return result

def evaluate_android(observation,logs='',measurements=None):
    measurements=measurements or {};result=[];oid=observation['id'];url=observation['url']
    def add(rule,pillar,title,observed,expected,recommendation,severity='P2',classification='defect'):
        item=dict(rule=rule,pillar=pillar,title=title,observed=str(observed),expected=expected,recommendation=recommendation,severity=severity,classification=classification,evidence_id=oid,url=url,verifier_status='CONFIRMED',source='deterministic',confidence=1.0,status='open',owner='')
        item['fingerprint']=fingerprint(item);result.append(item)
    for control in observation.get('controls',[]):
        if not control.get('labeled'):add('unlabeled-control','ux_ui','Interactive control has no accessible label',control.get('resource_id') or control['role'],'A meaningful accessible label','Add contentDescription or visible associated text')
        box=control.get('box',{});dpi=observation.get('viewport',{}).get('density_dpi') or 160
        if min(box.get('width',0),box.get('height',0))*160/dpi<48:add('small-touch-target','ux_ui','Touch target is smaller than 48 dp',box,'At least 48 dp in both dimensions','Increase the tappable bounds','P3','risk')
    launch=measurements.get('launch_ms')
    if isinstance(launch,(int,float)) and launch>5000:add('slow-launch','performance','Initial activity launch exceeded five seconds',f'{launch} ms','Launch-to-display at or below 5000 ms','Profile cold startup','P2','risk')
    for match in re.finditer(r'FATAL EXCEPTION:.*?\n.*?Process: ([^,]+).*?\n.*?([\w.]+(?:Exception|Error))(?:: ([^\n]+))?',logs,re.S):
        add('crash-'+match[2].split('.')[-1].lower(),'functionality','App crashed',match.group(0)[:2000],'No attributable fatal exception','Fix the first app stack frame','P1')
    for match in re.finditer(r'ANR in ([\w.:]+)([^\n]*)',logs):add('anr','functionality','App stopped responding',match.group(0),'Responsive main thread','Move blocking work off the main thread','P1')
    return result

def compare_runs(a,b):
    platform_a=a.get('platform') or a.get('mission',{}).get('platform') or 'web';platform_b=b.get('platform') or b.get('mission',{}).get('platform') or 'web'
    if platform_a=='android' or platform_b=='android':
        keys=('project_id','platform','target_id','goal','success_text','mode','pillars','provider','model','model_max','effort','max_steps','observe_seconds','url','allowed_domains')
        ma={**a.get('mission',{}),'platform':platform_a};mb={**b.get('mission',{}),'platform':platform_b}
        mismatch=[k for k in keys if ma.get(k)!=mb.get(k)]
        if a.get('target',{}).get('package')!=b.get('target',{}).get('package'):mismatch.append('package')
        for key in ('api','abi','renderer','display','density_dpi','rotation','locale'):
            if a.get('device',{}).get(key)!=b.get('device',{}).get(key):mismatch.append('device_'+key)
        if a.get('network_applied')!=b.get('network_applied'):mismatch.append('network_settings')
        fa={finding_identity(f):f for f in a.get('findings',[]) if f.get('verifier_status')!='REJECTED'};fb={finding_identity(f):f for f in b.get('findings',[]) if f.get('verifier_status')!='REJECTED'}
        compatible=not mismatch;complete=compatible and b.get('status')=='completed' and not b.get('evaluation_error') and all(v.get('status')=='evaluated' for v in b.get('coverage',{}).values())
        delta={k:(b.get('measurements',{}).get(k)-a.get('measurements',{}).get(k)) if isinstance(a.get('measurements',{}).get(k),(int,float)) and isinstance(b.get('measurements',{}).get(k),(int,float)) else None for k in ('launch_ms','jank_pct','pss_kb')}
        return {'compatible':compatible,'mismatches':mismatch,'build_changed':a.get('app',{}).get('sha256')!=b.get('app',{}).get('sha256'),'new':[fb[k] for k in fb.keys()-fa.keys()],'resolved':[fa[k] for k in fa.keys()-fb.keys()] if complete else [],'not_assessed':[fa[k] for k in fa.keys()-fb.keys()] if not complete else [],'identity_uncertain':[],'persisting':[fb[k] for k in fb.keys()&fa.keys()],'metric_delta':delta,'baseline':a['id'],'candidate':b['id']}
    keys=('project_id','browser','viewport','network','persona_id','egress_id','locale','mode','pillars','provider','model','model_max','effort','success_text','max_steps','observe_seconds','competitors')
    mismatch=[k for k in keys if a['mission'].get(k)!=b['mission'].get(k)]
    if a['mission'].get('goal')!=b['mission'].get('goal'):mismatch.append('goal')
    if normalized_url(a['mission'].get('url',''))!=normalized_url(b['mission'].get('url','')):mismatch.append('url')
    def network_settings(r):
        return {k:v for k,v in r.get('network_snapshot',{}).items() if k not in ('id','name','created_at','updated_at')}
    if network_settings(a)!=network_settings(b):mismatch.append('network_settings')
    fa={finding_identity(f):f for f in a.get('findings',[]) if f.get('verifier_status')!='REJECTED'}
    fb={finding_identity(f):f for f in b.get('findings',[]) if f.get('verifier_status')!='REJECTED'}
    am=(a.get('observations') or [{}])[-1].get('metrics',{});bm=(b.get('observations') or [{}])[-1].get('metrics',{})
    delta={k:(bm[k]-am[k]) if isinstance(am.get(k),(int,float)) and isinstance(bm.get(k),(int,float)) else None for k in ('lcp','cls','inp','ttfb_ms')}
    assessed=not mismatch and b.get('status') in (None,'completed') and not b.get('evaluation_error') and not b.get('policy_blocked_requests') and all(v.get('status')=='evaluated' for v in b.get('coverage',{}).values())
    missing=[fa[k] for k in fa.keys()-fb.keys()]
    added=[fb[k] for k in fb.keys()-fa.keys()]
    def legacy_ai(f):return f.get('source')=='ai' and not f.get('issue_key')
    uncertain=[f for f in missing+added if legacy_ai(f)]
    return {'compatible':not mismatch,'mismatches':mismatch,
            'new':[f for f in added if not legacy_ai(f)],
            'resolved':[f for f in missing if not legacy_ai(f)] if assessed else [],
            'not_assessed':[f for f in missing if not assessed or legacy_ai(f)],
            'identity_uncertain':uncertain,
            'persisting':[fb[k] for k in fb.keys()&fa.keys()],
            'metric_delta':delta,'baseline':a['id'],'candidate':b['id']}
