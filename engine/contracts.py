import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal
from urllib.parse import urlsplit

# --- Android scenario steps -------------------------------------------------
# A scenario is an ordered list of steps stored as normalized objects. YAML is an
# editing and exchange representation only; the mission never keeps the text.
PLACEHOLDER=re.compile(r'<[^<>]{0,120}>')
ORACLES=('text','text_absent','activity','playing','notification','no_crash')
EVENTS=('network','speed','delay_ms','kill','home','wait','relaunch','deep_link','open_notification')
KINDS=('goal','manual','event','check','hold')
STRICT=dict(extra='forbid',populate_by_name=True,serialize_by_alias=True)

def https_link(value):
    # A template still carrying its <placeholder> is reported by step number later, not as a bad URL here.
    if PLACEHOLDER.fullmatch(value):return value
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Deep links need an HTTPS URL without credentials')
    return value

def placeholder_in(value):
    """The first unresolved <placeholder> anywhere in a step, so the author is told what to replace."""
    if isinstance(value,str):
        found=PLACEHOLDER.search(value);return found.group(0) if found else ''
    if isinstance(value,dict):
        for item in value.values():
            found=placeholder_in(item)
            if found:return found
    if isinstance(value,list):
        for item in value:
            found=placeholder_in(item)
            if found:return found
    return ''

class Match(BaseModel):
    """Exact or substring match on package/activity. No author-supplied regular expression is executed."""
    model_config=ConfigDict(**STRICT)
    contains: str = Field(default='', max_length=300)
    equals: str = Field(default='', max_length=300)
    @model_validator(mode='after')
    def one(self):
        if bool(self.contains)==bool(self.equals):raise ValueError('Match an activity with exactly one of contains or equals')
        return self

class Notification(BaseModel):
    model_config=ConfigDict(**STRICT)
    text: str = Field(min_length=1, max_length=300)
    present: bool = True

class Until(BaseModel):
    """An early stop for a goal. Reaching it proves navigation, nothing later in the scenario."""
    model_config=ConfigDict(**STRICT)
    text: str = Field(min_length=1, max_length=300)

class Oracle(BaseModel):
    model_config=ConfigDict(**STRICT)
    text: str = Field(default='', max_length=4000)
    text_absent: str = Field(default='', max_length=4000)
    activity: Match | None = None
    playing: bool | None = None
    notification: Notification | None = None
    no_crash: bool | None = None
    policy: Literal['confirmed','unknown'] = 'confirmed'
    severity: Literal['P1','P2','P3','info'] = 'P2'
    required: bool | None = None
    @property
    def kind(self):return next(k for k in ORACLES if getattr(self,k) not in (None,''))
    @model_validator(mode='after')
    def one_oracle(self):
        chosen=[k for k in ORACLES if getattr(self,k) not in (None,'')]
        if len(chosen)!=1:raise ValueError('A check or hold states exactly one of: '+', '.join(ORACLES))
        # An unknown expectation is an observation: it never blocks a release, so it cannot be required.
        if self.policy=='unknown':
            if self.required:raise ValueError('An unknown-policy observation records what happened; it cannot be required')
            self.required=False
        elif self.required is None:self.required=True
        return self

class Check(Oracle):
    """Establish the fact once, any time inside the window."""
    within: int = Field(default=10, ge=1, le=1800)

class Hold(Oracle):
    """Establish the fact repeatedly across the whole interval."""
    for_: int = Field(default=10, ge=1, le=1800, alias='for')

class Event(BaseModel):
    model_config=ConfigDict(**STRICT)
    network: Literal['wifi','cellular','offline','restore'] | None = None
    speed: Literal['edge','gsm','umts','lte','full'] | None = None
    delay_ms: int | None = Field(default=None, ge=0, le=5000)
    kill: bool | None = None
    home: bool | None = None
    wait: int | None = Field(default=None, ge=1, le=1800)
    relaunch: bool | None = None
    deep_link: str | None = Field(default=None, max_length=2000)
    open_notification: str | None = Field(default=None, min_length=1, max_length=300)
    @property
    def kind(self):
        chosen=[k for k in EVENTS if getattr(self,k) is not None]
        if 'speed' in chosen and 'delay_ms' in chosen:chosen.remove('delay_ms')
        return chosen[0]
    @model_validator(mode='after')
    def one_operation(self):
        chosen=[k for k in EVENTS if getattr(self,k) is not None]
        # A link speed may carry its own added delay; everything else stands alone.
        if 'speed' in chosen and 'delay_ms' in chosen:chosen.remove('delay_ms')
        if len(chosen)!=1:raise ValueError('An event step performs exactly one of: '+', '.join(EVENTS))
        for flag in ('kill','home','relaunch'):
            if getattr(self,flag) is False:raise ValueError(flag+' takes true, or leave the key out')
        if self.deep_link:https_link(self.deep_link)
        return self

