// Host settings: tab changes keep drafts; model discovery is visibly selectable.
async function waitForAgentRuntime(){
  const deadline=Date.now()+45000;
  do{
    runtime=await api('runtime');runtimeBadge();
    if(runtime.gateway)return;
    await new Promise(resolve=>setTimeout(resolve,1500));
  }while(Date.now()<deadline);
  throw new Error('The agent runtime is not ready. Try Start agents again.');
}
const settingsButton=document.createElement('button');settingsButton.id='studio-config';settingsButton.className='studio-config';settingsButton.type='button';settingsButton.textContent='⚙';settingsButton.title='Settings';settingsButton.setAttribute('aria-label','Settings');settingsButton.hidden=true;document.querySelector('.studio-header-actions').append(settingsButton);
let settingsOpenRequest=0;
function scenarioHasWork(id=selectedScenario){
 const scenario=(data.scenarios||[]).find(s=>s.id===id);
 return !!(scenario?.hasWork||scenario?.busy);
}
function syncResetButtons(){
 const hasAgents=!!(data.agents||[]).length,hasAnyScenario=(data.scenarios||[]).some(s=>s.hasWork||s.busy);
 for(const id of ['agent-reset','settings-bac-reset','reset-all','bac-reset']){
  const button=el(id);if(!button)continue;
  const empty=id==='agent-reset'?!hasAgents:id==='reset-all'?!hasAgents&&!hasAnyScenario:!scenarioHasWork();
  button.disabled=resetInProgress||!!data.bacResetting||removingAgent||empty;
  button.title=empty?'Nothing to reset':'';
 }
 if(resetInProgress&&el('settings-status'))el('settings-status').textContent='Reset in progress. Agent cleanup is still running.';
}
settingsButton.onclick=()=>openModelConnections();
el('dialog').addEventListener('close',()=>{for(const id of ['connect-key','telegram-token'])if(el(id))el(id).value='';});
function settingsUtilityPanels(){return `  <section id="studio-settings-location-panel" role="tabpanel" aria-labelledby="studio-settings-location-tab" hidden><label for="studio-location-city">City</label><input id="studio-location-city" autocomplete="address-level2" maxlength="80" required aria-describedby="studio-location-note"><small id="studio-location-note">Default city for weather and local requests.</small></section>
  <section id="studio-settings-telegram-panel" role="tabpanel" aria-labelledby="studio-settings-telegram-tab" hidden>
  <p>Sends summaries from the <strong>Tech Radar skill</strong> only.</p>
  <label for="studio-telegram-token">Bot token (from <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a>)</label><input id="studio-telegram-token" type="password" autocomplete="off" spellcheck="false" placeholder="Token from @BotFather (e.g. 123456789:ABCdef...)">
  <label for="studio-telegram-chat">Chat ID (<a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a> → /start)</label><input id="studio-telegram-chat" autocomplete="off" spellcheck="false" placeholder="Numeric chat ID (e.g. 123456789)">
  <p id="studio-telegram-status" role="status" hidden></p><div id="studio-telegram-controls" hidden><div class="studio-dialog-actions"><button type="button" id="studio-telegram-test" class="studio-secondary">Send test</button><button type="button" id="studio-telegram-disconnect" class="studio-secondary">Disconnect</button></div></div></section>
  <section id="studio-settings-reset-panel" role="tabpanel" aria-labelledby="studio-settings-reset-tab" class="studio-agent-reset" hidden>
   <div class="studio-reset-row"><div><small class="studio-reset-stage">STAGES 01 / 02</small><h3>Hiring &amp; Agent lounge</h3><p>Remove hired agents and their chats, files, and workspaces.</p></div><button type="button" id="studio-agent-reset" class="studio-secondary" aria-label="Remove Stage 1 and 2 agents" ${(data.agents||[]).length?'':'disabled'}>Remove agents</button></div>
   <div class="studio-reset-row"><div><small class="studio-reset-stage">STAGE ${selectedScenario==='event-brief'?'03-1':'03-2'}</small><h3>${escape(stageScenarios.find(s=>s.id===selectedScenario)?.title||'Multi-Agent demo')}</h3><p>Stop this scenario’s work and clear its chats, documents and results. Other scenarios are preserved.</p></div><button type="button" id="studio-settings-bac-reset" class="studio-secondary" aria-label="Reset Stage 3">Reset scenario</button></div>
   <div class="studio-reset-footer"><p>Reset all stages. Model and connection settings are kept.</p><button type="button" id="studio-reset-all" class="studio-danger">Reset all</button></div>
  </section>
`;}

