import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {chromium,firefox,webkit} from 'playwright';
const token=process.env.PEX_NETEM_TOKEN;
if(!token||token.length<24)throw Error('Set a random PEX_NETEM_TOKEN of at least 24 characters');
let browser,watchdog;
function tc(args,optional=false){try{return execFileSync('tc',args,{encoding:'utf8'})}catch(e){if(!optional)throw Error(String(e.stderr||e.message))}}
function clear(){tc(['qdisc','del','dev','eth0','root'],true)}
async function stop(){clear();clearTimeout(watchdog);if(browser){await browser.close();browser=null}}
function number(v,min,max){if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)throw Error('Invalid network parameter');return v}
const server=http.createServer(async(req,res)=>{
 res.setHeader('Content-Type','application/json');
 if(req.headers.authorization!==`Bearer ${token}`){res.writeHead(403);return res.end('{"error":"Unauthorized"}')}
 try{
  if(req.url==='/health'&&req.method==='GET')return res.end(JSON.stringify({ok:true,busy:!!browser,scope:'Isolated Linux browser container; egress packet shaping'}));
  if(req.url==='/stop'&&req.method==='POST'){await stop();return res.end('{"ok":true}')}
  if(req.url==='/start'&&req.method==='POST'){
   if(browser){res.writeHead(409);return res.end('{"error":"Runner busy"}')}
   let raw='';for await(const part of req){raw+=part;if(raw.length>10000)throw Error('Request too large')}
   const p=JSON.parse(raw);const b={chromium,firefox,webkit}[p.browser];if(!b)throw Error('Unknown browser');
   const latency=number(p.latency_ms,0,5000),jitter=number(p.jitter_ms||0,0,2000),loss=number(p.loss_pct||0,0,100),up=number(p.up_mbps||0,0,10000);
   if(p.offline)throw Error('Use browser offline emulation; complete netem loss would break control traffic');
   if((p.down_mbps||0)>0)throw Error('This netem adapter shapes egress only. Set download to 0; use browser throttling for a download cap.');
   clear();browser=await b.launchServer({host:'0.0.0.0',port:8753,headless:true});
   const args=['qdisc','replace','dev','eth0','root','netem'];
   if(latency)args.push('delay',`${latency}ms`,`${jitter}ms`);
   if(loss)args.push('loss',`${loss}%`);
   if(p.reorder_pct){number(p.reorder_pct,0,50);if(!latency)throw Error('Reordering requires latency');args.push('reorder',`${p.reorder_pct}%`)}
   if(p.duplicate_pct){number(p.duplicate_pct,0,50);args.push('duplicate',`${number(p.duplicate_pct,0,50)}%`)}
   if(up)args.push('rate',`${up}mbit`);
   if(args.length>6)tc(args);
   const applied=tc(['-j','qdisc','show','dev','eth0']);
   watchdog=setTimeout(()=>stop(),Math.min(p.max_seconds||600,3600)*1000+30000);
   return res.end(JSON.stringify({endpoint:browser.wsEndpoint(),applied:JSON.parse(applied),scope:'Container egress only, including control traffic; download cap unavailable'}));
  }
  res.writeHead(404);res.end('{"error":"Not found"}');
 }catch(e){await stop();res.writeHead(400);res.end(JSON.stringify({error:e.message}))}
});
server.listen(8752,'0.0.0.0');
process.on('SIGTERM',async()=>{await stop();server.close();process.exit()});
