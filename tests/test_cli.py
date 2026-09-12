"""The command line subcommands the .claude/skills call, run against a test app.

cli.py is a script: it parses sys.argv and builds its own httpx client at import
time. Both are replaced here, so the real dispatch code runs offline.
"""
import json,pathlib,sys
import httpx,pytest
from engine import store
from tests.test_phase1 import client,mission  # noqa: F401  (pytest fixtures)

CLI=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'cli.py'

class ApiPrefix:
    """cli.py asks for /findings; the test client serves /api/findings."""
    def __init__(self,c):self.c=c
    def __getattr__(self,name):
        method=getattr(self.c,name)
        return lambda path,**kw:method('/api'+path,**kw)

def cli(client,monkeypatch,capsys,*argv):
    monkeypatch.setattr(sys,'argv',['cli.py',*argv])
    monkeypatch.setattr(httpx,'Client',lambda **kw:ApiPrefix(client))
    code=0
    try:exec(compile(CLI.read_text(),str(CLI),'exec'),{'__name__':'__main__'})
    except SystemExit as e:code=e.code or 0
    return capsys.readouterr().out,code

def run_with_finding(m,run_id,**finding):
    return store.save('run',{'id':run_id,'mission':m,'mission_id':m['id'],'status':'completed','gate':'warn',
        'coverage':{p:{'status':'evaluated'} for p in m['pillars']},'observations':[{'metrics':{}}],
        'findings':[{'id':run_id+'-f','run_id':run_id,'evidence_id':'step-000','fingerprint':'shared','pillar':'functionality',
                     'title':'Broken step','severity':'P2','classification':'defect','source':'deterministic',
                     'verifier_status':'CONFIRMED','status':'open','owner':'',**finding}]})

def test_findings_lists_and_filters_by_run(client,monkeypatch,capsys):
    m=mission(client);run_with_finding(m,'run-one');run_with_finding(m,'run-two')
    out,code=cli(client,monkeypatch,capsys,'findings')
    assert code==0 and len(json.loads(out))==2
    out,_=cli(client,monkeypatch,capsys,'findings','--run','run-two')
    listed=json.loads(out);assert [f['run_id'] for f in listed]==['run-two']
    out,_=cli(client,monkeypatch,capsys,'findings','--grouped')
    assert len(json.loads(out))==1,'one issue seen twice is one grouped row'

def test_review_sets_status_and_owner(client,monkeypatch,capsys):
    m=mission(client);run_with_finding(m,'run-three')
    out,code=cli(client,monkeypatch,capsys,'review','run-three','run-three-f','--status','accepted','--owner','QA')
    assert code==0 and json.loads(out)['ok']
    saved=store.get('run','run-three')['findings'][0]
    assert saved['status']=='accepted' and saved['owner']=='QA'

def test_review_keeps_the_status_when_only_the_owner_changes(client,monkeypatch,capsys):
    m=mission(client);run_with_finding(m,'run-four',status='accepted')
    cli(client,monkeypatch,capsys,'review','run-four','run-four-f','--owner','Web team')
    saved=store.get('run','run-four')['findings'][0]
    assert saved['owner']=='Web team' and saved['status']=='accepted'

def test_compare_reports_what_changed(client,monkeypatch,capsys):
    m=mission(client)
    run_with_finding(m,'base');run_with_finding(m,'candidate',fingerprint='new-one',id='candidate-f')
    out,code=cli(client,monkeypatch,capsys,'compare','base','candidate')
    result=json.loads(out)
    assert code==0 and result['compatible']
    assert [f['id'] for f in result['new']]==['candidate-f']
