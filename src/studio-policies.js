// Live, account-scoped policies.
let policyActivityKey='',policyCrewRole=null,policyRefreshTimer=null;
// Counts use the same pending destinations as the policy panel, scoped per identity.
const policyBadgeReports=new Map();
function policyBadgeCount(report){
 const catalog=report.catalog||{},covered=new Set((report.requested||[]).flatMap(key=>catalog[key]?.hosts||[]));
 return new Set((report.pendingAccess||report.recentDenied||[]).map(item=>item.host).filter(host=>!covered.has(host)&&catalog['host:'+host])).size;
}
function paintPolicyBadge(button,key,name){
 const count=policyBadgeReports.get(key)?.count||0;
 button.classList.toggle('has-policy-alert',count>0);
 button.innerHTML='◇ OpenShell Policy'+(count?'<span class="policy-pending-badge" aria-hidden="true">'+count+'</span>':'');
 button.setAttribute('aria-label','OpenShell Policy for '+name+(count?' · '+count+' website'+(count===1?'':'s')+' awaiting approval':''));
 button.title=count?count+' website'+(count===1?'':'s')+' awaiting approval':'';
}
function rememberPolicyBadge(key,report){
 const previous=policyBadgeReports.get(key)||{};
 policyBadgeReports.set(key,{...previous,loading:false,count:policyBadgeCount(report)});
 paintVisiblePolicyBadges();
}
function visiblePolicyBadges(){
 const targets=[];
 if(room==='lounge'&&data.profile?.protection==='openshell'&&!data.deleting)targets.push({button:el('agent-policy'),owner:agentId,key:agentId+':personal',name:data.profile.name,route:'agent-policy',role:null});
 const member=window.BacCrewCatalog[selectedCrewRole];
 if(room==='mission'&&member?.protection==='openshell'&&!data.deleting)targets.push({button:el('crew-policy'),owner:agentId,key:agentId+':crew:'+selectedCrewRole,name:member.name,route:'crew-policy?role='+selectedCrewRole,role:selectedCrewRole});
 return targets;
}
function paintVisiblePolicyBadges(){for(const target of visiblePolicyBadges())paintPolicyBadge(target.button,target.key,target.name);}
function syncPolicyBadges(){
 const live=new Set((data.agents||[]).map(agent=>agent.key));live.add(agentId);
 for(const key of policyBadgeReports.keys())if(!live.has(key.split(':')[0]))policyBadgeReports.delete(key);
 for(const target of visiblePolicyBadges()){
  paintPolicyBadge(target.button,target.key,target.name);
  const jobs=target.role===null?(data.jobs||[]).filter(j=>!['crew','crew-chat','prepare','prepare-agent'].includes(j.kind)):[...(data.jobs||[]).filter(j=>j.kind==='crew'),...(data.crewChats||[]).filter(j=>(j.payload.crewRole===target.role||j.payload.collaboration))];
  const signature=JSON.stringify([jobs.map(j=>[j.id,j.status]),(data.protectionEvents||[]).filter(e=>e.role===target.role&&(target.role!==null||e.owner===target.owner)).map(e=>e.id),target.role===null?data.agents?.find(a=>a.key===target.owner)?.workspacePreparation:data.preparation]);
  let entry=policyBadgeReports.get(target.key);
  if(entry?.loading||entry?.signature===signature||Date.now()<(entry?.retryAfter||0))continue;
  entry={...entry,loading:true};policyBadgeReports.set(target.key,entry);
  api(target.route,undefined,target.owner).then(report=>{
   if(policyBadgeReports.get(target.key)!==entry)return;
   entry.signature=signature;entry.count=policyBadgeCount(report);entry.retryAfter=0;
  }).catch(()=>{entry.retryAfter=Date.now()+15000;}).finally(()=>{entry.loading=false;syncPolicyBadges();});
 }
}

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
  syncPolicyBadges();
  const agents=(data.agents||[]).filter(a=>a.protection==='openshell');
  const crew=window.BacCrewCatalog.map((a,i)=>({...a,index:i})).filter(a=>a.protection==='openshell');
  const selected=policyCrewRole!==null?crew.some(a=>a.index===policyCrewRole):agents.some(a=>a.key===agentId);
  const options=(!selected?'<option value="" disabled>Select an agent</option>':'')+(agents.length?'<optgroup label="Lounge">'+agents.map(a=>`<option value="${a.key}">${escape(a.name)}</option>`).join('')+'</optgroup>':'')+(crew.length?'<optgroup label="BaC">'+crew.map(a=>`<option value="crew:${a.index}">${escape(a.name)}</option>`).join('')+'</optgroup>':'');
  if(el('policy-agent').innerHTML!==options)el('policy-agent').innerHTML=options;
  el('policy-agent').value=selected?(policyCrewRole===null?agentId:'crew:'+policyCrewRole):'';
  el('policy-agent').disabled=policySaving;
  const target=policyTarget(),agent=data.agents?.find(a=>a.key===agentId);
  const activityKey=JSON.stringify(policyCrewRole===null?[target.key,agent?.pending||0,agent?.workspacePreparation,agent?.latestMission?.id,agent?.latestMission?.status]:[target.key,data.preparation,(data.crewChats||[]).filter(j=>(j.payload.crewRole===policyCrewRole||j.payload.collaboration)).map(j=>[j.id,j.status]),(data.jobs||[]).filter(j=>j.kind==='crew').map(j=>[j.id,j.status,j.payload.stage])]);
  const activityChanged=activityKey!==policyActivityKey;
  policyActivityKey=activityKey;
  if(el('policy-panel').open){
    if(activityChanged)renderPolicy();
    if(!policyLoading&&!policySaving&&(policySnapshot?._targetKey!==target.key||activityChanged))loadPolicy();
  }
}
async function loadPolicy(){
  if(policyLoading)return;
  clearTimeout(policyRefreshTimer);policyRefreshTimer=null;
  const version=++policyVersion,target=policyTarget(),activity=policyActivityKey;policyLoading=true;
  const current=()=>version===policyVersion&&target.key===policyTarget().key;
  if(target.mode!=='openshell'){policySnapshot=null;policyLoading=false;renderPolicy();return;}
  if(policySnapshot?._targetKey!==target.key)policySnapshot=null;
  renderPolicy();
  try{const report=await api(target.route,undefined,target.owner);if(current()){policySnapshot={...report,_targetKey:target.key};rememberPolicyBadge(target.key,report);renderPolicy();}}
  catch(error){if(current()){policySnapshot={...(policySnapshot?._targetKey===target.key?policySnapshot:{}),_targetKey:target.key,agentId:target.owner,status:'unavailable',updating:false,mode:target.mode,error:error.message,fetchFailed:true};renderPolicy();}}
  finally{if(version===policyVersion){policyLoading=false;renderPolicy();if(el('policy-panel').open&&!policySaving&&(target.key!==policyTarget().key||activity!==policyActivityKey))loadPolicy();else schedulePolicyRefresh();}}
}
function schedulePolicyRefresh(){
  clearTimeout(policyRefreshTimer);policyRefreshTimer=null;
  const version=policyVersion,key=policyTarget().key;
  if(!el('policy-panel').open||policySnapshot?._targetKey!==key||!policySnapshot?.updating||policySnapshot.fetchFailed)return;
  policyRefreshTimer=setTimeout(()=>{
    if(version!==policyVersion||key!==policyTarget().key||!el('policy-panel').open)return;
    if(policySaving||policyLoading)schedulePolicyRefresh();else loadPolicy();
  },2500);
}
function renderPolicy(){
  const target=policyTarget(),p={name:target.name,protection:target.mode},r=policySnapshot?._targetKey===target.key?policySnapshot:null,crew=policyCrewRole!==null;
  const working=policySaving||!!r?.updating;
  el('policy-content').setAttribute('aria-busy',String(p.protection==='openshell'&&(working||!r)));
  el('policy-agent').disabled=working;
  if(p.protection==='openshell'&&(working||!r)){
    el('policy-content').innerHTML='<div class="policy-loading" role="status" aria-live="polite"><span class="policy-loading-spinner" aria-hidden="true"></span><span>'+(working?'Applying permissions…':'Checking permissions…')+'</span></div>';
    return;
  }
  if(p.protection!=='openshell'){el('policy-content').innerHTML='<p class="studio-muted">'+'Select an agent to view its permissions.'+'</p>';return;}
  const applied=r.status==='applied',requested=r.requested||[],catalog=r.catalog||{};
  const preparing=crew?!!r.preparing:['queued','running','stopping'].includes(data.agents?.find(a=>a.key===agentId)?.workspacePreparation);
  const busy=crew?!!r.busy:!!data.agents?.find(a=>a.key===agentId)?.pending;
  el('policy-agent').disabled=policySaving;
  const disabled=(!r.sandboxes?.length&&r.status!=='awaiting-first-mission')||preparing||busy||policyLoading||data.deleting;
  const covered=new Set(requested.flatMap(key=>catalog[key]?.hosts||[]));
  const denied=[...new Set((r.pendingAccess||r.recentDenied||[]).map(e=>e.host))].filter(host=>!covered.has(host));
  const blocked=denied.map(host=>['host:'+host,catalog['host:'+host]?{...catalog['host:'+host],networkSuggested:r.pendingAccess?.some(e=>e.host===host&&e.reason==='suggested'),networkRequested:r.pendingAccess?.some(e=>e.host===host&&e.reason==='requested')}:null]).filter(([,rule])=>rule);
  const approved=requested.map(key=>[key,catalog[key]]).filter(([,rule])=>rule?.hosts?.length);
  const presets=Object.entries(catalog).filter(([key,rule])=>rule.hosts?.length&&(!key.startsWith('host:')||(r.recommended||[]).includes(key))&&!requested.includes(key)&&!rule.hosts.every(host=>covered.has(host)));
  function cards(rows,kind){return rows.map(([key,rule])=>`<article class="policy-access-card"><div><h4>${escape(rule.title)}</h4><small>${rule.hosts.map(escape).join(' · ')}</small>${rule.networkSuggested?'<small>Requested by the agent · not a confirmed policy block.</small>':rule.networkRequested?'<small>Requested in your message · not a confirmed policy block.</small>':''}${kind==='approved'&&!applied?'<small>'+'Saved · not active until verified'+'</small>':''}</div><button class="${kind==='approved'||kind==='preset'?'studio-secondary':'studio-primary'}" data-policy-permission="${escape(key)}" data-policy-allow="${kind!=='approved'}" ${disabled?'disabled':''}>${kind==='approved'?'Revoke':'Approve'}</button></article>`).join('');}
  function section(title,rows,kind,empty){
    const batchButton=((kind==='blocked'&&rows.length>1)||(kind==='preset'&&rows.length))?`<div class="policy-bulk-action"><button type="button" class="studio-secondary" data-policy-approve-all data-policy-scope="${kind==='preset'?'presets':'pending'}" data-policy-permissions="${escape(JSON.stringify(rows.map(([key])=>key)))}" ${disabled?'disabled':''}>Approve all</button></div>`:'';
    return `<section class="policy-access-section" data-policy-section="${kind}"><div class="policy-section-heading"><h3>${title}<span>${rows.length}</span></h3>${batchButton}</div>${rows.length?'<div class="policy-access-list">'+cards(rows,kind)+'</div>':'<p class="studio-muted">'+empty+'</p>'}</section>`;
  }
  const approvedSection=section(applied?'Approved websites':'Saved websites · not verified',approved,'approved','No websites approved.');
  const unavailable=r.status==='unavailable',setupRequired=r.status==='setup-required';
  const notice=preparing?'Preparing protected workspace automatically. You can send a message while it finishes.':policyLoading?'Checking OpenShell':busy?'Wait for this agent to finish before changing access.':r.status==='awaiting-first-mission'?'Protected workspace is not ready. Retry setup.':setupRequired?'OpenShell needs setup on the host computer.':r.status==='needs-review'?'Saved approvals are not active. Apply them again.':unavailable?(r.checkFailure==='timeout'?'OpenShell did not respond in time. Your saved approvals are unchanged.':r.error||'Could not connect to OpenShell. Your saved approvals are unchanged.'):'';
  const recoveryDisabled=preparing||busy||policyLoading||data.deleting;
  const recovery=!preparing&&['awaiting-first-mission','needs-review'].includes(r.status)?'<button type="button" class="studio-secondary" data-policy-retry '+(recoveryDisabled?'disabled':'')+'>'+(r.status==='awaiting-first-mission'?'Retry':'Apply saved approvals')+'</button>':'';
  const recheck=unavailable||setupRequired||r.logsUnavailable?'<button type="button" class="studio-secondary" data-policy-check '+(policyLoading?'disabled':'')+'>'+(policyLoading?'Checking':'Check again')+'</button>':'';
  const hostHelp=unavailable||setupRequired?'<details class="policy-host-help"><summary>Host troubleshooting</summary><p>On the computer running this studio, open the project folder in a terminal and run:</p><pre><code>./bac dev runtime check --wait 30</code></pre>'+(setupRequired?'<p>To set up OpenShell:</p><pre><code>./bac dev openshell enable</code></pre>':'<p>If the connection remains unavailable, check the OpenShell service on that computer. Check again here after restoring it.</p>')+'</details>':'';
  const recoveryMarkup=(notice?'<p class="'+(preparing?'studio-muted':'studio-policy-error')+'" role="status">'+escape(notice)+'</p>':'')+'<div class="policy-recovery-actions">'+recovery+recheck+'</div>'+hostHelp;
  if(r.fetchFailed&&!r.catalog){el('policy-content').innerHTML=recoveryMarkup;return;}
  el('policy-content').innerHTML=`${recoveryMarkup}
    ${[...new Map((r.connectionIssues||[]).map(e=>[e.host,e])).values()].slice(0,3).map(e=>'<p class="studio-policy-error">'+escape(e.host)+': '+(e.reason==='dns-failed'?'DNS lookup failed inside OpenShell. Check the host network or VPN, then retry the request.':'OpenShell blocked the destination address. Review the destination on the host.')+'</p>').join('')}
    ${section('Websites awaiting approval',blocked,'blocked',r.logsUnavailable?'Recent access requests could not be checked. Use Check again above.':'No websites waiting for approval.')}
    ${approvedSection}
    ${section('Pre-approve common tasks',presets,'preset','All available tasks are already covered.')}
    <p class="policy-access-note">${'Access applies only to '+escape(p.name)+'. After approval, resend your request.'}</p>${crew?'<details><summary>Policy details &amp; network activity</summary><pre>'+escape(JSON.stringify({status:r.status,checkedAt:r.checkedAt,sandboxes:r.sandboxes,rules:r.rules,filesystem:r.filesystem,logs:r.logs},null,2))+'</pre></details>':''}`;
}
el('policy-agent').onchange=async e=>{if(policySaving)return;const value=e.target.value;++policyVersion;policyLoading=false;policySnapshot=null;if(value.startsWith('crew:')){policyCrewRole=Number(value.slice(5));}else{policyCrewRole=null;await switchAgent(value);}renderPolicySelector();loadPolicy();};
el('agent-policy').onclick=()=>openPolicy();
el('policies').onclick=async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-policy-check')){if(!policyLoading&&!policySaving)loadPolicy();return;}
  const permission=b.dataset.policyPermission,retry=b.hasAttribute('data-policy-retry'),all=b.hasAttribute('data-policy-approve-all');
  if(!permission&&!retry&&!all)return;
  if(b.disabled)return;
  const request=all?{permissions:JSON.parse(b.dataset.policyPermissions),allow:true,scope:b.dataset.policyScope||'pending'}:retry?{retry:true}:{permission,allow:b.dataset.policyAllow==='true'};
  if(policySaving||pendingWrites||changingAgent)return;
  const target=policyTarget(),role=policyCrewRole;
  if(role!==null)request.role=role;
  policySaving=true;renderPolicy();
  let failure='';
  try{await api(role===null?'agent-policy':'crew-policy',request,target.owner);await refresh();await loadPolicy();}
  catch(error){failure=error.message;await loadPolicy();}
  finally{policySaving=false;renderPolicy();schedulePolicyRefresh();if(failure)el('policy-content').insertAdjacentHTML('afterbegin','<p class="policy-warning" role="alert">'+escape(failure)+'</p>');}
};
