#!/usr/bin/env python3
"""Dry-run by default. Import one stopped local workspace into an empty hub workspace."""
import argparse, copy, fcntl, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import store, hub, targets

def checksum(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def comparable(value):return {k:v for k,v in value.items() if k!='_revision'}

def prepared(kind,value,target,origin,target_map):
    r=copy.deepcopy(store.clean(value))
    if kind!='project':r['project_id']=target
    for key in ('mission','snapshot'):
        if isinstance(r.get(key),dict):
            r[key]['project_id']=target;r[key].pop('login_password',None)
            if r[key].get('target_id') in target_map:r[key]['target_id']=target_map[r[key]['target_id']]
    if r.get('target_id') in target_map:r['target_id']=target_map[r['target_id']]
    if kind=='target':r['id']=target_map[r['id']]
    if isinstance(r.get('target'),dict):
        r['target']['project_id']=target
        if r['target'].get('id') in target_map:r['target']['id']=target_map[r['target']['id']]
    r.pop('login_password',None)
    if kind in ('run','schedule'):r['origin']=origin
    if kind=='run' and r.get('status') in ('queued','running'):
        r.update(status='interrupted',error='Imported unfinished history. Replay to continue.')
    if kind=='schedule':r['enabled']=False
    return r

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('target');parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    with (store.DATA/'runtime.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Stop the local app before importing workspace data')
        store.init();hub.load();hub.login_for(args.target)
        source=store.get('project',args.source,local=True)
        if not source:raise ValueError('Local workspace not found')
        target=hub.get('project',args.target,args.target)
        if not target:raise ValueError('Hub workspace not found')
        path=store.DATA/'imports'/f'{args.source}-{args.target}.json'
        manifest=json.loads(path.read_text()) if path.exists() else {'url':hub.CONFIG['url'],'source':args.source,'target':args.target,'origin':hub.origin(),'records':{},'target_map':{}}
        if (manifest['url'],manifest['source'],manifest['target'])!=(hub.CONFIG['url'],args.source,args.target):raise ValueError('Import manifest belongs to another source or server')
        source_records={kind:[r for r in store.all_records(kind,local=True) if store.workspace_of(kind,r)==args.source] for kind in ('target','mission','mission_version','run','schedule')}
        source_default=targets.default_id(args.source);destination_default=targets.default_id(args.target)
        remote_targets={r['id']:r for r in hub.all_records('target',args.target)}
        target_map=manifest.setdefault('target_map',{})
        for r in source_records['target']:
            if r.get('visibility')=='local':continue
            if r['id']==source_default:target_map[r['id']]=destination_default;continue
            mapped=target_map.get(r['id'],r['id'])
            if mapped in remote_targets and comparable(remote_targets[mapped])!=comparable(prepared('target',r,args.target,manifest['origin'],{r['id']:mapped})):
                mapped='import-'+hashlib.sha256((args.source+'|'+r['id']).encode()).hexdigest()[:24]
                if mapped in remote_targets:raise ValueError('Deterministic target ID collides on destination: '+r['id'])
            target_map[r['id']]=mapped
        private_targets={r['id'] for r in source_records['target'] if r.get('visibility')=='local'}
        private_missions={r['id'] for r in source_records['mission'] if r.get('visibility')=='local' or r.get('target_id') in private_targets}
        excluded={kind:0 for kind in source_records};data=[];original=[];missing=[]
        for kind in ('target','mission','mission_version','run','schedule'):
            for r in source_records[kind]:
                ws=store.workspace_of(kind,r)
                if not ws:raise ValueError('Repair unresolved workspace ownership before import: '+r['id'])
                snapshot=r.get('mission') or r.get('snapshot') or {}
                private=r.get('visibility')=='local' or (kind!='target' and (r.get('mission_id') in private_missions or snapshot.get('target_id') in private_targets))
                if private:excluded[kind]+=1;continue
                original.append({'kind':kind,'record':r})
                if kind=='target' and r['id']==source_default:continue
                value=prepared(kind,r,args.target,manifest['origin'],target_map)
                if kind=='run':
                    artifacts={}
                    value=hub.shareable(value)
                    for name in hub.evidence_names(value,store.ARTIFACTS/r['id']):
                        file=hub.file_path(store.ARTIFACTS,r['id'],name)
                        if not file.is_file():missing.append(str(file));continue
                        artifacts[name]=hub.digest(file)
                    value['_artifacts']=artifacts
                data.append((kind,value))
        if missing:raise ValueError('Missing source evidence: '+', '.join(missing))
        # Existing teammates' records must not be overwritten, including before an initial apply.
        for kind in ('target','mission','mission_version','run','schedule'):
            existing=hub.all_records(kind,args.target)
            if not path.exists() and kind!='target' and existing:raise ValueError('Use an empty unseeded target workspace')
            if kind!='target' and any(r['id'] not in manifest['records'] for r in existing):raise ValueError('Target contains records outside this import')
        for kind,r in data:
            entry=manifest['records'].get(r['id'])
            if entry and entry['source_hash']!=checksum(r):raise ValueError('Source changed since import: '+r['id'])
        print(json.dumps({'mode':'apply' if args.apply else 'dry-run','records':{kind:sum(k==kind for k,r in data) for kind in ('target','mission','mission_version','run','schedule')},'excluded_local':excluded,'target_map':target_map,'artifacts':sum(len(r.get('_artifacts',{})) for k,r in data),'schedules':'paused','local_resources':'APKs, passwords, personas, custom networks and proxy credentials remain on the source machine'},indent=2))
        if not args.apply:return
        if not path.exists():
            hub.atomic(path.with_suffix('.backup.json'),{'source_project':source,'source_records':original,'empty_target_project':target})
            # Predeclare IDs before the first request so a lost response can be reconciled.
            manifest['records']={r['id']:{'kind':k,'source_hash':checksum(r),'staged':None,'saved':None} for k,r in data}
            hub.atomic(path,manifest)
        for kind,r in data:
            entry=manifest['records'][r['id']]
            current=hub.get(kind,r['id'],args.target)
            if entry['saved']:
                if not current or current['_revision']!=entry['revision'] or checksum(comparable(current))!=entry['saved']:raise ValueError('Target was edited after import: '+r['id'])
                # Uploaded evidence is immutable on the server, so verify each run once instead of on every resume.
                if kind=='run' and not entry.get('verified'):
                    verify_artifacts(r,args.target);entry['verified']=True;hub.atomic(path,manifest)
                continue
            if kind=='run':
                staged={**r,'status':'importing','_artifacts':{}}
                entry['staged']=checksum(staged);hub.atomic(path,manifest)
                if current:
                    if checksum(comparable(current))==checksum(r):
                        verify_artifacts(r,args.target)
                        entry.update(saved=checksum(comparable(current)),revision=current['_revision'],verified=True);hub.atomic(path,manifest);continue
                    if checksum(comparable(current))!=entry['staged']:raise ValueError('Conflicting staged run: '+r['id'])
                else:current=hub.save(kind,staged,preserve_times=True)
                for name in r.get('_artifacts',{}):hub.put_artifact(r['id'],hub.file_path(store.ARTIFACTS,r['id'],name),args.target)
                saved=hub.save(kind,r|{'_revision':current['_revision']},preserve_times=True)
                verify_artifacts(r,args.target);entry['verified']=True
            elif current:
                if checksum(comparable(current))!=checksum(r):raise ValueError('Conflicting target record: '+r['id'])
                saved=current
            else:saved=hub.save(kind,r,preserve_times=True)
            entry.update(saved=checksum(comparable(saved)),revision=saved['_revision']);hub.atomic(path,manifest)
        manifest['complete']=True;hub.atomic(path,manifest)
        print('Import verified. Source data was retained. Enable schedules only after checking local resources.')

def verify_artifacts(run,workspace):
    login=hub.login_for(workspace)
    for name,want in run.get('_artifacts',{}).items():
        h=hashlib.sha256();size=0
        with hub.client().stream('GET',hub.CONFIG['url']+f'/hub/artifacts/{run["id"]}/{name}',auth=(login['username'],login['password']),headers={'X-PEX-Console':hub.VERSION}) as response:
            if response.status_code!=200:raise ValueError('Imported artifact is unavailable: '+name)
            for chunk in response.iter_bytes():size+=len(chunk);h.update(chunk)
        if {'size':size,'sha256':h.hexdigest()}!=want:raise ValueError('Imported artifact checksum differs: '+name)

if __name__=='__main__':
    try:main()
    except (ValueError,hub.HubError) as e:print('Import incomplete: '+str(e),file=sys.stderr);sys.exit(1)
    finally:hub.close()
