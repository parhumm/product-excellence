"""Offline checks for shared evidence rendered by the browser console."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_shared_evidence_links_are_inert_outside_the_run():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the offline JavaScript rendering check')
    source = Path(__file__).resolve().parents[1] / 'static' / 'app.js'
    subprocess.run([node, '-e', r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({document:{querySelector:()=>null}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8').split("window.addEventListener('hashchange'")[0],context);
vm.runInContext(`
const path='/api/runs/run-1/artifacts/step-001.png';
if(evidenceURL('run-1',path)!==path)throw Error('Valid evidence was rejected');
const invalid=['javascript:alert(1)','//example.com/file','/api/runs/other/artifacts/file.png',
'/api/runs/run-1/artifacts/..','/api/runs/run-1/artifacts/%2e%2e',
'/api/runs/run-1/artifacts/file.png?x=1',path+'" onerror="bad',null,{}];
for(const value of invalid)if(evidenceURL('run-1',value)!=='#')throw Error('Unsafe evidence accepted');
state={missions:[]};
for(const name of ['summarySection','consoleSection','aiUsage','runText','timelineText',
'conditionsText','coverageText','logText','evidenceText','statusNotice'])globalThis[name]=()=>'';
const bad='" onerror="MARKER';
const run={id:'run-1',mission:{name:'Example',network:'baseline'},status:'completed',
observations:[{id:bad,screenshot:bad,dom:'javascript:MARKER',metrics:{}}],
trace:'javascript:MARKER',video:bad,findings:[],events:[],actions:[],
sites:[{url:'https://example.com',evidence_id:bad}]};
globalThis.html=detail(run);
`,context);
assert(!context.html.includes('onerror="MARKER'));
assert(!context.html.includes('javascript:MARKER'));
assert(context.html.includes('src="#"'));
assert(context.html.includes('href="#"'));
''', str(source)], check=True, capture_output=True, text=True)
