(() => {
  const supported=new Set(PerformanceObserver.supportedEntryTypes||[]);
  window.__pex={lcp:null,cls:supported.has('layout-shift')?0:null,inp:null,long_tasks:supported.has('longtask')?0:null,video:[],player_events:[],errors:[],supported:[...supported]};
  const watch=(type,fn,options={})=>{try{new PerformanceObserver(l=>l.getEntries().forEach(fn)).observe({type,buffered:true,...options})}catch{}};
  watch('largest-contentful-paint',e=>window.__pex.lcp=e.startTime);
  let session=0,first=0,last=0;
  watch('layout-shift',e=>{if(e.hadRecentInput)return;if(e.startTime-last>1000||e.startTime-first>5000){session=0;first=e.startTime}session+=e.value;last=e.startTime;window.__pex.cls=Math.max(window.__pex.cls,session)});
  const interactions=new Map();watch('event',e=>{if(e.interactionId){interactions.set(e.interactionId,Math.max(interactions.get(e.interactionId)||0,e.duration));window.__pex.inp=Math.max(...interactions.values())}},{durationThreshold:16});
  watch('longtask',()=>window.__pex.long_tasks++);
  addEventListener('error',e=>{if(window.__pex.errors.length<100)window.__pex.errors.push(String(e.message))});
  addEventListener('pex:player',e=>{const d=e.detail;if(d&&typeof d==='object'){window.__pex.player_events.push({at:performance.now(),type:String(d.type||'custom'),bitrate_kbps:Number.isFinite(d.bitrate_kbps)?d.bitrate_kbps:null,resolution:String(d.resolution||''),error:String(d.error||'')});if(window.__pex.player_events.length>500)window.__pex.player_events.shift()}});
  const seen=new WeakMap();const players=[];
  const closeWait=(s,t)=>{if(s.waiting_at!==null){s.stall_ms+=Math.max(0,t-s.waiting_at);s.waiting_at=null}};
  const hook=()=>document.querySelectorAll('video').forEach(v=>{
    if(seen.has(v))return;
    const s={events:[],play_requested:null,startup_ms:null,stall_ms:0,stall_count:0,waiting_at:null,error:null,width:0,height:0,dropped_frames:null,total_frames:null};
    seen.set(v,s);players.push([v,s]);window.__pex.video.push(s);
    for(const type of ['play','playing','waiting','stalled','pause','ended','error','loadedmetadata','resize','emptied'])v.addEventListener(type,()=>{
      const t=performance.now();s.events.push({type,ms:t,current_time:v.currentTime});if(s.events.length>200)s.events.shift();
      if(type==='play'&&s.play_requested===null)s.play_requested=t;
      if(type==='waiting'&&s.startup_ms!==null&&!v.seeking&&s.waiting_at===null){s.waiting_at=t;s.stall_count++}
      if(type==='playing'){if(s.play_requested!==null&&s.startup_ms===null)s.startup_ms=t-s.play_requested;closeWait(s,t)}
      if(['pause','ended','error','emptied'].includes(type))closeWait(s,t);
      if(type==='error')s.error=v.error?.code??null;
    });
  });
  // A notification the page creates is kept live, so a scenario can click it and the page's own handler runs.
  const notes=[];window.__pex.notifications=notes;
  const Native=window.Notification;
  if(Native)try{
    const Wrapped=function(title,options){const made=new Native(title,options||{});notes.push(made);return made};
    Wrapped.prototype=Native.prototype;Object.setPrototypeOf(Wrapped,Native);window.Notification=Wrapped;
  }catch{}
  window.__pexSnapshot=()=>{
    hook();const t=performance.now();
    return {...window.__pex,notifications:notes.length,video:players.map(([v,s])=>{const q=v.getVideoPlaybackQuality?.();const stall=s.stall_ms+(s.waiting_at===null?0:t-s.waiting_at);const elapsed=s.play_requested===null?null:t-s.play_requested;return {...s,width:v.videoWidth,height:v.videoHeight,current_time:v.currentTime,paused:v.paused,dropped_frames:q?.droppedVideoFrames??null,total_frames:q?.totalVideoFrames??null,stall_ms:stall,elapsed_ms:elapsed,stall_ratio:elapsed>0?stall/elapsed:null}})};
  };
  const start=()=>{hook();new MutationObserver(hook).observe(document.documentElement,{childList:true,subtree:true})};
  if(document.readyState==='loading')addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
