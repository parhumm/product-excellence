"""The shipped Claude Code skills stay well formed, safe and documented."""
import pathlib,re
import pytest,yaml

ROOT=pathlib.Path(__file__).resolve().parents[1]
SKILLS=sorted((ROOT/'.claude'/'skills').glob('*/SKILL.md'))
DOCS=['README.md','docs/SKILLS.md','docs/USER_MANUAL.md','docs/REFERENCE.md','docs/DEPLOY.md','docs/FEATURE_STATUS.md','static/intro.html','static/app.js']

def front_matter(path):
    text=path.read_text()
    assert text.startswith('---\n'),f'{path} has no front matter'
    return yaml.safe_load(text.split('---\n',2)[1]),text.split('---\n',2)[2]

def test_every_skill_is_present():
    assert {p.parent.name for p in SKILLS}=={'pex-mission-write','pex-mission-suggest','pex-env-check','pex-run-diagnose',
                                             'pex-findings-triage','pex-run-brief','pex-issue-report','pex-release-ship'}

@pytest.mark.parametrize('path',SKILLS,ids=lambda p:p.parent.name)
def test_front_matter(path):
    meta,body=front_matter(path)
    assert meta['name']==path.parent.name
    # The description is always in context and is what routes the skill, so keep it short.
    assert 0<len(meta['description'])<120,meta['description']
    assert meta['description'].startswith('Use when')
    assert meta['argument-hint'] and meta['allowed-tools']
    assert len(body.splitlines())<500

@pytest.mark.parametrize('path',SKILLS,ids=lambda p:p.parent.name)
def test_secrets_are_only_ever_mentioned_as_forbidden(path):
    for line in path.read_text().splitlines():
        if 'data/secrets' in line:assert 'never' in line.lower(),line

@pytest.mark.parametrize('path',SKILLS,ids=lambda p:p.parent.name)
def test_bundled_paths_exist(path):
    for target in re.findall(r'`(references/[\w.-]+|\.claude/skills/[\w./-]+)`',path.read_text()):
        resolved=(path.parent/target) if target.startswith('references/') else (ROOT/target)
        assert resolved.exists(),f'{path.parent.name} points at missing {target}'

def test_the_docs_name_real_skills():
    named=set()
    for doc in DOCS:
        named|=set(re.findall(r'/(pex-[a-z]+-[a-z]+)\b',(ROOT/doc).read_text()))
    assert named,'no skill is documented anywhere'
    assert named<={p.parent.name for p in SKILLS},sorted(named-{p.parent.name for p in SKILLS})

def test_every_skill_is_in_the_user_guide():
    guide=(ROOT/'docs'/'SKILLS.md').read_text()
    for path in SKILLS:assert path.parent.name in guide,f'{path.parent.name} is missing from docs/SKILLS.md'
