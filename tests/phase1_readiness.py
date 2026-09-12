"""Real browser acceptance for Phase 1 fixes; uses Claude subscription quota."""
import json,time
from pathlib import Path
import httpx
from engine import pricing


def main():
    c=httpx.Client(base_url='http://127.0.0.1:8741/api',headers={'X-PEX-Request':'1'},timeout=30,trust_env=False)
    def request(method,path,**kw):
        response=c.request(method,path,**kw);response.raise_for_status();return response.json()
    def queue(name,**kw):
        m=request('POST','/missions',json={'name':'Phase 1 readiness · '+name,'url':'http://127.0.0.1:8741/demo?bug=true','goal':'Audit the fixture for usability and functional defects.','mode':'audit','provider':'none','pillars':['functionality','seo_aeo','ux_ui','performance'],'locale':'en-US','max_seconds':180,**kw})
        return request('POST','/runs',json={'mission_id':m['id']})['id']
    def wait(id):
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            r=request('GET','/runs/'+id)
            if r['status'] not in ('queued','running'):
                assert r['status']=='completed',(id,r.get('error'))
                assert r.get('video') and r.get('trace') and r.get('duration_seconds') is not None,r
                return r
            time.sleep(2)
        raise AssertionError('Timed out: '+id)
    records=[]
    first=wait(queue('natural P2 auto-replay',auto_replay=True))
    for _ in range(20):
        first=request('GET','/runs/'+first['id'])
        if first.get('automatic_replay_id'):break
        time.sleep(.5)
    child=wait(first['automatic_replay_id'])
    assert child['replay_of']==first['id'] and not child.get('automatic_replay_id')
    assert any(f['severity']=='P2' and f.get('reproduced') for f in child['findings'])
    comparison=request('GET','/compare',params={'baseline':first['id'],'candidate':child['id']})
    assert comparison['compatible'] and comparison['persisting']
    assert child['network_snapshot']==first['network_snapshot']
    records.extend([first,child]);print('Natural P2 queued one compatible replay with reproduced findings',flush=True)
    for browser in ('firefox','webkit'):
        r=wait(queue(browser,browser=browser));records.append(r)
        assert {'missing-title','overflow'} <= {f.get('rule') for f in r['findings']}
        print(browser,'fixture and artifacts passed',flush=True)
    first=wait(queue('Claude stable keys',provider='claude',model='claude-sonnet-5',effort='low',ai_budget=3,max_seconds=600,pillars=['functionality','cro','seo_aeo','ux_ui','performance']))
    assert first.get('ai_evaluation_completed') and not first.get('evaluation_error'),first.get('evaluation_error')
    assert any(f.get('issue_key') for f in first['findings'] if f['source']=='ai')
    child=wait(request('POST','/runs/'+first['id']+'/replay')['id'])
    assert child.get('ai_evaluation_completed') and not child.get('evaluation_error'),child.get('evaluation_error')
    comparison=request('GET','/compare',params={'baseline':first['id'],'candidate':child['id']})
    assert comparison['compatible']
    records.extend([first,child])
    print('Claude schema and replay passed; AI persisting:',[(f.get('issue_key'),f['title']) for f in comparison['persisting'] if f['source']=='ai'],flush=True)
    for r in records:
        assert c.get('/runs/'+r['id']+'/export?format=json').json()['id']==r['id']
        report=c.get('/runs/'+r['id']+'/export').text
        assert 'Screenshot: /api/runs/' in report
    Path('data/phase1-readiness-results.json').write_text(json.dumps({'runs':records,'ai_comparison':comparison},ensure_ascii=False,indent=2))
    print('PASS',[(r['id'],r['mission']['name'],r['ai_calls']) for r in records],flush=True)
    for r in records:
        print(r['mission']['name'],'·',r['id'],flush=True)
        print(pricing.report(r,indent='  '),flush=True)

if __name__=='__main__':main()
