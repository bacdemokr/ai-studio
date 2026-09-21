// Live, account-scoped policies. The separate Security lab remains an illustrative walkthrough.
let policyActivityKey='',policyAccessTab='file';
function renderPolicySelector(){
  const agents=(data.agents||[]).filter(a=>a.protection==='openshell');
  const selected=agents.some(a=>a.key===agentId);
  const options=(!selected?`<option value="" disabled>${agents.length?'Select an agent':'No OpenShell agents'}</option>`:'')+agents.map(a=>`<option value="${a.key}">${escape(a.name)}</option>`).join('');
  if(el('policy-agent').innerHTML!==options)el('policy-agent').innerHTML=options;
  el('policy-agent').value=selected?agentId:'';el('policy-agent').disabled=policySaving||!agents.length;
  const agent=data.agents?.find(a=>a.key===agentId);
  const activityKey=JSON.stringify([agentId,agent?.pending||0,agent?.latestMission?.id,agent?.latestMission?.status]);
  const activityChanged=activityKey!==policyActivityKey;
  policyActivityKey=activityKey;
  if(el('policy-panel').open){
    if(activityChanged)renderPolicy();
    // Completion releases the controls and refreshes destinations from this run.
    if(!policyLoading&&!policySaving&&(policySnapshot?.agentId!==agentId||activityChanged))loadPolicy();
  }
}
async function loadPolicy(){
  const version=++policyVersion,target=agentId,activity=policyActivityKey;policyLoading=true;
  if(data.profile?.protection!=='openshell'){policySnapshot=null;policyLoading=false;renderPolicy();return;}
  if(policySnapshot?.agentId!==target)policySnapshot=null;
  renderPolicy();
  try{const report=await api('agent-policy',undefined,target);if(version===policyVersion&&target===agentId){policySnapshot=report;renderPolicy();}}
  catch(error){if(version===policyVersion&&target===agentId){policySnapshot={...(policySnapshot?.agentId===target?policySnapshot:{}),agentId:target,status:'unavailable',mode:data.profile?.protection||'standard',error:error.message,fetchFailed:true};renderPolicy();}}
  finally{if(version===policyVersion){policyLoading=false;renderPolicy();if(el('policy-panel').open&&target===agentId&&activity!==policyActivityKey&&!policySaving)loadPolicy();}}
}
function renderPolicy(){
  const p=data.profile,r=policySnapshot;
  if(!p||p.protection!=='openshell'){el('policy-content').innerHTML='<p class="studio-muted">'+((data.agents||[]).some(a=>a.protection==='openshell')?'Select an agent to view its permissions.':'No agents are using OpenShell yet.')+'</p>';return;}
  if(!r){el('policy-content').innerHTML='<p role="status">Loading permissions…</p>';return;}
  const applying=policySaving||r.updating,applied=r.status==='applied'&&!applying,requested=r.requested||[],catalog=r.catalog||{};
  const busy=!!data.agents?.find(a=>a.key===agentId)?.pending;
  const disabled=(!r.sandboxes?.length&&r.status!=='awaiting-first-mission')||busy||applying||policyLoading||data.deleting;
  const covered=new Set(requested.flatMap(key=>catalog[key]?.hosts||[]));
  const denied=[...new Set((r.pendingAccess||r.recentDenied||[]).map(e=>e.host))].filter(host=>!covered.has(host));
  const blocked=[...denied.map(host=>['host:'+host,catalog['host:'+host]?{...catalog['host:'+host],networkSuggested:r.pendingAccess?.some(e=>e.host===host&&e.reason==='suggested')}:null]),...(r.pendingFiles||[]).map(key=>[key,catalog[key]])].filter(([,rule])=>rule);
  const bulk=blocked.filter(([key])=>!key.startsWith('file:read:')||!blocked.some(([other])=>other==='file:write:'+key.slice('file:read:'.length)));
  const bulkWrites=bulk.filter(([,rule])=>rule.kind==='file'&&rule.access==='write').length;
  const bulkSuggested=bulk.some(([,rule])=>rule.suggested);
  const bulkDisabled=disabled||bulk.some(([,rule])=>rule.unavailableReason);
  const approved=requested.map(key=>[key,catalog[key]]).filter(([,rule])=>rule);
  const presets=Object.entries(catalog).filter(([key,rule])=>!key.startsWith('host:')&&!key.startsWith('file:')&&!requested.includes(key)&&!rule.hosts.every(host=>covered.has(host)));
  function cards(rows,kind){return rows.map(([key,rule])=>`<article class="policy-access-card"><div><h4>${escape(rule.title)}</h4>${kind==='preset'?'<p>'+escape(rule.description)+'</p>':''}<small>${rule.kind==='file'?(rule.access==='write'?'Read/write · saves back to this file':'Read only · protected copy'):rule.hosts.map(escape).join(' · ')}</small>${rule.networkSuggested?'<small>Requested by the agent · not a confirmed policy block.</small>':''}${rule.suggested?'<small>Agent-suggested path · confirm this is the file you mean.</small>':''}${rule.unavailableReason?'<small role="status">'+escape(rule.unavailableReason)+'</small>':''}${kind==='approved'&&!applied?'<small>'+(applying?'Applying · waiting for verification':'Saved · not active until verified')+'</small>':''}</div><button class="${kind==='approved'?'studio-secondary':'studio-primary'}" data-policy-permission="${escape(key)}" data-policy-allow="${kind!=='approved'}" ${disabled||(kind!=='approved'&&rule.unavailableReason)?'disabled':''}>${kind==='approved'?'Revoke':rule.suggested?(rule.access==='write'?'Confirm path & approve read/write':'Confirm path & approve read'):rule.kind==='file'?(rule.access==='write'?'Approve read/write':'Approve read'):'Approve'}</button></article>`).join('');}
  function section(title,rows,kind,empty){
    const batchButton=kind==='blocked'&&bulk.length>1?`<div class="policy-bulk-action">${bulkWrites?`<small>Includes read/write access to ${bulkWrites} file${bulkWrites===1?'':'s'}</small>`:''}<button type="button" class="studio-primary" data-policy-approve-all data-policy-permissions="${escape(JSON.stringify(bulk.map(([key])=>key)))}" ${bulkDisabled?'disabled':''}>${applying?'Applying…':bulkSuggested?'Confirm & approve all':'Approve all'}${applying?'':' ('+bulk.length+')'}</button></div>`:'';
    return `<section class="policy-access-section" data-policy-section="${kind}"><div class="policy-section-heading"><h3>${title}<span>${rows.length}</span></h3>${batchButton}</div>${rows.length?'<div class="policy-access-list">'+cards(rows,kind)+'</div>':'<p class="studio-muted">'+empty+'</p>'}</section>`;
  }
  const files=approved.filter(([,rule])=>rule.kind==='file');
  const webpages=approved.filter(([,rule])=>rule.kind!=='file');
  function fileGroup(title,access){
    const rows=files.filter(([,rule])=>rule.access===access);
    return `<div class="policy-file-group"><h4>${title}</h4>${rows.length?'<div class="policy-access-list">'+cards(rows,'approved')+'</div>':'<p class="studio-muted">No '+title.toLowerCase()+' files approved.</p>'}</div>`;
  }
  const approvedSection=`<section class="policy-access-section" data-policy-section="approved">
    <h3>${applying?'Applying saved approvals':applied?'Approved access':'Saved approvals · not verified'}<span>${approved.length}</span></h3>
    <div class="studio-settings-tabs policy-access-tabs" role="tablist" aria-label="Approved access type">
      ${[['file','File',files.length],['webpage','Webpage',webpages.length]].map(([key,label,count])=>`<button type="button" role="tab" id="policy-access-tab-${key}" aria-controls="policy-access-panel-${key}" aria-selected="${policyAccessTab===key}" tabindex="${policyAccessTab===key?0:-1}" data-policy-access-tab="${key}">${label} <span>${count}</span></button>`).join('')}
    </div>
    <div role="tabpanel" id="policy-access-panel-file" aria-labelledby="policy-access-tab-file" ${policyAccessTab==='file'?'':'hidden'}>${fileGroup('Read','read')}${fileGroup('Read/write','write')}</div>
    <div role="tabpanel" id="policy-access-panel-webpage" aria-labelledby="policy-access-tab-webpage" ${policyAccessTab==='webpage'?'':'hidden'}>${webpages.length?'<div class="policy-access-list">'+cards(webpages,'approved')+'</div>':'<p class="studio-muted">No webpages approved.</p>'}</div>
  </section>`;
  const unavailable=r.status==='unavailable',setupRequired=r.status==='setup-required';
  const notice=applying?'Applying access and checking OpenShell. Approval is effective after verification.':policyLoading?'Checking OpenShell':busy?'Wait for this agent to finish before changing access.':r.status==='awaiting-first-mission'?'This agent’s protected workspace has not been created yet.':setupRequired?'OpenShell needs setup on the host computer.':r.status==='needs-review'?'Saved approvals are not active. Apply them again.':unavailable?(r.checkFailure==='timeout'?'OpenShell did not respond in time. Your saved approvals are unchanged.':r.error||'Could not connect to OpenShell. Your saved approvals are unchanged.'):'';
  const recoveryDisabled=busy||applying||policyLoading||data.deleting;
  const recovery=['awaiting-first-mission','needs-review'].includes(r.status)?'<button type="button" class="studio-secondary" data-policy-retry '+(recoveryDisabled?'disabled':'')+'>'+(applying?'Preparing workspace':r.status==='awaiting-first-mission'?'Prepare workspace':'Apply saved approvals')+'</button>':'';
  const recheck=unavailable||setupRequired||r.logsUnavailable?'<button type="button" class="studio-secondary" data-policy-check '+(applying||policyLoading?'disabled':'')+'>'+(policyLoading?'Checking':'Check again')+'</button>':'';
  const hostHelp=unavailable||setupRequired?'<details class="policy-host-help"><summary>Host troubleshooting</summary><p>On the computer running this studio, open the project folder in a terminal and run:</p><pre><code>./bac dev runtime check --wait 30</code></pre>'+(setupRequired?'<p>To set up OpenShell:</p><pre><code>./bac dev openshell enable</code></pre>':'<p>If the connection remains unavailable, check the OpenShell service on that computer. Check again here after restoring it.</p>')+'</details>':'';
  const recoveryMarkup=(notice?'<p class="studio-policy-error" role="status">'+escape(notice)+'</p>':'')+'<div class="policy-recovery-actions">'+recovery+recheck+'</div>'+hostHelp;
  if(r.fetchFailed&&!r.catalog){el('policy-content').innerHTML=recoveryMarkup;return;}
  el('policy-content').innerHTML=`${recoveryMarkup}
    ${[...new Map((r.connectionIssues||[]).map(e=>[e.host,e])).values()].slice(0,3).map(e=>'<p class="studio-policy-error">'+escape(e.host)+': '+(e.reason==='dns-failed'?'DNS lookup failed inside OpenShell. Check the host network or VPN, then retry the request.':'OpenShell blocked the destination address. Review the destination on the host.')+'</p>').join('')}
    ${(r.unsupportedFolders||[]).map(path=>'<p class="studio-policy-error">'+escape(path)+': Host folder access is not supported here. Ask the agent to create the folder inside its workspace.</p>').join('')}
    ${(r.fileIssues||[]).length?'<section class="policy-access-section"><h3>File path needs correction</h3>'+r.fileIssues.map(issue=>'<p class="studio-policy-error"><strong>'+escape(issue.path)+'</strong><br>'+escape(issue.reason)+'</p>').join('')+'<p class="studio-muted">These are file-path issues, not OpenShell approval requests. Correct the path in chat and retry.</p></section>':''}
    ${section('Needs approval from the latest conversation',blocked,'blocked',r.logsUnavailable?'Recent access requests could not be checked. Use Check again above.':'No access requests waiting for approval.')}
    ${approvedSection}
    ${section('Pre-approve common tasks',presets,'preset','All available tasks are already covered.')}
    <p class="policy-access-note">Access applies only to ${escape(p.name)}. After approval, resend your request. File grants cover individual files, not folders.</p>`;
}
el('policy-agent').onchange=async e=>{await switchAgent(e.target.value);loadPolicy();};
el('agent-policy').onclick=()=>setRoom('policies');
el('policies').onclick=async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.policyAccessTab){policyAccessTab=b.dataset.policyAccessTab;renderPolicy();document.getElementById('policy-access-tab-'+policyAccessTab)?.focus();return;}
  if(b.hasAttribute('data-policy-check')){if(!policyLoading&&!policySaving)loadPolicy();return;}
  if(b.hasAttribute('data-policy-setup'))return setup();
  const permission=b.dataset.policyPermission,retry=b.hasAttribute('data-policy-retry'),all=b.hasAttribute('data-policy-approve-all');
  if(!permission&&!retry&&!all)return;
  if(b.disabled)return;
  const request=all?{permissions:JSON.parse(b.dataset.policyPermissions),allow:true}:retry?{retry:true}:{permission,allow:b.dataset.policyAllow==='true'};
  if(policySaving||pendingWrites||changingAgent)return;
  const target=agentId;
  policySaving=true;renderPolicy();
  let failure='';
  try{await api('agent-policy',request,target);await refresh();await loadPolicy();}
  catch(error){failure=error.message;await loadPolicy();}
  finally{policySaving=false;renderPolicy();if(failure)el('policy-content').insertAdjacentHTML('afterbegin','<p class="policy-warning" role="alert">'+escape(failure)+'</p>');}
};

el('policies').addEventListener('keydown',e=>{
  if(!e.target.matches('[data-policy-access-tab]')||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
  e.preventDefault();
  policyAccessTab=e.key==='Home'?'file':e.key==='End'?'webpage':policyAccessTab==='file'?'webpage':'file';
  renderPolicy();document.getElementById('policy-access-tab-'+policyAccessTab)?.focus();
});