class Step(BaseModel):
    model_config=ConfigDict(**STRICT)
    name: str = Field(default='', max_length=200)
    goal: str = Field(default='', max_length=4000)
    until: Until | None = None
    manual: str = Field(default='', max_length=4000)
    ask: str = Field(default='', max_length=80)
    timeout: int | None = Field(default=None, ge=1, le=1800)
    event: Event | None = None
    check: Check | None = None
    hold: Hold | None = None
    @property
    def kind(self):return next(k for k in KINDS if getattr(self,k) not in (None,''))
    @property
    def seconds(self):
        """Time this step commits to spend. Windows and operator timeouts are maximums, not runtime."""
        if self.hold:return self.hold.for_
        if self.event:return self.event.wait or 0
        return 0
    @model_validator(mode='after')
    def one_kind(self):
        chosen=[k for k in KINDS if getattr(self,k) not in (None,'')]
        if len(chosen)!=1:raise ValueError('Each step is exactly one of: '+', '.join(KINDS))
        if self.until is not None and not self.goal:raise ValueError('until describes when a goal step may stop early')
        if self.timeout is not None and not self.manual:raise ValueError('timeout is how long an operator step may wait')
        if self.ask and not self.manual:raise ValueError('ask names the value an operator step supplies')
        if self.goal and len(self.goal)<5:raise ValueError('Describe the goal in at least five characters')
        if self.manual and self.timeout is None:self.timeout=300
        return self

