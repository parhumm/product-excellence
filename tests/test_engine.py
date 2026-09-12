import pytest
from engine.policy import PASSWORD_PLACEHOLDER,allowed_url,allowed_hosts,own_hosts,action_allowed,mutation_allowed,redact,safe_url
from engine.contracts import Mission,NetworkProfile
from engine.runner import describe
from engine.evaluate import evaluate,compare_runs
M={'url':'https://www.example.com','allowed_domains':['example.com']}
def test_domain_boundary():
 assert allowed_url('https://example.com/a',M)
 for u in ['https://example.com.evil.test/a','javascript:alert(1)','http://127.0.0.1:8741/api/state','https://x:secret@example.com']:assert not allowed_url(u,M)
 # A site redirects between its bare and its www host, so listing either allows both.
 bare={'url':'https://example.org','allowed_domains':['example.org']}
 assert own_hosts(bare)=={'example.org','www.example.org'}
 assert allowed_url('https://www.example.org/m/1',bare)
 assert not allowed_url('https://evil.example.org.test/',bare)
def test_local_fixture_only():
 m={'url':'http://127.0.0.1:8741/demo','allowed_domains':[]}
 assert allowed_url('http://127.0.0.1:8741/demo?page=movie',m)
 assert not allowed_url('http://127.0.0.1:8741/api/state',m)
 assert not allowed_url('http://127.0.0.1:8742/demo',m)
def test_payment_and_secret_policy():
 for text in ['Pay now','Delete account','پرداخت','خرید اشتراک']:assert not action_allowed({'type':'click'},M,{'text':text})[0]
 assert not action_allowed({'type':'press','value':'Enter'},M)[0]
 assert not action_allowed({'type':'press','value':'Space'},M)[0]
 assert action_allowed({'type':'press','value':'Enter'},M,{'input_type':'search'})[0]
 assert not action_allowed({'type':'press','value':'Enter'},M,{'input_type':'password'})[0]
 assert not action_allowed({'type':'press','value':'Space'},M,{'input_type':'search'})[0]
 assert not action_allowed({'type':'type'},M,{'input_type':'password'})[0]
 assert action_allowed({'type':'click'},M,{'text':'Search movies'})[0]
def test_password_scrubbed_from_page_captures():
    from engine.policy import scrub, PASSWORD_PLACEHOLDER
    html = '<input type="password" value="s3cret"><p>s3cret</p>'
    assert scrub(html, 's3cret') == f'<input type="password" value="{PASSWORD_PLACEHOLDER}"><p>{PASSWORD_PLACEHOLDER}</p>'
    # Without stored credentials every capture is kept exactly as the page served it.
    assert scrub(html, '') == html
    secret = 'quoted"\\password'
    evidence = {'text': secret, 'console': [{'message': 'Error: '+secret}],
                'metrics': {'input_tokens': 12, 'cached_tokens': 0, 'missing': None, 'ok': False}}
    clean = scrub(evidence, secret)
    assert clean['text'] == PASSWORD_PLACEHOLDER
    assert clean['console'][0]['message'] == 'Error: '+PASSWORD_PLACEHOLDER
    assert clean['metrics'] == evidence['metrics']
    assert evidence['text'] == secret  # Do not mutate the caller's data.


def test_sign_in_policy():
 signed={**M,'login_identifier':'test-user@example.invalid'}
 password={'input_type':'password','text':''}
 assert action_allowed({'type':'type','value':PASSWORD_PLACEHOLDER},signed,password)[0]
 # The real secret must never travel through the model, and the placeholder must not
 # land in a plain-text field where a screenshot would show it.
 assert not action_allowed({'type':'type','value':'test12345678'},signed,password)[0]
 assert not action_allowed({'type':'type','value':PASSWORD_PLACEHOLDER},signed,{'input_type':'tel','text':''})[0]
 assert not action_allowed({'type':'type','value':PASSWORD_PLACEHOLDER},M,password)[0]
 assert action_allowed({'type':'type','value':'test-user@example.invalid'},signed,{'input_type':'tel','text':'Mobile'})[0]
 assert mutation_allowed('GET','https://www.google-analytics.com/g/collect',M)
 assert mutation_allowed('POST','https://example.com/api/auth/lookup',signed)
 assert not mutation_allowed('POST','https://example.com/api/auth/lookup',M)
 assert not mutation_allowed('POST','https://www.google-analytics.com/g/collect',signed)
