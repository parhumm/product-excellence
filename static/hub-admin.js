// Shared native forms for the server admin page and local Settings.
(() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const input = (name, label, type='text', value='', extra='', help='') => `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${extra}>${help?`<small>${escape(help)}</small>`:''}</label>`;
  const run = async (form, action) => {
    const button=form.querySelector('button[type=submit]'), error=form.querySelector('[role=alert]');
    button.disabled=true;error.textContent='';
    try {await action()} catch(e) {error.textContent=e.message} finally {button.disabled=false}
  };
  // Basic authentication has no session: replacing the cached credentials with invalid ones signs the browser out.
  window.signOut = () => {
    const request=new XMLHttpRequest();
    request.open('GET','/logout',true,'signed','out');
    request.onloadend=()=>location.replace('/');
    request.send();
  };
  window.renderHubAdmin = async (el, call) => {
    el.innerHTML='<p role="status">Loading workspace administration…</p>';
    try {
      const workspaces=await call('GET','workspaces');
      el.innerHTML=`<h2>Workspace administration</h2><p class="muted">Each workspace here is shared with everyone who has its sign-in. Changing the password requires teammates to sign in again. A shared workspace appears in the sidebar once this console signs in to it.</p>${workspaces.map(w=>`<details><summary>${escape(w.name)} · ${escape(w.username)}</summary><p>${escape(w.url)}</p><p class="muted">Workspace ID: <code>${escape(w.id)}</code></p><form data-workspace="${escape(w.id)}"><div class="formgrid">${input('username','Username','text',w.username,'required maxlength="60" autocomplete="username"')}${input('password','New password (leave blank to keep current)','password','','minlength="15" maxlength="256" autocomplete="new-password"')}</div><p class="error" role="alert"></p><button type="submit">Change sign-in</button></form></details>`).join('') || '<p>No workspaces yet.</p>'}<details><summary>Add workspace</summary><form data-create><div class="formgrid">${input('name','Workspace name','text','','required maxlength="100"')}${input('url','Website URL','url','https://','required')}${input('allowed_domains','Allowed navigation domains','text','','',"Comma-separated hostnames a run may visit besides the website's own, for example cdn.example.com.")}${input('username','Workspace username','text','','required maxlength="60" autocomplete="username"')}${input('password','Workspace password','password','','required minlength="15" maxlength="256" autocomplete="new-password"')}<label><input name="seed" type="checkbox" checked> Add starter missions (leave off before importing a website's history)</label></div><p class="error" role="alert"></p><button class="primary" type="submit">Create workspace</button></form></details>`;
      el.querySelectorAll('form').forEach(form => form.onsubmit=e=>{
        e.preventDefault();run(form,async()=>{
          const body=Object.fromEntries(new FormData(form));
          if(form.hasAttribute('data-create')) {
            body.allowed_domains=body.allowed_domains.split(',').map(s=>s.trim()).filter(Boolean);
            body.seed=form.elements.seed.checked;
            await call('POST','workspaces',body);
          } else await call('PUT',`workspaces/${form.dataset.workspace}/login`,body);
          await window.renderHubAdmin(el,call);
        });
      });
    } catch(e) {el.innerHTML=`<p class="error" role="alert">${escape(e.message)}</p>`}
  };
  window.renderHubSettings = async (el, api, changed) => {
    try {
      const status=await api('/hub/status');
      el.innerHTML=`<h2>Team server</h2><p class="muted">${status.mode==='hybrid'?`Connected to <strong>${escape(new URL(status.url).host)}</strong>. Workspaces you sign in to here are shared there; every other workspace stays on this Mac. Browser and AI always run here.`:'Not connected. Sign in with a workspace&rsquo;s username and password to share its results, or as admin to create workspaces.'}</p>${Object.entries(status.logins).map(([id,w])=>`<p><strong>${escape(w.name)}</strong> · ${escape(w.username)} <button data-signout="${escape(id)}">Sign out</button></p>`).join('')}${status.admin?'<p>Admin signed in <button data-signout="admin">Sign out admin</button></p>':''}${status.pending.length?`<p class="notice">${status.pending.length} run${status.pending.length===1?'':'s'} finished while the server was unreachable. Their evidence stays on this Mac until the upload succeeds.</p><button data-retry-upload>Retry uploads</button>`:''}<p class="error" role="alert" data-connection-error></p><form data-hub-login><div class="formgrid">${input('url','Team server URL','url',status.url,'required placeholder="https://team.example.com"')}${input('username','Username','text','','required maxlength="60" autocomplete="username"')}${input('password','Password','password','','required maxlength="256" autocomplete="current-password"')}</div><p class="error" role="alert"></p><button type="submit" class="primary">Sign in</button></form>${status.admin?'<section class="section" data-admin></section>':''}`;
      const form=el.querySelector('[data-hub-login]');
      form.onsubmit=e=>{e.preventDefault();run(form,async()=>{await api('/hub/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});await changed()})};
      el.querySelectorAll('[data-signout]').forEach(b=>b.onclick=async()=>{
        b.disabled=true;
        try{await api('/hub/login/'+encodeURIComponent(b.dataset.signout),{method:'DELETE'});await changed()}catch(e){el.querySelector('[data-connection-error]').textContent=e.message}finally{b.disabled=false}
      });
      const retry=el.querySelector('[data-retry-upload]');
      if(retry)retry.onclick=async()=>{retry.disabled=true;try{await api('/hub/retry',{method:'POST'});await changed()}catch(e){el.querySelector('[data-connection-error]').textContent=e.message}finally{retry.disabled=false}};
      if(status.admin)await window.renderHubAdmin(el.querySelector('[data-admin]'),(method,path,body)=>api('/hub/admin/'+path,{method,body:body?JSON.stringify(body):undefined}));
    } catch(e) {el.innerHTML=`<p class="error" role="alert">${escape(e.message)}</p>`}
  };
})();
