import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal
from urllib.parse import urlsplit

class Mission(BaseModel):
    project_id: str = 'default'
    name: str = Field(min_length=1, max_length=200)
    url: str
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
    pillars: list[Literal['functionality','cro','seo_aeo','ux_ui','performance']] = Field(min_length=1,default_factory=lambda:['functionality','cro','seo_aeo','ux_ui','performance'])
    @field_validator('url')
    @classmethod
    def valid_url(cls,v):
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
class ContinueRequest(BaseModel):
    """How much more work a finished run may do. Zero means the same amount its mission asked for."""
    ai_calls: int = Field(default=0, ge=0, le=60)
    steps: int = Field(default=0, ge=0, le=40)
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
    def valid_url(cls,v):return Mission.valid_url(v)
    @field_validator('codex_account')
    @classmethod
    def account_alias(cls,v):return Mission.account_alias(v)
