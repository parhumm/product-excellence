const $=s=>document.querySelector(s), main=$('#main');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Shared run records are untrusted; evidence links must stay inside this run.
function evidenceURL(runId,value){
const match=typeof value==='string'&&value.match(/^\/api\/runs\/([A-Za-z0-9_-]+)\/artifacts\/([A-Za-z0-9_.-]+)$/);
return match&&match[1]===runId&&!['.','..'].includes(match[2])?esc(value):'#';
}
const runRevisions={};
let state={},health={},currentRun=null,selectedStep=0,followLatest=true,refreshTimer,renderGeneration=0;
// Browser storage is unavailable in some privacy modes; the console must still work there.
const recall=(k,fallback)=>{try{return localStorage.getItem(k)??fallback}catch(e){return fallback}};
const remember=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
let workspace=recall('pex.workspace','');
const project=()=>(state.projects||[]).find(p=>p.id===workspace)||{};
const target=id=>(state.targets||[]).find(t=>t.id===id);
const targetLabel=id=>target(id)?.name||'Workspace website';
const label={functionality:'Functionality',cro:'CRO',seo_aeo:'SEO / AEO',ux_ui:'UX / Accessibility',performance:'Performance / Video'};
const badge=s=>`<span class="badge ${esc(s)}">${esc(String(s||'unknown').replaceAll('_',' '))}</span>`;
const empty=(title,body,action='')=>`<div class="empty"><h2>${title}</h2><p class="muted">${body}</p>${action}</div>`;
const date=s=>s?new Date(s).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
const ms=n=>typeof n==='number'?`${Math.round(n)} ms`:'Not observed';
// Any section or finding can be pasted into a ticket or a chat. The text is built with the page and copied by key.
let copyTexts={},copySerial=0;
const copyButton=(text,label)=>{const key='c'+(++copySerial);copyTexts[key]={text:String(text||''),label};return `<button type="button" class="copy" data-copy="${key}" aria-label="Copy ${esc(label)}" title="Copy ${esc(label)}">&#10697;</button>`};
const lines=parts=>parts.filter(Boolean).join('\n');
// The shipped Claude Code skills are the next step for most run states, so the command is never typed by hand.
const skillHint=(why,command)=>`<div class="skillhint"><div><strong>${esc(why)}</strong><br><code>${esc(command)}</code><small>Paste into Claude Code started in this folder.</small></div>${copyButton(command,'the command')}</div>`;
// Plain words for the stored codes, so a reader never meets a raw enum.
const VERDICT={CONFIRMED:'Confirmed',PROBABLE:'Probable',UNCONFIRMED:'Not confirmed',REJECTED:'Rejected by critic'};
const SOURCEWORD={deterministic:'measured',ai:'AI suggestion'};
const CONFIRMED_MEANS='Confirmed means the recorded rule was observed, not that business impact is proven.';
const networkName=r=>(state.networks||[]).find(n=>n.id===r.mission.network)?.name||r.mission.network;
const metricCell=(name,meaning,value)=>`<div><small><abbr title="${esc(meaning)}">${esc(name)}</abbr></small><strong>${esc(value)}</strong></div>`;
const LAB='Measured in this browser session, not from real users.';
// Copied text mirrors the markdown export, so a paste reads the same wherever it lands.
const findingText=f=>lines([`### ${f.severity} · ${f.title}`,
`${label[f.pillar]||f.pillar} · ${VERDICT[f.verifier_status]||f.verifier_status} · ${f.classification} · ${SOURCEWORD[f.source]||f.source}`,
'Observed: '+f.observed,'Expected: '+f.expected,'Recommendation: '+f.recommendation,
f.verifier_reason?'Why this verdict: '+f.verifier_reason:'',
f.pages>1?`Seen on ${f.pages} pages of this run.`:'',
`Evidence: ${f.evidence_id} · run ${f.run_id}`,`Review: ${f.status||'open'} · owner ${f.owner||'unassigned'}`]);
const findingsText=list=>lines(['## Findings',...list.map(findingText)]);
const summaryText=s=>lines(['## Executive summary','### '+s.headline,s.summary,
'Recorded facts:',...s.facts.map(x=>'- '+x),
s.top_findings.length?'Most severe open findings:':'',
...s.top_findings.map(f=>`- ${f.severity} · ${f.title} (${label[f.pillar]||f.pillar})`),
'Next steps:',...s.next_steps.map((x,i)=>`${i+1}. ${x}`),'Source: '+s.source]);
const scoresText=r=>{const s=r.scores||{};return lines(['## Scores',
...Object.entries(s).filter(([k])=>!['overall','basis'].includes(k)).map(([p,v])=>`${label[p]||p}: ${v.score!=null?v.score:'not scored'}.${v.score==null?' '+v.reason+'.':v.deductions.length?' Deductions: '+v.deductions.map(d=>`${d.title} −${d.points}`).join('; ')+'.':' No open findings.'}`),
s.overall?`Overall: ${s.overall.score!=null?s.overall.score:'not scored'} (${s.overall.scored} of ${s.overall.of} pillars scored).`:'',s.basis||''])};
const stepText=(r,o,i)=>lines([`${String(i+1).padStart(2,'0')}. ${o.title||'Page observation'}`,'   '+o.url,
...(r.actions||[]).filter(a=>a.evidence_before===o.id).map(a=>{const res=actionResult(a);return `   ${actionSummary(a)} · ${a.status||'pending'}${res?' · '+res:''}`})]);
// A continued run reopened the browser partway through, so the timeline says where each visit begins.
const partStart=(r,o,i)=>o.part>1&&o.part!==r.observations[i-1]?.part?`Part ${o.part} · continued ${date(o.at)}`:'';
const timelineText=r=>lines(['## Journey timeline',...(r.observations||[]).flatMap((o,i)=>[partStart(r,o,i),stepText(r,o,i)])]);
const evidenceText=(r,o)=>{const m=o?.metrics||{};return lines(['## Browser evidence',o.title||'Page observation',o.url,date(o.at),
'Largest contentful paint: '+ms(m.lcp),'Cumulative layout shift: '+(typeof m.cls==='number'?m.cls.toFixed(3):'Not observed'),
'Interaction to next paint: '+ms(m.inp),'Time to first byte: '+ms(m.ttfb_ms),LAB])};
const blockedLine=r=>r.policy_blocked_requests?`The read-only policy blocked ${r.policy_blocked_requests} request${r.policy_blocked_requests===1?'':'s'} that would have changed data on the site.`:'No request tried to change data on the site.';
const checkLine=c=>(c.step?'Step '+c.step:'At the start')+': '+(c.route_name||'')+' · '+(c.status==='verified'?'exits from '+c.observed_ip:c.status+(c.error?' · '+c.error:''));
const conditionsText=r=>lines(['## Run conditions','Network: '+networkName(r)+'. '+(r.network_applied?.scope||'Not yet applied.'),
'Route: '+(r.egress?.name||'Direct connection'),r.egress?.verification||'',...(r.route_checks||[]).map(checkLine),blockedLine(r)]);
const coverageText=r=>lines(['## What this run checked',...Object.entries(r.coverage||{}).map(([p,c])=>`${label[p]||p}: ${String(c.status).replaceAll('_',' ')}${c.note?'. '+c.note:''}`)]);
const consoleText=e=>lines([`### ${e.kind} · ${(e.name||'').trim()||'console'}`,String(e.message||''),
`Source: ${e.source||'Not reported'} · Page: ${e.page_url||'Unknown'} · Step: ${typeof e.step==='number'?e.step+1:'n/a'} · At: ${e.at||''}`,e.stack||'']);
const aiUsageText=r=>{const t=r.ai_totals||{};return lines(['## AI usage',
`Calls: ${r.ai_calls||0} · Provider: ${r.provider||'none'} · Models: ${(t.models||[]).join(', ')||'unknown'}`,
`Tokens: ${tok(t.input_tokens)} input, ${tok(t.cached_tokens)} cached, ${tok(t.output_tokens)} output`,
'Estimated cost: '+money(t.est_cost_usd,t.cost_partial)])};
const logText=r=>lines(['## Execution log',...(r.events||[]).map(e=>`${date(e.at)}  ${e.message}`)]);
const runText=r=>lines([`# ${r.mission.name}`,r.mission.url,'Run: '+r.id,
`Status: ${r.status}. Release check: ${String(r.gate||'not_evaluated').replaceAll('_',' ')}.`,
r.mission.goal?'Goal: '+r.mission.goal:'',
`Conditions: ${r.mission.browser} · ${r.mission.viewport} · ${networkName(r)} network`,
r.error?'Message: '+r.error:'',
r.executive_summary?summaryText(r.executive_summary):'',scoresText(r),
`Open findings: ${(r.findings||[]).filter(f=>!closed(f)).length} of ${(r.findings||[]).length} records.`]);
// One title, one reason, one next action for every way a run can end badly.
const STATUS_NOTICE={blocked:['The journey did not reach its goal','Read the timeline to see where it stopped, then fix the site or adjust the mission and replay.'],
failed:['The run failed before it finished','Replay to try again. If it fails the same way, run the command below or check Settings.'],
cancelled:['You stopped this run','Evidence collected before the stop is kept below. Replay to run it again.'],
interrupted:['The service restarted during this run','Replay to continue.']};
// A run that stopped on a budget can carry on from its last page instead of starting over.
const canContinue=r=>(r.platform||r.mission.platform||'web')==='web'&&!['queued','running'].includes(r.status)&&!!(r.observations||[]).length&&r.mission.mode!=='benchmark'&&!shared(r.project_id||workspace)
&&(r.mission_outcome==='budget_stop'||r.status==='interrupted'||!!r.evaluation_error||/budget/i.test(r.error||''));
const CONTINUE_NEXT='Continue below to pick up where it stopped, or adjust the mission and replay from the start.';
function continueSection(r){if(!canContinue(r))return '';
return `<div class="notice"><strong>Continue this run</strong><p>The browser reopens the last page in the same session. Every step, screenshot and finding below is kept. The AI review runs when the journey ends.</p><form id="continue-form" class="toolbar"><div class="field"><label for="add-calls">AI calls to add</label><input id="add-calls" name="ai_calls" type="number" min="0" max="60" value="${r.mission.ai_budget}" style="width:130px"></div><div class="field"><label for="add-steps">Steps to add</label><input id="add-steps" name="steps" type="number" min="0" max="40" value="${r.mission.max_steps}" style="width:130px"></div><button class="primary" data-continue="${r.id}">Continue run</button></form><small class="muted">Used so far: ${r.ai_calls||0} AI calls and ${(r.actions||[]).length} steps. A mission allows 60 AI calls and 40 steps at most. The recording and the trace continue in a new part.</small></div>`}
// A pause is silent otherwise, and the operator is usually looking at another window.
let dinged='',titleBase=document.title;
function ding(r){const w=r&&r.waiting_for,key=w?r.id+':'+w.step:'';
if(!w){if(document.title!==titleBase)document.title=titleBase;dinged='';return}
document.title='\u{1F514} '+titleBase;
if(key===dinged)return;dinged=key;
// Audio needs a prior gesture on the page; the operator clicked their way here, and the title bell covers the rest.
try{const ctx=new (window.AudioContext||window.webkitAudioContext)();
[[880,0],[1175,.18]].forEach(([hz,at])=>{const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=hz;o.connect(g);g.connect(ctx.destination);
g.gain.setValueAtTime(.0001,ctx.currentTime+at);g.gain.exponentialRampToValueAtTime(.2,ctx.currentTime+at+.02);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+at+.15);
o.start(ctx.currentTime+at);o.stop(ctx.currentTime+at+.16)});
setTimeout(()=>ctx.close(),600)}catch(e){}}
// A pause for the operator: on a device the recording is stopped, so the notice must say so and say how long is left.
function operatorNotice(r){const w=r.waiting_for;if(!w)return '';
const left=Math.max(0,Math.round((new Date(w.until)-Date.now())/1000));
const android=(r.platform||r.mission.platform)==='android',asking=w.kind==='ask',choosing=w.kind==='choose';
const options=w.options||[];
const how=choosing?`Pick how the run should carry on and the console ${android?'taps':'clicks'} it for you.`
:!w.ask?'Do this on the device, then continue.'
:android?'Type the value here and the console enters it into the focused field on the device, or enter it on the device yourself and continue with the box empty.'
:'Type the value here and the console fills it into the field. That field is masked in every screenshot and the value is scrubbed from the saved evidence, but the journey video may still show it.';
const release=`data-continue-step="${r.id}" data-step-number="${w.step}" data-token="${esc(w.token)}"`;
// A choice is released by one of its own buttons, so each option is a Continue run of its own.
const pick=choosing?options.map(o=>`<button class="primary" ${release} data-value="${esc(o.id)}" dir="auto">${esc(o.label)}</button>`).join('')
:`${w.ask?`<input id="ask-value" dir="auto" type="${/password|card|cvv|pin/i.test(w.ask)?'password':'text'}" placeholder="${esc(w.ask)}" autocomplete="off" maxlength="200">`:''}<button class="primary" ${release}>Continue run</button>`;
return `<div class="notice"><strong>${choosing?'The run needs a choice from you':asking?'The run needs a value from you':`Step ${w.step} is waiting for you`}</strong><p dir="auto">${esc(w.instruction)}</p><p>${android&&!choosing?'Screen recording is stopped until you continue, and no screenshots are taken while this step waits. ':''}${how}</p><p><strong>${left?left+' seconds left':'No time left'}</strong> of the ${w.seconds} allowed. ${asking||choosing?'The run stops if nobody answers in time.':'This step fails if nobody continues in time.'}</p><div class="toolbar">${pick}${asking||choosing?`<button data-skip-step="${r.id}" data-step-number="${w.step}" data-token="${esc(w.token)}">Skip</button>`:''}<button class="danger" data-cancel="${r.id}">Stop run</button></div></div>`}
function statusNotice(r){const known=STATUS_NOTICE[r.status];if(!known&&!r.error)return '';
const [title,fallback]=known||['Run message',''];const next=canContinue(r)?CONTINUE_NEXT:fallback;
const body=(r.status==='blocked'&&r.success_basis)||r.error||'';
const steps=(r.actions||[]).filter(a=>a.status&&a.status!=='executed').map(a=>`<p class="muted">Step ${a.step+1}: ${esc(actionSummary(a))}. ${esc(firstLine(a.error)||a.status)}</p>`).join('');
return `<div class="notice"><strong>${esc(title)}</strong>${body?`<p dir="auto">${esc(body)}</p>`:''}${steps}${next?`<p><strong>Next:</strong> ${esc(next)}</p>`:''}${['blocked','failed','interrupted'].includes(r.status)?skillHint('Find the cause and the smallest fix:','/pex-run-diagnose '+r.id):''}</div>`}
// The team server stores results and serves no write route: missions run in each teammate's local console.
const SERVER=()=>state.hub?.mode==='server';
const COMING_SOON='Coming soon. Run this in your local console; published results appear here.';
// A workspace lives in exactly one place: this Mac, or the team server this console is signed in to for it.
const shared=id=>!!state.hub?.logins?.[id];
const host=()=>{try{return new URL(state.hub.url).host}catch(e){return state.hub?.url||'the team server'}};
const where=id=>shared(id)?'Shared on '+host():'On this Mac';
const uploadNote=r=>!shared(r.project_id||workspace)?'':state.hub?.pending?.includes(r.id)?'Awaiting upload':['queued','running'].includes(r.status)?'Uploads when finished':'Shared';
const WRITE_CONTROLS='[data-export-html],[data-start],[data-cancel],[data-continue-step],[data-skip-step],[data-replay],[data-continue],[data-matrix],[data-owner],[data-done],[data-finding],[data-toggle-schedule],[data-delete-schedule],[data-delete-mission],[data-delete-egress],[data-verify-egress],[data-share],[data-archive-build],[data-remove-build],[data-delete-snapshot]';
function readOnly(){
  if(!SERVER())return;
  document.querySelectorAll('nav a[href="#network"]').forEach(a=>a.hidden=true);
  document.querySelectorAll('a[href="#new"],a[href^="#edit/"]').forEach(a=>{a.removeAttribute('href');a.setAttribute('aria-disabled','true');a.title=COMING_SOON});
  main.querySelectorAll('#mission-form,#project-form,#target-form,#schedule-form,#network-form,#egress-form').forEach(el=>(el.closest('details')||el).remove());
  main.querySelectorAll('#persona-import,#mission-import').forEach(el=>el.closest('label')?.remove());
  main.querySelectorAll('[data-apk]').forEach(el=>el.closest('label')?.remove());
  main.querySelectorAll('[data-project-codex]').forEach(el=>el.closest('.field')?.remove());
  main.querySelectorAll(WRITE_CONTROLS).forEach(el=>{el.disabled=true;el.title=COMING_SOON});
  // The skills call this machine's local console, so the team server never offers them.
  main.querySelectorAll('.skillhint').forEach(el=>el.remove());
  main.querySelectorAll('[data-start]').forEach(b=>b.textContent='Run (coming soon)');
}
// The team server can stop answering mid-session. The console keeps the copy it already has and says so.
const outageNotice=o=>`<div class="notice" role="alert"><strong>The team server is not responding.</strong><p>${o.synced_at?`Showing the last copy this console received, synced ${date(o.synced_at)}.`:'This console has no copy of the shared records, so these lists stay empty until the server answers.'} Saving changes and starting runs wait until the server answers again.</p><div class="toolbar"><button type="button" id="outage-retry">Try again</button></div></div>`;
function toast(s){const t=$('#toast');t.textContent=s;t.style.display='block';clearTimeout(t.timer);t.timer=setTimeout(()=>t.style.display='none',4500)}
async function api(path,options={}){if(options.method&&options.method!=='GET'&&SERVER())throw Error(COMING_SOON);const parts=path.split('/'),kind=parts[1],id=parts[2];const record=kind==='missions'?state.missions?.find(m=>m.id===id):kind==='targets'?state.targets?.find(m=>m.id===id):kind==='schedules'?state.schedules?.find(m=>m.id===id):kind==='projects'?state.projects?.find(m=>m.id===id):kind==='findings'?(currentRun?.id===id?currentRun:state.runs?.find(m=>m.id===id)):null;const revision=kind==='findings'?(runRevisions[id]??record?._revision):record?._revision;const r=await fetch('/api'+path,{...options,headers:{'X-PEX-Request':'1',...(workspace?{'X-PEX-Workspace':workspace}:{}),...(revision!=null?{'X-PEX-Revision':String(revision)}:{}),...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}});if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))}const result=await r.json();if(result._revision!=null){if(record)record._revision=result._revision;if(kind==='findings')runRevisions[id]=result._revision;if(kind==='runs'&&result.id)runRevisions[result.id]=result._revision}return result}
// The sidebar describes the workspace in front of you, not the connection: the two no longer say the same thing.
function modeLine(){
  if(SERVER())return '<span class="dot"></span> Team server<small>Shared results, read only.<br>Missions run in your local console.</small><button id="signout" class="compact">Sign out</button>';
  const outage=state.hub?.outage,waiting=state.hub?.pending?.length||0;
  const note=waiting?`<br><a href="#settings">${waiting} run${waiting===1?'':'s'} awaiting upload</a>`:'';
  if(shared(workspace))return `${outage?'':'<span class="dot"></span> '}Shared on ${esc(host())}<small>${outage?(outage.synced_at?'Not responding. Showing the last copy.':'Not responding. No copy on this Mac.'):'Missions and results sync to the team server. Browser and AI run on this Mac.'}${note}</small>`;
  return `<span class="dot"></span> On this Mac<small>Missions and evidence stay on this Mac.${state.hub?.mode==='hybrid'?`<br>Team server: ${outage?'not responding':'connected to '+esc(host())}`:''}${note}</small>`;
}
async function reload(){state=await api('/state?project='+encodeURIComponent(workspace));
if((state.projects||[]).length&&!state.projects.some(p=>p.id===workspace)){workspace=state.projects[0].id;remember('pex.workspace',workspace);state=await api('/state?project='+encodeURIComponent(workspace))}
if($('#mode'))$('#mode').innerHTML=modeLine();if($('#signout'))$('#signout').onclick=window.signOut;workspacePicker();$('#running-count').textContent=state.runs.filter(r=>['running','queued'].includes(r.status)).length||''}
function workspacePicker(){const el=$('#workspace');if(!el)return;const all=state.projects||[],mine=all.filter(p=>!shared(p.id)),team=all.filter(p=>shared(p.id));
el.innerHTML=mine.length&&team.length?`<optgroup label="On this Mac">${mine.map(p=>option(p.id,p.name,workspace)).join('')}</optgroup><optgroup label="Shared on ${esc(host())}">${team.map(p=>option(p.id,p.name,workspace)).join('')}</optgroup>`:all.map(p=>option(p.id,p.name,workspace)).join('');
el.onchange=()=>{workspace=el.value;remember('pex.workspace',workspace);selectedStep=0;
// A run or mission of the previous website does not belong to the new one.
if(['#run/','#edit/'].some(h=>location.hash.startsWith(h)))location.hash='#overview';else render()}}
function head(title,sub,actions=''){return `<div class="pagehead"><div><h1>${title}</h1><p>${sub}</p></div><div class="actions">${actions}</div></div>`}
const scoreCell=r=>{const o=r.scores&&r.scores.overall;return o&&o.score!=null?`<strong>${o.score}</strong><small>${o.scored}/${o.of} pillars</small>`:'<span class="muted">—</span>'};
function runTable(runs){return runs.length?`<div class="tablewrap"><table><thead><tr><th>Mission</th><th>Status</th><th>Environment</th><th>AI</th><th>Findings</th><th>Score</th><th>Started</th></tr></thead><tbody>${runs.map(r=>{const native=(r.platform||r.mission.platform)==='android',app=r.app||{};return `<tr><td><a href="#run/${r.id}"><strong>${esc(r.mission.name)}</strong></a><small>${esc(native?targetLabel(r.mission.target_id)+' · '+(app.version_name||app.sha256?.slice(0,10)||'build'):r.mission.url)}</small></td><td>${badge(r.status)}${uploadNote(r)?`<small>${uploadNote(r)}</small>`:''}</td><td>${native?`Android · ${esc(r.device?.avd||r.mission.device||'not selected')}<small>${esc(r.mission.network)}</small>`:`${esc(r.mission.browser)} · ${esc(r.mission.viewport)}<small>${esc(r.mission.network)}</small>`}</td><td>${aiCell(r)}</td><td>${r.finding_count}</td><td>${scoreCell(r)}</td><td>${date(r.created_at)}</td></tr>`}).join('')}</tbody></table></div>`:empty('Your first run starts here','Choose a saved mission to collect real evidence.','<a class="button primary" href="#missions">Choose a mission</a>')}
function overview(){const runs=state.runs.filter(r=>!r.mission.url.includes('/demo'));return `<section class="welcome"><span class="eyebrow">${esc(String(project().name||'Workspace').toUpperCase())} / PHASE 1 WEB</span><h1 style="margin-top:12px">See the journey.<br>Understand what gets in the way.</h1><p class="muted">${esc(project().url||'')}<br>Give the engine a goal. Review the browser actions, measured signals and findings together.</p><div class="toolbar"><a class="button primary" href="#missions">Start a mission</a><a class="button" href="#settings">Check readiness</a></div><div class="factline"><span><strong>${state.missions.length}</strong> saved missions</span><span><strong>${runs.length}</strong> runs</span><span><strong>${runs.reduce((n,r)=>n+r.finding_count,0)}</strong> recorded findings</span></div></section><div class="split"><section><div class="pagehead"><h2>Recent runs</h2><a href="#runs">View all →</a></div>${runTable(runs.slice(0,5))}</section><section><h2>From mission to evidence</h2><ol class="checklist"><li><span class="index">01</span><div><strong>Define a user goal</strong><small>Pick the website or Android app, then browser, viewport, persona and network.</small></div></li><li><span class="index">02</span><div><strong>Watch the engine work</strong><small>Follow actions and screenshots. Stop a run at any time.</small></div></li><li><span class="index">03</span><div><strong>Challenge each finding</strong><small>Inspect evidence, replay and compare releases.</small></div></li></ol><p class="muted" style="margin-top:20px;font-size:12px">Public browsing is enabled. Account and payment actions are blocked. Authenticated checks require an imported test session.</p></section></div>`}
function missions(){return head('Missions',`Reusable goals for website and Android journeys. · ${esc(where(workspace))}`,'<label class="button">Import YAML<input type="file" id="mission-import" accept=".yaml,.yml,.json" hidden></label><a class="button" href="#journeys">Start from a journey</a><a class="button primary" href="#new">New mission</a>')+`<div class="tablewrap"><table><thead><tr><th>Mission</th><th>Mode / AI</th><th>Target</th><th>Actions</th></tr></thead><tbody>${state.missions.map(m=>{const native=m.platform==='android';return `<tr><td><a href="#edit/${m.id}"><strong>${esc(m.name)}</strong></a><small style="max-width:460px">${esc(m.goal)}</small></td><td>${esc(m.mode)}<small>${esc(workerLabel(m))}</small></td><td>${esc(targetLabel(m.target_id))}<small>${(m.scenario||[]).length?`Scenario · ${m.scenario.length} steps · up to ${Math.ceil(Math.min(scenarioBudget(m.scenario).ceiling,m.max_seconds)/60)} min<br>`:''}${native?`Android · ${esc(m.build?m.build.slice(0,10):'latest')} · ${esc(m.visibility||'team')}`:`${esc(m.browser)} · ${esc(m.viewport)} · ${esc(m.network)}`}</small></td><td><div class="actions"><button class="primary compact" data-start="${m.id}">Run</button><a class="button compact" href="#edit/${m.id}">Edit</a>${native?'':`<button class="compact" data-matrix="${m.id}">5 networks</button>`}<a class="button compact" href="/api/missions/${m.id}/export">YAML</a>${m.visibility==='local'&&shared(workspace)?`<button class="compact" data-share="missions/${m.id}">Share</button>`:''}</div></td></tr>`}).join('')}</tbody></table></div>`}
// --- journey gallery ----------------------------------------------------------
// A journey carries no platform. The target chosen on the form decides whether its steps
// run on a device or in a page, so nothing here is filtered by one.
function journeys(){const found=scenarioPresets||[];
return head('Journeys',`Ordered scenarios that run on an Android app or a website. Pick one, fill the blanks, run it. · ${esc(where(workspace))}`,'<a class="button" href="#missions">Back</a>')
+`<div class="field full"><label for="journey-search">Search</label><input id="journey-search" dir="auto" value="${esc(journeySearch)}" placeholder="playback, sign-in, offline, checkout…"></div>`
+`<div class="journeys">${found.map(p=>`<article class="journey" data-find="${esc([p.name,p.about,(p.tags||[]).join(' ')].join(' ').toLowerCase())}"><h3>${esc(p.name)}</h3><p class="muted" dir="auto">${esc(p.about)}</p><div class="findmeta"><span class="badge">${esc(journeySize(p))}</span>${(p.tags||[]).map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</div>${(p.needs||[]).length?`<small class="caveat">Needs: ${esc(p.needs.join(' · '))}</small>`:''}<div class="toolbar"><a class="button compact primary" href="#new/${esc(p.id)}">Use this journey</a></div></article>`).join('')}</div>`
+`<p class="muted" id="journey-none" hidden>No journey matches that. Try a shorter word, or clear the search.</p>`}
const option=(v,t,selected)=>`<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(t)}</option>`;
let fieldSerial=0;
function field(name,title,value,type='text',help='',full=false){const id=name+'-'+(++fieldSerial);return `<div class="field ${full?'full':''}"><label for="${id}">${title}</label><input id="${id}" name="${name}" type="${type}" ${type==='number'?'step="any"':''} value="${esc(value)}" ${name==='name'?'required':''}>${help?`<small>${help}</small>`:''}</div>`}
function listField(name,title,value,options,help=''){const id=name+'-'+(++fieldSerial);return `<div class="field"><label for="${id}">${title}</label><input id="${id}" name="${name}" list="${id}-options" value="${esc(value)}" autocomplete="off"><datalist id="${id}-options">${options.map(o=>`<option value="${esc(o)}"></option>`).join('')}</datalist>${help?`<small>${help}</small>`:''}</div>`}
const aiModels=provider=>(health.ai?.[provider]?.models)||[];
const codexAccounts=()=>health.ai?.codex?.accounts||[];
const codexAccountLabel=id=>{const a=codexAccounts().find(a=>a.id===(id||'default'));return a?(a.label+(a.email?' · '+a.email:'')):(id||'Default')};
function codexAccountOptions(value='',inherit=false,workspaceDefault='default'){return (inherit?option('',`Workspace default (${codexAccountLabel(workspaceDefault)})`,value):'')+codexAccounts().map(a=>option(a.id,`${a.label}${a.email?' · '+a.email:''}${a.signed_in?'':' · sign-in needed'}`,value||(inherit?'':'default'))).join('')}
const modelLabel=(provider,value)=>aiModels(provider).find(o=>o.value===(value||''))?.label||value||'default model';
const workerLabel=m=>m.provider+' · '+modelSummary(m.provider,m.model,m.model_max,m.effort);
// An unavailable token count is shown as unknown; it is never displayed as zero.
const tok=n=>typeof n==='number'?(n>=1000?(n/1000).toFixed(1)+'k':String(n)):'—';
// Input as a reader means it: fresh prompt tokens plus tokens written to the cache.
const inputTokens=e=>{const parts=[e.input_tokens,e.cache_write_5m_tokens,e.cache_write_1h_tokens]
.filter(n=>typeof n==='number');return parts.length?parts.reduce((a,b)=>a+b,0):null};
const money=(v,partial)=>typeof v==='number'?'≈$'+v.toFixed(4)+(partial?' +':''):'n/a';
const DYNAMIC='dynamic';
const catalogGroups=chosen=>['codex','claude'].map(p=>{const entries=aiModels(p).filter(o=>o.value);return entries.length?`<optgroup label="${esc(p)}">${entries.map(o=>option(o.value,o.label+(o.price_hint?' · '+o.price_hint:''),chosen)).join('')}</optgroup>`:''}).join('');
function modelOptions(current){const known=[DYNAMIC,...['codex','claude'].flatMap(p=>aiModels(p).map(o=>o.value))],chosen=current&&!known.includes(current)?'__custom__':(current||'');
return option(DYNAMIC,'Dynamic · cheapest model that fits each call',chosen)+option('','CLI default for the selected worker',chosen)+catalogGroups(chosen)+option('__custom__','Custom model id…',chosen)}
// The ceiling for Dynamic: empty means the strongest model this console lists.
const maxModelOptions=current=>option('','Strongest listed model',current||'')+catalogGroups(current||'')+(current&&!['codex','claude'].some(p=>aiModels(p).some(o=>o.value===current))?option(current,current,current):'');
// How a mission or run describes the model it asked for.
const modelSummary=(provider,model,modelMax,effort)=>model===DYNAMIC
?'Dynamic · up to '+(modelMax?modelLabel(provider,modelMax):'the strongest listed model')
:modelLabel(provider,model)+' · '+(effort||'low');
function aiCell(r){if(!r.provider||r.provider==='none')return '<span class="muted">No AI</span>';const t=r.ai_totals||{};
if(!t.calls)return `<span class="muted">${r.ai_calls||0} calls</span>`;
return `${esc((t.models||[]).join(', ')||(r.ai_model?modelSummary(r.provider,r.ai_model,r.ai_model_max,r.ai_effort):'default model'))}<small>${tok(t.input_tokens)} in / ${tok(t.output_tokens)} out · ${money(t.est_cost_usd,t.cost_partial)}</small>`}
function aiUsage(r){const u=r.ai_usage||[],t=r.ai_totals||{};if(!u.length)return '';
const row=e=>`<tr><td>${e.call}</td><td>${esc((e.purpose||'reasoning')+(e.step!=null?' '+(e.step+1):''))}${e.error?`<small class="error">${esc(e.error)}</small>`:''}</td><td>${esc(e.model_reported||e.model_requested||'unknown')}</td><td>${esc(e.effort||'')}</td><td>${tok(inputTokens(e))}</td><td>${tok(e.cached_tokens)}</td><td>${tok(e.output_tokens)}</td><td>${((e.wall_ms||0)/1000).toFixed(1)} s</td><td>${money(e.est_cost_usd)}</td></tr>`;
return `<section class="section"><h2>AI usage <span class="muted">${u.length} calls</span>${copyButton(aiUsageText(r),'the AI usage')}</h2><div class="tablewrap"><table class="usage"><thead><tr><th>#</th><th>Purpose</th><th>Model reported</th><th>Effort</th><th>Input</th><th>Cached</th><th>Output</th><th>Time</th><th>Estimate</th></tr></thead><tbody>${u.map(row).join('')}<tr class="totals"><td></td><td><strong>Total</strong></td><td>${esc((t.models||[]).join(', '))}</td><td></td><td>${tok(t.input_tokens)}</td><td>${tok(t.cached_tokens)}</td><td>${tok(t.output_tokens)}</td><td></td><td>${money(t.est_cost_usd,t.cost_partial)}</td></tr></tbody></table></div><p class="muted">Input counts fresh prompt tokens plus tokens written to the prompt cache; cached counts cache hits. Estimate at published standard API prices. Runs use your Codex/Claude subscription; nothing is billed per call here.</p></section>`}
function select(name,title,options,help=''){return `<div class="field"><label for="${name}">${title}</label><select id="${name}" name="${name}">${options}</select>${help?`<small>${help}</small>`:''}</div>`}
// Where apps come from is the question every first Android mission asks; answer it under the picker.
const targetHelp=available=>{const base='Websites and Android apps are managed under <a href="#settings">Settings</a>.';if(!available.some(t=>t.type==='android'))return base+' To test an app, add it there with its APK.';return health.android?.available?base:base+' Android runs are not ready: '+esc(health.android?.reason||'')};
// --- Scenario builder ---------------------------------------------------------
// The rows and the YAML are two spellings of one normalized list of steps. The server
// owns the spelling, so YAML is adopted only after it has parsed there. One vocabulary
// runs on an Android device and in a browser page; the target decides which.
const STEP_KINDS={goal:'Goal for the AI worker',check:'Check a fact',hold:'Hold a fact',event:'Do something to the app',manual:'Ask the operator'};
const EVENT_KINDS={route:'Change the way out',network:'Switch transport',speed:'Shape link speed',delay_ms:'Add network delay',wait:'Wait',home:'Send to the background',kill:'Kill the app / drop the page',back:'Go back',relaunch:'Start again',deep_link:'Open a link',open_notification:'Open a notification'};
const ORACLE_KINDS={text:'Text is on screen',text_absent:'Text is not on screen',screen:'Screen (activity or page address)',playing:'Playback',notification:'Notification posted',no_crash:'No crash or ANR'};
const EVENT_DEFAULT={route:'direct',network:'wifi',speed:'edge',delay_ms:300,wait:10,home:true,kill:true,back:true,relaunch:true,deep_link:'https://',open_notification:''};
const ORACLE_DEFAULT={text:'',text_absent:'',screen:{contains:''},playing:true,notification:{text:'',present:true},no_crash:true};
const routeName=id=>id==='direct'?'Direct connection':((state.egresss||[]).find(e=>e.id===id)?.name||'missing route '+id);
// A route the operator picked and then deleted stays visible as wrong; it never becomes direct on its own.
const routeOptions=v=>option('direct','Direct connection',v)+(state.egresss||[]).map(e=>option(e.id,e.name,v)).join('')+(v&&v!=='direct'&&!(state.egresss||[]).some(e=>e.id===v)?option(v,'Missing route '+v,v):'');
const NETWORKS={wifi:'Wi-Fi only',cellular:'Mobile data only',offline:'Nothing connected',restore:'Back to what it was'};
const SPEED_NAMES={edge:'edge',gsm:'gsm',umts:'umts',lte:'lte',full:'full'};
const PLACE=/<[^<>]{0,120}>/;
let scenarioSteps=[],scenarioPresets=null,pendingJourney='',journeySearch='';
// What a card promises before it is opened: the work in it, and the blanks it asks for.
const journeySize=p=>`${p.mission.scenario.length} steps · ${p.blanks.length} blank${p.blanks.length===1?'':'s'}`;
const clone=v=>JSON.parse(JSON.stringify(v));
// A step or oracle is named by the key it carries, even while that key is still blank.
const stepKind=s=>Object.keys(STEP_KINDS).find(k=>s[k]!==undefined)||'goal';
const eventKind=e=>Object.keys(EVENT_KINDS).find(k=>e&&e[k]!==undefined)||'network';
const oracleKind=o=>Object.keys(ORACLE_KINDS).find(k=>o&&o[k]!==undefined)||'text';
const blankStep=k=>k==='goal'?{goal:''}:k==='manual'?{manual:'',timeout:300}:k==='event'?{event:{network:'wifi'}}:k==='check'?{check:{text:'',within:10}}:{hold:{text:'',for:10}};
// Windows and operator timeouts are maximums; only waits and holds commit real time.
function scenarioBudget(steps){let committed=0,ceiling=0;
for(const s of steps){const k=stepKind(s);
if(k==='hold')committed+=+s.hold.for||10;
else if(k==='event')committed+=+s.event.wait||0;
else if(k==='check')ceiling+=+s.check.within||10;
else if(k==='manual')ceiling+=+s.timeout||300;
else ceiling+=60}
return {committed,ceiling:committed+ceiling+60}}
// One readable line per step, used in the draft preview and anywhere a scenario is summarised.
function describeStep(s){const k=stepKind(s);
if(k==='goal')return 'Goal: '+s.goal+(s.until&&s.until.text?' · stops early at "'+s.until.text+'"':'');
if(k==='manual')return 'Operator: '+s.manual+(s.ask?' · asks for '+s.ask:'')+' · up to '+(s.timeout||300)+' s';
if(k==='event'){const e=eventKind(s.event),v=s.event[e];
if(e==='route')return 'Event: '+EVENT_KINDS.route+' · '+routeName(v)+(s.event.speed?' · '+s.event.speed:'')+(s.event.delay_ms?' · +'+s.event.delay_ms+' ms':'');
return 'Event: '+EVENT_KINDS[e]+(typeof v==='boolean'?'':' · '+v)+(e==='speed'&&s.event.delay_ms?' · +'+s.event.delay_ms+' ms':'')}
const o=s[k],f=oracleKind(o),v=f==='screen'?(o.screen.contains||o.screen.equals):f==='notification'?o.notification.text+(o.notification.present===false?' (must be absent)':''):typeof o[f]==='boolean'?(o[f]?'yes':'no'):o[f];
return (k==='check'?'Check':'Hold')+' · '+ORACLE_KINDS[f]+': '+v+' · '+(k==='check'?(o.within||10)+' s window':(o.for||10)+' s throughout')+(o.policy==='unknown'?' · observation only':'')}
function setPath(target,path,value){const parts=path.split('.');
while(parts.length>1)target=(target[parts.shift()]??={});
if(value===null)delete target[parts[0]];else target[parts[0]]=value}
function pruneStep(step){if(step.until&&!step.until.text)delete step.until;
if(step.event&&step.event.speed==='')delete step.event.speed;
if(step.name==='')delete step.name;
if(step.ask==='')delete step.ask;
for(const k of ['check','hold']){const o=step[k];if(o&&o.policy==='unknown')o.required=false}
return step}
function applyControl(step,el){const value=el.dataset.bool?el.value==='true':el.type==='number'?(el.value===''?null:+el.value):el.value;
setPath(step,el.dataset.path,value);pruneStep(step)}
const cell=(title,inner,cls='')=>`<label class="cell ${cls}"><span>${esc(title)}</span>${inner}</label>`;
const inp=(i,path,value,title,placeholder='',cls='wide',type='text')=>cell(title,`<input type="${type}" ${type==='number'?'step="1" min="0"':''} dir="auto" data-index="${i}" data-path="${path}" value="${esc(value??'')}" placeholder="${esc(placeholder)}"${PLACE.test(String(value??''))?' class="ph"':''}>`,cls);
const pick=(i,path,title,options,cls='',bool=false)=>cell(title,`<select data-index="${i}" data-path="${path}"${bool?' data-bool="1"':''}>${options}</select>`,cls);
const act=(i,name,title,options,cls='')=>cell(title,`<select data-index="${i}" data-act="${name}">${options}</select>`,cls);
const BOOLS=v=>option('true','Yes',String(v))+option('false','No',String(v));
function eventBody(step,i){const e=step.event,k=eventKind(e),v=e[k];
const kinds=act(i,'event-kind','Operation',Object.entries(EVENT_KINDS).map(([x,t])=>option(x,t,k)).join(''),'wide');
if(k==='route')return kinds+pick(i,'event.route','Way out',routeOptions(v),'wide')
+pick(i,'event.speed','Link speed while routed (optional)',option('','Leave it as it is',e.speed||'')+Object.keys(SPEED_NAMES).map(x=>option(x,x,e.speed||'')).join(''),'narrow')
+inp(i,'event.delay_ms',e.delay_ms,'Added delay in ms (optional)','','narrow','number');
if(k==='network')return kinds+pick(i,'event.network','Transport',Object.entries(NETWORKS).map(([x,t])=>option(x,t,v)).join(''));
if(k==='speed')return kinds+pick(i,'event.speed','Emulator link speed',Object.keys(SPEED_NAMES).map(x=>option(x,x,v)).join(''))+inp(i,'event.delay_ms',e.delay_ms,'Added delay in ms (optional)','','narrow','number');
if(k==='delay_ms')return kinds+inp(i,'event.delay_ms',v,'Delay in milliseconds','','narrow','number');
if(k==='wait')return kinds+inp(i,'event.wait',v,'Seconds to wait','','narrow','number');
if(k==='deep_link')return kinds+inp(i,'event.deep_link',v,'HTTPS link','https://example.com/title/1');
if(k==='open_notification')return kinds+inp(i,'event.open_notification',v,'Text on the notification this app posted','Download finished');
return kinds+`<p class="cell wide muted">${esc({home:'Sends the app to the home screen, or brings another tab in front of the page.',kill:'Lets the system reclaim the backgrounded app, or drops the page to a blank one. Stored data survives; whatever was only in memory does not.',back:'Presses the system back button, or takes the page back one entry in its history.',relaunch:'Force-stops the app and starts it again, or brings the page back and reloads it. Stored data is untouched.'}[k])}</p>`}
function oracleBody(step,kind,i){const o=step[kind],f=oracleKind(o),p=kind+'.';
const kinds=act(i,'oracle-kind','Fact',Object.entries(ORACLE_KINDS).map(([x,t])=>option(x,t,f)).join(''),'wide');
let fact;
if(f==='text'||f==='text_absent')fact=inp(i,p+f,o[f],f==='text'?'Text that must be readable':'Text that must not be there','Now playing');
else if(f==='screen'){const mk=o.screen.equals?'equals':'contains';
fact=act(i,'match-kind','Match',option('contains','contains',mk)+option('equals','equals',mk),'narrow')+inp(i,p+'screen.'+mk,o.screen[mk],'Activity name on a device, page address on the web','com.example.app/.PlayerActivity');}
else if(f==='playing')fact=pick(i,p+'playing','MediaSession reports playback',BOOLS(o.playing),'',true);
else if(f==='notification')fact=inp(i,p+'notification.text',o.notification.text,'Text on the notification','Download finished')+pick(i,p+'notification.present','Must be',option('true','Posted now',String(o.notification.present!==false))+option('false','Not posted',String(o.notification.present!==false)),'narrow',true);
else fact=`<p class="cell wide muted">No fatal exception or ANR attributed to this app since the last goal or event.</p>`;
const unknown=o.policy==='unknown';
return kinds+fact
+inp(i,kind==='check'?p+'within':p+'for',kind==='check'?o.within:o.for,kind==='check'?'Window in seconds':'Seconds throughout','','narrow','number')
+pick(i,p+'policy','Expected behaviour',option('confirmed','Confirmed',o.policy||'confirmed')+option('unknown','Nobody has confirmed it',o.policy||'confirmed'),'narrow')
+pick(i,p+'severity','If contradicted',['P1','P2','P3','info'].map(x=>option(x,x,unknown?'info':(o.severity||'P2'))).join(''),'narrow')
+cell('Later steps',`<select data-index="${i}" data-path="${p}required" data-bool="1" ${unknown?'disabled':''}>${option('true','Stop if this fails',String(o.required!==false))+option('false','Keep going',String(o.required!==false))}</select>`,'narrow')
+(unknown?`<p class="cell wide muted">An unconfirmed expectation is recorded as an observation: severity info, no score deduction, never release-blocking.</p>`:'')}
function stepBody(step,kind,i){
if(kind==='goal')return inp(i,'goal',step.goal,'What the AI worker should achieve on the screen','Open the downloads list and start the saved title')+inp(i,'until.text',step.until&&step.until.text,'Stop early when this text appears (optional)','Now playing');
if(kind==='manual')return inp(i,'manual',step.manual,'What the operator should do','Sign in as the second account')
+cell('Value they supply, by name (optional)',`<input maxlength="80" dir="auto" data-index="${i}" data-path="ask" value="${esc(step.ask||'')}" placeholder="one-time code">`,'narrow')
+inp(i,'timeout',step.timeout,'Seconds they have','','narrow','number')+`<p class="cell wide muted">No screenshots are taken while this step waits. On a device the screen recording stops too, so credentials stay off the evidence. Name the value the operator supplies; never write the value here.</p>`;
if(kind==='event')return eventBody(step,i);
return oracleBody(step,kind,i)}
function stepRow(step,i,total){const kind=stepKind(step);
return `<li class="step" data-index="${i}"><div class="stephead"><span class="stepno">${i+1}</span>
<select aria-label="Kind of step ${i+1}" data-index="${i}" data-act="kind">${Object.entries(STEP_KINDS).map(([k,t])=>option(k,t,kind)).join('')}</select>
<input aria-label="Label for step ${i+1}" placeholder="Label, optional" dir="auto" data-index="${i}" data-path="name" value="${esc(step.name||'')}">
<span class="stepacts"><button type="button" class="compact" data-index="${i}" data-act="up" ${i?'':'disabled'} aria-label="Move step ${i+1} earlier">Up</button><button type="button" class="compact" data-index="${i}" data-act="down" ${i<total-1?'':'disabled'} aria-label="Move step ${i+1} later">Down</button><button type="button" class="compact" data-index="${i}" data-act="dup" aria-label="Duplicate step ${i+1}">Duplicate</button><button type="button" class="compact danger" data-index="${i}" data-act="del" aria-label="Remove step ${i+1}">Remove</button></span></div>
<div class="stepbody">${stepBody(step,kind,i)}</div></li>`}
function scenarioSection(m){scenarioSteps=clone(m.scenario||[]);
const start=m.snapshot?'snapshot':m.reset==='keep'?'keep':'fresh';
const radio=(v,t,help)=>`<label id="start-${v}"><input type="radio" name="start_state" value="${v}" ${start===v?'checked':''}><span>${t}<small>${help}</small></span></label>`;
return `<section class="field full scenario" id="scenario-section"><label>Steps</label>
<small>Ordered steps one tester would carry out, once the app or the page is open. The goal above still says why. Leave this empty to run the goal on its own.</small>
<div class="blanks" id="scenario-blanks" hidden></div>
<div class="toolbar" id="scenario-modes"><button type="button" class="compact" id="edit-steps" aria-expanded="false" aria-controls="scenario-steps">Edit steps</button><span id="scenario-summary" class="muted" aria-live="polite"></span></div>
<ol class="steplines" id="scenario-lines"></ol>
<ol class="steps" id="scenario-steps" hidden></ol>
<div class="toolbar" id="step-tools" hidden><button type="button" class="compact" id="add-step">Add a step</button></div>
<fieldset class="startstate"><legend>Start state</legend><div class="checks">${radio('fresh','Fresh app data','App data or browser storage is cleared first. This is not a reinstall and changes nothing on the server.')}${radio('keep','Keep previous app data','Whatever the last run left behind stays. Replays cannot confirm a reproduction from it.')}${radio('snapshot','Load a saved device state','Same saved device state. Account and server preconditions are still checked by the steps.')}</div>
<div class="field" id="snapshot-field"><label for="snapshot_id">Saved device state</label><select id="snapshot_id" name="snapshot_id"></select><small id="snapshot-note">Reading what is saved on this Mac…</small></div></fieldset>
<details id="scenario-more"><summary><strong>Other ways to get steps</strong></summary><div class="scenariotools">
<details id="scenario-presets"><summary><strong>Start from a shipped journey</strong></summary><div id="preset-body">Loading the shipped journeys…</div></details>
<details id="scenario-draft"><summary><strong>Describe it and let the AI worker draft the steps</strong></summary><div class="draftbody">
<textarea id="scenario-describe" dir="auto" placeholder="Download a title on a shaped connection, pause and resume it twice, then play it with the device offline."></textarea>
<input id="scenario-texts" dir="auto" placeholder="Text that really appears in your app, separated by commas">
<div class="toolbar"><button type="button" class="compact" id="draft-steps">Draft the steps</button><small>Nothing runs and no device is touched. Every drafted step is checked against the same contract as the rows.</small></div>
<div id="draft-result" aria-live="polite"></div></div></details>
<details id="scenario-yaml-box"><summary>Advanced: edit as YAML</summary><textarea id="scenario-yaml" spellcheck="false" aria-describedby="scenario-yaml-error"></textarea><div class="toolbar"><button type="button" class="compact primary" id="yaml-apply">Apply YAML</button><small>Comments are not kept. The rows come back only once this parses.</small></div><p class="error" id="scenario-yaml-error" role="alert"></p></details>
</div></details></section>`}
// The scenario section, bound. Callers get back only what they actually need: a way to put
// other steps in, the blanks, the one unapplied-YAML question, and where to send focus.
function scenarioBind(mf,sync,gate){const box=$('#scenario-section');if(!box)return null;
const list=$('#scenario-steps'),summary=$('#scenario-summary'),tools=$('#step-tools'),runButton=mf.querySelector('[name=run]');
const lines=$('#scenario-lines'),editButton=$('#edit-steps'),more=$('#scenario-more');
const yamlBox=$('#scenario-yaml-box'),yamlArea=$('#scenario-yaml'),yamlError=$('#scenario-yaml-error');let appliedYaml='';
const limit=()=>+mf.querySelector('[name=max_seconds]').value||0;
const blanksBox=$('#scenario-blanks'),nameField=mf.querySelector('[name=name]'),goalField=mf.querySelector('[name=goal]');
// A blank is <angle-bracketed> text anywhere the author can still read it: the name, the goal, the steps.
const written=()=>[nameField,goalField].filter(Boolean).map(f=>f.value).join(' ')+' '+JSON.stringify(scenarioSteps);
const blanksLeft=()=>[...new Set(written().match(/<[^<>]{0,120}>/g)||[])];
const fill=(blank,value)=>{
// The steps are JSON here, so the replacement is escaped the way JSON spells it.
scenarioSteps=JSON.parse(JSON.stringify(scenarioSteps).split(blank).join(JSON.stringify(value).slice(1,-1)));
for(const f of [nameField,goalField])if(f)f.value=f.value.split(blank).join(value);
draw()};
const drawBlanks=()=>{const left=blanksLeft();blanksBox.hidden=!left.length;
if(!left.length){blanksBox.innerHTML='';return left}
blanksBox.innerHTML=`<strong>${left.length} blank${left.length===1?'':'s'} to fill</strong><small>Each one is replaced everywhere it appears: the mission name, the goal and every step.</small>`
+left.map(b=>cell(b.slice(1,-1),`<input dir="auto" data-blank="${esc(b)}" placeholder="What it is in your product">`,'wide')).join('');
blanksBox.querySelectorAll('[data-blank]').forEach(el=>el.onchange=()=>{const v=el.value.trim();if(v)fill(el.dataset.blank,v)});
return left};
// A journey is worth no less time than its own windows need, and never more than the ceiling.
const fitLimit=()=>{const f=mf.querySelector('[name=max_seconds]');
f.value=Math.min(3600,Math.max(+f.value||0,Math.ceil(scenarioBudget(scenarioSteps).ceiling/60)*60))};
// Rows, readable lines and YAML are three spellings of one scenario; exactly one is on screen.
let editing=false;
const present=()=>{const yaml=yamlBox.open;
lines.hidden=yaml||editing;list.hidden=yaml||!editing;tools.hidden=list.hidden;
editButton.disabled=yaml;editButton.setAttribute('aria-expanded',String(editing&&!yaml));
editButton.textContent=editing?'Done editing steps':'Edit steps'};
// Anything that focuses a row has to put the rows on screen first.
const revealEditor=()=>{yamlBox.open=false;editing=true;present()};
const summarise=()=>{const b=scenarioBudget(scenarioSteps),over=b.committed>=limit(),left=blanksLeft().length;
// The server refuses a mission that still has a blank; this only says so sooner. Saving is
// decided in one place, so this can never re-enable a button another rule disabled.
if(gate)gate();
summary.innerHTML=(left?`<strong class="error">${left} blank${left===1?'':'s'} left</strong> · `:'')+(scenarioSteps.length
?`${scenarioSteps.length} step${scenarioSteps.length===1?'':'s'} · waits and holds commit ${b.committed} s · up to about ${b.ceiling} s if every window runs out, against a ${limit()} s limit`
+(b.ceiling>limit()?` <button type="button" class="compact" id="raise-limit">Raise the limit to ${Math.min(3600,Math.ceil(b.ceiling/60)*60)} s</button>`:'')
+(over?'<br><strong class="error">The waits and holds alone need more time than the limit allows. This mission cannot be saved until the limit is higher.</strong>':'')
:'');
const raise=$('#raise-limit');
if(raise)raise.onclick=()=>{mf.querySelector('[name=max_seconds]').value=Math.min(3600,Math.ceil(scenarioBudget(scenarioSteps).ceiling/60)*60);summarise();$('#add-step').focus()};
if(runButton)runButton.textContent=scenarioSteps.length?`Save and run ${scenarioSteps.length} steps`:'Save and run'};
// The readable list and the rows are drawn from the same steps, so neither can drift.
const drawLines=()=>{lines.innerHTML=scenarioSteps.map(step=>`<li dir="auto">${esc(describeStep(step))}</li>`).join('')
||'<li class="nosteps muted">No steps yet. This mission runs the goal on its own.</li>'};
const draw=()=>{list.innerHTML=scenarioSteps.map((s,i)=>stepRow(s,i,scenarioSteps.length)).join('')
||'<li class="nosteps muted">No steps yet. Add one, start from a shipped journey, or describe what you want.</li>';drawLines();drawBlanks();summarise();present()};
editButton.onclick=()=>{editing=!editing;present();
(editing?list.querySelector('input,select')||$('#add-step'):editButton).focus()};
for(const f of [nameField,goalField])if(f)f.addEventListener('input',()=>{drawBlanks();summarise()});
// A value edit changes one field; anything that changes which fields exist redraws the rows.
list.onchange=e=>{const el=e.target,i=+el.dataset.index;if(!Number.isInteger(i)||!scenarioSteps[i])return;
const step=scenarioSteps[i];
// Editing a value touches one field; only the policy changes which fields are usable.
if(el.dataset.path){applyControl(step,el);el.classList.toggle('ph',el.tagName==='INPUT'&&PLACE.test(el.value));
// Only the policy changes which fields exist; everything else keeps the focused row where it is.
if(el.dataset.path.endsWith('policy')){draw();return}
drawLines();drawBlanks();summarise();return}
if(el.dataset.act==='kind')scenarioSteps[i]=pruneStep({...(step.name?{name:step.name}:{}),...blankStep(el.value)});
if(el.dataset.act==='event-kind')step.event={[el.value]:EVENT_DEFAULT[el.value]};
if(el.dataset.act==='oracle-kind'){const kind=stepKind(step),o=step[kind];
for(const f of Object.keys(ORACLE_KINDS))delete o[f];o[el.value]=clone(ORACLE_DEFAULT[el.value])}
if(el.dataset.act==='match-kind'){const o=step[stepKind(step)].screen,kept=o.contains||o.equals;step[stepKind(step)].screen={[el.value]:kept}}
draw()};
list.onclick=e=>{const button=e.target.closest('button[data-act]');if(!button)return;
const i=+button.dataset.index,what=button.dataset.act;
if(what==='up'&&i)scenarioSteps.splice(i-1,0,scenarioSteps.splice(i,1)[0]);
if(what==='down'&&i<scenarioSteps.length-1)scenarioSteps.splice(i+1,0,scenarioSteps.splice(i,1)[0]);
if(what==='dup'&&scenarioSteps.length<40)scenarioSteps.splice(i+1,0,clone(scenarioSteps[i]));
if(what==='del')scenarioSteps.splice(i,1);
draw();
// Keyboard users stay on the step they just moved, not at the top of the list.
const landed=what==='up'?i-1:what==='down'||what==='dup'?i+1:Math.min(i,scenarioSteps.length-1);
const row=list.querySelector(`li[data-index="${landed}"]`);
(row&&(what==='del'?row.querySelector('select'):row.querySelector(`button[data-act="${what}"]`))||$('#add-step')).focus()};
$('#add-step').onclick=()=>{if(scenarioSteps.length>=40){toast('A scenario holds at most 40 steps');return}
scenarioSteps.push(blankStep('goal'));revealEditor();draw();list.querySelector('li:last-child input[data-path="goal"]')?.focus()};
// --- shipped journeys -------------------------------------------------------
const usePreset=preset=>{const mission=preset.mission;scenarioSteps=clone(mission.scenario||[]);
const goal=mf.querySelector('[name=goal]');if(goal&&mission.goal)goal.value=mission.goal;
const name=mf.querySelector('[name=name]');if(name&&!name.value.trim())name.value=preset.name;
for(const key of ['mode','max_seconds','ai_budget','provider']){const input=mf.querySelector(`[name=${key}]`);if(input&&mission[key]!=null)input.value=mission[key]}
mf.querySelectorAll('[name=pillars]').forEach(c=>c.checked=(mission.pillars||[]).includes(c.value));
const start=mission.snapshot?'snapshot':mission.reset==='keep'?'keep':'fresh';
mf.querySelectorAll('[name=start_state]').forEach(r=>r.checked=r.value===start);
sync();startState();fitLimit();revealEditor();draw();$('#scenario-presets').open=false;
const left=blanksLeft().length;
toast(left?`Journey loaded. Fill ${left} blank${left===1?'':'s'} before saving.`:'Journey loaded.');
(blanksBox.querySelector('input')||list.querySelector('input,select'))?.focus()};
const drawPresets=()=>{const body=$('#preset-body');
body.innerHTML=scenarioPresets.map((p,i)=>`<div class="preset"><div><strong>${esc(p.name)}</strong><small dir="auto">${esc(p.about)}</small></div><div class="presetact"><span class="badge">${journeySize(p)}</span><button type="button" class="compact" data-preset="${i}">Use this journey</button></div></div>`).join('');
body.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>usePreset(scenarioPresets[+b.dataset.preset]));
// The same shipped journeys, offered as sentences to start from rather than steps to load.
const starters=$('#idea-starters'),idea=$('#mission-idea');
if(starters&&idea){starters.innerHTML=scenarioPresets.slice(0,4).map((p,i)=>`<button type="button" class="compact" data-starter="${i}" dir="auto">${esc(p.name)}</button>`).join('');
starters.querySelectorAll('[data-starter]').forEach(b=>b.onclick=()=>{const p=scenarioPresets[+b.dataset.starter];
idea.value=p.about||p.name;idea.focus()})}
// Arriving from the gallery: pick the target this journey suits, then load it.
if(pendingJourney){const wanted=scenarioPresets.find(p=>p.id===pendingJourney);pendingJourney='';
 if(wanted){const mine=(state.targets||[]).filter(t=>t.project_id===mf.querySelector('[name=project_id]').value);
  const operator=(wanted.needs||[]).join(' ').toLowerCase().includes('operator');
  const chosen=(operator&&mine.find(t=>t.type==='android'))||mine[0],picker=mf.querySelector('[name=target_id]');
  if(chosen&&picker){picker.value=chosen.id;sync(true)}
  usePreset(wanted)}}};
if(scenarioPresets)drawPresets();
else api('/scenarios').then(found=>{scenarioPresets=found;drawPresets()}).catch(e=>$('#preset-body').innerHTML=`<p class="error">${esc(e.message)}</p>`);
// --- start state ------------------------------------------------------------
// Declared, not assigned: a journey deep link runs usePreset while this section is still being bound.
function chosen(){return [...mf.querySelectorAll('[name=start_state]')].find(r=>r.checked)?.value||'fresh'}
function startState(){$('#snapshot-field').hidden=chosen()!=='snapshot'}
mf.querySelectorAll('[name=start_state]').forEach(r=>r.onchange=startState);startState();
const picker=mf.querySelector('[name=snapshot_id]'),note=$('#snapshot-note'),saved=mf.dataset.snapshot||'';
api('/android/snapshots?project='+encodeURIComponent(mf.querySelector('[name=project_id]').value)).then(answer=>{
const found=answer.snapshots||[],usable=found.filter(s=>s.available);
picker.innerHTML=found.map(s=>`<option value="${esc(s.id)}" ${s.id===saved?'selected':''} ${s.available?'':'disabled'}>${esc(s.name)} · saved ${esc(date(s.created_at))}${s.available?'':' · '+esc(s.note)}</option>`).join('')||option('','Nothing saved on this Mac yet','');
const radio=[...mf.querySelectorAll('[name=start_state]')].find(r=>r.value==='snapshot');
radio.disabled=!usable.length;
note.textContent=usable.length?'A saved state restores this Mac\'s emulator only. Account and server preconditions are still checked by the steps.':'Save a device state under Settings first.';
if(!usable.length&&chosen()==='snapshot'){mf.querySelector('[name=start_state][value=keep]').checked=true;startState()}})
.catch(e=>{[...mf.querySelectorAll('[name=start_state]')].find(r=>r.value==='snapshot').disabled=true;note.textContent=e.message});
// --- drafting ---------------------------------------------------------------
const draftButton=$('#draft-steps'),draftOut=$('#draft-result');
draftButton.onclick=async()=>{const description=$('#scenario-describe').value.trim()||(goalField?.value||'').trim();
if(description.length<10){draftOut.innerHTML='<p class="error">Describe the journey in a sentence or two first, or write the goal above.</p>';$('#scenario-describe').focus();return}
const original=draftButton.textContent;draftButton.disabled=true;draftButton.textContent='Asking the AI worker…';
draftOut.innerHTML='<div class="skeleton"></div>';
try{const answer=await api('/scenarios/draft',{method:'POST',body:JSON.stringify({
project_id:mf.querySelector('[name=project_id]').value,target_id:mf.querySelector('[name=target_id]').value,
build:mf.querySelector('[name=build]').value,description,
texts:$('#scenario-texts').value.split(',').map(s=>s.trim()).filter(Boolean),
provider:mf.querySelector('[name=provider]').value,codex_account:mf.querySelector('[name=codex_account]')?.value||''})});
const drafted=answer.steps;
draftOut.innerHTML=`<p><strong>${drafted.length} drafted step${drafted.length===1?'':'s'}.</strong> Nothing has changed yet.</p><ol class="draftlines">${drafted.map(s=>`<li dir="auto">${esc(describeStep(s))}</li>`).join('')}</ol>${answer.rejected&&answer.rejected.length?`<p class="muted">${answer.rejected.length} suggestion${answer.rejected.length===1?'':'s'} did not fit the contract and ${answer.rejected.length===1?'was':'were'} dropped: ${esc(answer.rejected.join('; '))}</p>`:''}<div class="toolbar"><button type="button" class="compact primary" id="draft-replace">Replace the ${scenarioSteps.length} step${scenarioSteps.length===1?'':'s'} above</button><button type="button" class="compact" id="draft-append">Add these to the end</button></div>`;
$('#draft-replace').onclick=()=>{scenarioSteps=clone(drafted);fitLimit();revealEditor();draw();toast('Steps replaced. Review every one before saving.');list.querySelector('input,select')?.focus()};
$('#draft-append').onclick=()=>{scenarioSteps=scenarioSteps.concat(clone(drafted)).slice(0,40);fitLimit();draw();toast('Steps added. Review every one before saving.')};
draftButton.textContent='Draft again'}
catch(e){draftOut.innerHTML=`<p class="error">${esc(e.message)}</p>`;draftButton.textContent=original}
finally{draftButton.disabled=false}};
// --- YAML, the same steps in the other spelling ------------------------------
let reopening=false;
yamlBox.ontoggle=async()=>{
if(!yamlBox.open){
  // Unapplied text is not a scenario, so the rows do not come back until it parses.
  if(yamlArea.value.trim()!==appliedYaml.trim()){reopening=true;yamlBox.open=true;yamlError.textContent='These edits are not applied yet. Select Apply YAML, or undo them, before going back to the rows.';yamlArea.focus();return}
  present();yamlError.textContent='';return}
// Forcing the editor back open must not refetch over the edits that kept it open.
if(reopening){reopening=false;return}
yamlError.textContent='';yamlArea.value='Reading…';
// Steps that cannot be spelled yet leave the rows in place, because the rows are where the gap is fixed.
try{appliedYaml=yamlArea.value=(await api('/scenarios/yaml',{method:'POST',body:JSON.stringify({steps:scenarioSteps})})).yaml;present()}
catch(e){yamlArea.value=appliedYaml='';yamlError.textContent=e.message}};
$('#yaml-apply').onclick=()=>submitAction($('#yaml-apply'),async()=>{yamlError.textContent='';
try{const answer=await api('/scenarios/yaml',{method:'POST',body:JSON.stringify({yaml:yamlArea.value})});
scenarioSteps=answer.steps;appliedYaml=yamlArea.value=answer.yaml;draw();
toast(`${answer.steps.length} step${answer.steps.length===1?'':'s'} applied`)}
catch(e){yamlError.textContent=e.message;yamlArea.focus()}});
mf.querySelector('[name=max_seconds]').addEventListener('change',summarise);
draw();
return {
 // Other steps, drawn everywhere they show. Undo restores exact values, so it skips the fit.
 replace(steps,{fit=true}={}){scenarioSteps=clone(steps||[]);if(fit)fitLimit();draw()},
 blanks:()=>blanksLeft().length,
 // Unapplied text is not a scenario, so nothing may replace the steps while it sits there.
 dirtyYaml:()=>yamlBox.open&&yamlArea.value.trim()!==appliedYaml.trim(),
 showYaml(){more.open=true;yamlBox.open=true;yamlArea.focus()},
 focusBlank(){const first=blanksBox.querySelector('input');if(first)first.focus();return !!first}}}