def test_open_url_from_either_field_and_precise_refusal():
 # A model that puts the URL in target must not be refused as an off-domain navigation.
 assert action_allowed({'type':'open','target':'https://example.com/x','value':''},M)[0]
 assert action_allowed({'type':'open','target':'','value':'https://example.com/x'},M)[0]
 ok,reason=action_allowed({'type':'open','target':'','value':'https://evil.example/'},M)
 assert not ok and 'evil.example' in reason and 'allowed hosts' in reason
 ok,reason=action_allowed({'type':'open','target':'','value':''},M)
 assert not ok and 'value' in reason
def test_action_descriptions():
 card={'id':'pex-24','text':'رایگان\nمسیر شغلی','href':'https://example.com/books/the-squiggly-career'}
 assert describe({'type':'click'},card)=='Click «مسیر شغلی» → /books/the-squiggly-career'
 opened=describe({'type':'open','value':'https://example.com/x?token=abc'})
 assert opened.startswith('Open https://example.com/x?token=') and 'abc' not in opened
 assert describe({'type':'scroll','value':'down'})=='Scroll down'
 assert describe({'type':'click'},None)=='Click'
 assert describe({'type':'invalid'})=='Malformed AI response'
def test_redaction():
 assert redact({'password':'abc','nested':{'authorization':'Bearer xxx'}})['password']=='[REDACTED]'
 assert 'abc' not in safe_url('https://a.com/?token=abc')
 # Token counts are measurements, not credentials, and a run record must keep them.
 usage=redact({'input_tokens':21930,'cached_tokens':0,'output_tokens':None,'session_key':'abc'})
 assert (usage['input_tokens'],usage['cached_tokens'],usage['output_tokens'])==(21930,0,None)
 assert usage['session_key']=='[REDACTED]'
def test_limits():
 with pytest.raises(ValueError):Mission(name='X',url='file:///etc/passwd',goal='Test this')
 with pytest.raises(ValueError):Mission(name='X',url='https://example.com',goal='Test this',max_steps=1000)
 with pytest.raises(ValueError):NetworkProfile(name='X',loss_pct=120)
def test_known_findings_and_no_invented_metrics():
 o={'id':'step-000','url':'https://example.com','title':'','metadata':{'description':'','robots':'noindex','jsonld':['{invalid}'],'overflow':True},'metrics':{'lcp':None,'cls':0,'inp':None,'video':[]}}
 fs=evaluate(o,[{'status':500,'url':'https://example.com/api'}],[{'kind':'pageerror','message':'boom'}],{})
 rules={f['rule'] for f in fs};assert {'missing-title','schema-json-syntax-0-$','overflow','noindex','js-boom'}<=rules
 assert 'lcp' not in rules and all(f['evidence_id']=='step-000' for f in fs)
def test_comparison_flags_different_conditions():
 a={'id':'a','mission':{'browser':'chromium','goal':'search'},'findings':[{'fingerprint':'f','title':'F'}],'observations':[]}
 b={'id':'b','mission':{'browser':'webkit','goal':'search'},'findings':[],'observations':[]}
 c=compare_runs(a,b);assert not c['compatible'] and c['mismatches']==['browser']
 assert not c['resolved'] and len(c['not_assessed'])==1 and c['metric_delta']['lcp'] is None

def test_fingerprint_stable_key_and_page_identity():
 from engine.evaluate import fingerprint,finding_identity
 f={'source':'ai','pillar':'seo_aeo','title':'Page asks search engines not to index it','issue_key':'noindex','url':'https://EXAMPLE.com:443/movie?id=4&utm_source=test#top'}
 same={**f,'title':'Page Explicitly Marked as Non-Indexable by Search Engines','url':'https://example.com/movie?id=4'}
 assert fingerprint(f)==fingerprint(same)
 assert fingerprint(f)!=fingerprint({**same,'url':'https://other.example/movie?id=4'})
 assert fingerprint(f)!=fingerprint({**same,'url':'https://example.com/movie?id=5'})
 assert fingerprint(f)==fingerprint({**same,'source':'deterministic','rule':'noindex'})
 legacy={**same,'fingerprint':'old'};legacy.pop('issue_key')
 assert finding_identity(legacy)==fingerprint({**same,'issue_key':'legacy-old'})

