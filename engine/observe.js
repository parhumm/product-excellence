() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const actionable=[...document.querySelectorAll('a[href],button,input,textarea,select,[role="button"],[role="link"]')].filter(visible).slice(0,120);
 const controls=actionable.map((e,i)=>{const id='pex-'+i;e.setAttribute('data-pex-id',id);const r=e.getBoundingClientRect();return {id,tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',text:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.getAttribute('name')||'').trim().slice(0,160),input_type:e.getAttribute('type')||'',href:e.href||'',disabled:!!e.disabled,options:e.tagName==='SELECT'?[...e.options].slice(0,50).map(o=>({label:o.label,value:o.value})):[],box:{x:r.x,y:r.y,width:r.width,height:r.height}}});
 const meta=n=>document.querySelector(`meta[name="${n}"]`)?.content||'';
 const jsonld=[...document.querySelectorAll('script[type="application/ld+json"]')].slice(0,20).map(e=>e.textContent.slice(0,10000));
 const nav=performance.getEntriesByType('navigation')[0];
 return {url:location.href,title:document.title,lang:document.documentElement.lang,dir:document.documentElement.dir,text:document.body.innerText.slice(0,14000),controls,
 metadata:{description:meta('description'),robots:meta('robots'),canonical:document.querySelector('link[rel="canonical"]')?.href||'',headings:[...document.querySelectorAll('h1,h2,h3')].slice(0,60).map(e=>({level:e.tagName,text:e.innerText.slice(0,200)})),jsonld,overflow:document.documentElement.scrollWidth>innerWidth+4},
 metrics:{...(window.__pexSnapshot?.()||window.__pex),ttfb_ms:nav?nav.responseStart-nav.requestStart:null,dom_loaded_ms:nav?.domContentLoadedEventEnd||null,requests:performance.getEntriesByType('resource').length,inp_note:'Maximum observed interaction duration in this lab visit; not a field percentile'},
 viewport:{width:innerWidth,height:innerHeight,scroll_y:scrollY}};
}