class Mission(BaseModel):
    project_id: str = 'default'
    target_id: str = ''
    build: str = ''
    device: str = ''
    visibility: Literal['team','local'] = 'team'
    platform: Literal['web','android'] = 'web'
    name: str = Field(min_length=1, max_length=200)
    url: str = ''
    goal: str = Field(min_length=5, max_length=4000)
    success_text: str = Field(default='', max_length=300)
    allowed_domains: list[str] = Field(default_factory=list, max_length=30)
    mode: Literal['journey','explore','audit','benchmark'] = 'journey'
    # Benchmark mode pursues the same goal on the own site and then on each competitor start URL.
    competitors: list[str] = Field(default_factory=list, max_length=10)
    browser: Literal['chromium','firefox','webkit'] = 'chromium'
    viewport: Literal['desktop','mobile','tablet'] = 'desktop'
    network: str = 'baseline'
    auto_replay: bool = False
    observe_seconds: int = Field(default=0, ge=0, le=300)
    provider: Literal['codex','claude','auto','none'] = 'codex'
    # Empty inherits the workspace default; values identify a local .codex-* profile.
    codex_account: str = Field(default='', max_length=80)
    model: str = Field(default='', max_length=60)
    # Highest model Dynamic may use; empty means the strongest listed model.
    model_max: str = Field(default='', max_length=60)
    effort: Literal['low','medium','high','xhigh'] = 'low'
    max_steps: int = Field(default=6, ge=1, le=40)
    max_seconds: int = Field(default=600, ge=30, le=3600)
    ai_budget: int = Field(default=10, ge=0, le=60)
    locale: str = Field(default='fa-IR', max_length=20)
    persona_id: str = ''
    # The AI types the identifier literally; the password is stored under data/secrets
    # and filled by the engine, so it never reaches a prompt or a run record.
    login_identifier: str = Field(default='', max_length=200)
    login_password: str = Field(default='', max_length=200)
    egress_id: str = ''
    release: str = Field(default='live', max_length=100)
    # Android start state. `fresh` clears app data before the mission; `keep` carries it between runs.
    reset: Literal['fresh','keep'] = 'fresh'
    snapshot: str = Field(default='', pattern=r'^$|^[a-z0-9]{8,64}$')
    scenario: list[Step] = Field(default_factory=list, max_length=40)
    pillars: list[Literal['functionality','cro','seo_aeo','ux_ui','performance']] = Field(min_length=1,default_factory=lambda:['functionality','cro','seo_aeo','ux_ui','performance'])
    @field_validator('url')
    @classmethod
    def valid_url(cls,v):
        if not v:return v
        u=urlsplit(v)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password: raise ValueError('Use an HTTP(S) URL without credentials')
        return v
    @field_validator('model','model_max')
    @classmethod
    def model_alias(cls,v):
        # The value becomes a CLI argument; keep it to a plain model alias or identifier.
        if v and not re.fullmatch(r'[A-Za-z0-9._-]+',v): raise ValueError('Use a plain model id such as claude-sonnet-5 or gpt-5.6-terra')
        return v
    @field_validator('codex_account')
    @classmethod
    def account_alias(cls,v):
        if v and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',v):raise ValueError('Choose an available Codex account')
        return v
    @field_validator('competitors')
    @classmethod
    def competitor_urls(cls,values):
        for v in values: Mission.valid_url(v)
        return values
    @field_validator('allowed_domains')
    @classmethod
    def domains(cls, values):
        for v in values:
            if not v or any(c in v for c in '/:@* ') or v.startswith('.'): raise ValueError('Use plain exact domain names')
        return [v.lower() for v in values]
    @model_validator(mode='after')
    def coherent(self):
        # An explicit target owns the platform; the request is validated again after
        # target resolution. Legacy web missions still need their own URL here.
        if self.platform=='web' and not self.url and not self.target_id:raise ValueError('Website missions require a URL')
        if self.platform!='android' and (self.scenario or self.snapshot or self.reset!='fresh'):
            raise ValueError('Scenarios and saved device state apply to Android missions')
        if self.snapshot:
            # The name of a saved state is not its identity; loading one always keeps the data it holds.
            if 'reset' in self.model_fields_set and self.reset=='fresh':raise ValueError('A saved device state keeps its data; choose Keep previous app data or remove the snapshot')
            self.reset='keep'
        if self.scenario:
            if 'functionality' not in self.pillars:raise ValueError('Scenario verdicts are recorded under Functionality; select that pillar')
            committed=0
            for number,step in enumerate(self.scenario,1):
                found=placeholder_in(step.model_dump())
                if found:raise ValueError(f'Step {number} still says {found}; replace it with the real value before saving')
                committed+=step.seconds
            if committed>=self.max_seconds:raise ValueError(f'The waits and holds in this scenario already need {committed} s; raise the run time limit above that')
        if self.platform=='android':
            if self.mode=='benchmark' or self.competitors or self.persona_id or self.egress_id or self.login_identifier or self.login_password:raise ValueError('Android missions do not support benchmark, competitors, personas, egress or sign-in')
            if 'seo_aeo' in self.pillars:raise ValueError('Android missions do not support SEO/AEO')
            if self.url and urlsplit(self.url).scheme!='https':raise ValueError('Android deep links require HTTPS')
        if self.mode!='audit' and (self.provider=='none' or self.ai_budget==0):
            raise ValueError('Journeys require an AI worker and a positive AI-call budget')
        if self.observe_seconds>=self.max_seconds:raise ValueError('Observation duration must be shorter than the run time limit')
        if self.provider!='none' and self.ai_budget==0:raise ValueError('Choose no AI or allow at least one AI call')
        if self.login_password and not self.login_identifier:raise ValueError('Sign-in needs an identifier as well as a password')
        if self.mode=='benchmark' and not self.competitors:raise ValueError('A benchmark needs at least one competitor URL')
        return self
class GoalRequest(BaseModel):
    """One ask for goal suggestions on the mission form. Nothing here is stored."""
    project_id: str
    target_id: str = ''
    build: str = ''
    goal: str = Field(min_length=3, max_length=4000)
    url: str = ''
    mode: Literal['journey','explore','audit','benchmark'] = 'journey'
    viewport: Literal['desktop','mobile','tablet'] = 'desktop'
    provider: Literal['codex','claude','auto','none'] = 'auto'
    codex_account: str = Field(default='', max_length=80)
    competitors: list[str] = Field(default_factory=list, max_length=10)
    @field_validator('codex_account')
    @classmethod
    def account_alias(cls,v):return Mission.account_alias(v)
def ceiling(field):
    """The highest value a mission may hold for this field, so callers need not repeat the number."""
    return next(c.le for c in Mission.model_fields[field].metadata if hasattr(c,'le'))
class RunRequest(BaseModel):
    mission_id: str
    network: str | None = None
    baseline_id: str = ''
    build: str = ''
    visibility: Literal['team','local'] | None = None
class ContinueRequest(BaseModel):
    """How much more work a finished run may do. Zero means the same amount its mission asked for."""
    ai_calls: int = Field(default=0, ge=0, le=60)
    steps: int = Field(default=0, ge=0, le=40)
class ContinueStepRequest(BaseModel):
    """Which operator pause is being released. The token is issued by the run and used once."""
    model_config=ConfigDict(extra='forbid')
    step: int = Field(ge=1, le=40)
    token: str = Field(pattern=r'^[0-9a-f]{32}$')
    # Typed with `input text`, which only carries ASCII; never stored anywhere.
    value: str = Field(default='', max_length=64, pattern=r'^[\x20-\x7e]*$')