def test_ai_schema_requires_stable_issue_key():
 from engine.ai import EVAL_SCHEMA
 from jsonschema import validate,ValidationError
 f=dict(title='Different title',pillar='seo_aeo',classification='risk',severity='P2',observed='noindex',expected='Indexable',recommendation='Check robots',evidence_id='step-000')
 summary={'headline':'One page is not indexable','summary':'The homepage asks search engines not to index it.','next_steps':['Confirm the robots directive']}
 with pytest.raises(ValidationError):validate({'benchmark':[],'findings':[f],'executive_summary':summary},EVAL_SCHEMA)
 validate({'benchmark':[],'findings':[{**f,'issue_key':'noindex'}],'executive_summary':summary},EVAL_SCHEMA)
 with pytest.raises(ValidationError):validate({'benchmark':[],'findings':[{**f,'issue_key':'A prose title!'}],'executive_summary':summary},EVAL_SCHEMA)
 # The narrative is part of every review answer, so a run always has a reader-level report.
 with pytest.raises(ValidationError):validate({'benchmark':[],'findings':[{**f,'issue_key':'noindex'}]},EVAL_SCHEMA)

@pytest.mark.parametrize('change',[{'evaluation_error':'budget exhausted'},{'coverage':{'cro':{'status':'not_evaluated'}}},{'policy_blocked_requests':1},{'network_snapshot':{'latency_ms':300}}])
def test_incomplete_or_changed_conditions_do_not_resolve(change):
 a={'id':'a','mission':{},'status':'completed','findings':[{'fingerprint':'one'}]}
 b={'id':'b','mission':{},'status':'completed','findings':[],**change}
 result=compare_runs(a,b)
 assert not result['resolved'] and len(result['not_assessed'])==1

def test_title_changes_persist_and_legacy_rules_still_compare():
 from engine.evaluate import fingerprint
 f={'pillar':'seo_aeo','rule':'noindex','url':'https://example.com','title':'No index','fingerprint':'old-format'}
 a={'id':'a','mission':{},'status':'completed','findings':[f]}
 g={**f,'title':'New wording','fingerprint':fingerprint(f)}
 b={'id':'b','mission':{},'status':'completed','findings':[g]}
 result=compare_runs(a,b)
 assert len(result['persisting'])==1 and not result['new'] and not result['resolved']

def test_historical_ai_wording_is_unknown_not_new_or_resolved():
 a={'id':'a','mission':{},'status':'completed','findings':[{'source':'ai','pillar':'seo_aeo','title':'Old prose','url':'https://example.com','fingerprint':'old'}]}
 b={'id':'b','mission':{},'status':'completed','findings':[{'source':'ai','pillar':'seo_aeo','title':'Different prose','url':'https://example.com','fingerprint':'other'}]}
 result=compare_runs(a,b)
 assert not result['new'] and not result['resolved']
 assert len(result['identity_uncertain'])==2 and len(result['not_assessed'])==1

def test_javascript_error_keeps_debugging_detail_and_stable_rule():
 event={'kind':'pageerror','name':'TypeError','message':'boom','step':2,'page_url':'https://example.com/movie',
        'source':'render (https://example.com/app.js:12:5)',
        'stack':'TypeError: boom\n    at render (https://example.com/app.js:12:5)\n    at start (https://example.com/app.js:40:1)'}
 o={'id':'step-000','url':'https://example.com','title':'T','metadata':{'description':'d','canonical':'https://example.com','robots':''},'metrics':{}}
 f=next(x for x in evaluate(o,[],[event],{}) if x['rule']=='js-boom')
 for expected in ['TypeError: boom','Source: render (https://example.com/app.js:12:5)','Page: https://example.com/movie','Observation step: 3','at start (https://example.com/app.js:40:1)']:
  assert expected in f['observed']

def run_fixture(**kw):
 base={'id':'r','mission':{'pillars':['functionality','cro','ux_ui']},'status':'completed','gate':'warn',
       'coverage':{'functionality':{'status':'evaluated'},'cro':{'status':'not_evaluated'},'ux_ui':{'status':'evaluated'}},
       'findings':[{'id':'a','pillar':'functionality','severity':'P1','verifier_status':'CONFIRMED','status':'open','owner':'QA','title':'Search returns nothing','evidence_id':'step-000'},
                   {'id':'b','pillar':'functionality','severity':'P2','verifier_status':'CONFIRMED','status':'open','owner':'QA','title':'Slow filter','evidence_id':'step-000'},
                   {'id':'c','pillar':'ux_ui','severity':'P2','verifier_status':'UNCONFIRMED','status':'open','owner':'QA','title':'Contrast is low','evidence_id':'step-001'}]}
 return {**base,**kw}

