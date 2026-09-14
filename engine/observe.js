() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 // Offering a control that something else covers sends the worker to a click that can only time out:
 // a leftover widget from a previous screen, a control under a banner. Only judge what is on screen now.
 const hittable=e=>{const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
  if(x<0||y<0||x>innerWidth||y>innerHeight)return true;
  const top=document.elementFromPoint(x,y);return !top||top===e||e.contains(top)};
 const actionable=[...document.querySelectorAll('a[href],button,input,textarea,select,[role="button"],[role="link"],[role="checkbox"],[role="radio"],[role="switch"],[role="tab"],[role="menuitem"],[role="option"],[role="combobox"]')].filter(e=>visible(e)&&hittable(e)).slice(0,120);
 // A widget built from a div carries its label in a sibling, so borrow the row's text when it has none of its own.
 const label=e=>{const by=e.getAttribute('aria-labelledby');
  const own=(e.getAttribute('aria-label')||(by&&document.getElementById(by)?.innerText)||e.innerText||e.getAttribute('placeholder')||e.getAttribute('title')||e.getAttribute('name')||'').trim();
  // The row's first line is the label; what follows is status, and a countdown would rename the control every second.
  const borrowed=(e.parentElement?.innerText||'').trim().split('\n').map(s=>s.trim()).find(Boolean)||own;
  return (own.length>2||!e.getAttribute('role')?own:borrowed).slice(0,160)};
 const controls=actionable.map((e,i)=>{const id='pex-'+i;e.setAttribute('data-pex-id',id);const r=e.getBoundingClientRect();return {id,tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',text:label(e),input_type:e.getAttribute('type')||'',href:e.href||'',disabled:!!e.disabled,filled:(e.tagName==='INPUT'||e.tagName==='TEXTAREA')&&!!e.value,options:e.tagName==='SELECT'?[...e.options].slice(0,50).map(o=>({label:o.label,value:o.value})):[],box:{x:r.x,y:r.y,width:r.width,height:r.height}}});
 const meta=n=>document.querySelector(`meta[name="${n}"]`)?.content||'';
 const jsonld=[...document.querySelectorAll('script[type="application/ld+json"]')].slice(0,20).map(e=>e.textContent.slice(0,10000));
 const nav=performance.getEntriesByType('navigation')[0];
 return {url:location.href,title:document.title,lang:document.documentElement.lang,dir:document.documentElement.dir,text:document.body.innerText.slice(0,14000),controls,
 metadata:{description:meta('description'),robots:meta('robots'),canonical:document.querySelector('link[rel="canonical"]')?.href||'',headings:[...document.querySelectorAll('h1,h2,h3')].slice(0,60).map(e=>({level:e.tagName,text:e.innerText.slice(0,200)})),jsonld,overflow:document.documentElement.scrollWidth>innerWidth+4},
 metrics:{...(window.__pexSnapshot?.()||window.__pex),ttfb_ms:nav?nav.responseStart-nav.requestStart:null,dom_loaded_ms:nav?.domContentLoadedEventEnd||null,requests:performance.getEntriesByType('resource').length,inp_note:'Maximum observed interaction duration in this lab visit; not a field percentile'},
 viewport:{width:innerWidth,height:innerHeight,scroll_y:scrollY}};
}
