// Live, account-scoped policies. The separate Security lab remains an illustrative walkthrough.
let policyActivityKey='',policyCrewRole=null;
function policyTarget(){
  const crew=policyCrewRole===null?null:window.BacCrewCatalog[policyCrewRole];
  return {owner:agentId,key:agentId+':'+(crew?'crew:'+policyCrewRole:'personal'),
    name:crew?.name||data.profile?.name,mode:crew?.protection||data.profile?.protection,
    route:crew?'crew-policy?role='+policyCrewRole:'agent-policy'};
}
function openPolicy(role=null){
  policyCrewRole=role;policySnapshot=null;++policyVersion;policyLoading=false;
  renderPolicySelector();openSurface('policies');
}
function renderPolicySelector(){
  const agents=(data.agents||[]).filter(a=>a.protection==='openshell');
  const crew=window.BacCrewCatalog.map((a,i)=>({...a,index:i})).filter(a=>a.protection==='openshell');
  const selected=policyCrewRole!==null?crew.some(a=>a.index===policyCrewRole):agents.some(a=>a.key===agentId);
  const options=(!selected?'<option value="" disabled>Select an agent</option>':'')+(agents.length?'<optgroup label="Lounge">'+agents.map(a=>`<option value="${a.key}">${escape(a.name)}</option>`).join('')+'</optgroup>':'')+(crew.length?'<optgroup label="BaC">'+crew.map(a=>`<option value="crew:${a.index}">${escape(a.name)}</option>`).join('')+'</optgroup>':'');
  if(el('policy-agent').innerHTML!==options)el('policy-agent').innerHTML=options;
  el('policy-agent').value=selected?(policyCrewRole===null?agentId:'crew:'+policyCrewRole):'';
  el('policy-agent').disabled=policySaving;
  const target=policyTarget(),agent=data.agents?.find(a=>a.key===agentId);
  const activityKey=JSON.stringify(policyCrewRole===null?[target.key,agent?.pending||0,agent?.workspacePreparation,agent?.latestMission?.id,agent?.latestMission?.status]:[target.key,data.preparation,(data.crewChats||[]).filter(j=>j.payload.crewRole===policyCrewRole).map(j=>[j.id,j.status]),(data.jobs||[]).filter(j=>j.kind==='crew').map(j=>[j.id,j.status,j.payload.stage])]);
  const activityChanged=activityKey!==policyActivityKey;
  policyActivityKey=activityKey;
  if(el('policy-panel').open){
    if(activityChanged)renderPolicy();
    if(!policyLoading&&!policySaving&&(policySnapshot?._targetKey!==target.key||activityChanged))loadPolicy();
  }
}
async function loadPolicy(){
  if(policyLoading)return;
  const version=++policyVersion,target=policyTarget(),activity=policyActivityKey;policyLoading=true;
  const current=()=>version===policyVersion&&target.key===policyTarget().key;
  if(target.mode!=='openshell'){policySnapshot=null;policyLoading=false;renderPolicy();return;}
  if(policySnapshot?._targetKey!==target.key)policySnapshot=null;
  renderPolicy();
  try{const report=await api(target.route,undefined,target.owner);if(current()){policySnapshot={...report,_targetKey:target.key};renderPolicy();}}
  catch(error){if(current()){policySnapshot={...(policySnapshot?._targetKey===target.key?policySnapshot:{}),_targetKey:target.key,agentId:target.owner,status:'unavailable',mode:target.mode,error:error.message,fetchFailed:true};renderPolicy();}}
  finally{if(version===policyVersion){policyLoading=false;renderPolicy();if(el('policy-panel').open&&(target.key!==policyTarget().key||activity!==policyActivityKey)&&!policySaving)loadPolicy();}}
}
function renderPolicy(){
  const target=policyTarget(),p={name:target.name,protection:target.mode},r=policySnapshot?._targetKey===target.key?policySnapshot:null,crew=policyCrewRole!==null;
  if(p.protection!=='openshell'){el('policy-content').innerHTML='<p class="studio-muted">'+'Select an agent to view its permissions.'+'</p>';return;}
  if(!r){el('policy-content').innerHTML='<p role="status">Loading permissions…</p>';return;}
  const applying=policySaving||r.updating,applied=r.status==='applied'&&!applying,requested=r.requested||[],catalog=r.catalog||{};
  const preparing=!crew&&['queued','running','stopping'].includes(data.agents?.find(a=>a.key===agentId)?.workspacePreparation);
  const busy=crew?!!r.busy:!!data.agents?.find(a=>a.key===agentId)?.pending;
  el('policy-agent').disabled=policySaving;
  const disabled=(!r.sandboxes?.length&&r.status!=='awaiting-first-mission')||preparing||busy||applying||policyLoading||data.deleting;
  const covered=new Set(requested.flatMap(key=>catalog[key]?.hosts||[]));
  const denied=[...new Set((r.pendingAccess||r.recentDenied||[]).map(e=>e.host))].filter(host=>!covered.has(host));
  const blocked=denied.map(host=>['host:'+host,catalog['host:'+host]?{...catalog['host:'+host],networkSuggested:r.pendingAccess?.some(e=>e.host===host&&e.reason==='suggested')}:null]).filter(([,rule])=>rule);
  const approved=requested.map(key=>[key,catalog[key]]).filter(([,rule])=>rule?.hosts?.length);
  const presets=Object.entries(catalog).filter(([key,rule])=>rule.hosts?.length&&(!key.startsWith('host:')||(r.recommended||[]).includes(key))&&!requested.includes(key)&&!rule.hosts.every(host=>covered.has(host)));
  function cards(rows,kind){return rows.map(([key,rule])=>`<article class="policy-access-card"><div><h4>${escape(rule.title)}</h4>${kind==='preset'?'<p>'+escape(rule.description)+'</p>':''}<small>${rule.hosts.map(escape).join(' · ')}</small>${rule.networkSuggested?'<small>Requested by the agent · not a confirmed policy block.</small>':''}${kind==='approved'&&!applied?'<small>'+(applying?'Applying · waiting for verification':'Saved · not active until verified')+'</small>':''}</div><button class="${kind==='approved'?'studio-secondary':'studio-primary'}" data-policy-permission="${escape(key)}" data-policy-allow="${kind!=='approved'}" ${disabled?'disabled':''}>${kind==='approved'?'Revoke':'Approve'}</button></article>`).join('');}
  function section(title,rows,kind,empty){
    const batchButton=kind==='blocked'&&blocked.length>1?`<div class="policy-bulk-action"><button type="button" class="studio-primary" data-policy-approve-all data-policy-permissions="${escape(JSON.stringify(blocked.map(([key])=>key)))}" ${disabled?'disabled':''}>${applying?'Applying…':'Approve all ('+blocked.length+')'}</button></div>`:'';
    return `<section class="policy-access-section" data-policy-section="${kind}"><div class="policy-section-heading"><h3>${title}<span>${rows.length}</span></h3>${batchButton}</div>${rows.length?'<div class="policy-access-list">'+cards(rows,kind)+'</div>':'<p class="studio-muted">'+empty+'</p>'}</section>`;
  }
  const approvedSection=section(applying?'Applying websites':applied?'Approved websites':'Saved websites · not verified',approved,'approved','No websites approved.');
  const unavailable=r.status==='unavailable',setupRequired=r.status==='setup-required';
  const notice=preparing?'Preparing protected workspace automatically. You can send a message while it finishes.':applying?'Applying access and checking OpenShell. Approval is effective after verification.':policyLoading?'Checking OpenShell':busy?'Wait for this agent to finish before changing access.':r.status==='awaiting-first-mission'?'Protected workspace is not ready. Retry setup.':setupRequired?'OpenShell needs setup on the host computer.':r.status==='needs-review'?'Saved approvals are not active. Apply them again.':unavailable?(r.checkFailure==='timeout'?'OpenShell did not respond in time. Your saved approvals are unchanged.':r.error||'Could not connect to OpenShell. Your saved approvals are unchanged.'):'';
  const recoveryDisabled=preparing||busy||applying||policyLoading||data.deleting;
  const recovery=!preparing&&['awaiting-first-mission','needs-review'].includes(r.status)?'<button type="button" class="studio-secondary" data-policy-retry '+(recoveryDisabled?'disabled':'')+'>'+(applying?'Retrying':r.status==='awaiting-first-mission'?'Retry':'Apply saved approvals')+'</button>':'';
  const recheck=unavailable||setupRequired||r.logsUnavailable?'<button type="button" class="studio-secondary" data-policy-check '+(applying||policyLoading?'disabled':'')+'>'+(policyLoading?'Checking':'Check again')+'</button>':'';
  const hostHelp=unavailable||setupRequired?'<details class="policy-host-help"><summary>Host troubleshooting</summary><p>On the computer running this studio, open the project folder in a terminal and run:</p><pre><code>./bac dev runtime check --wait 30</code></pre>'+(setupRequired?'<p>To set up OpenShell:</p><pre><code>./bac dev openshell enable</code></pre>':'<p>If the connection remains unavailable, check the OpenShell service on that computer. Check again here after restoring it.</p>')+'</details>':'';
  const recoveryMarkup=(notice?'<p class="'+(preparing?'studio-muted':'studio-policy-error')+'" role="status">'+escape(notice)+'</p>':'')+'<div class="policy-recovery-actions">'+recovery+recheck+'</div>'+hostHelp;
  if(r.fetchFailed&&!r.catalog){el('policy-content').innerHTML=recoveryMarkup;return;}
  el('policy-content').innerHTML=`${recoveryMarkup}
    ${[...new Map((r.connectionIssues||[]).map(e=>[e.host,e])).values()].slice(0,3).map(e=>'<p class="studio-policy-error">'+escape(e.host)+': '+(e.reason==='dns-failed'?'DNS lookup failed inside OpenShell. Check the host network or VPN, then retry the request.':'OpenShell blocked the destination address. Review the destination on the host.')+'</p>').join('')}
    ${section('Needs approval from the latest conversation',blocked,'blocked',r.logsUnavailable?'Recent access requests could not be checked. Use Check again above.':'No websites waiting for approval.')}
    ${approvedSection}
    ${section('Pre-approve common tasks',presets,'preset','All available tasks are already covered.')}
    <p class="policy-access-note">${'Access applies only to '+escape(p.name)+'. After approval, resend your request.'}</p>${crew?'<details><summary>Policy details &amp; network activity</summary><pre>'+escape(JSON.stringify({status:r.status,checkedAt:r.checkedAt,sandboxes:r.sandboxes,rules:r.rules,filesystem:r.filesystem,logs:r.logs},null,2))+'</pre></details>':''}`;
}
el('policy-agent').onchange=async e=>{if(policySaving)return;const value=e.target.value;++policyVersion;policyLoading=false;policySnapshot=null;if(value.startsWith('crew:')){policyCrewRole=Number(value.slice(5));}else{policyCrewRole=null;await switchAgent(value);}renderPolicySelector();loadPolicy();};
el('agent-policy').onclick=()=>openPolicy();
el('policies').onclick=async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-policy-check')){if(!policyLoading&&!policySaving)loadPolicy();return;}
  if(b.hasAttribute('data-policy-setup'))return setup();
  const permission=b.dataset.policyPermission,retry=b.hasAttribute('data-policy-retry'),all=b.hasAttribute('data-policy-approve-all');
  if(!permission&&!retry&&!all)return;
  if(b.disabled)return;
  const request=all?{permissions:JSON.parse(b.dataset.policyPermissions),allow:true}:retry?{retry:true}:{permission,allow:b.dataset.policyAllow==='true'};
  if(policySaving||pendingWrites||changingAgent)return;
  const target=policyTarget(),role=policyCrewRole;
  if(role!==null)request.role=role;
  policySaving=true;renderPolicy();
  let failure='';
  try{await api(role===null?'agent-policy':'crew-policy',request,target.owner);await refresh();await loadPolicy();}
  catch(error){failure=error.message;await loadPolicy();}
  finally{policySaving=false;renderPolicy();if(failure)el('policy-content').insertAdjacentHTML('afterbegin','<p class="policy-warning" role="alert">'+escape(failure)+'</p>');}
};
