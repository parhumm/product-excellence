from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from engine import store, targets, presets
from engine.contracts import Mission, Project, Target

@pytest.fixture
def records(monkeypatch,tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    monkeypatch.setattr(store,'engine',engine);monkeypatch.setattr(store,'Session',sessionmaker(engine,expire_on_commit=False));monkeypatch.setattr(store,'DATA',tmp_path)
    store.init();yield tmp_path;engine.dispose()

def test_default_migration_is_bounded_idempotent_and_preserves_history(records):
    project=store.save('project',{'id':'site','name':'Site','url':'https://example.com','allowed_domains':['example.com']},local=True)
    mission=store.save('mission',{'id':'legacy','project_id':'site','url':'https://example.com/old'},local=True)
    revision=store.get('mission','legacy',local=True,metadata=True)['_revision']
    store.init();store.init()
    target=store.get('target','web-site',local=True)
    assert target['url']=='https://example.com' and target['name']=='Site'
    assert store.get('mission','legacy',local=True,metadata=True)==mission|{'_revision':revision}
    assert len(list((records/'backups').glob('records-before-targets-*.json')))==1

def test_app_only_project_has_no_preset_or_default(records):
    project=store.save('project',{'id':'app','name':'App','url':'','allowed_domains':[]},local=True)
    assert presets.seed_project(project)==project
    store.init()
    assert store.all_records('target','app',local=True)==[]
    assert Project(name='App',url='').url==''

def test_target_resolution_pins_latest_and_keeps_legacy_web(records):
    store.save('project',{'id':'app','name':'App','url':'','allowed_domains':[]},local=True)
    builds=[{'sha256':str(n)*64,'version_name':str(n),'version_code':n,'min_sdk':23,'target_sdk':34,'launch_activity':'dev.app.Main','abis':[],'size':10,'uploaded_at':f'2026-01-0{n}T00:00:00Z','archived':False} for n in (1,2)]
    target=Target(project_id='app',type='android',name='App',package='dev.app',builds=builds).model_dump()
    store.save('target',{'id':'android-app',**target},local=True)
    mission={'project_id':'app','target_id':'android-app','name':'Audit','goal':'Audit the app','url':'','mode':'audit','provider':'none','pillars':['functionality']}
    resolved=targets.resolve_mission(mission)
    assert resolved['platform']=='android' and resolved['build']=='2'*64
    legacy=targets.resolve_mission({'project_id':'app','name':'Old','goal':'Audit old website','url':'https://example.com','mode':'audit','provider':'none'})
    assert legacy['platform']=='web' and not legacy['target_id']

def test_android_request_can_reach_target_resolution_with_blank_url(records):
    store.save('project',{'id':'app','name':'App','url':'','allowed_domains':[]},local=True)
    build={'sha256':'a'*64,'version_name':'1','version_code':1,'min_sdk':23,'target_sdk':34,'launch_activity':'dev.app.Main','abis':[],'size':10,'uploaded_at':'2026-01-01T00:00:00Z','archived':False}
    store.save('target',{'id':'android-app',**Target(project_id='app',type='android',name='App',package='dev.app',builds=[build]).model_dump()},local=True)
    request=Mission(project_id='app',target_id='android-app',name='Audit',goal='Audit the app',url='',mode='audit',provider='none',pillars=['functionality'])
    assert targets.resolve_mission(request.model_dump())['platform']=='android'

def test_apk_metadata_and_split_rejection(monkeypatch,tmp_path):
    apk=tmp_path/'app.apk';apk.write_bytes(b'apk')
    monkeypatch.setattr(targets,'tool',lambda name:Path('/bin/true'))
    class Result:
        returncode=0;stderr=''
        stdout="package: name='dev.app' versionCode='7' versionName='1.7'\nsdkVersion:'23'\ntargetSdkVersion:'34'\nlaunchable-activity: name='dev.app.Main'\n"
    monkeypatch.setattr(targets.subprocess,'run',lambda *a,**kw:Result())
    metadata=targets.inspect_apk(apk)
    assert metadata['package']=='dev.app' and metadata['abis']==[] and metadata['size']==3
    Result.stdout="package: name='dev.app' versionCode='7' versionName='1.7' split='config.arm64'\nlaunchable-activity: name='dev.app.Main'\n"
    with pytest.raises(ValueError,match='Split'):targets.inspect_apk(apk)

def test_default_web_target_allows_its_own_host_without_project_domains(records):
    with store.Session.begin() as s:
        project=store.save('project',{'id':'site','name':'Site','url':'https://example.org','allowed_domains':[]},session=s)
        targets.default_web(project,s)
    mission={'project_id':'site','target_id':'web-site','name':'Audit','goal':'Audit the site','url':'','mode':'audit','provider':'none','pillars':['functionality']}
    resolved=targets.resolve_mission(mission)
    assert resolved['url']=='https://example.org' and resolved['platform']=='web'
    with pytest.raises(ValueError):targets.resolve_mission({**mission,'url':'https://other.example'})