def test_scores_deduct_by_severity_and_never_invent_an_unevaluated_pillar():
 from engine.outcomes import scores
 s=scores(run_fixture())
 assert s['functionality']['score']==45 and s['ux_ui']['score']==92
 assert s['cro']['score'] is None and 'AI review' in s['cro']['reason']
 assert s['overall']=={'score':68,'scored':2,'of':3}
 assert [d['points'] for d in s['functionality']['deductions']]==[40,15]
 # One recurring issue costs its points once, so a deeper crawl of the same site scores no lower.
 repeated=run_fixture(mission={'pillars':['performance']},coverage={'performance':{'status':'evaluated'}},
   findings=[{'id':str(i),'pillar':'performance','rule':'lcp','severity':'P2','verifier_status':'CONFIRMED',
              'status':'open','title':'Slow largest contentful paint in this visit'} for i in range(5)])
 hit=scores(repeated)['performance']
 assert hit['score']==85 and len(hit['deductions'])==1 and hit['deductions'][0]['pages']==5
 blocked=scores(run_fixture(mission_outcome='blocked'))
 assert blocked['functionality']['score']==15
 dismissed=scores(run_fixture(findings=[{**f,'status':'dismissed'} for f in run_fixture()['findings']]))
 assert dismissed['functionality']['score']==100 and dismissed['overall']['score']==100
 unevaluated=scores(run_fixture(coverage={},status='failed'))
 assert unevaluated['overall']=={'score':None,'scored':0,'of':3}

def test_executive_summary_states_facts_and_marks_its_source():
 from engine.outcomes import executive_summary
 deterministic=executive_summary(run_fixture())
 assert deterministic['source'].startswith('Deterministic')
 # The headline is a sentence a reader understands, not the status and gate codes.
 assert deterministic['headline']=='The run finished' and 'Release check: review before release.' in deterministic['summary']
 assert executive_summary(run_fixture(mission_outcome='blocked'))['headline']=='The journey did not reach its goal'
 assert '1 P1, 2 P2' in deterministic['summary'] and 'Overall score 68' in deterministic['summary']
 assert deterministic['coverage_gaps']==['cro'] and [f['id'] for f in deterministic['top_findings']]==['a','b','c']
 assert any('cro' in step for step in deterministic['next_steps'])
 narrated=executive_summary(run_fixture(ai_summary={'headline':'Search is broken','summary':'Visitors cannot search.','next_steps':['Fix search']}))
 assert narrated['headline']=='Search is broken' and narrated['summary']=='Visitors cannot search.'
 assert narrated['next_steps']==['Fix search'] and narrated['source'].startswith('AI narrative')
 # Even with a narrative, the deterministic facts stay attached to the report.
 assert 'Overall score 68 of 100 across 2 of 3 selected pillars.' in narrated['facts']

B={'url':'https://www.example.com','allowed_domains':['example.com'],'mode':'benchmark',
   'competitors':['https://example.org','https://example.net']}
def test_benchmark_opens_competitors_but_owns_only_its_site():
 # Both the bare and the www host, because a competitor redirects between them.
 assert allowed_hosts(B)>={'www.example.com','example.com','example.org','www.example.org','example.net','www.example.net'}
 assert own_hosts(B)=={'www.example.com','example.com'}
 assert allowed_url('https://example.org/plans',B) and allowed_url('https://www.example.net/',B)
 assert not allowed_url('https://example.edu/',B)
 assert action_allowed({'type':'open','value':'https://example.org/'},B)[0]
 assert not action_allowed({'type':'open','value':'https://example.edu/'},B)[0]
def test_benchmark_mission_needs_competitor_urls():
 base={'name':'Benchmark','url':'https://www.example.com','goal':'Compare the pricing pages','mode':'benchmark','provider':'auto'}
 assert Mission(**base,competitors=['https://example.org']).competitors==['https://example.org']
 with pytest.raises(ValueError):Mission(**base)
 with pytest.raises(ValueError):Mission(**base,competitors=['example.org'])
