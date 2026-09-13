#!/usr/bin/env python3
import argparse,json,time,sys
import httpx,yaml
p=argparse.ArgumentParser(description='Product Excellence CLI')
p.add_argument('--url',default='http://127.0.0.1:8741')
sp=p.add_subparsers(dest='command',required=True)
sp.add_parser('health');sp.add_parser('missions')
sp.add_parser('models',help='List selectable AI models with their estimated prices')
r=sp.add_parser('run');r.add_argument('mission_id');r.add_argument('--wait',action='store_true');r.add_argument('--network')
k=sp.add_parser('continue',help='Carry on a finished run from the page it stopped on')
k.add_argument('run_id');k.add_argument('--ai-calls',type=int,default=0,help='Extra AI calls; 0 repeats the mission budget')
k.add_argument('--steps',type=int,default=0,help='Extra steps; 0 repeats the mission limit');k.add_argument('--wait',action='store_true')
i=sp.add_parser('import');i.add_argument('file')
e=sp.add_parser('export');e.add_argument('run_id');e.add_argument('--format',choices=['json','md'],default='md')
f=sp.add_parser('findings',help='Print findings as JSON');f.add_argument('--project',default='');f.add_argument('--run');f.add_argument('--grouped',action='store_true',help='One row per issue instead of one per run')
v=sp.add_parser('review',help='Set the status or owner of one finding');v.add_argument('run_id');v.add_argument('finding_id');v.add_argument('--status',choices=['open','accepted','resolved','dismissed']);v.add_argument('--owner')
d=sp.add_parser('compare',help='What changed between two runs');d.add_argument('baseline');d.add_argument('candidate')
args=p.parse_args();c=httpx.Client(base_url=args.url+'/api',headers={'X-PEX-Request':'1'},timeout=30)

def count(value):return '-' if value is None else format(value,',')

def input_tokens(call):
 """Fresh prompt tokens plus tokens written to the cache; None when nothing was reported."""
 parts=[call.get(k) for k in ('input_tokens','cache_write_5m_tokens','cache_write_1h_tokens')]
 known=[p for p in parts if p is not None]
 return sum(known) if known else None

def usage_report(run):
 """Model names, token use and the estimated cost of a finished run."""
 totals=run.get('ai_totals') or {}
 lines=[f"AI calls: {run.get('ai_calls',0)} | provider: {run.get('provider') or 'none'}"]
 for call in run.get('ai_usage') or []:
  purpose=call.get('purpose') or 'reasoning'
  if call.get('step') is not None:purpose+=f" {call['step']+1}"
  cost='n/a' if call.get('est_cost_usd') is None else f"~${call['est_cost_usd']:.4f}"
  lines.append(f"  {call.get('call')}. {purpose} | {call.get('model_reported') or call.get('model_requested') or 'unknown'}"
               f" | {count(input_tokens(call))} in | {count(call.get('cached_tokens'))} cached"
               f" | {count(call.get('output_tokens'))} out | {round((call.get('wall_ms') or 0)/1000,1)}s | {cost}")
 if totals.get('calls'):
  cost='n/a' if totals.get('est_cost_usd') is None else f"~${totals['est_cost_usd']:.4f}"
  lines.append(f"  Total: {', '.join(totals.get('models') or ['unknown'])} | {count(totals.get('input_tokens'))} in"
               f" | {count(totals.get('cached_tokens'))} cached | {count(totals.get('output_tokens'))} out | {cost}"
               +(' (partial)' if totals.get('cost_partial') else ''))
 if run.get('ai_usage'):
  lines.append('Input counts fresh prompt tokens plus tokens written to the prompt cache.')
  lines.append('Estimate at published API list prices. Runs use your Codex/Claude subscription; nothing is billed per call.')
 return '\n'.join(lines)

if args.command=='models':
 health=c.get('/health');health.raise_for_status()
 for provider,info in health.json()['ai'].items():
  print(f"{provider}: {'signed in' if info['logged_in'] else 'not available'}")
  for entry in info.get('models') or []:
   print(f"  {entry['value'] or '(CLI default)':<20} {entry['label']:<26} {entry.get('price_hint') or 'no published price'}")
 print('Estimate at published API list prices. Runs use your Codex/Claude subscription; nothing is billed per call.')
 sys.exit(0)
if args.command in ('health','missions'):r=c.get('/'+args.command)
elif args.command=='import':
 with open(args.file,'rb') as f:r=c.post('/import',files={'file':f})
elif args.command=='export':r=c.get(f'/runs/{args.run_id}/export',params={'format':args.format})
elif args.command=='findings':
 r=c.get('/findings',params={'project':args.project,'grouped':args.grouped});r.raise_for_status()
 print(json.dumps([f for f in r.json() if not args.run or f.get('run_id')==args.run],indent=2));sys.exit(0)
elif args.command=='continue':
 r=c.post(f'/runs/{args.run_id}/continue',json={'ai_calls':args.ai_calls,'steps':args.steps});r.raise_for_status()
 if args.wait:
  while r.json()['status'] in ('queued','running'):
   time.sleep(3);r=c.get('/runs/'+args.run_id);r.raise_for_status()
elif args.command=='compare':r=c.get('/compare',params={'baseline':args.baseline,'candidate':args.candidate})
elif args.command=='review':
 # The team server rejects a blind write: send back the revision the run carried when we read it.
 run=c.get('/runs/'+args.run_id);run.raise_for_status();revision=run.json().get('_revision')
 body={k:val for k,val in (('status',args.status),('owner',args.owner)) if val is not None}
 r=c.patch(f'/findings/{args.run_id}/{args.finding_id}',json=body,
           headers={'X-PEX-Revision':str(revision)} if revision is not None else {})
else:
 r=c.post('/runs',json={'mission_id':args.mission_id,'network':args.network});r.raise_for_status();id=r.json()['id']
 if args.wait:
  while r.json()['status'] in ('queued','running'):
   time.sleep(3);r=c.get('/runs/'+id);r.raise_for_status()
r.raise_for_status()
print(r.text)
if args.command in ('run','continue') and args.wait:
 run=r.json();print(usage_report(run))
 sys.exit(2 if run['status']!='completed' or run.get('gate')=='block' else 1 if run.get('gate')=='warn' else 0)
