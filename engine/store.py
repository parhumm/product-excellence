import os, uuid, logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, Column, String, JSON, Integer, select, inspect, text, update, delete as sql_delete
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('PEX_DATA', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
ARTIFACTS = DATA / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql+psycopg://localhost:55439/product_excellence')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if DATABASE_URL.startswith('sqlite') else {}))
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class Record(Base):
    __tablename__ = 'records'
    id = Column(String, primary_key=True)
    kind = Column(String, index=True, nullable=False)
    payload = Column(JSON, nullable=False)
    workspace = Column(String, nullable=False, server_default='')
    revision = Column(Integer, nullable=False, server_default='1')

class Conflict(ValueError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def workspace_of(kind, value):
    if kind == 'project': return value.get('id', '')
    return value.get('project_id') or (value.get('mission') or {}).get('project_id') or (value.get('snapshot') or {}).get('project_id', '')

def clean(value):
    if isinstance(value, dict): return {k:clean(v) for k,v in value.items() if k not in ('_revision','_artifacts')}
    if isinstance(value, list): return [clean(v) for v in value]
    return value

def init():
    with engine.begin() as conn:
        if engine.dialect.name=='sqlite' and not conn.connection.driver_connection.in_transaction:conn.exec_driver_sql('BEGIN IMMEDIATE')
        if inspect(conn).has_table('records'):
            names={c['name'] for c in inspect(conn).get_columns('records')}
            if not {'workspace','revision'}<=names:
                from .hub import atomic
                backup=[dict(r) for r in conn.execute(text('SELECT id, kind, payload FROM records')).mappings()]
                atomic(DATA/'backups'/('records-before-hub-'+uuid.uuid4().hex+'.json'),backup)
            if 'workspace' not in names: conn.execute(text("ALTER TABLE records ADD COLUMN workspace VARCHAR NOT NULL DEFAULT ''"))
            if 'revision' not in names: conn.execute(text('ALTER TABLE records ADD COLUMN revision INTEGER NOT NULL DEFAULT 1'))
        Base.metadata.create_all(conn)
        rows=conn.execute(select(Record).where(Record.workspace=='',Record.kind.in_(['project','mission','mission_version','run','schedule']))).mappings().all()
        missions={r.id:r.payload.get('project_id','default') for r in conn.execute(select(Record.id,Record.payload).where(Record.kind=='mission'))} if rows else {}
        for r in rows:
            if r['workspace'] or r['kind'] not in ('project','mission','mission_version','run','schedule'): continue
            v=r['payload']; ws=workspace_of(r['kind'],v)
            if not ws and r['kind']=='mission': ws=missions[r['id']]
            if not ws and r['kind']=='run': ws=v.get('mission',{}).get('project_id','default')
            if not ws: ws=missions.get(v.get('mission_id'),'')
            if ws:
                v={**v,'project_id':ws} if r['kind']!='project' else v
                conn.execute(update(Record).where(Record.id==r['id']).values(workspace=ws,payload=v))
            else: logging.warning('Unresolved workspace: %s %s',r['kind'],r['id'])
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_records_workspace_kind ON records (workspace, kind)'))

def side(kind, workspace, local, session):
    """Where this record lives: 'local', 'hub', or 'both' when the workspace is not known yet."""
    from . import hub
    if local or session is not None or kind not in hub.ROUTED or not hub.enabled(): return 'local'
    if workspace: return 'hub' if hub.shared(workspace) else 'local'
    return 'both'

def unpack(row, metadata=False):
    return dict(row.payload) | ({'_revision':row.revision} if metadata else {})

def save(kind, value, *, session=None, local=False, expected=None, workspace='', preserve_times=False):
    if side(kind,workspace or workspace_of(kind,value),local,session)=='hub':
        from . import hub
        return hub.save(kind,value)
    if session is None:
        try:
            with Session.begin() as s: return save(kind,value,session=s,expected=expected,workspace=workspace,preserve_times=preserve_times)
        except IntegrityError as e: raise Conflict('Record already exists; reload before saving') from e
    value=dict(value); value.pop('_revision',None)
    value.setdefault('id',uuid.uuid4().hex); value.setdefault('created_at',now())
    if not preserve_times: value['updated_at']=now()
    row=session.get(Record,value['id']); ws=workspace_of(kind,value)
    if row and (row.kind!=kind or (workspace and row.workspace!=workspace)): raise Conflict('Record is unavailable')
    if workspace and ws!=workspace: raise Conflict('Workspace cannot change')
    if expected is not None:
        if expected==0:
            if row: raise Conflict('Record already exists')
            session.add(Record(id=value['id'],kind=kind,payload=value,workspace=ws,revision=1)); session.flush(); revision=1
        else:
            changed=session.execute(update(Record).where(Record.id==value['id'],Record.kind==kind,Record.workspace==workspace,Record.revision==expected).values(payload=value,revision=expected+1),execution_options={'synchronize_session':False}).rowcount
            if changed!=1: raise Conflict('This record changed. Reload before saving; your changes were not applied.')
            session.expire_all(); revision=expected+1
        return value | {'_revision':revision}
    if row:
        row.payload=value; row.workspace=ws; row.revision+=1
    else: session.add(Record(id=value['id'],kind=kind,payload=value,workspace=ws,revision=1))
    session.flush()
    return value

def get(kind,id,workspace='',*,local=False,session=None,metadata=False):
    where=side(kind,workspace,local,session)
    if where!='local':
        from . import hub
        if where=='hub':return hub.get(kind,id,workspace)
        # The workspace is unknown, so this machine answers first and the server only for what it does not hold.
        return get(kind,id,local=True,metadata=metadata) or hub.get(kind,id)
    if session is None:
        with Session() as s:return get(kind,id,workspace,session=s,metadata=metadata)
    q=select(Record).where(Record.id==id,Record.kind==kind)
    if workspace:q=q.where(Record.workspace==workspace)
    r=session.scalar(q)
    return unpack(r,metadata) if r else None

def all_records(kind,workspace='',*,local=False,session=None,metadata=False,limit=None,offset=0,summaries=False):
    where=side(kind,workspace,local,session)
    if where!='local':
        from . import hub
        if where=='hub':return hub.all_records(kind,workspace,limit=limit,summaries=summaries)
        # Every workspace this console can reach: the ones on this machine and the shared ones together.
        values=all_records(kind,local=True,metadata=metadata,summaries=summaries)+hub.all_records(kind,limit=limit,summaries=summaries)
        values.sort(key=lambda r:r.get('created_at',''),reverse=True)
        return values[offset:None if limit is None else offset+limit]
    if session is None:
        with Session() as s:return all_records(kind,workspace,session=s,metadata=metadata,limit=limit,offset=offset,summaries=summaries)
    q=select(Record).where(Record.kind==kind)
    if workspace:q=q.where(Record.workspace==workspace)
    q=q.order_by(Record.payload['created_at'].as_string().desc(),Record.id)
    if limit is not None:q=q.limit(limit).offset(offset)
    values=[unpack(r,metadata) for r in session.scalars(q).all()]
    return [summary(r) for r in values] if summaries else values

def summary(r):
    return {k:v for k,v in r.items() if k not in ('observations','events','http','console','actions','findings','_artifacts')} | {'finding_count':len(r.get('findings',[])),'step_count':len(r.get('actions',[]))}

def delete(kind,id,workspace='',*,local=False,session=None,expected=None):
    where=side(kind,workspace,local,session)
    if where=='hub' or (where=='both' and not get(kind,id,local=True)):
        from . import hub
        return hub.delete(kind,id,workspace,expected)
    if session is None:
        with Session.begin() as s:return delete(kind,id,workspace,session=s,expected=expected)
    q=sql_delete(Record).where(Record.id==id,Record.kind==kind)
    if workspace:q=q.where(Record.workspace==workspace)
    if expected is not None:q=q.where(Record.revision==expected)
    count=session.execute(q).rowcount
    if expected is not None and count!=1:raise Conflict('This record changed. Reload before deleting.')
