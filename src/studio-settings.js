// Host settings: tab changes keep drafts; model discovery is visibly selectable.
async function waitForAgentRuntime(requireModel=false){
  const deadline=Date.now()+45000;
  do{
    runtime=await api('runtime');runtimeBadge();
    if(requireModel?runtime.ready:runtime.gateway)return;
    await new Promise(resolve=>setTimeout(resolve,1500));
  }while(Date.now()<deadline);
  throw new Error(requireModel?'The model was verified, but the agent runtime has not applied the connection. Retry Connect model.':'Model settings are saved, but the agent runtime is not ready. Try Start agents again.');
}
const settingsButton=document.createElement('button');settingsButton.id='studio-config';settingsButton.className='studio-config';settingsButton.type='button';settingsButton.textContent='⚙';settingsButton.title='Settings';settingsButton.setAttribute('aria-label','Settings');settingsButton.hidden=true;document.querySelector('#bac-planner .topbar').append(settingsButton);
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
settingsButton.onclick=async()=>{
 const request=++settingsOpenRequest,revision=dialogRevision;
 const currentOpen=()=>request===settingsOpenRequest&&revision===dialogRevision;
 try{
  const settings=await api('settings');
  if(!currentOpen())return;
  let telegram;
  try{telegram=await api('telegram');}
  catch(error){telegram={connected:false,error:error.message};}
  if(!currentOpen())return;
  dialog('Settings',`<form id="studio-config-form" novalidate><nav class="studio-settings-tabs" role="tablist" aria-label="Settings"><button type="button" role="tab" id="studio-settings-model-tab" data-settings-tab="model" aria-controls="studio-settings-model-panel" aria-selected="true">Lounge model</button><button type="button" role="tab" id="studio-settings-location-tab" data-settings-tab="location" aria-controls="studio-settings-location-panel" aria-selected="false" tabindex="-1">Location</button><button type="button" role="tab" id="studio-settings-telegram-tab" data-settings-tab="telegram" aria-controls="studio-settings-telegram-panel" aria-selected="false" tabindex="-1">Telegram</button><button type="button" role="tab" id="studio-settings-reset-tab" data-settings-tab="reset" aria-controls="studio-settings-reset-panel" aria-selected="false" tabindex="-1">Reset</button></nav>
  <section id="studio-settings-model-panel" role="tabpanel" aria-labelledby="studio-settings-model-tab"><div class="studio-model-scope"><span>STAGES 01 / 02</span><h3>Hiring &amp; Agent lounge</h3></div><div class="studio-model-link"><button type="button" id="studio-open-team-settings" class="studio-secondary">Set up Stage 03 ↗</button></div><label for="studio-provider">Provider</label><select id="studio-provider">${Object.entries(settings.providers).map(([id,p])=>`<option value="${id}">${escape(p.label)}</option>`).join('')}</select><label for="studio-api-key">API key</label><input id="studio-api-key" type="password" autocomplete="off" spellcheck="false"><small id="studio-key-note"></small><div class="studio-settings-model"><label for="studio-model">Model</label><button type="button" id="studio-load-models" class="studio-secondary">Load models ↻</button></div><button type="button" id="studio-change-model" class="studio-secondary" aria-expanded="false" aria-controls="studio-model-options" hidden>Change model</button><p id="studio-model-status" role="status" aria-live="polite"></p><input id="studio-model-search" type="search" aria-label="Search models" placeholder="Search models…" autocomplete="off" spellcheck="false" hidden><select id="studio-model-options" size="6" aria-label="Available models" hidden></select><input id="studio-model" autocomplete="off" placeholder="Load models to choose, or enter a model ID" required><small>Choose a text model with tool calling.</small><details id="studio-connection-options"><summary>Connection options</summary><label for="studio-endpoint">API endpoint</label><input id="studio-endpoint" type="url" aria-describedby="studio-endpoint-note" required><small id="studio-endpoint-note" hidden>vLLM on this PC: <code>http://127.0.0.1:8000/v1</code>. Use your server’s port, then select a model with Load models.</small><label for="studio-model-context">Context limit · tokens</label><input id="studio-model-context" type="number" min="8192" max="2000000" step="1" required></details><small>Keys stay in memory for this tab only. Closing or refreshing clears them.</small></section>

  <section id="studio-settings-location-panel" role="tabpanel" aria-labelledby="studio-settings-location-tab" hidden><label for="studio-location-city">City</label><input id="studio-location-city" autocomplete="address-level2" maxlength="80" required aria-describedby="studio-location-note"><small id="studio-location-note">Default city in every agent’s USER.md for weather and local requests.</small></section>
  <section id="studio-settings-telegram-panel" role="tabpanel" aria-labelledby="studio-settings-telegram-tab" hidden>
  <p><strong>Tech Radar only.</strong> Send its scheduled Heartbeat summaries to Telegram as well as chat. Other agents’ replies and Multi-Agent results are not sent to Telegram.</p>
  <label for="studio-telegram-token">Bot token (create your bot with <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a> and paste its token)</label><input id="studio-telegram-token" type="password" autocomplete="off" spellcheck="false" placeholder="Token from @BotFather (e.g. 123456789:ABCdef...)">
  <label for="studio-telegram-chat">Chat ID (open <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a>, type /start, copy your Id)</label><input id="studio-telegram-chat" autocomplete="off" spellcheck="false" placeholder="Numeric chat ID (e.g. 123456789)">
  <p id="studio-telegram-status" role="status" hidden></p><div id="studio-telegram-controls" hidden><div class="studio-dialog-actions"><button type="button" id="studio-telegram-test" class="studio-secondary">Send test</button><button type="button" id="studio-telegram-disconnect" class="studio-secondary">Disconnect</button></div></div></section>
  <section id="studio-settings-reset-panel" role="tabpanel" aria-labelledby="studio-settings-reset-tab" class="studio-agent-reset" hidden>
   <div class="studio-reset-row"><div><small class="studio-reset-stage">STAGES 01 / 02</small><h3>Hiring &amp; Agent lounge</h3><p>Remove hired agents and their chats, files, and workspaces.</p></div><button type="button" id="studio-agent-reset" class="studio-secondary" aria-label="Remove Stage 1 and 2 agents" ${(data.agents||[]).length?'':'disabled'}>Remove agents</button></div>
   <div class="studio-reset-row"><div><small class="studio-reset-stage">STAGE ${selectedScenario==='event-brief'?'03-1':'03-2'}</small><h3>${escape(stageScenarios.find(s=>s.id===selectedScenario)?.title||'Multi-Agent demo')}</h3><p>Stop this scenario’s work and clear its chats, documents and results. Other scenarios are preserved.</p></div><button type="button" id="studio-settings-bac-reset" class="studio-secondary" aria-label="Reset Stage 3">Reset scenario</button></div>
   <div class="studio-reset-footer"><p>Reset all stages. Model and connection settings are kept.</p><button type="button" id="studio-reset-all" class="studio-danger">Reset all</button></div>
  </section>
  <p id="studio-settings-status" role="status"></p><div class="studio-dialog-actions"><button type="button" id="studio-start-agents" class="studio-secondary" ${runtime.gateway?'hidden':''}>Start agents</button><button type="submit" class="studio-primary" id="studio-save-settings">Connect model</button></div></form>`);
  const form=el('config-form'),modelList=el('model-options'),modelStatus=el('model-status'),loadButton=el('load-models');
  function showTelegram(){el('telegram-status').textContent=telegram.connected?'Connected to @'+telegram.bot+' · chat '+telegram.chatId:telegram.error||'';el('telegram-status').hidden=!telegram.connected&&!telegram.error;el('telegram-controls').hidden=!telegram.connected;el('telegram-test').disabled=!telegram.connected;el('telegram-disconnect').disabled=!telegram.connected;el('telegram-chat').value=telegram.chatId||'';}
  showTelegram();
  el('open-team-settings').onclick=openTeamSettings;
  async function telegramAction(action){if(connecting)return;connecting=true;el('settings-status').textContent='Connecting';try{const result=await api(action==='test'?'telegram/test':'telegram',action==='test'?{}:{disconnect:true});if(!currentForm())return;if(action==='test')el('settings-status').textContent='Test message sent.';else{telegram=result;showTelegram();el('settings-status').textContent='';}}catch(error){if(currentForm())el('settings-status').textContent=error.message;}finally{connecting=false;}}
  el('telegram-test').onclick=()=>telegramAction('test');el('telegram-disconnect').onclick=()=>telegramAction('disconnect');
  el('location-city').value=settings.location?.city||'Zurich';
  el('agent-reset').onclick=()=>resetStudio('lounge');
  el('settings-bac-reset').onclick=()=>resetStudio('bac');
  el('reset-all').onclick=()=>resetStudio('all');
  syncResetButtons();
  let tab='model',generation=0,availableModels=[],hasMoreModels=false,connecting=false;
  const currentForm=()=>el('config-form')===form&&el('dialog').open;
  const modelSearch=el('model-search'),changeModel=el('change-model');
  let browsingWithKeyboard=false;
  function closeModelList(){if(!modelList.value)return;el('model').value=modelList.value;modelList.hidden=true;modelSearch.hidden=true;changeModel.hidden=false;changeModel.setAttribute('aria-expanded','false');modelStatus.textContent='';el('model').focus();}
  changeModel.onclick=()=>{modelSearch.hidden=false;filterModels();changeModel.setAttribute('aria-expanded','true');modelSearch.focus();};
  function filterModels(){const query=modelSearch.value.trim().toLowerCase();const matches=availableModels.filter(m=>(m.id+' '+(m.name||'')).toLowerCase().includes(query));modelList.replaceChildren(...matches.map(m=>new Option(!m.name||m.name===m.id?m.id:m.name+' · '+m.id,m.id)));modelList.value=el('model').value;modelList.hidden=!matches.length;modelStatus.dataset.state=matches.length?'ready':'empty';modelStatus.textContent=(query?`${matches.length} of ${availableModels.length} models`:`${availableModels.length} models`)+(matches.length?'':' · No matches')+(hasMoreModels?' · More IDs can be entered manually.':'');}
  modelSearch.oninput=filterModels;
  modelSearch.onkeydown=e=>{if(e.key==='Enter')e.preventDefault();if(e.key==='ArrowDown'&&!modelList.hidden){e.preventDefault();modelList.focus();}};
  function selectTab(next){if(connecting)return;tab=next;form.querySelectorAll('[data-settings-tab]').forEach(b=>{const active=b.dataset.settingsTab===tab;b.setAttribute('aria-selected',active);b.tabIndex=active?0:-1;});el('settings-model-panel').hidden=tab!=='model';el('settings-location-panel').hidden=tab!=='location';el('settings-reset-panel').hidden=tab!=='reset';el('settings-telegram-panel').hidden=tab!=='telegram';el('save-settings').textContent=tab==='telegram'?'Connect Telegram':tab==='location'?'Save location':'Connect model';el('save-settings').hidden=tab==='reset';el('start-agents').hidden=tab!=='model'||!!runtime.gateway;el('settings-status').textContent='';if(tab==='reset')syncResetButtons();}
  form.querySelectorAll('[data-settings-tab]').forEach(b=>{b.onclick=()=>selectTab(b.dataset.settingsTab);b.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const tabs=['model','location','telegram','reset'];selectTab(e.key==='Home'?tabs[0]:e.key==='End'?tabs.at(-1):tabs[(tabs.indexOf(tab)+(e.key==='ArrowLeft'?-1:1)+tabs.length)%tabs.length]);el('settings-'+tab+'-tab').focus();}};});

  const input=()=>({provider:el('provider').value,apiKey:el('api-key').value.trim(),baseUrl:el('endpoint').value.trim(),model:el('model').value.trim(),contextWindow:Number(el('model-context').value)});
  function resetModels(){changeModel.hidden=true;changeModel.setAttribute('aria-expanded','false');availableModels=[];hasMoreModels=false;modelSearch.value='';modelSearch.hidden=true;generation++;loadButton.disabled=false;loadButton.textContent='Load models ↻';modelList.replaceChildren();modelList.hidden=true;modelStatus.textContent='';modelStatus.dataset.state='';}
  function fill(){const id=el('provider').value,profile=settings.profiles[id]||{};el('connection-options').open=id==='local';el('endpoint-note').hidden=id!=='local';el('endpoint').value=profile.baseUrl||settings.providers[id].baseUrl;el('model').value=profile.model||'';el('model-context').value=profile.contextWindow||32768;el('api-key').value='';el('api-key').placeholder=profile.hasKey?'Active in this tab · leave blank to keep':'Enter API key';el('key-note').textContent=id==='nvidia'?'Use your employee key from inference.nvidia.com.':id==='local'?'API key is optional for a local server.':'';resetModels();el('settings-status').textContent='';}
  el('provider').value=settings.provider;el('provider').onchange=fill;fill();el('endpoint').oninput=resetModels;el('api-key').oninput=resetModels;
  modelList.onchange=()=>{el('model').value=modelList.value;if(!browsingWithKeyboard)closeModelList();};
  modelList.onpointerdown=()=>{browsingWithKeyboard=false;};
  modelList.onclick=closeModelList;
  modelList.onkeydown=e=>{browsingWithKeyboard=true;if(e.key==='Enter'){e.preventDefault();closeModelList();}else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();modelList.hidden=true;modelSearch.hidden=true;changeModel.hidden=false;changeModel.setAttribute('aria-expanded','false');changeModel.focus();}};
  loadButton.onclick=async()=>{const token=++generation,request=input();loadButton.disabled=true;loadButton.textContent='Loading…';modelSearch.hidden=true;modelList.hidden=true;modelStatus.dataset.state='loading';modelStatus.textContent='Loading models…';const current=()=>el('config-form')===form&&el('dialog').open&&token===generation;
    try{const result=await api('settings/models',request);if(!current())return;availableModels=result.models;hasMoreModels=!!result.hasMore;modelSearch.hidden=!availableModels.length;changeModel.hidden=!availableModels.length;changeModel.setAttribute('aria-expanded',String(!!availableModels.length));filterModels();if(!availableModels.length)modelStatus.textContent='No models returned for this key. Check its access or enter a model ID manually.';}
    catch(error){if(current()){modelStatus.dataset.state='error';modelStatus.textContent=error.message;}}
    finally{if(current()){loadButton.disabled=false;loadButton.textContent='Load models ↻';}}
  };
  el('start-agents').onclick=async()=>{if(connecting)return;connecting=true;el('start-agents').disabled=true;el('settings-status').textContent='Starting agent runtime…';try{await api('settings/start',{});await waitForAgentRuntime();if(!currentForm())return;el('settings-status').textContent=runtime.ready?'Model and agent runtime connected.':'Agent runtime ready. Reconnect the model to continue.';el('start-agents').hidden=true;}catch(error){if(currentForm())el('settings-status').textContent=error.message;}finally{connecting=false;if(currentForm())el('start-agents').disabled=false;}};
  form.onsubmit=async e=>{
    e.preventDefault();if(connecting||tab==='reset')return;
    if(tab==='telegram'){
      connecting=true;el('save-settings').disabled=true;el('settings-status').textContent='Checking bot';
      try{const result=await api('telegram',{token:el('telegram-token').value.trim(),chatId:el('telegram-chat').value.trim()});if(currentForm()){telegram=result;showTelegram();el('telegram-token').value='';el('settings-status').textContent='Bot connected. Send a test to check delivery.';}}
      catch(error){if(currentForm())el('settings-status').textContent=error.message;}
      finally{connecting=false;if(currentForm())el('save-settings').disabled=false;}
      return;
    }
    if(tab==='location'){
      const field=el('location-city'),button=el('save-settings'),status=el('settings-status');
      if(!field.checkValidity()){field.reportValidity();return;}
      connecting=true;button.disabled=true;field.disabled=true;status.textContent='Saving location';
      try{
        const saved=await api('settings',{section:'location',location:{city:field.value.trim()}});
        settings.location=saved.location;runtime.location=saved.location;
        if(currentForm()){field.value=saved.location.city;status.textContent='Saved. Applies to every agent’s next request.';}
      }catch(error){if(currentForm())status.textContent=error.message;}
      finally{connecting=false;if(currentForm()){button.disabled=false;field.disabled=false;}}
      return;
    }
    for(const id of ['model','endpoint','model-context']){const field=el(id);if(!field.checkValidity()){const details=field.closest('details');if(details)details.open=true;field.reportValidity();return;}}
    const request=input(),button=el('save-settings'),status=el('settings-status');
    const controls=[...form.querySelectorAll('#studio-settings-model-panel input,#studio-settings-model-panel select,#studio-settings-model-panel button,#studio-start-agents')].map(node=>[node,node.disabled]);
    connecting=true;button.disabled=true;button.textContent='Connecting';status.dataset.state='connecting';status.textContent='Checking model connection';
    controls.forEach(([node])=>node.disabled=true);
    try{
      await api('settings',{...request,section:'model',verifyConnection:true});
      runtime=await api('runtime');
      if(!runtime.installed&&!runtime.gateway)throw new Error('Model verified. Install the agent runtime on this host to run agents.');
      if(!runtime.gateway){if(currentForm())status.textContent='Starting agent runtime…';await api('settings/start',{});await waitForAgentRuntime();}
      if(!runtime.ready){if(currentForm())status.textContent='Applying model connection';await waitForAgentRuntime(true);}
      runtimeBadge();render();
      if(currentForm()){form.querySelector('#studio-api-key').value='';el('dialog').close();alert('Model and agent runtime connected.');}
    }catch(error){if(currentForm()){status.dataset.state='error';status.textContent=error.message;}}
    finally{connecting=false;if(currentForm()){button.disabled=false;button.textContent='Connect model';controls.forEach(([node,disabled])=>node.disabled=disabled);}}
  };
 }catch(error){if(request===settingsOpenRequest)alert(error.message);}
};
el('dialog').addEventListener('close',()=>{if(el('api-key'))el('api-key').value='';if(el('telegram-token'))el('telegram-token').value='';});

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
    status.textContent='Stopping BaC work and resetting…';
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
   alert('Removing '+agents.length+' agents in the background. Cleanup progress stays visible in their workspaces.');
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
  if(background)alert('Cleanup complete. '+completed+' agents removed.');
 }catch(error){
  status.textContent=(scope==='all'&&teamCleared?'Stage 3 was reset. ':'')+(completed?`${completed} / ${total} removed. `:'')+error.message;
  if(background)alert(status.textContent);
  try{const state=await api('state',undefined,'');if(state.agentId===agentId){data=state;render();}else openAgentState(state);}catch{}
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


const teamModelDrafts=new Map();
let teamModelDraftOwner=null;
function openLegacyTeamSettings(){
 if(!modelPickerSaving||teamModelDraftOwner!==agentId)teamModelDrafts.clear();
 teamModelDraftOwner=agentId;
 const available=window.BacCrewCatalog.map((member,role)=>({...member,roleIndex:role})).filter(member=>selectedScenario==='event-brief'?member.roleIndex<4:member.planEligible!==false);
 dialog('Multi-Agent setup',`<form id="studio-team-config-form">
  <div class="studio-model-scope"><span>STAGE ${selectedScenario==='event-brief'?'03-1':'03-2'}</span><h3>${selectedScenario==='event-brief'?'Event Brief':'Open Task'} models</h3><p>API is recommended for Stage 3. Local models are optional and may take longer.</p></div>
  <label for="studio-scenario-provider">Model source for this scenario</label><select id="studio-scenario-provider"><option value="api">NVIDIA API (recommended)</option><option value="local">Local model</option></select>
  <section id="studio-scenario-local" hidden><label for="studio-scenario-url">Local endpoint</label><input id="studio-scenario-url" type="url" value="${escape(data.teamConnection?.local?.baseUrl||'http://127.0.0.1:8000/v1')}"><small>Use a model server reachable from the OpenClaw host. All agents in this scenario use this model.</small><button type="button" id="studio-scenario-load" class="studio-secondary">Load models</button><label for="studio-scenario-model">Model</label><select id="studio-scenario-model">${data.teamConnection?.local?.model?`<option>${escape(data.teamConnection.local.model)}</option>`:''}</select><label for="studio-scenario-context">Context limit · tokens</label><input id="studio-scenario-context" type="number" min="8192" max="2000000" value="${Number(data.teamConnection?.local?.contextWindow)||32768}"></section>
  <button type="button" id="studio-scenario-apply" class="studio-primary">Apply model source</button><p id="studio-scenario-status" role="status"></p>
  <section id="studio-scenario-api"><div class="studio-team-api-card"><div class="studio-team-api-heading"><strong>NVIDIA Inference</strong><span class="studio-team-api-state" data-connected="${!!runtime.teamModel}">${runtime.teamModel?(runtime.teamReady?'Connected':'API connected · Runtime offline'):'Not connected'}</span></div>
  <small>inference-api.nvidia.com</small>
  <small>${runtime.teamModel?'Key loaded from <code>api.cfg</code>.':'Add a key to <code>api.cfg</code> and run <code>./bac start</code>.'}</small></div>
  <div class="studio-team-models-heading"><h3>Agent models</h3></div><p id="studio-team-model-status" role="status" hidden></p>
  <div class="studio-team-setup-models">${available.map(member=>`<div><span><strong>${escape(member.name)}</strong><small>${escape(selectedScenario==='event-brief'?member.role:member.collaboration.title)}</small></span><div class="studio-team-model-controls"><button type="button" class="team-model-trigger" data-team-model="${member.roleIndex}" ${!runtime.teamModel||data.bacResetting||(data.crewChats||[]).some(j=>['queued','running','waiting','stopping'].includes(j.status))?'disabled':''}><span>${escape(teamModel(member.roleIndex)?.label||'Choose model')}</span><span aria-hidden="true">⌕</span></button></div></div>`).join('')}</div>
  <div class="studio-team-model-save"><button type="button" class="studio-primary" data-team-apply-all disabled>Apply changes</button></div></section></form>`);
 el('dialog').classList.add('studio-team-settings');
 el('team-config-form').onsubmit=event=>event.preventDefault();
 bindScenarioModelSettings();
 syncTeamModelForm();
 if(modelPickerSaving){const notice=el('team-model-status');notice.hidden=false;notice.textContent='Applying model changes…';}
}

function bindScenarioModelSettings(){
 const owner=agentId,scenario=selectedScenario,form=el('team-config-form'),source=el('scenario-provider'),notice=el('scenario-status');
 const current=()=>agentId===owner&&selectedScenario===scenario&&el('team-config-form')===form;
 const busy=()=>modelPickerSaving||data.bacResetting||data.scenarios?.find(s=>s.id===scenario)?.busy||(data.crewChats||[]).some(j=>['queued','running','waiting','stopping'].includes(j.status));
 source.value=data.teamConnection?.provider||'api';
 const update=()=>{el('scenario-local').hidden=source.value!=='local';el('scenario-api').hidden=source.value!=='api';el('scenario-apply').textContent=source.value==='local'?'Apply local model':'Use API for this scenario';el('scenario-apply').hidden=source.value==='api'&&(data.teamConnection?.provider||'api')==='api';el('scenario-apply').disabled=!!busy();source.disabled=!!busy();};
 source.onchange=update;update();
 const payload=()=>({provider:source.value,baseUrl:el('scenario-url').value,model:el('scenario-model').value,contextWindow:Number(el('scenario-context').value)});
 el('scenario-load').onclick=async()=>{
  const button=el('scenario-load');button.disabled=true;notice.textContent='Loading local models…';
  try{const result=await api('settings/scenario-models',payload(),owner);if(!current())return;el('scenario-model').innerHTML=result.models.map(m=>`<option value="${escape(m.id)}">${escape(m.label)}</option>`).join('');notice.textContent=result.models.length?'Models loaded.':'No models found.';}
  catch(error){if(current())notice.textContent=error.message;}finally{if(current())button.disabled=false;}
 };
 el('scenario-apply').onclick=async()=>{
  if(busy())return;const values=payload();modelPickerSaving=true;update();notice.textContent='Applying…';
  try{const result=await api('settings/scenario-model',values,owner);if(!current())return;++refreshVersion;stateCache.clear();data.teamConnection=result.teamConnection;render();notice.textContent='Applied. Used from the next request in this scenario.';}
  catch(error){if(current())notice.textContent=error.message;}
  finally{modelPickerSaving=false;if(current()){update();syncTeamModelForm();}}
 };
}

const openOtherSettings=settingsButton.onclick;
settingsButton.onclick=()=>openModelConnections();
function openTeamSettings(){return openModelConnections();}
async function openModelConnections(){
 const request=++settingsOpenRequest,revision=dialogRevision;
 let state,settings;
 try{[state,settings]=await Promise.all([api('settings/connections'),api('settings')]);}
 catch(error){alert(error.message);return;}
 if(request!==settingsOpenRequest||revision!==dialogRevision)return;
 dialog('Settings',`<div id="studio-model-connections">
  <nav class="connection-tabs"><button type="button" aria-current="page">Model</button><button type="button" data-connection-tab="location">Location</button><button type="button" data-connection-tab="telegram">Telegram</button><button type="button" data-connection-tab="reset">Reset</button></nav>
  <div class="connection-section-heading"><h3>Connections</h3><button type="button" class="connection-text-button" id="studio-connections-check">↻ Refresh</button></div>
  <div class="connection-grid">${['local','api'].map(source=>`<section class="connection-card" data-source="${source}"><header><label class="connection-toggle"><input type="checkbox" data-connection-enable="${source}"><strong>${source==='local'?'Local':'External Endpoint'}</strong></label><span data-connection-status="${source}" role="status"></span></header><p data-connection-summary="${source}"></p><button type="button" class="connection-text-button" data-connection-edit="${source}">Configure →</button></section>`).join('')}</div>
  <div id="studio-connection-editor" hidden></div>
  <div class="connection-section-heading"><h3>Stage preferences</h3><button type="button" class="connection-text-button" id="studio-connections-defaults">Recommended defaults</button></div>
  <p class="connection-hint">If your preferred connection is unavailable, the other ready connection is used.</p>
  <div class="connection-routes">${[['lounge','01 / 02','Hiring & Agent lounge'],['event-brief','03-1','Event Brief'],['plan','03-2','Open Task']].map(([key,number,title])=>`<section class="connection-route"><div class="connection-route-name"><small>${number}</small><strong>${escape(title)}</strong><span id="studio-connection-${key}-effective" role="status"></span></div><div class="connection-choice" role="group" aria-label="${escape(title)} connection">${['local','api'].map(source=>`<button type="button" data-route="${key}" data-route-source="${source}" aria-pressed="false">${source==='local'?'Local':'External'}</button>`).join('')}</div></section>`).join('')}</div>
  <p id="studio-connections-status" role="status"></p><div class="connection-footer"><button type="button" id="studio-connections-agent-models" class="connection-text-button">Per-agent models →</button><button type="button" id="studio-connections-save" class="studio-primary">Save changes</button></div></div>`);
 const panel=el('model-connections'),notice=el('connections-status'),owner=agentId,scenario=selectedScenario;
 let working=false,editing=false,inventoryRevision=0;
 const current=()=>el('model-connections')===panel&&el('dialog').open&&agentId===owner&&selectedScenario===scenario;
 const prefs={lounge:state.loungePreference||'auto','event-brief':state.scenarioPreferences?.['event-brief']||'auto',plan:state.scenarioPreferences?.plan||'auto'};
 function paint(){
  for(const source of ['local','api']){const c=state.connections[source],badge=panel.querySelector(`[data-connection-status="${source}"]`);badge.textContent=c.ready?'Ready':['Not configured','Disabled','Checking…'].includes(c.message)?c.message:'Unavailable';badge.title=c.message;badge.dataset.ready=String(c.ready);const summary=panel.querySelector(`[data-connection-summary="${source}"]`);summary.textContent=c.model?[c.provider==='local'?'':({nvidia:'NVIDIA Inference',openai:'OpenAI',anthropic:'Anthropic'}[c.provider]),c.model].filter(Boolean).join(' · '):source==='local'?'':'NVIDIA · OpenAI · Anthropic';summary.title=c.model||'';const toggle=panel.querySelector(`[data-connection-enable="${source}"]`);if(!working)toggle.checked=c.enabled&&c.message!=='Not configured';toggle.disabled=working;}
  for(const kind of ['lounge','event-brief','plan']){
   const preferred=prefs[kind]==='auto'?(kind==='lounge'?'local':'api'):prefs[kind],other=preferred==='local'?'api':'local',effective=state.connections[preferred].ready?preferred:state.connections[other].ready?other:null;
   for(const button of panel.querySelectorAll(`[data-route="${kind}"]`)){const source=button.dataset.routeSource;button.setAttribute('aria-pressed',String(effective===source));button.disabled=working||!state.connections[source].ready;button.title=state.connections[source].ready?'Prefer '+(source==='local'?'Local':'External Endpoint'):'Connection not ready';}
   const label=el('connection-'+kind+'-effective');label.textContent=!effective?'Model not connected':effective!==preferred?(preferred==='local'?'Local':'External')+' unavailable · Using '+(effective==='local'?'Local':'External'):'Using '+(effective==='local'?'Local':'External Endpoint');label.dataset.error=String(!effective);
  }
  el('connections-agent-models').hidden=selectedScenario==='plan'||state.connections.api.provider!=='nvidia'||!state.connections.api.ready;
  el('connections-save').disabled=working;el('connections-check').disabled=working;el('connections-defaults').disabled=working;
 }
 paint();
 for(const button of panel.querySelectorAll('[data-route]'))button.onclick=()=>{if(working)return;prefs[button.dataset.route]=button.dataset.routeSource;notice.textContent='Unsaved changes';paint();};
 el('connections-defaults').onclick=()=>{if(working)return;for(const key of Object.keys(prefs))prefs[key]='auto';notice.textContent='Local preferred for Hiring & Lounge; External preferred for Event Brief and Open Task. Save to apply.';paint();};
 async function refreshConnections(force=false){const revision=inventoryRevision;try{const next=await api('settings/connections'+(force?'/check':''),force?{}:undefined);if(current()&&revision===inventoryRevision&&!working){state=next;paint();}}catch(error){if(current())notice.textContent=error.message;}}
 const timer=setInterval(()=>{if(!current()){clearInterval(timer);return;}if(!working&&!editing)refreshConnections();},2500);
 el('connections-check').onclick=()=>refreshConnections(true);
 for(const tab of panel.querySelectorAll('[data-connection-tab]'))tab.onclick=async()=>{if(working)return;await openOtherSettings();const target=el('settings-'+tab.dataset.connectionTab+'-tab');if(target){target.click();const model=el('settings-model-tab');model.textContent='Model';model.onclick=()=>openModelConnections();}};
 el('connections-agent-models').onclick=()=>{if(!working)openLegacyTeamSettings();};
 el('connections-save').onclick=async()=>{if(working)return;working=true;++inventoryRevision;paint();notice.textContent='Applying…';try{
  const result=await api('settings/connections/preferences',{lounge:prefs.lounge,scenarios:{'event-brief':prefs['event-brief'],plan:prefs.plan}},owner);if(!current())return;state=result;
  ++refreshVersion;stateCache.clear();data.teamConnection=result.teamConnection;runtime=await api('runtime');if(!current())return;render();notice.textContent='Saved. Applies to new requests.';
 }catch(error){if(current())notice.textContent=error.message;}finally{working=false;if(current())paint();}};
 for(const toggle of panel.querySelectorAll('[data-connection-enable]'))toggle.onchange=async()=>{
  if(working)return;const source=toggle.dataset.connectionEnable,on=toggle.checked;
  if(on&&state.connections[source].message==='Not configured'){editConnection(source);paint();return;}
  working=true;++inventoryRevision;paint();try{state=await api('settings/connections/preferences',{lounge:state.loungePreference,[on?'enable':'disable']:source},owner);if(current())notice.textContent=on?'Enabled. Checking connection…':'Disabled. New requests use the other ready connection.';}catch(error){if(current())notice.textContent=error.message;}finally{working=false;if(current()){paint();await refresh();}}
 };
 for(const button of panel.querySelectorAll('[data-connection-edit]'))button.onclick=()=>editConnection(button.dataset.connectionEdit);
 function editConnection(source){
  if(working)return;editing=true;const editor=el('connection-editor');editor.hidden=false;
  editor.innerHTML=`<h3>${source==='local'?'Local model':'API connection'}</h3>${source==='api'?'<label>Provider<select id="studio-connect-provider"><option value="nvidia">NVIDIA Inference</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select></label><label>API key<input id="studio-connect-key" type="password" autocomplete="off" placeholder="Leave blank to keep the current key"></label><small id="studio-connect-key-status"></small>':''}<label>Endpoint<input id="studio-connect-url" type="url"></label><div class="studio-settings-model"><label for="studio-connect-model">Model</label><button type="button" class="studio-secondary" id="studio-connect-load">Load models ↻</button></div><label><input id="studio-connect-model" list="studio-connect-models" autocomplete="off" placeholder="Load models or enter a model ID"><datalist id="studio-connect-models"></datalist></label><details><summary>Advanced</summary><label>Context budget · tokens<input id="studio-connect-context" type="number" min="8192" max="2000000" value="32768"></label><small>App budget, not the model’s maximum. Keep within your model server’s context limit.</small></details><p id="studio-connect-status" role="status"></p><div class="studio-dialog-actions"><button type="button" class="studio-secondary" id="studio-connect-cancel">Close</button><button type="button" class="studio-primary" id="studio-connect-apply">Connect &amp; enable</button></div>`;
  const provider=()=>source==='local'?'local':el('connect-provider').value;
  const lockFields=()=>{const active=state.connections[source],verified=source==='api'&&active.provider===provider()&&active.ready;el('connect-url').disabled=source==='api';if(el('connect-key')){el('connect-key').disabled=verified;el('connect-key').placeholder=verified?'API key verified':'Enter API key';el('connect-key-status').textContent=verified?'':'Keys entered here last for this tab only.';}};
  const fill=()=>{const id=provider(),profile=settings.profiles[id]||{},active=state.connections[source];el('connect-url').value=profile.baseUrl||settings.providers[id].baseUrl;el('connect-url').readOnly=source==='api';el('connect-model').value=profile.model||(active.provider===id?active.model:'');el('connect-context').value=profile.contextWindow||32768;if(el('connect-key'))el('connect-key').value='';el('connect-models').innerHTML='';lockFields();};
  if(source==='api'){el('connect-provider').value=state.connections.api.provider;el('connect-provider').onchange=fill;}fill();
  const payload=()=>({source,provider:provider(),apiKey:el('connect-key')?.value.trim()||'',baseUrl:el('connect-url').value.trim(),model:el('connect-model').value.trim(),contextWindow:Number(el('connect-context').value)});
  el('connect-cancel').onclick=()=>{if(!working){editor.replaceChildren();editor.hidden=true;editing=false;}};
  async function action(load){if(working)return;working=true;++inventoryRevision;paint();const values=payload(),message=el('connect-status');editor.querySelectorAll('input,select,button').forEach(e=>e.disabled=true);message.textContent=load?'Loading models…':'Checking connection…';try{
   const result=await api('settings/connections'+(load?'/models':''),values,owner);if(!current()||!editor.contains(message))return;
   if(load){el('connect-models').replaceChildren(...result.models.map(m=>new Option(m.name||m.id,m.id)));message.textContent=result.models.length+' models available.';}
   else{state=result;settings.profiles[values.provider]={baseUrl:values.baseUrl,model:values.model,contextWindow:values.contextWindow};if(el('connect-key'))el('connect-key').value='';runtime=await api('runtime');if(current()){await refresh();paint();message.textContent='Connected.';}}
  }catch(error){if(current())message.textContent=error.message;}finally{working=false;if(current()){editor.querySelectorAll('input,select,button').forEach(e=>e.disabled=false);lockFields();paint();}}}
  el('connect-load').onclick=()=>action(true);el('connect-apply').onclick=()=>action(false);
 }
}