function missionForm(id){const site=project(),host=(()=>{try{return new URL(site.url||'').hostname}catch(e){return ''}})(),existing=state.missions.find(m=>m.id===id);
const available=(state.targets||[]).filter(t=>t.project_id===(existing?.project_id||workspace)),fallback=available[0];
const m=existing||{project_id:workspace,target_id:fallback?.id||'',platform:fallback?.type||'web',build:'',device:health.android?.avd||'',visibility:'team',name:'',url:fallback?.url||site.url||'',goal:'',success_text:'',allowed_domains:fallback?.allowed_domains||site.allowed_domains||[host].filter(Boolean),provider:'codex',codex_account:'',model:DYNAMIC,model_max:'',effort:'low',mode:'journey',browser:'chromium',viewport:'desktop',network:'baseline',locale:'fa-IR',release:'live',competitors:[],max_steps:6,max_seconds:600,ai_budget:10,observe_seconds:0,pillars:Object.keys(label)};
// The extra settings open by themselves when this mission already uses one of them.
const extras=!!(m.persona_id||m.login_identifier||m.egress_id||m.success_text||m.observe_seconds||m.auto_replay||(m.locale&&m.locale!=='fa-IR')||(m.release&&m.release!=='live'));
// An idea is where a brand-new mission starts. A journey link or a saved mission already has a draft.
const fresh=!id&&!pendingJourney;
const worker=['codex','claude'].find(p=>health.ai?.[p]?.logged_in)||'';
return head(id?'Edit mission':'New mission','Describe what you want to find out, then review the mission before it runs.','<a class="button" href="#missions">Back</a>')+`<form id="mission-form" data-id="${id||''}" data-snapshot="${esc(m.snapshot||'')}"><div class="formgrid">${select('target_id','Target',available.map(t=>option(t.id,`${t.type==='android'?'Android app':'Website'} · ${t.name}`,m.target_id)).join(''),targetHelp(available))}${field('url','Start URL or optional HTTPS deep link',m.url,'url')}${select('build','App build',option('','Latest non-archived',m.build)+(target(m.target_id)?.builds||[]).map(b=>option(b.sha256,`${b.version_name} · ${b.sha256.slice(0,10)}`,m.build)).join(''))}${field('device','Disposable Android device',m.device||health.android?.avd||'','text','Only the operator-designated AVD is accepted.')}</div>
<details class="section idea" id="idea-box" ${fresh?'open':''}><summary><strong>${fresh?'Start from an idea':'Start over from an idea'}</strong></summary>
<div class="ideabody"><div class="field full"><label for="mission-idea">What do you want to find out?</label>
<textarea id="mission-idea" dir="auto" placeholder="Does a downloaded title still play when the phone loses its connection?"></textarea>
<small>Opening this never erases the mission below.</small></div>
<div class="starters" id="idea-starters" role="group" aria-label="Questions the shipped journeys answer"></div>
<div class="assist"><button type="button" class="compact primary" id="idea-suggest" ${worker?'':'disabled'}>Suggest missions</button><button type="button" class="compact" id="idea-manual">Write it yourself</button><small>${worker?esc(worker)+' will suggest two goals and two scenarios.':'Sign in Codex or Claude under Settings to get suggestions. You can still write and save a mission.'}</small></div>
<p class="error" id="idea-error" role="alert"></p></div></details>
<div id="mission-suggestions" class="suggestions" aria-live="polite" hidden></div>
<div id="draft-section" ${fresh?'hidden':''}><div class="drafthead"><h2>Your mission</h2><button type="button" class="compact" id="undo-ai" hidden>Undo</button></div>
<div class="formgrid">${field('name','Mission name',m.name)}
<div class="field full"><label for="goal">User goal</label><textarea id="goal" name="goal" required placeholder="As a visitor, search for a movie and inspect its detail page. Stop before login or purchase.">${esc(m.goal)}</textarea></div></div>
${scenarioSection(m)}
<div class="field full" id="revise-box"><label for="mission-revise">Change something</label>
<textarea id="mission-revise" dir="auto" placeholder="Add a relaunch before the last check, and say the download must survive it."></textarea>
<div class="assist"><button type="button" class="compact" id="revise-go" ${worker?'':'disabled'}>Revise this mission</button><small>${worker?'The whole mission comes back changed. Undo puts it straight back.':'Sign in Codex or Claude under Settings to revise a mission.'}</small></div>
<p class="error" id="revise-error" role="alert"></p></div>
<details class="section" id="run-settings"><summary><strong>Run settings</strong> <span id="run-summary" class="muted"></span></summary><div class="formgrid">${select('project_id','Workspace',state.projects.map(p=>option(p.id,state.hub?.mode==='hybrid'?`${p.name} · ${where(p.id)}`:p.name,m.project_id||workspace)).join(''))}${select('visibility','Visibility',option('team','Team',m.visibility||'team')+option('local','Only on this Mac',m.visibility||'team'))}
${select('mode','Execution mode',['journey','explore','audit','benchmark'].map(v=>option(v,{journey:'Goal-driven journey',explore:'Exploratory mission',audit:'Page / pillar audit',benchmark:'Benchmark · compare with competitors'}[v],m.mode)).join(''))}
<div class="field full" id="competitors-field"><label for="competitors">Competitor start URLs</label><textarea id="competitors" name="competitors" placeholder="https://competitor-one.com&#10;https://competitor-two.com">${esc((m.competitors||[]).join('\n'))}</textarea><small>One URL per line. Benchmark mode answers the same goal here first, then on each competitor.</small></div>
${select('provider','AI worker',['codex','claude','auto','none'].map(v=>option(v,{codex:'Codex · ChatGPT subscription',claude:'Claude · Claude Code subscription',auto:'First available worker',none:'No AI · deterministic audit only'}[v],m.provider)).join(''),'Each mission can use its own worker.')}${select('codex_account','Codex account',codexAccountOptions(m.codex_account||'',true,site.codex_account||'default'),'Inherits the workspace default unless this mission needs another local Codex login.')}${select('model','AI model',modelOptions(m.model||''),'Dynamic reads a page on a small model and saves the strong one for the evidence review. Any other choice runs every call on that model.')}${select('model_max','Highest model allowed',maxModelOptions(m.model_max||''),'Dynamic never goes above this model. Reviews use Opus/Sol unless capped lower. Prices are estimates at standard API prices; runs use your subscription.')}<div class="field model-custom"><label for="model_custom">Custom model id</label><input id="model_custom" name="model_custom" value="${esc(['codex','claude'].flatMap(p=>aiModels(p).map(o=>o.value)).includes(m.model||'')?'':m.model===DYNAMIC?'':m.model||'')}" autocomplete="off"><small>Any model id the selected CLI accepts.</small></div>${select('effort','Reasoning effort',['low','medium','high','xhigh'].map(v=>option(v,v,m.effort||'low')).join(''),'Higher effort is slower and uses more subscription quota.')}${field('ai_budget','Maximum AI calls',m.ai_budget,'number')}
${select('browser','Browser',['chromium','firefox','webkit'].map(v=>option(v,v,m.browser)).join(''))}${select('viewport','Viewport',['desktop','mobile','tablet'].map(v=>option(v,v,m.viewport)).join(''))}
${select('network','Network profile',state.networks.map(v=>option(v.id,v.name,m.network)).join(''),'Browser throttling requires Chromium; an Android run shapes latency and bandwidth on the emulator\u2019s mobile radio. These are synthetic conditions.')}${field('max_steps','Maximum actions',m.max_steps,'number')}${field('max_seconds','Time limit in seconds',m.max_seconds,'number')}
<div class="field full"><label>Evaluation pillars</label><div class="checks">${Object.entries(label).map(([k,v])=>`<label><input type="checkbox" name="pillars" value="${k}" ${(m.pillars||[]).includes(k)?'checked':''}>${v}</label>`).join('')}</div></div></div></details>
<details class="section" ${extras?'open':''}><summary><strong>Sign-in, proxy, replay and other settings</strong></summary><div class="formgrid">${select('persona_id','Test persona',option('','Unauthenticated visitor',m.persona_id)+state.personas.map(v=>option(v.id,v.name,m.persona_id)).join(''))}${field('login_identifier','Sign-in identifier',m.login_identifier||'','text','Phone, email or username the assistant types into the login form. Leave empty for a read-only run.')}${field('login_password','Sign-in password','','password','Stored locally and filled by the engine; the assistant never sees it. Leave blank to keep the saved password. Setting an identifier also lets this website send its own POST requests on the allowed domains.')}
${select('egress_id','Proxy route',option('','Direct connection',m.egress_id)+(state.egresss||[]).map(v=>option(v.id,v.name,m.egress_id)).join(''),'A real alternate ISP requires an actual proxy endpoint. An Android run launches its emulator against it, so the designated device must not already be running.')}${field('success_text','Success text (optional)',m.success_text,'text','Exact text that must be visible for the run to count as a success.')}${field('allowed_domains','Allowed navigation domains',m.allowed_domains.join(', '),'text','Comma-separated exact hostnames. The start hostname is always included.')}
${field('observe_seconds','Stay on the final page (seconds)',m.observe_seconds||0,'number','Records playback and network behaviour after the journey. 0 skips it.')}${select('auto_replay','Replay P0–P2 findings automatically',option('false','Off',String(m.auto_replay||false))+option('true','Once, with a separate run budget',String(m.auto_replay||false)))}${field('locale','Browser locale',m.locale)}${field('release','Release label',m.release,'text','Free tag such as live or staging, used when comparing runs.')}</div></details>
<div class="toolbar"><button class="primary" type="submit">Save mission</button><button type="submit" name="run" value="1">Save and run</button>${id?`<button type="button" class="danger" data-delete-mission="${id}">Delete mission</button>`:''}</div></div>
<p class="error" id="form-error" role="alert"></p></form>`}
// One readable line per action: what it did and what it changed.
const firstLine=t=>String(t||'').split('\n')[0].slice(0,160);
const actionResult=a=>a.status==='policy_blocked'?`refused: ${firstLine(a.error)}`:a.status==='skipped'?`skipped: ${firstLine(a.error)}`:a.status==='failed'?`failed: ${firstLine(a.error)}`:a.state_changed?'page changed':a.evidence_after?'no visible change':'';
const actionSummary=a=>a.summary||`${a.type} ${a.target||a.value||''}`.trim();
function actionLine(a){const result=actionResult(a);return `<div class="actionline">${badge(a.status||'pending')} <strong dir="auto">${esc(actionSummary(a))}</strong>${result?` <span class="muted">· ${esc(result)}</span>`:''}${a.reason?`<small dir="auto">${esc(a.reason)}</small>`:''}</div>`}
// A recorded accessibility rule can carry the raw node list; a reader gets the elements, not the JSON.
function observedHTML(f){const t=String(f.observed??'');
if(t.trim().startsWith('[')){try{const nodes=JSON.parse(t);
if(Array.isArray(nodes)&&nodes.length&&nodes.every(n=>n&&typeof n==='object'&&(n.target||n.summary))){
const shown=nodes.slice(0,8).map(n=>`<span class="mono">${esc([].concat(n.target||[]).join(' ')||'element')}</span>: ${esc(firstLine(n.summary||''))}`).join('<br>');
return shown+(nodes.length>8?`<br><span class="muted">${nodes.length-8} more elements.</span>`:'')}}catch(e){}}
return esc(t)}
// A rule link is a link, not a URL the reader has to pick out of a sentence.
function recommendationHTML(f){const t=String(f.recommendation??'').trim();
if(/^https?:\/\/\S+$/.test(t)){try{return `<a href="${esc(t)}" target="_blank" rel="noopener">Rule guidance and fix (${esc(new URL(t).hostname.replace(/^www\./,''))})</a>`}catch(e){}}
return esc(t)}
// Evidence ids mean nothing to a reader; the step that recorded them is a place they can open.
function stepLink(r,evidenceId,text){const i=(r?.observations||[]).findIndex(o=>o.id===evidenceId);
return i<0?`<span class="muted">${esc(text||evidenceId||'')}</span>`:`<button type="button" class="compact" data-step="${i}">${esc(text||('Step '+(i+1)))}</button>`}
function findingHTML(f,run){const meta=[VERDICT[f.verifier_status]||f.verifier_status,SOURCEWORD[f.source]||f.source,f.classification,label[f.pillar]||f.pillar].filter(Boolean);
const steps=run?[...new Set(f.steps||[f.evidence_id])].map(id=>stepLink(run,id)).join(' '):'';
return `<details class="finding${closed(f)?' closed':''}"><summary><span class="badge ${esc(f.severity)}">${esc(f.severity)}</span>${f.owner?` <span class="badge owner">${esc(f.owner)}</span>`:''} <strong>${esc(f.title)}</strong><span class="findactions">${copyButton(findingText(f),'this finding')}<label class="done"><input type="checkbox" data-done="${f.id}" data-run="${f.run_id}" ${f.status==='resolved'?'checked':''}> Done</label><button class="compact" data-replay="${f.run_id}">Recheck</button></span></summary><div class="findmeta">${f.status&&f.status!=='open'?badge(f.status):''}<span class="muted"><span title="${esc(CONFIRMED_MEANS)}">${esc(meta[0]||'')}</span>${meta.length>1?' · '+esc(meta.slice(1).join(' · ')):''}</span>${f.pages>1?`<span class="muted">Seen on ${f.pages} pages</span>`:''}${steps}${f.created_at?`<span class="muted">Last seen ${date(f.created_at)}</span>`:''}</div><p dir="auto"><strong>Observed</strong><br>${observedHTML(f)}</p><p><strong>Expected</strong><br>${esc(f.expected)}</p><p><strong>Recommendation</strong><br>${recommendationHTML(f)}</p>${f.verifier_reason?`<p><strong>Why this verdict</strong><br>${esc(f.verifier_reason)}</p>`:''}<div class="toolbar"><a class="button compact" href="#run/${f.run_id}">Open run evidence</a><select style="width:145px" aria-label="Finding status" data-finding="${f.id}" data-run="${f.run_id}">${['open','accepted','resolved','dismissed'].map(v=>option(v,v,f.status)).join('')}</select><input aria-label="Finding owner" style="width:170px" placeholder="Assign owner" value="${esc(f.owner||'')}" data-owner="${f.id}" data-run="${f.run_id}"><span class="mono">${esc(f.evidence_id)}</span>${f.occurrences?`<span class="badge">${f.occurrences.length} occurrences</span>`:''}${f.reproduced?badge('reproduced'):''}</div></details>`}
function scoreRow(r){const s=r.scores;if(!s||!s.overall)return '';
const cells=Object.entries(s).filter(([k])=>!['overall','basis'].includes(k)).map(([p,v])=>`<div><small>${esc(label[p]||p)}</small><strong>${v.score!=null?v.score:'Not scored'}</strong>${v.score==null?`<small>${esc(v.reason)}</small>`:v.deductions.length?`<details><summary>${v.deductions.length} deduction${v.deductions.length===1?'':'s'}</summary><ul>${v.deductions.map(d=>`<li>−${d.points} · ${esc(d.severity)} ${esc(d.title)}${d.pages>1?` <small>on ${d.pages} pages</small>`:''}</li>`).join('')}</ul></details>`:'<small>No open findings</small>'}</div>`).join('');
return `<div class="metricrow scorerow"><div><small>Overall · 0 to 100</small><strong>${s.overall.score!=null?s.overall.score:'Not scored'}</strong><small>${s.overall.scored} of ${s.overall.of} pillars scored</small></div>${cells}</div><div class="rowfoot"><details><summary>How scores are calculated</summary><p class="muted">${esc(s.basis||'')}</p></details>${copyButton(scoresText(r),'the scores')}</div>`}
function summarySection(r){const s=r.executive_summary;if(!s)return '';
const sourceText=s.source.startsWith('AI')?"The AI worker wrote the headline, summary and next steps from this run's evidence. Scores and facts are computed from the record.":'Assembled from the run record. No AI worker wrote a summary for this run.';
const brief=['running','queued'].includes(r.status)?'':skillHint('Share a one-page brief:','/pex-run-brief '+r.id);
return `<section class="section" style="border-top:0;padding-top:0"><h2>Executive summary${copyButton(summaryText(s),'the summary')}</h2><h3>${esc(s.headline)}</h3><p dir="auto">${esc(s.summary)}</p>${scoreRow(r)}<div class="split"><div><h3>Most severe open findings</h3>${s.top_findings.length?`<ul>${s.top_findings.map(f=>`<li><span class="badge ${esc(f.severity)}">${esc(f.severity)}</span> ${esc(f.title)}<small>${esc(label[f.pillar]||f.pillar)}</small>${stepLink(r,f.evidence_id)}</li>`).join('')}</ul>`:'<p class="muted">No open findings were recorded.</p>'}</div><div><h3>Next steps</h3><ol>${s.next_steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol>${s.source.startsWith('AI')?`<h3>Recorded facts</h3><ul>${s.facts.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>`:''}</div></div><p class="muted">${esc(sourceText)}</p>${brief}</section>`}
// Requests refused on the tested site itself, which is what can stall a journey.
function siteBlocked(r){const hosts=new Set(r.mission?.allowed_domains||[]);try{hosts.add(new URL(r.mission.url).hostname)}catch(e){}
const own=(r.blocked_request_log||[]).filter(b=>{try{return hosts.has(new URL(b.url).hostname)}catch(e){return false}});
if(!own.length)return '';
const lines=[...new Set(own.map(b=>{try{return b.method+' '+new URL(b.url).pathname}catch(e){return b.method}}))];
return `<br>On this website: ${esc(lines.join(', '))}`}
function consoleSection(r){const events=(r.console||[]).filter(e=>['pageerror','error','warning'].includes(e.kind));if(!events.length)return '';
return `<details class="section"><summary><strong>Console and JavaScript errors</strong> <span class="muted">${events.length}</span>${copyButton(lines(events.map(consoleText)),'the console errors')}</summary>${events.map(e=>`<details class="finding"><summary>${badge(e.kind)} <strong dir="auto">${esc((e.name?e.name+': ':'')+firstLine(e.message))}</strong>${copyButton(consoleText(e),'this error')}</summary><p dir="auto">${esc(e.message)}</p><div class="findmeta"><span class="mono">${esc(e.source||'Source not reported')}</span><span class="muted">${esc(e.page_url||'')}</span><span class="muted">${typeof e.step==='number'?'Step '+(e.step+1):''} ${date(e.at)}</span></div>${e.stack?`<pre class="raw">${esc(e.stack)}</pre>`:'<p class="muted">No stack trace was reported for this event.</p>'}</details>`).join('')}</details>`}
const SPEEDS=['0.5','1','2','4','10'];
// The site-by-site comparison of a benchmark run: measurements from the browser,
// strengths and weaknesses from the AI review, each beside its own screenshot.
function benchmarkSection(r){const sites=r.sites||[];if(!sites.length)return '';
const judged=Object.fromEntries((r.benchmark||[]).map(b=>[b.url,b]));
return `<section class="section"><h2>Benchmark</h2><div class="tablewrap"><table><thead><tr><th>Site</th><th>Outcome</th><th>Rank</th><th>LCP</th><th>CLS</th><th>TTFB</th><th>Accessibility</th></tr></thead><tbody>${sites.map(s=>{const m=s.metrics||{},b=judged[s.url]||{};return `<tr><td>${s.evidence_id?`<a href="${evidenceURL(r.id,`/api/runs/${r.id}/artifacts/${s.evidence_id}.png`)}" target="_blank"><strong>${esc(s.url)}</strong></a>`:`<strong>${esc(s.url)}</strong>`}<small>${esc(s.reason||'')}</small></td><td>${badge(s.outcome)}</td><td>${b.rank??'Not ranked'}</td><td>${ms(m.lcp)}</td><td>${typeof m.cls==='number'?m.cls.toFixed(3):'Not observed'}</td><td>${ms(m.ttfb_ms)}</td><td>${typeof s.axe_violations==='number'?s.axe_violations+' violations':'Not run'}</td></tr>`}).join('')}</tbody></table></div>${sites.filter(s=>judged[s.url]).map(s=>{const b=judged[s.url];return `<details><summary>${esc(s.url)}</summary><p>${esc(b.observed||'')}</p><p><strong>Strengths:</strong> ${esc(b.strengths||'None recorded')}</p><p><strong>Weaknesses:</strong> ${esc(b.weaknesses||'None recorded')}</p></details>`}).join('')}<p class="muted">Findings are recorded for this workspace's own website only. Competitor pages are evidence for the comparison.</p></section>`}
// Every visit writes its own trace; older runs carry a single link.
const traceParts=r=>r.traces?.length?r.traces:r.trace?[r.trace]:[];
// Each visit records its own file: the bundled ffmpeg cannot join webm parts, so they are played in order.
function videoSection(r){const parts=r.videos?.length?r.videos:r.video?[r.video]:[];if(!parts.length)return '';
return `<section class="section"><h2>Recorded journey</h2><div class="toolbar"><label for="video-speed">Playback speed</label><select id="video-speed" style="width:110px">${SPEEDS.map(v=>option(v,v+'×',recall('pex.video-speed','2'))).join('')}</select></div>${parts.map((part,i)=>`${parts.length>1?`<h3>Part ${i+1}</h3>`:''}<video controls preload="metadata" style="width:100%;max-height:500px" src="${evidenceURL(r.id,part)}"></video>`).join('')}<small class="muted">The recording has no audio. Above 4× the browser may drop frames.${parts.length>1?' Each continuation recorded its own part.':''}</small></section>`}
// --- the scenario on the run page -------------------------------------------
// Each step reports a word, never a colour alone, and carries its own evidence.
const STEP_STATUS={pending:'Not started',running:'Running now',waiting:'Waiting for you',passed:'Passed',failed:'Failed',unavailable:'No usable evidence',skipped:'Skipped',error:'Could not be carried out'};
const STEP_MARK={passed:'✓',failed:'✗',unavailable:'?',skipped:'–',error:'!',running:'▸',pending:'·'};
const stepWord=s=>STEP_STATUS[s.status]||s.status;
const sampleLine=s=>s.samples?.length?`${s.samples.length} sample${s.samples.length===1?'':'s'} over ${s.elapsed_s||0} s`:s.elapsed_s?`${s.elapsed_s} s`:'';
function scenarioText(r){return lines((r.scenario||[]).map(s=>`${s.number}. ${s.requested} · ${stepWord(s)}${s.reason?': '+s.reason:''}${sampleLine(s)?' ('+sampleLine(s)+')':''}`))}
function stepsSection(r){const steps=r.scenario||[];if(!steps.length)return '';
const cover=r.scenario_coverage||{},current=steps.find(s=>s.status==='running');
// Missing evidence is not a defect, so it is listed apart from what the run measured.
const gaps=steps.filter(s=>['unavailable','skipped','error'].includes(s.status));
const questions=steps.filter(s=>s.policy==='unknown'&&s.status==='failed');
const jump=(s,inner)=>{const i=(r.observations||[]).findIndex(o=>o.id===(s.evidence||[]).slice(-1)[0]);
return i<0?`<span class="stepchip ${esc(s.status)}">${inner}</span>`:`<button type="button" class="stepchip ${esc(s.status)}" data-step="${i}">${inner}</button>`};
return `<section class="section" id="scenario-progress"><div class="pagehead"><h2>Scenario${copyButton(scenarioText(r),'the scenario')}</h2><span class="muted">${cover.checks!=null?`${cover.passed} of ${cover.checks} checks established`:`${steps.length} steps`}${current?` · running step ${current.number}`:''}</span></div>
<ol class="stepstrip">${steps.map(s=>`<li>${jump(s,`<strong>${s.number}</strong><span>${esc(STEP_MARK[s.status]||'·')} ${esc(stepWord(s))}</span>`)}</li>`).join('')}</ol>
<div class="tablewrap"><table class="steptable"><thead><tr><th>Step</th><th>What was asked</th><th>Outcome</th><th>What was measured</th></tr></thead><tbody>${steps.map(s=>`<tr><td><strong>${s.number}</strong>${s.name?`<small dir="auto">${esc(s.name)}</small>`:''}${s.required&&['check','hold'].includes(s.kind)?'<small>Required</small>':''}</td><td dir="auto">${esc(s.requested)}${s.policy==='unknown'?'<small>Nobody has confirmed this behaviour</small>':''}</td><td>${esc(STEP_MARK[s.status]||'·')} ${esc(stepWord(s))}</td><td dir="auto">${esc(s.reason||'')}<small>${esc(sampleLine(s))}${(s.evidence||[]).length?' · ':''}${(s.evidence||[]).slice(-1).map(id=>stepLink(r,id)).join('')}</small></td></tr>`).join('')}</tbody></table></div>
${gaps.length?`<h3>Measurements that were not available</h3><ul class="plain">${gaps.map(s=>`<li dir="auto">Step ${s.number} · ${esc(stepWord(s))} · ${esc(s.reason||s.requested)}</li>`).join('')}</ul>`:''}
${questions.length?`<h3>Questions about intended behaviour</h3><ul class="plain">${questions.map(s=>`<li dir="auto">Step ${s.number} · ${esc(s.requested)} · ${esc(s.reason||'')}</li>`).join('')}<li class="muted">Recorded as observations with severity info. They never deduct from a score or block a release.</li></ul>`:''}
<p class="muted">${esc(cover.note||'')}${(r.video_gaps||[]).length?` Recording gaps: ${(r.video_gaps||[]).map(g=>`${g.seconds} s after part ${g.after_part}`).join(', ')}.`:''}</p></section>`}
// The HTML report is one AI call, so the worker, model and Codex account are chosen here,
// the same way a mission chooses them. A run that used no AI can still be reported on.
function exportPicker(r){const worker=['codex','claude','auto'].includes(r.provider)?r.provider:'auto';
return `<details class="export-html"><summary class="button">Export HTML</summary><div class="formgrid">
${select('export_provider','AI worker',['codex','claude','auto'].map(v=>option(v,{codex:'Codex · ChatGPT subscription',claude:'Claude · Claude Code subscription',auto:'First available worker'}[v],worker)).join(''))}
${select('export_model','AI model',modelOptions(r.ai_model||''),'Dynamic uses the review model this console reserves for reading evidence.')}
${select('export_codex_account','Codex account',codexAccountOptions(r.codex_account||'',true,project().codex_account||'default'))}
<div class="field model-custom"><label for="export_model_custom">Custom model id</label><input id="export_model_custom" autocomplete="off"><small>Any model id the selected CLI accepts.</small></div>
<div class="field full"><div class="toolbar"><button class="primary" data-export-html="${r.id}">Write report</button><small>One AI call, about a minute. It reads the screens and ranks what to improve; every number stays the run's own.</small></div></div>
</div></details>`}

function detail(r){currentRun=r;copyTexts={};copySerial=0;
// A running journey follows its newest step until the reader picks one themselves.
const lastStep=Math.max(0,r.observations.length-1);selectedStep=followLatest&&['running','queued'].includes(r.status)?lastStep:Math.min(selectedStep,lastStep);
const o=r.observations[selectedStep],metric=o?.metrics||{},active=['running','queued'].includes(r.status),native=(r.platform||r.mission.platform)==='android';
// One issue, one row: the list matches the deductions the score already charged once.
const folded=foldFindings(r),openCount=folded.filter(f=>!closed(f)).length;
return head(esc(r.mission.name),`${badge(r.status)} <span class="muted">${esc((r.platform||r.mission.platform)==='android'?`Android · ${targetLabel(r.mission.target_id)} · ${r.app?.version_name||'build'} · ${r.device?.avd||r.mission.device}`:`${r.mission.browser} · ${r.mission.viewport}`)} · ${esc(networkName(r))} network · ${esc(where(r.project_id||workspace))}${r.continuations?` · ${r.continuations+1} visits`:''}</span>${r.provider&&r.provider!=='none'?`<small class="muted">AI: ${esc(r.provider)} · ${esc(modelSummary(r.provider,r.ai_model,r.ai_model_max,r.ai_effort))} · ${r.ai_calls} call${r.ai_calls===1?'':'s'}${r.ai_totals?.calls?' · '+esc(money(r.ai_totals.est_cost_usd,r.ai_totals.cost_partial)):''}</small>`:''}${active?'<small class="muted">This page updates every 4 seconds. Stop run ends the executor and AI worker.</small>':''}`,`${active?`<button class="danger" data-cancel="${r.id}">Stop run</button>`:`<button data-replay="${r.id}">Replay</button>`}${r.visibility==='local'&&shared(workspace)&&!active?`<button data-share="runs/${r.id}">Share run</button>`:''}${state.missions.some(m=>m.id===r.mission_id)?`<a class="button" href="#edit/${r.mission_id}">Edit mission</a>`:''}<a class="button" href="/api/runs/${r.id}/export">Export Markdown</a>${active?'':exportPicker(r)}${copyButton(runText(r),'this run')}`)+
`${r.mission.goal?`<p dir="auto"><strong>User goal</strong><br>${esc(r.mission.goal)}</p>`:''}${operatorNotice(r)}${statusNotice(r)}${state.hub?.pending?.includes(r.id)?`<div class="notice"><strong>Awaiting upload</strong><p>Finished on this Mac. Evidence uploads to ${esc(host())} when it answers.</p><div class="toolbar"><button type="button" id="retry-upload">Retry upload</button></div></div>`:''}${r.evaluation_error?`<div class="notice"><strong>The AI review did not finish</strong><p>${esc(r.evaluation_error)}</p><p>Measured findings are complete. AI suggestions may be missing. ${canContinue(r)?'Continue below to finish the review without repeating the journey.':'Replay to run the review again.'}</p></div>`:''}${continueSection(r)}
${stepsSection(r)}${summarySection(r)}${benchmarkSection(r)}<div class="split"><section><div class="evidence-head"><h2>${native?'App':'Browser'} evidence${o?copyButton(evidenceText(r,o),'this page'):''}</h2><span class="muted">${o?`${selectedStep+1} / ${r.observations.length}`:`Waiting for ${native?'app':'browser'}`}</span></div>${o?`${o.screenshot?`<a href="${evidenceURL(r.id,o.screenshot)}" target="_blank"><img class="screenshot" src="${evidenceURL(r.id,o.screenshot)}" alt="${native?'App':'Browser'} screenshot for ${esc(o.id)}" /></a>`:`<p class="muted">No screenshot for this step. ${esc(o.screenshot_error||'')}</p>`}<div class="metricrow">${native?metricCell('Launch time','Launch to initial activity display',ms(r.measurements?.launch_ms))+metricCell('Jank','Rendering frames since reset',typeof r.measurements?.jank_pct==='number'?r.measurements.jank_pct.toFixed(1)+'%':'Not measured')+metricCell('Memory (PSS)','Package memory in KiB',typeof r.measurements?.pss_kb==='number'?r.measurements.pss_kb.toLocaleString()+' KiB':'Not measured')+metricCell('Crashes and errors','Attributed app incidents',String((r.findings||[]).filter(f=>f.rule==='anr'||f.rule?.startsWith('crash-')||f.rule?.startsWith('native-crash-')).length)):metricCell('Largest contentful paint','LCP. '+LAB,ms(metric.lcp))+metricCell('Cumulative layout shift','CLS. '+LAB,typeof metric.cls==='number'?metric.cls.toFixed(3):'Not observed')+metricCell('Interaction to next paint','INP. '+LAB,ms(metric.inp))+metricCell('Time to first byte','TTFB. '+LAB,ms(metric.ttfb_ms))}</div><div class="actions">${native?`<a class="button compact" href="${evidenceURL(r.id,`/api/runs/${r.id}/artifacts/${o.id}.json`)}">Observation JSON</a>${(r.logs||[]).map((log,i)=>`<a class="button compact" href="${evidenceURL(r.id,log)}">App log${r.logs.length>1?' · part '+(i+1):''}</a>`).join('')}`:`<a class="button compact" href="${evidenceURL(r.id,o.dom)}">DOM snapshot</a><a class="button compact" href="${evidenceURL(r.id,`/api/runs/${r.id}/artifacts/${o.id}.json`)}">Observation JSON</a>${traceParts(r).map((t,i,all)=>`<a class="button compact" href="${evidenceURL(r.id,t)}">Browser trace${all.length>1?' · part '+(i+1):''}</a>`).join('')}`}</div>`:empty(active?`Opening the ${native?'app':'browser'}…`:`No ${native?'app screen':'page'} was captured`,active?'The timeline will update as evidence arrives.':'Read the message at the top of this page, then replay.')}</section><section><h2>Journey timeline${copyButton(timelineText(r),'the timeline')}</h2><div class="timeline">${r.observations.map((o,i)=>`${partStart(r,o,i)?`<p class="part">${esc(partStart(r,o,i))}</p>`:''}<button class="${i===selectedStep?'selected':''}" data-step="${i}"><strong>${String(i+1).padStart(2,'0')} · ${esc(o.title||'Page observation')}</strong><small dir="auto">${esc(o.url)}</small><small>${date(o.at)}</small>${(r.actions||[]).filter(a=>a.evidence_before===o.id).map(actionLine).join('')}</button>`).join('')}</div><div class="section"><h3>Run conditions${copyButton(conditionsText(r),'the run conditions')}</h3><p class="muted">Network: ${esc(networkName(r))}. ${esc(r.network_applied?.scope||'Not yet applied.')}</p>${native?`<p class="muted">${esc(`${r.device?.avd||r.mission.device} · API ${r.device?.api||'unknown'} · ${r.device?.display||'display not measured'}`)}</p>`:''}${!native||r.egress?`<p class="muted">${esc(r.egress?.name||'Direct connection')}<br>${esc(r.egress?.verification||'')}</p>`:''}${(r.route_checks||[]).map(c=>`<p class="${c.status==='verified'?'muted':'error'}">${esc(checkLine(c))}</p>`).join('')}<small>${esc(blockedLine(r))}${siteBlocked(r)}</small></div></section></div>${videoSection(r)}<section class="section"><h2>Findings <span class="muted">${folded.length} issue${folded.length===1?'':'s'}${folded.length!==r.findings.length?` · ${r.findings.length} records`:''}</span>${folded.length?copyButton(findingsText(folded),'these findings'):''}</h2>${!active&&openCount?skillHint('Turn these into tickets with owners:','/pex-findings-triage '+r.id):''}${folded.length?folded.map(f=>findingHTML(f,r)).join(''):empty(active?'Evaluation is in progress':'No findings recorded',active?'Confirmed checks and AI observations will appear here.':'This is not proof the site is correct. Check what this run covered below.')}</section>${consoleSection(r)}${aiUsage(r)}<section class="section"><h2>What this run checked${copyButton(coverageText(r),'the coverage')}</h2><p class="pillars">${Object.entries(r.coverage||{}).map(([p,c])=>`<span class="muted" title="${esc(c.note||'')}">${esc(label[p]||p)} ${esc(String(c.status).replaceAll('_',' '))}</span>`).join('<span class="muted">·</span>')||'<span class="muted">Coverage not yet established.</span>'}</p><p class="muted">Video quality needs observed playback. A missing metric is not a zero. One run does not establish field percentiles or conversion impact.</p><h3>Execution log${copyButton(logText(r),'the log')}</h3><div class="log">${r.events.map(e=>`${date(e.at)}  ${esc(e.message)}`).join('\n')}</div><div class="toolbar"><a href="/api/runs/${r.id}/export?format=json">Download complete run JSON</a></div></section>`}
const SEV=['P0','P1','P2','P3','info'];
const closed=f=>['resolved','dismissed'].includes(f.status);
const rank=f=>{const i=SEV.indexOf(f.severity);return i<0?SEV.length:i};
// The same defect is recorded once per page that showed it. The score charges it once, so the page shows it once.
function foldFindings(r){const groups=new Map();
for(const f of r.findings||[]){const key=f.rule||f.issue_key||f.title,g=groups.get(key);
if(!g){groups.set(key,{...f,pages:1,steps:[f.evidence_id]});continue}
g.pages++;g.steps.push(f.evidence_id);
// The group keeps the worst severity, and an open record ahead of a closed one.
if(rank(f)<rank(g)||(rank(f)===rank(g)&&closed(g)&&!closed(f)))Object.assign(g,f,{pages:g.pages,steps:g.steps})}
return [...groups.values()].sort((a,b)=>rank(a)-rank(b))}
async function findings(){copyTexts={};copySerial=0;const fs=await api('/findings?grouped=true&project='+encodeURIComponent(workspace));for(const f of fs)if(f._run_revision!=null)runRevisions[f.run_id]=f._run_revision;
const sort=recall('pex.findings-sort','priority'),owner=recall('pex.findings-owner','all'),hideDone=recall('pex.findings-hide-done','0')==='1';
const shown=fs.filter(f=>(owner==='all'||(owner==='assigned')===!!f.owner)&&!(hideDone&&closed(f)));
const seen=f=>f.created_at||'';
shown.sort((a,b)=>sort==='recent'?seen(b).localeCompare(seen(a))||rank(a)-rank(b):rank(a)-rank(b)||seen(b).localeCompare(seen(a)));
// Every finding belongs to one topic; a pillar the label map does not know is still shown, after the known ones.
const topics=[...new Set([...Object.keys(label),...shown.map(f=>f.pillar)])].map(p=>[p,shown.filter(f=>f.pillar===p)]).filter(([,list])=>list.length);
return head('Findings',`Review claims beside their evidence. Confirmed means the recorded rule was observed, not that business impact is proven. · ${esc(where(workspace))}`)+`<div class="toolbar"><input id="finding-search" placeholder="Filter findings by title, pillar, severity or owner" aria-label="Filter findings" style="max-width:380px"><select id="finding-sort" style="width:190px" aria-label="Sort findings">${option('priority','Priority · P0 first',sort)+option('recent','Last detected first',sort)}</select><select id="finding-owner" style="width:170px" aria-label="Assignment">${option('all','Everything',owner)+option('assigned','Assigned',owner)+option('unassigned','Not assigned',owner)}</select><label class="done"><input type="checkbox" id="finding-hide-done" ${hideDone?'checked':''}> Hide done</label></div><div id="finding-list">${topics.length?topics.map(([p,list])=>`<details class="section topic" data-topic="${esc(p)}" open><summary><h2>${esc(label[p]||p)} <span class="muted">${list.length}</span></h2></summary>${list.map(f=>`<div data-filter="${esc((f.title+' '+f.pillar+' '+f.severity+' '+(f.owner||'')).toLowerCase())}">${findingHTML(f)}</div>`).join('')}</details>`).join(''):fs.length?empty('No findings match these filters','Change the sort, assignment or done filters above.'):empty('No findings yet','Run a mission to start collecting evidence.')}</div>`}
function benchmarkView(){const missions=state.missions.filter(m=>m.mode==='benchmark'),ids=new Set(missions.map(m=>m.id));
const runs=state.runs.filter(r=>r.mission.mode==='benchmark'||ids.has(r.mission_id));
return head('Benchmark',`Answer one question on this website and on each competitor, then compare the answers. · ${esc(where(workspace))}`,'<a class="button primary" href="#new">New mission</a>')+
(missions.length?`<div class="tablewrap"><table><thead><tr><th>Mission</th><th>Competitors</th><th>AI</th><th>Actions</th></tr></thead><tbody>${missions.map(m=>`<tr><td><a href="#edit/${m.id}"><strong>${esc(m.name)}</strong></a><small style="max-width:460px">${esc(m.goal)}</small></td><td>${(m.competitors||[]).map(esc).join('<br>')}</td><td>${esc(workerLabel(m))}</td><td><div class="actions"><button class="primary compact" data-start="${m.id}">Run</button><a class="button compact" href="#edit/${m.id}">Edit</a></div></td></tr>`).join('')}</tbody></table></div>`:empty('No benchmark mission yet','Create a mission in Benchmark mode and list the competitor start URLs.','<a class="button primary" href="#new">New mission</a>'))+
(runs.length?`<h2>Benchmark runs</h2>${runTable(runs)}`:'')}
function networks(){return head('Network & routes','Repeat the same journey under controlled conditions or a real proxy route.')+`<div class="notice">Browser profiles simulate latency and bandwidth. They do not change your ISP. Packet-level jitter and loss require the Linux netem deployment.</div><h2>Impairment profiles</h2><div class="tablewrap"><table><thead><tr><th>Profile</th><th>Latency</th><th>Download / upload</th><th>Scope</th></tr></thead><tbody>${state.networks.map(n=>`<tr><td><strong>${esc(n.name)}</strong></td><td>${n.latency_ms} ms</td><td>${n.down_mbps||'Unlimited'} / ${n.up_mbps||'Unlimited'} Mbps</td><td>${n.offline?'Offline':esc(n.backend)}</td></tr>`).join('')}</tbody></table></div><details class="section"><summary>Create a network profile</summary><form id="network-form"><div class="formgrid">${field('name','Profile name','')}${field('latency_ms','Added latency (ms)',100,'number')}${field('down_mbps','Download (Mbps)',5,'number')}${field('up_mbps','Upload (Mbps)',1,'number')}${select('backend','Execution backend',option('browser','Local browser','browser')+option('netem','Isolated Linux netem','browser'))}${field('jitter_ms','Jitter (ms, Linux only)',0,'number')}${field('loss_pct','Packet loss (%, Linux only)',0,'number')}${field('reorder_pct','Reordering (%, Linux only)',0,'number')}${field('duplicate_pct','Duplication (%, Linux only)',0,'number')}${field('disconnect_every_seconds','Disconnect every N seconds (0 disables)',0,'number')}${field('disconnect_seconds','Disconnect duration (seconds)',2,'number')}</div><div class="toolbar"><button class="primary">Save profile</button></div></form></details><section class="section"><h2>Real egress routes</h2>${state.egresss?.length?state.egresss.map(e=>`<div class="toolbar"><strong>${esc(e.name)}</strong><span>${esc(e.server)} ${e.verified_ip?`· IP ${esc(e.verified_ip)}`:""}</span><button class="compact" data-verify-egress="${e.id}">Verify connection</button><button class="compact danger" data-delete-egress="${e.id}">Remove</button></div>`).join(''):'<p class="muted">No proxy endpoints configured. Runs use this machine’s direct connection.</p>'}<details><summary>Add a proxy route</summary><form id="egress-form"><div class="formgrid">${field('name','Route label','')}${field('server','Proxy server','http://','text','HTTP(S) or SOCKS5 host and port. Credentials are stored locally.')}${field('username','Username','')}${field('password','Password','','password')}</div><div class="toolbar"><button class="primary">Save route</button></div></form></details></section>`}
// One form, two destinations: a workspace of your own on this Mac, or a shared one if you administer the team server.
function addWorkspace(){
  if(SERVER())return '<p class="muted">Workspaces are added by whoever administers this server, on its <a href="/admin">admin page</a>. Settings here are read only.</p>';
  const admin=!!state.hub?.admin;
  const choice=state.hub?.url?`<fieldset class="field full"><legend>Where</legend><div class="checks"><label class="done"><input type="radio" name="where" value="local" checked> On this Mac</label><label class="done"><input type="radio" name="where" value="shared" ${admin?'':'disabled'}> Shared on ${esc(host())}</label></div><small>${admin?'A workspace on this Mac is yours alone. A shared one is stored on the team server for everyone who has its sign-in.':'A workspace on this Mac is yours alone. Sign in as admin under Team server to create shared workspaces.'}</small></fieldset>`:'';
  return `<details${state.projects.length?'':' open'}><summary>Add workspace</summary><p class="muted">A new workspace starts with the ten ready missions.</p><form id="project-form"><div class="formgrid">${choice}${field('name','Workspace name','')}${field('url','Website URL','','url','Leave blank for an Android-only workspace and add the app under Websites and Android apps after creating it.')}${field('allowed_domains','Allowed navigation domains','','text','Comma-separated hostnames a run may visit besides the website\'s own, for example cdn.example.com.')}</div><div class="formgrid" id="shared-fields" hidden>${field('username','Workspace username','')}${field('password','Workspace password','','password','At least 15 characters. Teammates sign in to this workspace with these; you are signed in to it automatically.')}<label class="done"><input type="checkbox" name="seed" checked> Add starter missions</label></div><div class="toolbar"><button class="primary">Create workspace on this Mac</button></div></form></details>`;
}
function targetsSection(){const list=state.targets||[],hasApp=list.some(t=>t.type==='android');return `<section class="section"><h2>Websites and Android apps</h2><p class="muted">Every website of this workspace is a target. To test an Android app, add it here with its APK. APK files stay on this Mac; teammates see only the build details.</p>${list.length?`<div class="tablewrap"><table><thead><tr><th>Target</th><th>Location</th><th>Builds</th><th>Actions</th></tr></thead><tbody>${list.map(t=>`<tr><td><strong>${esc(t.name)}</strong><small>${esc(t.type==='android'?t.package||'Package name is set by the first APK':t.url)}</small></td><td>${badge(t.visibility||'team')}</td><td>${t.type==='android'?(t.builds||[]).map(b=>`<div class="actions"><span class="badge">${esc(b.version_name)}${b.archived?' · archived':''}</span>${b.archived?'':`<button class="compact" data-archive-build="${t.id}" data-sha="${b.sha256}">Archive</button>`}<button class="compact danger" data-remove-build="${t.id}" data-sha="${b.sha256}">Remove local file</button></div>`).join('')||'No builds yet':'URL and domains come from the workspace'}</td><td>${t.type==='android'?`<label class="button compact">Add APK build<input type="file" accept=".apk" data-apk="${t.id}" hidden></label>`:''}${t.visibility==='local'&&shared(workspace)?` <button class="compact" data-share="targets/${t.id}">Share</button>`:''}</td></tr>`).join('')}</tbody></table></div>`:empty('No websites or apps yet','Add the workspace website or an Android app with its APK.')}<details${hasApp?'':' open'}><summary>Add an Android app or another website</summary><form id="target-form"><input type="hidden" name="project_id" value="${esc(workspace)}"><div class="formgrid">${select('type','What to test',option('android','Android app','android')+option('web','Website','android'))}${field('name','Name','','text','Shown on missions and runs, for example Filimo Android.')}<div class="field"><label for="target-apk">APK file</label><input id="target-apk" name="apk" type="file" accept=".apk"><small>The first APK sets the app's package name. Up to 300 MB; it stays on this Mac.</small></div>${field('url','Website URL','','url')}${field('allowed_domains','Allowed domains','','text','Comma-separated exact hostnames. Website: extra hosts a run may visit. Android app: HTTPS deep-link hosts. Optional.')}${select('visibility','Visibility',option('team','Team','team')+option('local','Only on this Mac','team'))}</div><div class="toolbar"><button class="primary">Add Android app</button></div><p class="error" role="alert"></p></form></details></section>`}
// --- the designated Android device, and the states saved from it -------------
// Readiness is stated as facts an operator can act on, never as a single green word.
function androidSection(saved){const a=health.android||{};
const busy=state.runs.some(r=>['running','queued'].includes(r.status)&&(r.platform||r.mission?.platform)==='android');
const found=saved?.snapshots||[];
const reason=!a.avd?'The designated AVD is not named yet.':busy?'A run owns the device right now. Saving and deleting wait until it is free.':'';
const row=s=>`<tr><td><strong>${esc(s.name)}</strong><small class="mono">${esc(s.id)}</small></td><td>${esc(date(s.created_at))}<small>API ${esc(String(s.api||'unknown'))} · ${esc(s.abi||'abi unknown')}</small></td><td>${badge(s.available?'ready':'unusable')}<small>${esc(s.available?`${s.files_now} file${s.files_now===1?'':'s'} on disk`:s.note)}</small></td><td><button class="compact" data-delete-snapshot="${esc(s.id)}" data-name="${esc(s.name)}" ${reason?'disabled':''}>Delete</button></td></tr>`;
return `<section class="section" id="android-settings"><h2>Android device</h2>
<p class="muted">Runs and saved states use only the designated disposable AVD: <strong>${esc(a.avd||'not named yet')}</strong>. ${esc(a.reason?a.reason+'.':'It is ready for Android runs.')}</p>
<p class="muted">${a.window?'It starts with a visible window, so an operator can finish a manual step on screen.':'It starts without a window, so no one can finish a manual step on it. Set PEX_ANDROID_WINDOW=1 before start.command, and restart an emulator that is already running without one.'}</p>
<p class="muted">Weak-network steps shape the emulator console, which affects the whole device rather than one app. The console reports the setting it accepted; that is the configuration, not measured app throughput.</p>
<h3>Saved device states</h3>
<p class="muted">A saved state restores this Mac's emulator only. It cannot restore an account, a paid entitlement or an expired session, so the steps still check those. States are never overwritten, never leave this Mac and are not run evidence.</p>
${saved?.error&&a.avd?`<p class="error">${esc(saved.error)}</p>`:found.length?`<div class="tablewrap"><table><thead><tr><th>Name</th><th>Captured</th><th>State on disk</th><th>Actions</th></tr></thead><tbody>${found.map(row).join('')}</tbody></table></div>`:`<p class="muted">Nothing is saved on this Mac yet. Prepare the emulator by hand first: sign in, download what the journey needs, then save that state here.</p>`}
<form id="snapshot-form"><div class="formgrid">${field('name','Name this state','','text','What the device holds, for example Signed in as the download account. The name is a label; missions record the saved state itself.')}</div><div class="toolbar"><button class="primary" ${reason?'disabled':''}>Save the current device state</button>${reason?`<span class="muted">${esc(reason)}</span>`:'<span class="muted">Saves what the designated AVD holds right now. It can take several minutes.</span>'}</div><p class="error" role="alert"></p></form></section>`}
async function settings(){health=await api('/health');
// The saved states are local to this Mac, so an unreachable list is reported rather than hidden.
let saved=null;if(!SERVER()){try{saved=await api('/android/snapshots?project='+encodeURIComponent(workspace))}catch(e){saved={error:e.message}}}
return head('Settings','Readiness, workspaces, targets, team server, test sessions and schedules.')+`<div class="tablewrap"><table><thead><tr><th>Component</th><th>Status</th><th>Next step</th></tr></thead><tbody><tr><td>Database</td><td>${esc(health.database)}</td><td>Run history persists across restarts</td></tr>${Object.entries(health.ai).map(([k,v])=>`<tr><td>${esc(k)} subscription worker</td><td>${badge(v.logged_in?'ready':v.installed?'login_needed':'not_installed')}</td><td>${v.logged_in?`${esc(v.subscription||'Signed in')}<small>${k==='codex'?(v.accounts||[]).map(a=>`${esc(a.label)} · ${esc(a.email||'sign-in needed')}`).join('<br>'):(v.models||[]).filter(o=>o.value).map(o=>esc(o.label)+(o.price_hint?' · '+esc(o.price_hint):'')).join('<br>')||'CLI default'}</small>`:`Sign in using ${esc(k)} on this machine`}</td></tr>`).join('')}${Object.entries(health.browsers).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${badge(v?'installed':'missing')}</td><td>${v?'Ready for browser runs':'Run the setup script'}</td></tr>`).join('')}<tr><td>Android · ${esc(health.android?.avd||'no AVD')}</td><td>${badge(health.android?.available?'ready':'not_configured')}</td><td>${esc(health.android?.reason||'Disposable AVD ready')}</td></tr><tr><td>Linux packet shaping</td><td>${badge(health.network.netem?'connected':'not_connected')}</td><td>See the Linux deployment guide</td></tr></tbody></table></div><section class="section"><h2>Workspaces</h2><p class="muted">Each workspace has its own targets, missions, runs and findings. Switch between them in the sidebar.${SERVER()?'':' Each one inherits a Codex account that a mission can override.'}</p><div class="workspaces">${state.projects.map(p=>`<div class="toolbar"><span><strong>${esc(p.name)}</strong> · ${esc(p.url||'App-only workspace')}<small>${esc(where(p.id))}${shared(p.id)?' · signed in as '+esc(state.hub.logins[p.id].username):''}</small><small>${esc((p.allowed_domains||[]).join(', ')||'No website navigation domains')}</small></span><div class="field"><label for="codex-${p.id}">Default Codex account</label><select id="codex-${p.id}" data-project-codex="${p.id}">${codexAccountOptions(p.codex_account||'default')}</select></div></div>`).join('')}</div>${addWorkspace()}</section>${targetsSection()}${SERVER()?'':androidSection(saved)}<section class="section" id="hub-settings"></section><section class="section"><h2>Test personas</h2><p class="muted">Import a Playwright storage-state JSON from a test account you control. Credentials are not sent to the AI. Screenshots and page snapshots may still contain account information.</p>${state.personas.map(p=>`<p>${esc(p.name)} <small>${date(p.created_at)}</small></p>`).join('')}<label class="button">Import test session<input type="file" id="persona-import" accept=".json" hidden></label></section><section class="section"><h2>Scheduled runs</h2><p class="muted">Schedules execute while this local service is running. Missed intervals are not replayed in a burst.</p>${state.schedules.map(s=>`<div class="toolbar"><strong>${esc(state.missions.find(m=>m.id===s.mission_id)?.name||'Removed mission')}</strong><span>Every ${s.every_minutes} minutes · ${s.enabled?'Enabled':'Paused'}${s.origin?' · '+(s.origin===state.hub?.origin?'This machine':'Another machine'):''}</span><button class="compact" data-toggle-schedule="${s.id}" data-enabled="${!s.enabled}">${s.enabled?'Pause':'Enable'}</button><button class="compact danger" data-delete-schedule="${s.id}">Remove</button></div>`).join('')}<form id="schedule-form"><div class="formgrid">${select('mission_id','Mission',state.missions.map(m=>option(m.id,m.name,'')).join(''))}${field('every_minutes','Interval in minutes',60,'number')}</div><div class="toolbar"><button class="primary">Enable schedule</button></div></form></section><section class="section"><h2>Operating boundaries</h2><p class="muted">${SERVER()?'This team server stores and shows results only; browsers and AI stay on each teammate\'s machine.':'The console listens locally.'} Web runs block mutating requests. Android runs reset the selected package but cannot intercept app network writes. Raw app video and sanitized attributed logs are evidence; local visibility prevents hub upload, not AI-provider or app traffic.</p></section>`}
// What a comparison is allowed to claim: the same conditions are one question, and whether a
// finding seen twice may be called reproduced is another. A snapshot name alone answers neither.
const DIFFERENCE={scenario:'the scenario steps',reset:'the requested start state',snapshot:'the saved device state',start_state:'how the device actually started',fault_settings:'the network faults that were applied',package:'the app package',network_settings:'the network settings',goal:'the user goal',url:'the start URL',pillars:'which pillars were checked'};
const difference=key=>DIFFERENCE[key]||key.replace(/^device_/,'device ').replaceAll('_',' ');
function comparisonBasis(c){const repro=c.reproduction;
return `<section class="section"><h2>What this comparison establishes</h2>
<p><strong>Conditions</strong><br>${c.compatible?'Both runs were recorded under the same conditions.':`These differ: ${esc(c.mismatches.map(difference).join(', '))}. Read what follows as exploratory; it does not establish a change between releases.`}</p>
${c.build_changed?'<p><strong>Build</strong><br>The two runs ran different app builds, so every difference below includes everything else that changed in the build.</p>':''}
${repro?`<p><strong>Reproduction</strong><br>${repro.eligible?`A finding present in both runs may be called reproduced.${repro.reason?' '+esc(repro.reason)+'.':''}`:`${esc(repro.reason)}. A finding present in both runs is a second observation here, not a confirmed reproduction.`}</p>`:''}
</section>`}
function comparison(){const runLabel=r=>`${r.mission.name}${(r.platform||r.mission.platform)==='android'?` · ${r.app?.version_name||r.app?.sha256?.slice(0,10)||'build'}`:''} · ${date(r.created_at)}`;return head('Compare releases','Select runs of the same mission under equivalent browser, persona and network conditions.')+`<form id="compare-form"><div class="formgrid">${select('baseline','Baseline',state.runs.map(r=>option(r.id,runLabel(r),state.runs[1]?.id)).join(''))}${select('candidate','Candidate',state.runs.map(r=>option(r.id,runLabel(r),state.runs[0]?.id)).join(''))}</div><div class="toolbar"><button class="primary" ${state.runs.length<2?'disabled':''}>Compare runs</button></div></form><div id="comparison-result"></div>`}
// A four-second refresh must not pull the control out from under the person using it.
function keepLive(){const el=document.activeElement;
if(!el||!main.contains(el)||!el.matches('input,select,textarea,button'))return()=>{};
const key=el.id?'#'+CSS.escape(el.id):el.name?`[name="${el.name}"]`:el.dataset.step!==undefined?`[data-step="${el.dataset.step}"]`:'';
const value=el.value,start=el.selectionStart,end=el.selectionEnd;
return()=>{const back=key&&main.querySelector(key);if(!back)return;
if(value!==undefined&&back.value!==undefined&&back.value!==value)back.value=value;
back.focus({preventScroll:true});try{back.setSelectionRange(start,end)}catch(e){}}}
async function render(){const generation=++renderGeneration;clearTimeout(refreshTimer);const route=(location.hash||'#overview').slice(1).split('/');document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.hash===`#${route[0]}`||route[0]==='run'&&a.hash==='#runs'));try{try{await reload()}catch(e){if(route[0]!=='settings')throw e;state={projects:[],missions:[],runs:[],schedules:[],networks:[],egresss:[],personas:[],loadError:e.message};const connection=await api('/hub/status');state.hub=connection;state.projects=Object.entries(connection.logins).map(([id,w])=>({id,name:w.name}));workspacePicker()}let html;if(route[0]==='overview')html=overview();else if(route[0]==='missions')html=missions();else if(route[0]==='journeys'){if(!scenarioPresets)scenarioPresets=await api('/scenarios');html=journeys()}
else if(['new','edit'].includes(route[0])){if(SERVER()){location.hash='#missions';return}health=await api('/health');
// #new/<journey-id> opens the form already carrying that journey; scenarioBind picks it up.
pendingJourney=route[0]==='new'?(route[1]||''):'';html=missionForm(route[0]==='edit'?route[1]:'')}else if(route[0]==='runs')html=head('Runs',`A complete record of browser execution and its outcome. · ${esc(where(workspace))}`)+runTable(state.runs);// The export picker offers the same models and Codex accounts as a mission, so this page needs the worker list once.
else if(route[0]==='run'){const [r,h]=await Promise.all([api('/runs/'+route[1]),health.ai?health:api('/health').catch(()=>health)]);health=h;html=detail(r)}else if(route[0]==='findings')html=await findings();else if(route[0]==='benchmark')html=benchmarkView();else if(route[0]==='network')html=networks();else if(route[0]==='settings')html=state.loadError?head('Settings','Repair the connection to load workspace data.')+`<p class="error">${esc(state.loadError)}</p><section class="section" id="hub-settings"></section>`:await settings();else if(route[0]==='compare')html=comparison();else html=overview();if(generation!==renderGeneration)return;const resume=keepLive(),scroll=window.scrollY;const opened=[...main.querySelectorAll('details[open]')].map(e=>e.querySelector('summary')?.textContent);main.innerHTML=html;ding(route[0]==='run'?currentRun:null);main.querySelectorAll('details').forEach(e=>e.open=e.hasAttribute('open')||opened.includes(e.querySelector('summary')?.textContent));if(state.hub?.outage&&(shared(workspace)||state.loadError)){main.insertAdjacentHTML('afterbegin',outageNotice(state.hub.outage));$('#outage-retry').onclick=render}bind();readOnly();if(route[0]==='settings'){if(SERVER())$('#hub-settings').innerHTML=`<h2>Team server</h2><p class="muted">Signed in to <strong>${esc(project().name||'this workspace')}</strong>. Missions run in your local console with your own Claude and ChatGPT subscriptions; publishing a finished run shares it here.</p>`;else await renderHubSettings($('#hub-settings'),api,async()=>{workspace='';remember('pex.workspace','');await render()})}window.scrollTo(0,scroll);resume();$('#connection').innerHTML=state.loadError?'Connection needs attention':state.hub?.outage&&shared(workspace)?'Team server not responding · '+(state.hub.outage.synced_at?'last copy':'no copy yet'):SERVER()?'<span class="dot"></span>Connected · team server (read only)':shared(workspace)?'<span class="dot"></span>Connected · '+esc(host()):'<span class="dot"></span>Connected locally';if(route[0]==='run'&&['running','queued'].includes(currentRun.status)){if(followLatest){const t=main.querySelector('.timeline');if(t)t.scrollTop=t.scrollHeight}refreshTimer=setTimeout(render,4000)}}catch(e){if(generation!==renderGeneration)return;// A view with no earlier copy cannot be shown during an outage; say which side is at fault.
const down=String(e.message||'').startsWith('Team server unreachable');
main.innerHTML=head(down?'The team server is not responding':'Could not load this view',down?'This view needs records the console has not received before, so there is no copy to show. The rest of the console still works.':'The service returned an error.')+`<p class="error">${esc(e.message)}</p><button id="retry">Try again</button><a class="button" href="#settings">Connection settings</a>`;$('#retry').onclick=render;$('#connection').textContent=down?'Team server not responding':'Connection needs attention'}}
async function submitAction(button,fn){button.disabled=true;try{await fn()}catch(e){toast(e.message)}finally{button.disabled=false}}
function bind(){const videos=[...main.querySelectorAll('video')],speed=$('#video-speed');
const journeyBox=$('#journey-search');
if(journeyBox)journeyBox.oninput=()=>{journeySearch=journeyBox.value;const q=journeySearch.trim().toLowerCase();let shown=0;
main.querySelectorAll('.journey').forEach(el=>{const hit=!q||el.dataset.find.includes(q);el.hidden=!hit;if(hit)shown++});
$('#journey-none').hidden=shown>0};
if(videos.length&&speed){const apply=()=>{videos.forEach(v=>v.playbackRate=+speed.value);remember('pex.video-speed',speed.value)};apply();videos.forEach(v=>v.onloadedmetadata=apply);speed.onchange=apply}
const onward=$('#continue-form');if(onward)onward.onsubmit=e=>{e.preventDefault();const b=onward.querySelector('[data-continue]');submitAction(b,async()=>{await api(`/runs/${b.dataset.continue}/continue`,{method:'POST',body:JSON.stringify({ai_calls:+onward.ai_calls.value||0,steps:+onward.steps.value||0})});toast('Continuing this run');await render()})};
const releaseStep=(b,id,skip)=>submitAction(b,async()=>{
// A wrong or already used token is answered by showing what the run actually wants now, never by sending it again.
try{await api(`/runs/${id}/continue-step`,{method:'POST',body:JSON.stringify({step:+b.dataset.stepNumber,token:b.dataset.token,value:skip?'':(b.dataset.value??(($('#ask-value')||{}).value||'')),skip})});toast(skip?'Skipping this value':'Continuing the run')}catch(e){toast(e.message)}
await render()});
main.querySelectorAll('[data-continue-step]').forEach(b=>b.onclick=()=>releaseStep(b,b.dataset.continueStep,false));
main.querySelectorAll('[data-skip-step]').forEach(b=>b.onclick=()=>releaseStep(b,b.dataset.skipStep,true));
main.querySelectorAll('[data-done]').forEach(c=>{c.onclick=e=>e.stopPropagation();c.onchange=async()=>{try{const res=await api(`/findings/${c.dataset.run}/${c.dataset.done}`,{method:'PATCH',body:JSON.stringify({status:c.checked?'resolved':'open'})});toast(`${c.checked?'Marked done':'Reopened'} in ${(res.synced||0)+1} report${(res.synced||0)?'s':''}`);await render()}catch(e){c.checked=!c.checked;toast(e.message)}}});main.querySelectorAll('[data-owner]').forEach(el=>el.onchange=async()=>{try{await api('/findings/'+el.dataset.run+'/'+el.dataset.owner,{method:'PATCH',body:JSON.stringify({owner:el.value})});toast('Owner saved');await render()}catch(e){toast(e.message)}});const retryUpload=$('#retry-upload');if(retryUpload)retryUpload.onclick=()=>submitAction(retryUpload,async()=>{await api('/hub/retry',{method:'POST'});toast('Retrying the upload');await render()});
main.querySelectorAll('[data-archive-build]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{await api(`/targets/${b.dataset.archiveBuild}/builds/${b.dataset.sha}`,{method:'DELETE'});toast('Build archived');await render()}));main.querySelectorAll('[data-remove-build]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{await api(`/targets/${b.dataset.removeBuild}/builds/${b.dataset.sha}/local`,{method:'DELETE'});toast('Local APK removed');await render()}));
main.querySelectorAll('[data-toggle-schedule]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{await api('/schedules/'+b.dataset.toggleSchedule,{method:'PATCH',body:JSON.stringify({enabled:b.dataset.enabled==='true'})});await render()}));main.querySelectorAll('[data-verify-egress]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{const e=await api('/egress/'+b.dataset.verifyEgress+'/verify',{method:'POST'});toast('Proxy public IP: '+e.verified_ip);await render()}));main.querySelectorAll('[data-matrix]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{const runs=await api('/missions/'+b.dataset.matrix+'/matrix',{method:'POST'});toast(runs.length+' network runs queued');location.hash='#runs'}));main.querySelectorAll('[data-start]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{const r=await api('/runs',{method:'POST',body:JSON.stringify({mission_id:b.dataset.start})});selectedStep=0;location.hash='#run/'+r.id}));main.querySelectorAll('[data-replay]').forEach(b=>b.onclick=e=>{e.stopPropagation();submitAction(b,async()=>{const r=await api(`/runs/${b.dataset.replay}/replay`,{method:'POST'});selectedStep=0;location.hash='#run/'+r.id})});main.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{await api(`/runs/${b.dataset.cancel}/cancel`,{method:'POST'});toast('Stopping browser and AI worker');await render()}));main.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>{const line=b.closest('.timeline'),scroll=line?line.scrollTop:0,page=window.scrollY;followLatest=false;selectedStep=+b.dataset.step;main.innerHTML=detail(currentRun);bind();readOnly();const t=main.querySelector('.timeline');if(t)t.scrollTop=scroll;window.scrollTo(0,page)});main.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async e=>{e.preventDefault();e.stopPropagation();const entry=copyTexts[b.dataset.copy];if(!entry)return;try{await navigator.clipboard.writeText(entry.text);toast('Copied '+entry.label)}catch(err){toast('Copy is blocked here. Select the text and copy it.')}});main.querySelectorAll('[data-finding]').forEach(s=>s.onchange=async()=>{try{await api(`/findings/${s.dataset.run}/${s.dataset.finding}`,{method:'PATCH',body:JSON.stringify({status:s.value})});toast('Finding updated')}catch(e){toast(e.message)}});main.querySelectorAll('[data-project-codex]').forEach(el=>el.onchange=async()=>{const p=state.projects.find(p=>p.id===el.dataset.projectCodex);if(!p)return;await submitAction(el,async()=>{await api('/projects/'+p.id,{method:'PUT',body:JSON.stringify({name:p.name,url:p.url,allowed_domains:p.allowed_domains||[],codex_account:el.value})});p.codex_account=el.value;toast('Workspace Codex account saved')})});
const worker=$('#provider');if(worker)worker.onchange=()=>{const input=mf?.querySelector('[name=model]');if(!input)return;const models=health.ai?.[worker.value]?.models||[];const list=document.getElementById(input.getAttribute('list'));if(list)list.innerHTML=models.map(o=>`<option value="${esc(o)}"></option>`).join('');if(input.value&&!models.includes(input.value))input.value='';input.disabled=worker.value==='none'};
main.querySelectorAll('[data-export-html]').forEach(b=>b.onclick=()=>submitAction(b,async()=>{const box=b.closest('details'),pick=n=>box.querySelector('[name='+n+']')?.value||'';
const picked=pick('export_model'),model=picked==='__custom__'?box.querySelector('#export_model_custom').value.trim():picked;
toast('Writing the report. This takes about a minute.');
const res=await fetch('/api/runs/'+b.dataset.exportHtml+'/report',{method:'POST',headers:{'X-PEX-Request':'1','Content-Type':'application/json',...(workspace?{'X-PEX-Workspace':workspace}:{})},body:JSON.stringify({provider:pick('export_provider'),model,codex_account:pick('export_codex_account')})});
if(!res.ok){const e=await res.json().catch(()=>({detail:res.statusText}));throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))}
// The report is a file to send on, so it downloads rather than opening over the run page.
const url=URL.createObjectURL(await res.blob()),link=document.createElement('a');link.href=url;link.download='run-'+b.dataset.exportHtml.slice(0,8)+'.html';link.click();URL.revokeObjectURL(url);box.open=false;toast('Report downloaded')}));
const ep=main.querySelector('.export-html');if(ep){const model=ep.querySelector('[name=export_model]'),custom=ep.querySelector('.model-custom'),
worker=ep.querySelector('[name=export_provider]'),account=ep.querySelector('[name=export_codex_account]')?.closest('.field');
const syncExport=()=>{custom.style.display=model.value==='__custom__'?'':'none';if(account)account.style.display=['codex','auto'].includes(worker.value)?'':'none'};
model.onchange=syncExport;worker.onchange=syncExport;syncExport()}
const mf=$('#mission-form');if(mf){const picker=mf.querySelector('[name=model]'),custom=mf.querySelector('.model-custom'),
mode=mf.querySelector('[name=mode]'),competitors=$('#competitors-field'),
ceiling=mf.querySelector('[name=model_max]')?.closest('.field'),effort=mf.querySelector('[name=effort]')?.closest('.field'),account=mf.querySelector('[name=codex_account]')?.closest('.field'),targetPicker=mf.querySelector('[name=target_id]'),buildPicker=mf.querySelector('[name=build]'),deviceField=mf.querySelector('[name=device]')?.closest('.field');
// A hidden field keeps its value and still submits it, so switching back restores the choice.
const sync=(changed=false)=>{const dynamic=picker&&picker.value===DYNAMIC,native=target(targetPicker?.value)?.type==='android';
if(custom&&picker)custom.style.display=picker.value==='__custom__'?'':'none';
if(ceiling)ceiling.style.display=dynamic?'':'none';
if(effort)effort.style.display=dynamic?'none':'';
if(account)account.style.display=['codex','auto'].includes(worker?.value)?'':'none';
if(competitors&&mode)competitors.style.display=!native&&mode.value==='benchmark'?'':'none';
if(buildPicker){buildPicker.closest('.field').hidden=!native;const selected=target(targetPicker?.value);if(changed)buildPicker.innerHTML=option('','Latest non-archived','')+(selected?.builds||[]).map(b=>option(b.sha256,`${b.version_name} · ${b.sha256.slice(0,10)}`,'')).join('')}
if(deviceField)deviceField.hidden=!native;
// One vocabulary, two targets: the builder shows for both. Only a saved device state is Android's.
const scenarioBox=$('#scenario-section');if(scenarioBox)scenarioBox.hidden=!targetPicker?.value;
const savedState=$('#start-snapshot'),savedRadio=mf.querySelector('[name=start_state][value=snapshot]');
if(savedState){savedState.hidden=!native;
if(!native&&savedRadio?.checked){mf.querySelector('[name=start_state][value=fresh]').checked=true;$('#snapshot-field').hidden=true}
const note=$('#snapshot-note');if(note&&!native)note.textContent='A website mission loads a saved session through a persona instead.'}
for(const name of ['browser','viewport','competitors','persona_id','login_identifier','login_password']){const input=mf.querySelector(`[name="${name}"]`);if(input)input.disabled=native}
const seo=mf.querySelector('[name=pillars][value=seo_aeo]');if(seo){seo.disabled=native;if(native)seo.checked=false}
// The emulator console shapes latency and bandwidth on the mobile radio; nothing else was measured there.
const net=mf.querySelector('[name=network]');if(net){net.querySelectorAll('option').forEach(o=>{const p=state.networks.find(v=>v.id===o.value)||{};
o.disabled=native&&(p.backend==='netem'||!!p.offline||!!p.down_mbps!==!!p.up_mbps||['jitter_ms','loss_pct','reorder_pct','duplicate_pct','disconnect_every_seconds'].some(k=>p[k]))});
if(net.selectedOptions[0]?.disabled)net.value='baseline'}
if(native&&mode?.value==='benchmark')mode.value='audit'
if(changed){const selected=target(targetPicker.value),url=mf.querySelector('[name=url]'),domains=mf.querySelector('[name=allowed_domains]'),visibility=mf.querySelector('[name=visibility]');url.value=selected?.type==='web'?selected.url||'':'';domains.value=(selected?.allowed_domains||[]).join(', ');if(selected?.visibility==='local')visibility.value='local'}};
sync();if(picker)picker.onchange=sync;if(mode)mode.onchange=sync;if(targetPicker)targetPicker.onchange=()=>sync(true);if(worker)worker.addEventListener('change',sync)
// --- idea first -------------------------------------------------------------
// One endpoint answers both asks: two whole missions from an idea, or one revised mission.
let scenario=null,undo=null,busy=false,shown=[],rough='';
const draftBox=$('#draft-section'),ideaBox=$('#idea-box'),panel=$('#mission-suggestions'),
 undoButton=$('#undo-ai'),runSummary=$('#run-summary'),ideaField=$('#mission-idea'),ideaError=$('#idea-error'),
 suggestButton=$('#idea-suggest'),reviseField=$('#mission-revise'),reviseError=$('#revise-error'),reviseGo=$('#revise-go');
const value=name=>mf.querySelector(`[name="${name}"]`);
const checkedPillars=()=>[...mf.querySelectorAll('[name=pillars]:checked')].map(c=>c.value);
// Saving is decided here alone, so no single rule can re-enable what another one forbids.
function refreshSave(){const left=scenario?scenario.blanks():0,stuck=scenario?scenario.dirtyYaml():false;
 mf.querySelectorAll('button[type=submit]').forEach(b=>b.disabled=busy||left>0||stuck)}
// Every control sleeps while the worker thinks, and wakes to whatever the rules say afterwards.
const setBusy=on=>{busy=on;
 mf.querySelectorAll('input,select,textarea,button').forEach(el=>{
  if(on){if(el.disabled)el.dataset.wasOff='1';el.disabled=true}
  else{el.disabled=el.dataset.wasOff==='1';delete el.dataset.wasOff}});
 if(!on){sync();describeRun()}
 refreshSave()};
// What this mission will actually do, in the words of its own settings.
function describeRun(){if(!runSummary)return;
 const native=target(value('target_id')?.value)?.type==='android',bits=[value('provider').value,value('mode').value];
 if(!native)bits.push(value('browser').value);
 bits.push(Math.max(1,Math.round(+value('max_seconds').value/60))+' min',(+value('max_steps').value||0)+' actions');
 const on=checkedPillars().map(k=>label[k]||k);
 bits.push(on.length?on.join(', '):'no pillars');
 runSummary.textContent=bits.join(' · ')}
if(runSummary){mf.querySelectorAll('#run-settings input,#run-settings select').forEach(el=>el.addEventListener('change',describeRun));
 mf.querySelector('[name=target_id]')?.addEventListener('change',describeRun)}
// Network shaping is a Chromium capability; a suggestion that uses it says so and takes it.
const needsChromium=steps=>steps.some(s=>{const e=s.event;return !!e&&(!!e.speed||e.delay_ms!=null||['wifi','cellular'].includes(e.network))});
const snapshot=()=>({name:value('name').value,goal:value('goal').value,steps:clone(scenarioSteps),
 mode:value('mode').value,pillars:[...mf.querySelectorAll('[name=pillars]')].map(c=>c.checked),
 browser:value('browser').value,max_seconds:value('max_seconds').value,max_steps:value('max_steps').value,ai_budget:value('ai_budget').value});
const restore=was=>{value('name').value=was.name;value('goal').value=was.goal;value('mode').value=was.mode;
 [...mf.querySelectorAll('[name=pillars]')].forEach((c,i)=>c.checked=was.pillars[i]);
 for(const k of ['browser','max_seconds','max_steps','ai_budget'])value(k).value=was[k];
 // Exact values are coming back, so the time limit is not re-fitted around them.
 sync();if(scenario)scenario.replace(was.steps,{fit:false});describeRun();refreshSave()};
if(undoButton)undoButton.onclick=()=>{if(!undo)return;restore(undo);undo=null;undoButton.hidden=true;
 panel.querySelectorAll('.suggestion').forEach(el=>el.classList.remove('applied'));toast('Change undone.')};
// One suggestion, put where each part belongs. The previous mission waits in the single undo slot.
const apply=(s,revised)=>{undo=snapshot();if(undoButton)undoButton.hidden=false;
 const browserWas=value('browser').value;
 if(s.title)value('name').value=s.title;
 value('goal').value=s.goal;
 if(s.mode)value('mode').value=s.mode;
 mf.querySelectorAll('[name=pillars]').forEach(c=>c.checked=(s.pillars||[]).includes(c.value));
 const steps=s.steps||[];
 if(steps.length){
  // ponytail: a flat four actions per step, raised only upward; tune if scenarios start running out of room.
  const room=Math.max(8,Math.min(40,4*steps.length));
  if((+value('max_steps').value||0)<room)value('max_steps').value=room;
  if((+value('ai_budget').value||0)<room)value('ai_budget').value=room;
  if(needsChromium(steps))value('browser').value='chromium'}
 sync();if(scenario)scenario.replace(steps);
 if(draftBox)draftBox.hidden=false;if(ideaBox)ideaBox.open=false;
 describeRun();refreshSave();
 // The notice says only what actually happened: how much is left, and a setting this changed.
 const left=scenario?scenario.blanks():0;
 toast((revised?'Mission revised.':left?`Mission filled in. Fill the ${left} blank${left===1?'':'s'}, then save.`:'Mission filled in. Review it, then save.')
  +(value('browser').value!==browserWas?' Chromium selected for network shaping.':''));
 if(!(scenario&&scenario.focusBlank()))value('name').focus()};
// A card shows the whole mission, steps included, because that is what gets applied.
const HEADINGS={goal:'Let the worker find its own way',scenario:'Run these exact steps'};
const cards=(data,useLabel,revised)=>{shown=data.suggestions||[];
 const native=target(value('target_id').value)?.type==='android';
 panel.hidden=false;
 // data-apply is the index into shown, not into the group, so grouping never rewires a button.
 const card=(s,i)=>{const steps=s.steps||[],notes=[];
  if(s.caveat)notes.push('Needs first: '+s.caveat);
  if(needsChromium(steps))notes.push('Network shaping runs on Chromium, so applying this selects it.');
  if(steps.some(x=>x.manual))notes.push('This mission pauses for an operator at the screen.');
  if(!native&&steps.some(x=>x.event&&(x.event.home||x.event.back||x.event.relaunch||x.event.kill)))notes.push('App events such as home or relaunch only run on an Android target.');
  return `<article class="suggestion"><h3 dir="auto">${esc(s.title||'Mission')}</h3><p class="muted" dir="auto">What you learn: ${esc(s.why||'')}</p><p class="goaltext" dir="auto">${esc(s.goal)}</p>`
  +(steps.length?`<ol class="steplines">${steps.map(x=>`<li dir="auto">${esc(describeStep(x))}</li>`).join('')}</ol>`
   :'<p class="muted">No steps: the worker finds its own way from the goal.</p>')
  +`<div class="findmeta"><span class="badge">${esc(s.mode)}</span>${(s.pillars||[]).map(k=>`<span class="badge">${esc(label[k]||k)}</span>`).join('')}${steps.length?`<span class="badge">${steps.length} step${steps.length===1?'':'s'}</span>`:''}</div>`
  +notes.map(n=>`<small class="caveat" dir="auto">${esc(n)}</small>`).join('')
  +`<div class="toolbar"><button type="button" class="compact primary" data-apply="${i}">${esc(useLabel||(s.shape==='scenario'?'Use this scenario':'Use this goal'))}</button></div></article>`};
 const dropped=data.rejected?.length?`<p class="muted suggestfoot">${data.rejected.length} suggestion${data.rejected.length===1?'':'s'} did not fit the contract and ${data.rejected.length===1?'was':'were'} dropped: ${esc(data.rejected.join('; '))}</p>`:'';
 panel.innerHTML=(useLabel?shown.map(card).join('')
  :Object.keys(HEADINGS).map(shape=>{const group=shown.map((s,i)=>[s,i]).filter(([s])=>s.shape===shape);
   return group.length?`<h3 class="suggesthead">${esc(HEADINGS[shape])}</h3>`+group.map(([s,i])=>card(s,i)).join(''):''}).join(''))
 +dropped
 +`<small class="suggestfoot">Suggested by ${esc(data.usage?.provider||'')} · ${esc(data.usage?.model_reported||data.usage?.model_requested||'')}. Nothing runs until you save and start it.</small>`;
 panel.querySelectorAll('[data-apply]').forEach(b=>b.onclick=()=>{apply(shown[+b.dataset.apply],revised);
  panel.querySelectorAll('.suggestion').forEach(el=>el.classList.remove('applied'));b.closest('.suggestion').classList.add('applied')})};
const context=goal=>({project_id:value('project_id').value,target_id:value('target_id').value,build:value('build').value,
 url:value('url').value,goal,mode:value('mode').value,viewport:value('viewport').value,
 provider:value('provider').value,codex_account:value('codex_account')?.value||'',
 competitors:(value('competitors')?.value||'').split(/[\n,]/).map(s=>s.trim()).filter(Boolean)});
const request=async({button,busyText,doneText,errorBox,body,after})=>{
 // Unapplied YAML is not a scenario yet; nothing may replace the steps while it sits there.
 if(scenario&&scenario.dirtyYaml()){errorBox.textContent='Apply your YAML edits before changing the mission.';scenario.showYaml();return}
 const generation=renderGeneration,was=button.textContent;let arrived=false;
 errorBox.textContent='';setBusy(true);button.textContent=busyText;
 panel.hidden=false;panel.setAttribute('aria-busy','true');panel.innerHTML='<div class="skeleton"></div><div class="skeleton"></div>';
 try{const data=await api('/missions/suggest',{method:'POST',body:JSON.stringify(body)});
  // A later render replaced this form; an answer written into it would go nowhere.
  if(generation!==renderGeneration||!mf.isConnected)return;
  arrived=true;after(data)}
 catch(e){if(generation!==renderGeneration||!mf.isConnected)return;
  panel.hidden=true;panel.innerHTML='';errorBox.textContent=e.message}
 finally{if(generation===renderGeneration&&mf.isConnected){
  button.textContent=arrived&&doneText?doneText:was;panel.removeAttribute('aria-busy');setBusy(false)}}};
if(suggestButton&&ideaField)suggestButton.onclick=()=>{
 // Editing the box replaces the remembered idea; applying a suggestion does not.
 const typed=ideaField.value.trim();if(typed)rough=typed;
 if(rough.length<3){ideaError.textContent='Write what you want to find out first, in your own words.';ideaField.focus();return}
 if(!value('target_id').value){ideaError.textContent='Choose the target this mission runs against first.';value('target_id').focus();return}
 request({button:suggestButton,busyText:'Asking the AI worker…',doneText:'Try again',errorBox:ideaError,
  body:context(rough),after:data=>cards(data)})};
const manual=$('#idea-manual');
if(manual)manual.onclick=()=>{if(draftBox)draftBox.hidden=false;if(ideaBox)ideaBox.open=false;value('name').focus()};
if(reviseGo&&reviseField)reviseGo.onclick=()=>{const wanted=reviseField.value.trim();
 if(wanted.length<3){reviseError.textContent='Say what should change, in your own words.';reviseField.focus();return}
 request({button:reviseGo,busyText:'Revising…',errorBox:reviseError,
  body:{...context(wanted),revise:true,current:{name:value('name').value,goal:value('goal').value,
   steps:scenarioSteps,mode:value('mode').value,pillars:checkedPillars()}},
  after:data=>cards(data,'Use this revision',true)})};
scenario=scenarioBind(mf,sync,refreshSave);
$('#scenario-yaml')?.addEventListener('input',refreshSave);
describeRun();refreshSave()}
if(mf)mf.onsubmit=async e=>{e.preventDefault();const fd=new FormData(mf),data=Object.fromEntries(fd);data.allowed_domains=data.allowed_domains.split(',').map(s=>s.trim()).filter(Boolean);data.competitors=(data.competitors||'').split(/[\n,]/).map(s=>s.trim()).filter(Boolean);data.model=data.model==='__custom__'?(data.model_custom||'').trim():data.model;delete data.model_custom;data.pillars=fd.getAll('pillars');for(const k of ['max_steps','max_seconds','ai_budget','observe_seconds'])data[k]=+data[k];delete data.run;
// Steps and the start state run on either platform; a saved device state is Android's alone.
const start=data.start_state,snapshot=data.snapshot_id;delete data.start_state;delete data.snapshot_id;
if($('#scenario-section')){const native=target(data.target_id)?.type==='android';
data.scenario=scenarioSteps;data.reset=start==='fresh'?'fresh':'keep';
if(native)data.snapshot=start==='snapshot'?(snapshot||''):''}const button=e.submitter;await submitAction(button,async()=>{try{const id=mf.dataset.id,m=await api('/missions'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(data)});toast('Mission saved');if(button.name==='run'){const r=await api('/runs',{method:'POST',body:JSON.stringify({mission_id:m.id})});selectedStep=0;location.hash='#run/'+r.id}else location.hash='#missions'}catch(err){$('#form-error').textContent=err.message;throw err}})};
for(const [sel,path] of [['#mission-import','/import'],['#persona-import','/personas']]){const input=$(sel);if(input)input.onchange=async()=>{if(!input.files[0])return;const fd=new FormData();fd.append('file',input.files[0]);try{await api(path,{method:'POST',body:fd});toast('Import complete');await render()}catch(e){toast(e.message)}}}
const projectForm=$('#project-form');
if(projectForm){
  const label=projectForm.querySelector('button.primary'),extra=$('#shared-fields');
  projectForm.querySelectorAll('[name=where]').forEach(radio=>radio.onchange=()=>{const team=projectForm.elements.where.value==='shared';if(extra)extra.hidden=!team;label.textContent=team?'Create shared workspace':'Create workspace on this Mac'});
  projectForm.onsubmit=e=>{e.preventDefault();const data=Object.fromEntries(new FormData(projectForm));
    const body={name:data.name,url:data.url,allowed_domains:String(data.allowed_domains||'').split(',').map(s=>s.trim()).filter(Boolean)};
    submitAction(e.submitter,async()=>{
      if(data.where==='shared'){
        const created=await api('/hub/admin/workspaces',{method:'POST',body:JSON.stringify({...body,username:data.username,password:data.password,seed:!!data.seed})});
        // Signing in to the new workspace is what puts it in the picker; the workspace exists either way.
        try{await api('/hub/login',{method:'POST',body:JSON.stringify({url:state.hub.url,username:data.username,password:data.password})});workspace=created.id;remember('pex.workspace',workspace);toast('Shared workspace created on '+host())}
        catch(err){toast(`Workspace created on ${host()}. Sign in to it under Team server to open it.`)}
      }else{const created=await api('/projects',{method:'POST',body:JSON.stringify(body)});workspace=created.id;remember('pex.workspace',workspace);toast('Workspace created on this Mac')}
      await render();
    })};
}
const targetForm=$('#target-form');if(targetForm){const kind=targetForm.querySelector('[name=type]'),apk=targetForm.querySelector('[name=apk]'),siteUrl=targetForm.querySelector('[name=url]'),button=targetForm.querySelector('button.primary'),errorLine=targetForm.querySelector('.error');const shape=()=>{const native=kind.value==='android';apk.closest('.field').hidden=!native;siteUrl.closest('.field').hidden=native;siteUrl.required=!native;button.textContent=native?'Add Android app':'Add website'};shape();kind.onchange=shape;
targetForm.onsubmit=e=>{e.preventDefault();const fd=new FormData(targetForm),file=fd.get('apk');fd.delete('apk');const data=Object.fromEntries(fd);data.allowed_domains=String(data.allowed_domains||'').split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);data.package='';data.builds=[];if(data.type==='android')data.url='';errorLine.textContent='';submitAction(e.submitter,async()=>{let t;try{t=await api('/targets',{method:'POST',body:JSON.stringify(data)})}catch(err){errorLine.textContent=err.message;throw err}
if(data.type==='android'&&file&&file.size){try{const body=new FormData();body.append('file',file);const saved=await api(`/targets/${t.id}/builds`,{method:'POST',body});const b=saved.builds[saved.builds.length-1];toast(`${saved.name} added. Build ${b.version_name} stored on this Mac`)}catch(err){toast(`${t.name} added, but the APK was rejected: ${err.message}`)}}
else toast(data.type==='android'?`${t.name} added. Add its APK build from the table`:`${t.name} added`);await render()})}}
main.querySelectorAll('[data-apk]').forEach(input=>input.onchange=async()=>{if(!input.files[0])return;const form=new FormData();form.append('file',input.files[0]);const label=input.closest('label');await submitAction(label,async()=>{await api(`/targets/${input.dataset.apk}/builds`,{method:'POST',body:form});toast('APK validated and stored on this Mac');await render()})});
main.querySelectorAll('[data-share]').forEach(button=>button.onclick=()=>submitAction(button,async()=>{await api('/'+button.dataset.share+'/share',{method:'POST'});toast('Shared with the workspace');await render()}));
const snapshotForm=$('#snapshot-form');if(snapshotForm)snapshotForm.onsubmit=e=>{e.preventDefault();const line=snapshotForm.querySelector('.error');line.textContent='';
// Saving copies whatever the emulator holds now, so the wait is stated rather than hidden behind a spinner.
submitAction(e.submitter,async()=>{const input=snapshotForm.querySelector('[name=name]'),name=input.value.trim();
if(!name){line.textContent='Name this state so you can recognise it later.';input.focus();return}
const was=e.submitter.textContent;e.submitter.textContent='Saving the device state…';
try{const kept=await api('/android/snapshots',{method:'POST',body:JSON.stringify({name,project_id:workspace})});toast('Saved '+kept.name);await render()}
catch(err){line.textContent=err.message;e.submitter.textContent=was}})};
// Deleting a saved state cannot be undone, so the button asks once, naming the state.
main.querySelectorAll('[data-delete-snapshot]').forEach(b=>{const label=b.textContent;b.onclick=()=>{
if(b.dataset.armed!=='1'){b.dataset.armed='1';b.classList.add('danger');b.textContent=`Delete “${b.dataset.name}”?`;
setTimeout(()=>{if(b.dataset.armed==='1'){b.dataset.armed='';b.classList.remove('danger');b.textContent=label}},8000);return}
submitAction(b,async()=>{await api(`/android/snapshots/${b.dataset.deleteSnapshot}?project=${encodeURIComponent(workspace)}`,{method:'DELETE'});toast('Saved state deleted');await render()})}});
for(const [sel,path] of [['#network-form','/networks'],['#egress-form','/egress'],['#schedule-form','/schedules']]){const f=$(sel);if(f)f.onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(f));for(const k of ['latency_ms','down_mbps','up_mbps','every_minutes','jitter_ms','loss_pct','reorder_pct','duplicate_pct','disconnect_every_seconds','disconnect_seconds'])if(k in data)data[k]=+data[k];if(typeof data.allowed_domains==='string')data.allowed_domains=data.allowed_domains.split(',').map(s=>s.trim()).filter(Boolean);if(sel==='#schedule-form')data.enabled=true;await submitAction(e.submitter,async()=>{await api(path,{method:'POST',body:JSON.stringify(data)});toast('Saved');await render()})}}
for(const [attr,path] of [['deleteMission','missions'],['deleteSchedule','schedules'],['deleteEgress','egress']])main.querySelectorAll(`[data-${attr.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())}]`).forEach(b=>b.onclick=()=>submitAction(b,async()=>{await api(`/${path}/${b.dataset[attr]}`,{method:'DELETE'});toast('Removed');if(path==='missions')location.hash='#missions';else await render()}));
const topics=[...main.querySelectorAll('details[data-topic]')];
if(topics.length){const folded=recall('pex.findings-collapsed','').split(',').filter(Boolean);
topics.forEach(d=>{d.open=!folded.includes(d.dataset.topic);d.ontoggle=()=>remember('pex.findings-collapsed',topics.filter(t=>!t.open).map(t=>t.dataset.topic).join(','))})}
for(const [sel,key] of [['#finding-sort','pex.findings-sort'],['#finding-owner','pex.findings-owner'],['#finding-hide-done','pex.findings-hide-done']]){const el=$(sel);if(el)el.onchange=async()=>{remember(key,el.type==='checkbox'?(el.checked?'1':'0'):el.value);await render()}}
const search=$('#finding-search');if(search)search.oninput=()=>main.querySelectorAll('[data-filter]').forEach(el=>el.hidden=!el.dataset.filter.includes(search.value.toLowerCase()));const cf=$('#compare-form');if(cf)cf.onsubmit=async e=>{e.preventDefault();await submitAction(e.submitter,async()=>{const d=Object.fromEntries(new FormData(cf)),c=await api('/compare?'+new URLSearchParams(d));$('#comparison-result').innerHTML=`${comparisonBasis(c)}<div class="factline"><span><strong>${c.new.length}</strong> new</span><span><strong>${c.resolved.length}</strong> not seen again</span><span><strong>${c.persisting.length}</strong> persisting</span></div><div class="section"><h2>New findings</h2>${c.new.map(f=>findingHTML(f)).join('')||'<p>No new findings.</p>'}</div><div class="section"><h2>Metric change</h2><pre class="raw">${esc(JSON.stringify(c.metric_delta,null,2))}</pre>${c.identity_uncertain?.length?`<p class="notice">${c.identity_uncertain.length} historical AI findings lack stable issue keys. Review them manually or collect a new replay.</p>`:''}${c.not_assessed?.length?`<p class="notice">${c.not_assessed.length} findings could not be reassessed because conditions differ, coverage is incomplete, or historical issue keys are missing.</p>`:''}<p class="muted">Milliseconds except CLS. Single-visit differences are not statistically established regressions.</p></div>`})}}
window.addEventListener('hashchange',()=>{selectedStep=0;followLatest=true;render()});render();
