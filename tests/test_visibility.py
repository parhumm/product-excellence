import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from engine import store, hub

@pytest.fixture
def records(monkeypatch,tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False));monkeypatch.setattr(store,'DATA',tmp_path)
    store.init();store.save('project',{'id':'ws','name':'Workspace','url':'','allowed_domains':[]},local=True)
    monkeypatch.setattr(hub,'enabled',lambda:True);monkeypatch.setattr(hub,'shared',lambda ws:ws=='ws')
    yield
    engine.dispose()

def test_local_record_never_mutates_hub(records,monkeypatch):
    calls=[];monkeypatch.setattr(hub,'save',lambda *a,**k:calls.append((a,k)))
    value=store.save('mission',{'id':'private','project_id':'ws','visibility':'local','created_at':'2'},workspace='ws')
    assert value['id']=='private' and not calls
    assert store.get('mission','private','ws')['visibility']=='local'
    assert not store.remote('mission',value)

def test_shared_lists_merge_then_page_without_cache_shadow(records,monkeypatch):
    store.save('mission',{'id':'private','project_id':'ws','visibility':'local','created_at':'2026-03-01'},local=True)
    # A stale team-shaped local copy is cache, never authority.
    store.save('mission',{'id':'team','project_id':'ws','visibility':'team','created_at':'2025-01-01'},local=True)
    remote=[{'id':'team','project_id':'ws','visibility':'team','created_at':'2026-02-01'},{'id':'other','project_id':'ws','created_at':'2026-01-01'}]
    monkeypatch.setattr(hub,'all_records',lambda *a,**k:remote)
    page=store.all_records('mission','ws',limit=2)
    assert [v['id'] for v in page]==['private','team']
    assert page[1]['created_at']=='2026-02-01'
    assert store.all_records('mission','ws',limit=1,offset=2)[0]['id']=='other'

def test_missing_visibility_keeps_legacy_team_routing(records,monkeypatch):
    calls=[]
    monkeypatch.setattr(hub,'save',lambda kind,value:value|{'sent':'hub'})
    value=store.save('mission',{'id':'legacy','project_id':'ws'},workspace='ws')
    assert value['sent']=='hub'