function confirmTeamReset(sourceButton){
 if(resetInProgress||removingAgent||pendingWrites||changingAgent||data.bacResetting)return;
 dialog('RESET SCENARIO', '<h3>Reset '+(escape(stageScenarios.find(s=>s.id===selectedScenario)?.title||'Multi-Agent demo'))+'?</h3><p>This stops this scenario’s work and clears its chats, documents and results. Other scenarios and your hired agents are preserved.</p><div class="studio-dialog-actions"><button type="button" class="studio-secondary" id="studio-team-reset-cancel" autofocus>Cancel</button><button type="button" class="studio-danger" id="studio-team-reset-confirm">Reset scenario</button></div>');
 el('team-reset-cancel').onclick=()=>el('dialog').close();
 el('team-reset-confirm').onclick=()=>{el('dialog').close();resetStudio('bac',sourceButton);};
 el('team-reset-cancel').focus();
}

async function resetStudio(scope,sourceButton=null){
 if(resetInProgress||removingAgent||pendingWrites||changingAgent)return;
 resetInProgress=true;removingAgent=true;++refreshVersion;
 const modal=el('dialog'),status=sourceButton?el('team-reset-status'):el('settings-status'),blockClose=e=>e.preventDefault();
 const buttons=(sourceButton?[sourceButton]:[...modal.querySelectorAll('button')]).map(button=>[button,button.disabled]);
 modal.addEventListener('cancel',blockClose);buttons.forEach(([button])=>button.disabled=true);
 status.hidden=false;status.textContent='Resetting…';
 let completed=0,total=0,next=agentId,background=false,teamCleared=false;
 const originalSelection=agentId;
 try{
  const latest=await api('state',undefined,'');
  const agents=scope==='bac'?[]:latest.agents||[];total=agents.length;
  if(scope==='bac'||scope==='all'){
   let reset=await api('bac-reset',{scope:scope==='all'?'all':'scenario'},latest.agentId);
   while(reset.resetting){
    status.textContent=scope==='all'?'Stopping all scenarios and resetting…':'Stopping '+(stageScenarios.find(s=>s.id===selectedScenario)?.title||'the scenario')+' and resetting…';
    await new Promise(resolve=>setTimeout(resolve,1000));
    const snapshot=await api('state',undefined,'');
    reset={resetting:!!snapshot.bacResetting};
   }
   selectedJob=null;teamCleared=true;
  }
  // Persist every request first. Closing Settings or reloading must not lose
  // the remainder of a bulk deletion while the native runtime drains it.
  for(const agent of agents)await api('delete-agent',{name:agent.name},agent.key);
  if(agents.length){
   background=true;removingAgent=false;modal.removeEventListener('cancel',blockClose);modal.close();
   alert('Removing '+agents.length+' agent'+(agents.length===1?'':'s')+'…','progress');
   await refresh();
  }
  for(const agent of agents){
   status.textContent=`Removing ${completed+1} / ${total} · ${agent.name}`;
   const result=await waitForAgentDeletion(agent.key,agent.name,row=>{status.textContent=row?.deletionProgress||`Cleaning ${agent.name}`;});
   next=result.agentId;completed++;
   try{const layout=JSON.parse(localStorage.getItem('bac-lounge-layout-v1')||'{}');delete layout[agent.key];localStorage.setItem('bac-lounge-layout-v1',JSON.stringify(layout));}catch{}
  }
  const state=await api('state',undefined,completed?next:agentId);
  if(scope==='bac'){data=state;render();}
  else{
   clearTimeout(comparisonTimer);comparison=null;comparePanel.replaceChildren();delete comparePanel.dataset.batch;
   if(!changingAgent&&(agentId===originalSelection||agents.some(a=>a.key===agentId))){openAgentState(state);fillCreator(true);setRoom('workshop');}
  }
  status.textContent=scope==='all'?'All stages reset.':scope==='bac'?'Stage 3 reset.':'Lounge agents reset.';
  if(background)alert(completed+' agent'+(completed===1?'':'s')+' removed.','success');
 }catch(error){
  const message=(scope==='all'&&teamCleared?'Stage 3 was reset. ':'')+(completed?`${completed} / ${total} removed. `:'')+error.message;
  if(background)alert(message,'error');
  try{const state=await api('state',undefined,'');if(state.agentId===agentId){data=state;render();}else openAgentState(state);}catch{}
  // Refreshing controls while resetInProgress is true shows the busy notice.
  // Restore the failure afterward so the presenter can see why a retry is needed.
  status.textContent=message;
 }finally{
  // Background cleanup has released this lock; a newer individual deletion may own it now.
  if(!background)removingAgent=false;
  resetInProgress=false;modal.removeEventListener('cancel',blockClose);
  buttons.forEach(([button,disabled])=>button.disabled=disabled);
  if(background&&el('settings-status')&&el('settings-status')!==status)el('settings-status').textContent=status.textContent;
  syncResetButtons();
  refresh();
 }
}


