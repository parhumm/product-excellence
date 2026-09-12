"""Offline prompt-size comparison over saved runs. Reads run.json only; no browser, no AI."""
import json,sys
from pathlib import Path
from engine.prompts import (compact_json,evidence_json,prompt_note,prompt_observation,
                            prompt_observations,prompt_actions,prompt_findings,prompt_finding)

RUNS=sys.argv[1:] or ['7703fe2989bd4753afd010133943651b','bdbe4b','b421c6']

def load(prefix):
    for folder in sorted(Path('data/artifacts').iterdir()):
        if folder.name.startswith(prefix):
            return folder.name,json.loads((folder/'run.json').read_text())
    raise SystemExit('no run for '+prefix)

def row(label,before,after):
    saved=100*(1-len(after)/len(before)) if before else 0
    return (label,len(before),len(after),round(saved,1))

for prefix in RUNS:
    id,r=load(prefix)
    m=r['mission'];obs=r['observations'];actions=r['actions']
    known=[f for f in r['findings'] if f.get('source')!='ai']
    rows=[]
    # An audit run plans no actions, so it has no action prompts to compare.
    for i,o in enumerate(obs[:len(actions)]):
        recent=actions[:i][-5:]
        before=compact_json({'mission':m['goal'],'success_text':m.get('success_text'),'state':o,
                             'recent_actions':recent,'remaining_steps':m['max_steps']-i})
        after=(prompt_note('action')+'\n'+compact_json(
            {'mission':m['goal'],'success_text':m.get('success_text'),'state':prompt_observation(o,'action'),
             'recent_actions':prompt_actions(recent),'remaining_steps':m['max_steps']-i}))
        rows.append(row(f'action step {i+1}',before,after))
    before=evidence_json({'goal':m['goal'],'observations':obs[-4:],'actions':actions,
                          'known_findings':known,'issue_catalog':[]})
    after=(prompt_note('review')+'\n'+evidence_json(
        {'goal':m['goal'],'observations':prompt_observations(obs[-4:],'review'),
         'actions':prompt_actions(actions),'known_findings':prompt_findings(known),'issue_catalog':[]}))
    rows.append(row('review',before,after))
    for f in [f for f in r['findings'] if f.get('source')=='ai'][:2]:
        o=next((o for o in obs if o['id']==f.get('evidence_id')),None)
        if not o:continue
        before=compact_json({'finding':f,'observation':o})
        after=prompt_note('verify')+'\n'+compact_json({'finding':prompt_finding(f),
                                                       'observation':prompt_observation(o,'verify')})
        rows.append(row('verify · '+(f.get('rule') or f.get('issue_key') or f['title'])[:28],before,after))
    total_before=sum(x[1] for x in rows);total_after=sum(x[2] for x in rows)
    print(f"\n{id[:6]}… {m['name']} · {m.get('provider')}/{m.get('model') or 'default'}/{m.get('effort')} "
          f"· {len(obs)} observations, {len(actions)} actions")
    for label,b,a,saved in rows:
        print(f'  {label:<34} {b:>8,} -> {a:>8,} chars  -{saved:>5.1f}%')
    print(f"  {'TOTAL prompt characters':<34} {total_before:>8,} -> {total_after:>8,} chars  "
          f"-{100*(1-total_after/total_before):>5.1f}%")
