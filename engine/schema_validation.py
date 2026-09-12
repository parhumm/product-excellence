"""Offline Schema.org vocabulary checks; never fetch page-supplied contexts."""
import json,re
from functools import lru_cache
from pathlib import Path
@lru_cache(maxsize=1)
def vocabulary():
    path=Path(__file__).parent/'schemas/schemaorg.jsonld'
    if not path.exists():return {},{}
    graph=json.loads(path.read_text())['@graph'];types={};props={}
    def local(value):return value.rsplit('/',1)[-1].split(':')[-1]
    def refs(v):
        return [local(x['@id']) for x in (v if isinstance(v,list) else [v]) if isinstance(x,dict) and '@id'in x]
    for item in graph:
        id=local(item.get('@id',''));kind=item.get('@type',[]);kind=kind if isinstance(kind,list) else [kind]
        if any(local(k)=='Class' for k in kind):types[id]=refs(item.get('rdfs:subClassOf',[]))
        if any(local(k)=='Property' for k in kind):props[id]={'domains':refs(item.get('schema:domainIncludes',[])),'ranges':refs(item.get('schema:rangeIncludes',[]))}
    return types,props

def validate_schema(text):
    try:data=json.loads(text)
    except (ValueError,TypeError) as e:return [{'code':'json-syntax','path':'$','message':str(e)}]
    types,props=vocabulary();issues=[]
    def ancestors(t,seen=None):
        seen=set() if seen is None else seen
        if t in seen:return seen
        seen.add(t)
        for p in types.get(t,[]):ancestors(p,seen)
        return seen
    def walk(node,path='$',schema_context=False):
        if isinstance(node,list):
            for i,n in enumerate(node):walk(n,f'{path}[{i}]',schema_context)
        elif isinstance(node,dict):
            ctx=node.get('@context');schema_context=schema_context or ctx in ('https://schema.org','http://schema.org','https://schema.org/','http://schema.org/')
            if not schema_context and ctx:issues.append({'code':'context-unverified','path':path,'message':'Non-standard context is not resolved by this offline validator'})
            raw=node.get('@type',[]);ts=raw if isinstance(raw,list) else [raw];ts=[t.rsplit('/',1)[-1] for t in ts if isinstance(t,str)]
            if schema_context and types:
                for t in ts:
                    if t not in types:issues.append({'code':'unknown-type','path':path,'message':f'Unknown Schema.org type {t}'})
                lineage=set().union(*(ancestors(t) for t in ts)) if ts else set()
                for k,v in node.items():
                    if k.startswith('@'):continue
                    if k not in props:issues.append({'code':'unknown-property','path':path+'.'+k,'message':f'Unknown Schema.org property {k}'})
                    elif lineage and props[k]['domains'] and not lineage.intersection(props[k]['domains']):issues.append({'code':'property-domain','path':path+'.'+k,'message':f'{k} is not declared for the supplied types; review vocabulary/extension usage'})
            for k,v in node.items():
                if k!='@context':walk(v,path+'.'+k,schema_context)
    walk(data)
    return issues