class DraftRequest(BaseModel):
    """One ask for scenario steps. Nothing is stored and no device is touched."""
    model_config=ConfigDict(extra='forbid')
    project_id: str = 'default'
    target_id: str = ''
    build: str = ''
    description: str = Field(min_length=10, max_length=4000)
    # Text the author says appears in their app. Nothing is read off a device for this.
    texts: list[str] = Field(default_factory=list, max_length=30)
    provider: Literal['codex','claude','auto','none'] = 'auto'
    codex_account: str = Field(default='', max_length=80)
    @field_validator('codex_account')
    @classmethod
    def account_alias(cls,v):return Mission.account_alias(v)
class ScenarioText(BaseModel):
    """Translate between the step rows and their YAML spelling. Comments are not preserved."""
    model_config=ConfigDict(extra='forbid')
    yaml: str = Field(default='', max_length=40000)
    steps: list[Step] = Field(default_factory=list, max_length=40)
class SnapshotRequest(BaseModel):
    """Save the designated AVD's current state under a new managed ID. Names are labels, never identity."""
    model_config=ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    project_id: str = 'default'
class NetworkProfile(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    latency_ms: int = Field(default=0,ge=0,le=5000)
    down_mbps: float = Field(default=0,ge=0,le=10000)
    up_mbps: float = Field(default=0,ge=0,le=10000)
    offline: bool = False
    backend: Literal['browser','netem'] = 'browser'
    jitter_ms: int = Field(default=0,ge=0,le=2000)
    loss_pct: float = Field(default=0,ge=0,le=100)
    reorder_pct: float = Field(default=0,ge=0,le=50)
    duplicate_pct: float = Field(default=0,ge=0,le=50)
    disconnect_every_seconds: int = Field(default=0,ge=0,le=600)
    disconnect_seconds: int = Field(default=2,ge=1,le=30)
    @model_validator(mode='after')
    def coherent(self):
        if self.backend=='browser' and any((self.jitter_ms,self.loss_pct,self.reorder_pct,self.duplicate_pct)):
            raise ValueError('Packet loss, jitter, reordering and duplication require Linux netem')
        if (self.jitter_ms or self.reorder_pct) and not self.latency_ms:raise ValueError('Jitter and reordering require nonzero latency')
        return self
class Egress(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    server: str
    username: str = ''
    password: str = ''
    @field_validator('server')
    @classmethod
    def proxy(cls,v):
        u=urlsplit(v)
        if u.scheme not in ('http','https','socks5') or not u.hostname or u.username or u.password: raise ValueError('Use http(s)://host:port or socks5://host:port; separate credentials')
        return v
class Schedule(BaseModel):
    mission_id: str
    every_minutes: int = Field(ge=5,le=10080)
    enabled: bool = False

class Project(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    url: str
    allowed_domains: list[str] = Field(default_factory=list)
    # Empty means the standard ~/.codex profile.
    codex_account: str = Field(default='', max_length=80)
    @field_validator('url')
    @classmethod
    def valid_url(cls,v):return Mission.valid_url(v) if v else v
    @field_validator('codex_account')
    @classmethod
    def account_alias(cls,v):return Mission.account_alias(v)

class Build(BaseModel):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    version_name: str = Field(max_length=100)
    version_code: int = Field(ge=0)
    min_sdk: int = Field(ge=1)
    target_sdk: int = Field(ge=1)
    launch_activity: str = Field(max_length=300)
    abis: list[str] = Field(default_factory=list, max_length=20)
    size: int = Field(ge=1, le=300 * 1024 * 1024)
    uploaded_at: str
    archived: bool = False

class Target(BaseModel):
    project_id: str
    type: Literal['web','android']
    name: str = Field(min_length=1,max_length=100)
    visibility: Literal['team','local'] = 'team'
    url: str = ''
    allowed_domains: list[str] = Field(default_factory=list,max_length=30)
    package: str = Field(default='',pattern=r'^$|^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')
    builds: list[Build] = Field(default_factory=list,max_length=200)
    @field_validator('url')
    @classmethod
    def target_url(cls,v):return Mission.valid_url(v) if v else v
    @field_validator('allowed_domains')
    @classmethod
    def domains(cls,v):return Mission.domains(v)
    @model_validator(mode='after')
    def coherent(self):
        if self.type=='web' and (not self.url or self.package or self.builds):raise ValueError('Website targets need a URL and cannot contain app builds')
        if self.type=='android' and self.url:raise ValueError('Android target URLs belong to mission deep links')
        return self