function openTeamSettings(){return openModelConnections();}
async function openModelConnections(){
 const request=++settingsOpenRequest,revision=dialogRevision;
 let state,settings;
 try{[state,settings]=await Promise.all([api('settings/connections'),api('settings')]);}
 catch(error){alert(error.message,'error');return;}
 if(request!==settingsOpenRequest||revision!==dialogRevision)return;
 dialog('Settings',`<form id="studio-config-form" novalidate>
  <nav class="connection-tabs" role="tablist" aria-label="Settings">${['model','location','telegram','reset'].map((tab,index)=>`<button type="button" role="tab" id="studio-settings-${tab}-tab" data-connection-tab="${tab}" data-settings-tab="${tab}" aria-controls="studio-settings-${tab}-panel" aria-selected="${index===0}" tabindex="${index===0?0:-1}" ${index===0?'aria-current="page"':''}>${tab[0].toUpperCase()+tab.slice(1)}</button>`).join('')}</nav>
  <section id="studio-settings-model-panel" role="tabpanel" aria-labelledby="studio-settings-model-tab"><div id="studio-model-connections">
  <div class="connection-section-heading"><h3>Connections</h3><button type="button" class="connection-text-button" id="studio-connections-check">↻ Refresh</button></div>
  <div class="connection-grid">${['local','api'].map(source=>`<section class="connection-card" data-source="${source}"><header><label class="connection-toggle"><input type="checkbox" data-connection-enable="${source}"><strong>${source==='local'?'Local':'External Endpoint'}</strong></label><span data-connection-status="${source}" role="status"></span></header><p data-connection-summary="${source}"></p><button type="button" class="connection-text-button" data-connection-edit="${source}">Configure →</button></section>`).join('')}</div>
  <div id="studio-connection-editor" hidden></div>
  <div class="connection-section-heading"><h3>Stage connections</h3></div>
  <div class="connection-routes">${[['lounge','01 / 02','Hiring & Agent lounge'],['event-brief','03-1','Event Brief'],['plan','03-2','Open Task']].map(([key,number,title])=>`<section class="connection-route"><div class="connection-route-name"><small>${number}</small><strong>${escape(title)}</strong><span id="studio-connection-${key}-effective" role="status"></span></div><div class="connection-choice" role="group" aria-label="${escape(title)} connection">${['local','api'].map(source=>`<button type="button" data-route="${key}" data-route-source="${source}" aria-pressed="false">${source==='local'?'Local':'External'}</button>`).join('')}</div></section>`).join('')}</div>
  <p id="studio-connections-status" role="status"></p><div class="connection-footer"><button type="button" id="studio-connections-save" class="studio-primary">Save changes</button></div></div></section>
  ${settingsUtilityPanels()}
  <p id="studio-settings-status" role="status"></p><div class="studio-dialog-actions"><button type="button" id="studio-start-agents" class="studio-secondary" ${runtime.gateway?'hidden':''}>Start agents</button><button type="submit" class="studio-primary" id="studio-save-settings" hidden>Save location</button></div></form>`);
 const form=el('config-form');
 const panel=el('model-connections'),notice=el('connections-status'),owner=agentId,scenario=selectedScenario;
 let working=false,editing=false,inventoryRevision=0,tab='model',telegram=null,telegramRevision=0;
 const current=()=>el('model-connections')===panel&&el('dialog').open&&agentId===owner&&selectedScenario===scenario;
 const prefs={lounge:state.loungePreference||'auto','event-brief':state.scenarioPreferences?.['event-brief']||'auto',plan:state.scenarioPreferences?.plan||'auto'};
 function paint(){
  for(const source of ['local','api']){const c=state.connections[source],badge=panel.querySelector(`[data-connection-status="${source}"]`);badge.textContent=c.ready?'Ready':['Not configured','Disabled','Checking…'].includes(c.message)?c.message:'Unavailable';badge.title=c.message;badge.dataset.ready=String(c.ready);const summary=panel.querySelector(`[data-connection-summary="${source}"]`);summary.textContent=c.model?[c.provider==='local'?'':({nvidia:'NVIDIA Inference',openai:'OpenAI',anthropic:'Anthropic'}[c.provider]),c.model].filter(Boolean).join(' · '):source==='local'?'':'NVIDIA · OpenAI · Anthropic';summary.title=c.model||'';const toggle=panel.querySelector(`[data-connection-enable="${source}"]`);if(!working)toggle.checked=c.enabled&&c.message!=='Not configured';toggle.disabled=working;}
  for(const kind of ['lounge','event-brief','plan']){
   const preferred=prefs[kind]==='auto'?(kind==='lounge'?'local':'api'):prefs[kind],other=preferred==='local'?'api':'local',effective=state.connections[preferred].ready?preferred:state.connections[other].ready?other:null;
   for(const button of panel.querySelectorAll(`[data-route="${kind}"]`)){const source=button.dataset.routeSource;button.setAttribute('aria-pressed',String(effective===source));button.disabled=working||!state.connections[source].ready;button.title=state.connections[source].ready?'Prefer '+(source==='local'?'Local':'External Endpoint'):'Connection not ready';}
   const label=el('connection-'+kind+'-effective');label.textContent=!effective?'Model not connected':effective!==preferred?(preferred==='local'?'Local':'External')+' unavailable · Using '+(effective==='local'?'Local':'External'):'Using '+(effective==='local'?'Local':'External Endpoint');label.dataset.error=String(!effective);
  }
  el('connections-save').disabled=working;el('connections-check').disabled=working;
 }
 paint();
 for(const button of panel.querySelectorAll('[data-route]'))button.onclick=()=>{if(working)return;prefs[button.dataset.route]=button.dataset.routeSource;notice.textContent='Unsaved changes';paint();};
 async function refreshConnections(force=false){const revision=inventoryRevision;try{const next=await api('settings/connections'+(force?'/check':''),force?{}:undefined);if(current()&&revision===inventoryRevision&&!working){state=next;paint();}}catch(error){if(current())notice.textContent=error.message;}}
 const timer=setInterval(()=>{if(!current()){clearInterval(timer);return;}if(!working&&!editing)refreshConnections();},2500);
 el('connections-check').onclick=()=>refreshConnections(true);
 function showTelegram(){
  if(!current())return;
  const value=telegram||{};
  el('telegram-status').textContent=value.connected?'Connected to @'+value.bot+' · chat '+value.chatId:value.error||'';
  el('telegram-status').hidden=!value.connected&&!value.error;el('telegram-controls').hidden=!value.connected;
  el('telegram-test').disabled=!value.connected;el('telegram-disconnect').disabled=!value.connected;
  el('telegram-chat').value=value.chatId||el('telegram-chat').value;
 }
 async function loadTelegram(){
  const version=++telegramRevision;
  try{const value=await api('telegram');if(current()&&version===telegramRevision){telegram=value;showTelegram();}}
  catch(error){if(current()&&version===telegramRevision){telegram={connected:false,error:error.message};showTelegram();}}
 }
 function selectTab(next){
  if(working||resetInProgress)return;
  tab=next;el('dialog-body').scrollTop=0;
  for(const button of form.querySelectorAll('[data-settings-tab]')){
   const active=button.dataset.settingsTab===tab;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;
   if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
   el('settings-'+button.dataset.settingsTab+'-panel').hidden=!active;
  }
  el('save-settings').hidden=tab==='model'||tab==='reset';el('save-settings').textContent=tab==='telegram'?'Connect Telegram':'Save location';
  el('start-agents').hidden=tab!=='model'||!!runtime.gateway;el('settings-status').textContent='';
  if(tab==='reset')syncResetButtons();
  if(tab==='telegram'&&!telegram)loadTelegram();
 }
 for(const button of form.querySelectorAll('[data-settings-tab]')){
  button.onclick=()=>selectTab(button.dataset.settingsTab);
  button.onkeydown=event=>{
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
   event.preventDefault();if(working||resetInProgress)return;
   const tabs=['model','location','telegram','reset'];
   selectTab(event.key==='Home'?tabs[0]:event.key==='End'?tabs.at(-1):tabs[(tabs.indexOf(tab)+(event.key==='ArrowLeft'?-1:1)+tabs.length)%tabs.length]);
   el('settings-'+tab+'-tab').focus();
  };
 }
 el('location-city').value=settings.location?.city||'Zurich';
 el('agent-reset').onclick=()=>resetStudio('lounge');el('settings-bac-reset').onclick=()=>resetStudio('bac');el('reset-all').onclick=()=>resetStudio('all');syncResetButtons();
 async function utilityAction(action){
  if(working||!current())return;
  working=true;paint();
  const controls=[...form.querySelectorAll('#studio-settings-location-panel input,#studio-settings-telegram-panel input,#studio-settings-telegram-panel button,#studio-save-settings,#studio-start-agents')].map(node=>[node,node.disabled]);
  controls.forEach(([node])=>node.disabled=true);const status=el('settings-status');
  try{await action(status);}catch(error){if(current())status.textContent=error.message;}
  finally{working=false;if(current()){controls.forEach(([node,disabled])=>node.disabled=disabled);if(telegram)showTelegram();paint();}}
 }
 el('telegram-test').onclick=()=>utilityAction(async status=>{status.textContent='Sending test…';await api('telegram/test',{});if(current())status.textContent='Test message sent.';});
 el('telegram-disconnect').onclick=()=>utilityAction(async status=>{++telegramRevision;const value=await api('telegram',{disconnect:true});if(current()){telegram=value;showTelegram();status.textContent='Disconnected.';}});
 el('start-agents').onclick=()=>utilityAction(async status=>{status.textContent='Starting agent runtime…';await api('settings/start',{});await waitForAgentRuntime();if(current()){el('start-agents').hidden=true;status.textContent=runtime.ready?'Model and agent runtime connected.':'Agent runtime ready. Connect a model to continue.';}});
 form.onsubmit=event=>{
  event.preventDefault();if(working||!['location','telegram'].includes(tab))return;
  if(tab==='location'){
   const field=el('location-city');if(!field.checkValidity()){field.reportValidity();return;}
   const city=field.value.trim();
   utilityAction(async status=>{status.textContent='Saving location…';const saved=await api('settings',{section:'location',location:{city}});settings.location=saved.location;runtime.location=saved.location;if(current()){field.value=saved.location.city;status.textContent='Saved. Applies to every agent’s next request.';}});
  }else{
   const values={token:el('telegram-token').value.trim(),chatId:el('telegram-chat').value.trim()};++telegramRevision;
   utilityAction(async status=>{status.textContent='Checking bot…';const value=await api('telegram',values);if(current()){telegram=value;showTelegram();el('telegram-token').value='';status.textContent='Bot connected. Send a test to check delivery.';}});
  }
 };
 el('connections-save').onclick=async()=>{if(working)return;working=true;++inventoryRevision;paint();notice.textContent='Applying…';try{
  const result=await api('settings/connections/preferences',{lounge:prefs.lounge,scenarios:{'event-brief':prefs['event-brief'],plan:prefs.plan}},owner);if(!current())return;state=result;
  ++refreshVersion;stateCache.clear();data.teamConnection=result.teamConnection;runtime=await api('runtime');if(!current())return;render();notice.textContent='Saved. Applies to new requests.';
 }catch(error){if(current())notice.textContent=error.message;}finally{working=false;if(current())paint();}};
 for(const toggle of panel.querySelectorAll('[data-connection-enable]'))toggle.onchange=async()=>{
  if(working)return;const source=toggle.dataset.connectionEnable,on=toggle.checked;
  if(on&&state.connections[source].message==='Not configured'){editConnection(source);paint();return;}
  working=true;++inventoryRevision;paint();try{state=await api('settings/connections/preferences',{lounge:state.loungePreference,[on?'enable':'disable']:source},owner);if(current())notice.textContent=on?'Enabled. Checking connection…':'Disabled.';}catch(error){if(current())notice.textContent=error.message;}finally{working=false;if(current()){paint();await refresh();}}
 };
 for(const button of panel.querySelectorAll('[data-connection-edit]'))button.onclick=()=>editConnection(button.dataset.connectionEdit);
 function editConnection(source){
  if(working)return;editing=true;const editor=el('connection-editor');editor.hidden=false;
  editor.innerHTML=`<h3>${source==='local'?'Local model':'API connection'}</h3>${source==='api'?'<label>Provider<select id="studio-connect-provider"><option value="nvidia">NVIDIA Inference</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select></label><label>API key<input id="studio-connect-key" type="password" autocomplete="off" placeholder="Leave blank to keep the current key"></label><small id="studio-connect-key-status"></small>':''}<label>Endpoint<input id="studio-connect-url" type="url"></label><label for="studio-connect-model">Model</label><label><input id="studio-connect-model" list="studio-connect-models" autocomplete="off" placeholder="Search models…"><datalist id="studio-connect-models"></datalist></label><details><summary>Advanced</summary><label for="studio-connect-context">Context limit · tokens</label><input id="studio-connect-context" type="number" min="8192" max="2000000" step="1" required><small>Instructions, conversation, tool results and reply. Must fit the model endpoint.</small></details><p id="studio-connect-status" role="status"></p><div class="studio-dialog-actions"><button type="button" class="studio-secondary" id="studio-connect-cancel">Close</button><button type="button" class="studio-primary" id="studio-connect-apply">Connect &amp; enable</button></div>`;
  const provider=()=>source==='local'?'local':el('connect-provider').value;
  // A connection may be ready using another tab's key. Only this tab's key
  // or a host-saved key can be reused by the connection editor.
  const reusableKey=()=>!!settings.profiles[provider()]?.hasKey||(state.connections.api.provider===provider()&&['api.cfg','host'].includes(state.connections.api.keySource));
  const lockFields=()=>{const active=state.connections[source],verified=source==='api'&&active.provider===provider()&&active.ready&&reusableKey();el('connect-url').disabled=source==='api';if(el('connect-key')){el('connect-key').disabled=verified;el('connect-key').placeholder=verified?(active.keySource==='api.cfg'?'API key verified · api.cfg':active.keySource==='host'?'API key verified · saved on host':'API key verified · this session'):'Enter API key';el('connect-key-status').textContent=verified?'':'Key expires when this tab reloads or closes.';}};
  const fill=()=>{const id=provider(),profile=settings.profiles[id]||{},active=state.connections[source];el('connect-url').value=profile.baseUrl||settings.providers[id].baseUrl;el('connect-url').readOnly=source==='api';el('connect-model').value=profile.model||(active.provider===id?active.model:'');el('connect-context').value=profile.contextWindow||(active.provider===id?active.contextWindow:0)||32768;if(el('connect-key'))el('connect-key').value='';el('connect-models').innerHTML='';lockFields();};
  if(source==='api'){el('connect-provider').value=state.connections.api.provider;el('connect-provider').onchange=fill;}fill();
  const payload=()=>({source,provider:provider(),apiKey:el('connect-key')?.value.trim()||'',baseUrl:el('connect-url').value.trim(),model:el('connect-model').value.trim(),contextWindow:Number(el('connect-context').value)});
  el('connect-cancel').onclick=()=>{if(!working){editor.replaceChildren();editor.hidden=true;editing=false;}};
  async function action(){if(working)return;const context=el('connect-context');if(!context.checkValidity()){context.closest('details').open=true;context.reportValidity();return;}working=true;++inventoryRevision;paint();const values=payload(),message=el('connect-status');editor.querySelectorAll('input,select,button').forEach(e=>e.disabled=true);message.textContent='Checking connection…';try{
   const result=await api('settings/connections',values,owner);if(!current()||!editor.contains(message))return;
   {state=result;settings.profiles[values.provider]={baseUrl:values.baseUrl,model:values.model,contextWindow:values.contextWindow,hasKey:source==='api'};if(el('connect-key'))el('connect-key').value='';runtime=await api('runtime');if(current()){await refresh();paint();message.textContent='Connected.';}}
  }catch(error){if(current())message.textContent=error.message;}finally{working=false;if(current()){editor.querySelectorAll('input,select,button').forEach(e=>e.disabled=false);lockFields();paint();}}}
  let catalogVersion=0,catalogLoaded='',catalogPending='';
  async function loadCatalog(){
   const values=payload(),signature=JSON.stringify([values.provider,values.baseUrl,values.apiKey]);
   if(working||catalogLoaded===signature||catalogPending===signature)return;
   if(source==='api'&&!values.apiKey&&!reusableKey())return;
   const version=++catalogVersion,message=el('connect-status'),list=el('connect-models');catalogPending=signature;message.textContent='Loading models…';
   try{const result=await api('settings/connections/models',values,owner);if(!current()||!editor.contains(list)||version!==catalogVersion)return;
    list.replaceChildren(...result.models.map(m=>new Option(m.name||m.id,m.id)));catalogLoaded=signature;message.textContent=result.models.length?'':'No models found.';
   }catch(error){if(current()&&editor.contains(message)&&version===catalogVersion)message.textContent=error.message;}
   finally{if(version===catalogVersion)catalogPending='';}
  }
  el('connect-model').onfocus=()=>{el('connect-model').select();loadCatalog();};
  if(el('connect-provider'))el('connect-provider').onchange=()=>{++catalogVersion;catalogLoaded='';catalogPending='';fill();loadCatalog();};
  for(const id of ['connect-key','connect-url'])if(el(id))el(id).oninput=()=>{++catalogVersion;catalogLoaded='';catalogPending='';el('connect-models').replaceChildren();};
  el('connect-apply').onclick=()=>{++catalogVersion;catalogPending='';action();};
  loadCatalog();
 }
}
