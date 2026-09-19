// Three places in one studio: creation, a growing personal collection, and crew work.
const appearanceColors={green:'#76b900',cyan:'#55bfff',amber:'#f4b34f',coral:'#ff8873',violet:'#b49aff',ice:'#cbddea'};
const roomCopy={
  workshop:['WORKSHOP / CREATE & CONNECT','A personality you can see.','Choose a body, a personality and useful skills. Watch your teammate take shape.'],
  lounge:['AGENT LOUNGE / YOUR COLLECTION','Your people. Your possibilities.','Every agent you create gets a place here. Select one to talk, teach it a skill or give it a mission.'],
  mission:['MISSION ROOM / READY-MADE CREW','Different strengths. One shared brief.','Five specialists, ready to work. The preset crew runs without OpenShell restrictions.'],
  policies:['POLICIES / PERSONAL AGENT ACCESS','Useful skills. Deliberate access.','Choose the boundaries for your own agents. Inspect what is approved and what OpenShell actually enforces.']
};
function avatarBadge(avatar={}){return `<span class="studio-avatar tiny" aria-hidden="true" data-body="${escape(avatar.body||'classic')}" data-accessory="${escape(avatar.accessory||'antenna')}" style="--avatar-accent:${appearanceColors[avatar.color]||appearanceColors.green}"><i></i><i></i></span>`;}
function updateDraft(){
  root.querySelectorAll('[data-body]').forEach(b=>{if(b.tagName==='BUTTON')b.setAttribute('aria-pressed',b.dataset.body===draftAvatar.body);});
  root.querySelectorAll('[data-avatar-color]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.avatarColor===draftAvatar.color));
  draftAvatar.accessory=el('accessory').value;
  window.BacCampus?.setDraft({name:el('name').value.trim()||'Your new agent',persona,avatar:{...draftAvatar}});
}
function fillCreator(creating){
  draftMode=creating?'new':'edit';draftOwner=agentId;
  const n=data.agents?.length||0;
  const used=new Set((data.agents||[]).map(a=>[a.avatar?.body,a.avatar?.color,a.avatar?.accessory].join(':')));
  let defaults;
  for(let offset=0;offset<12;offset++){const index=n+offset;defaults={body:['classic','round','rover'][index%3],color:Object.keys(appearanceColors)[index%6],accessory:['antenna','headset','glasses','cap'][index%4]};if(!used.has([defaults.body,defaults.color,defaults.accessory].join(':')))break;}
  let name=['Jinny','Orbit','Scout','Echo','Pixel','Sage'][n%6];if(data.agents?.some(a=>a.name===name))name+=' '+(n+1);
  const p=creating?{name,persona:['guide','maker','analyst'][n%3],skills:Object.keys(titles),avatar:defaults}:data.profile;
  if(!p)return fillCreator(true);
  el('name').value=p.name;persona=p.persona;draftAvatar={...(p.avatar||defaults)};el('accessory').value=draftAvatar.accessory;
  root.querySelectorAll('[data-persona]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.persona===persona));
  el('skill-picker').querySelectorAll('input').forEach(i=>i.checked=p.skills.includes(i.value));
  el('onboarding').querySelectorAll('[name=protection]').forEach(i=>i.checked=i.value===(p.protection||'standard'));
  el('creator-title').textContent=creating?'Meet your next teammate.':'Make '+p.name+' your own.';
  el('creator-note').textContent=creating?'Their own look. Their own memory. Your choice of skills.':'Update the look, persona and skills. Memory and files stay with this agent.';
  el('create').textContent=creating?'Bring my agent to life ↗':'Save my agent ↗';el('cancel-create').hidden=!data.profile;el('create').disabled=creating&&n>=(data.agentLimit||12);
  updateDraft();
}
function setRoom(next,options={}){
  if(!roomCopy[next])return;
  const before=options.fromWorld&&!worldOpen?worldViewport.getBoundingClientRect().top:null;
  if(typeof worldOpen!=='undefined'&&worldOpen&&(next==='policies'||board))leaveWorld();
  room=next;if(next!=='mission')board=false;
  root.dataset.room=next;worldViewport.setAttribute('aria-label',roomCopy[next][0]+'. Drag to orbit, scroll to zoom. Press Enter to toggle full screen.');if(roomsReady)try{sessionStorage.setItem('bac-studio-room',next);}catch{}
  if(next==='mission')renderCrew();renderRoomVisibility();if(next==='policies')loadPolicy();else window.BacCampus?.setRoom(next,{instant:!roomsReady});
  if(before!==null)window.scrollBy(0,worldViewport.getBoundingClientRect().top-before);
}
function renderRoomVisibility(){
  const workshop=room==='workshop',lounge=room==='lounge',mission=room==='mission',policies=room==='policies';
  root.querySelectorAll('[data-room]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.room===room));
  const [kicker,title,description]=roomCopy[room];el('room-kicker').textContent=kicker;el('room-title').textContent=title;el('room-description').textContent=description;
  el('workshop').hidden=!workshop;el('passport').hidden=workshop||policies;el('connections').hidden=!workshop;el('policies').hidden=!policies;
  el('collection').hidden=!lounge||!data.profile;
  root.querySelector('.studio-viewbar').hidden=!mission;
  layout.hidden=policies||(mission&&board);el('board').hidden=!mission||!board;
  el('experiences').hidden=!lounge;el('workspace').hidden=workshop||policies;el('safety-bar').hidden=policies;
  root.querySelector('.studio-crew-invite').hidden=!lounge;
  el('campus-tab').setAttribute('aria-pressed',!board);el('board-tab').setAttribute('aria-pressed',board);
  const action=el('room-action');action.hidden=workshop&&!data.profile;action.textContent=mission?'Launch a crew mission ↗':lounge?'＋ Create an agent':'Back to my lounge ↗';
  document.getElementById('campus-roster').hidden=!mission;
  document.getElementById('campus-location').textContent=workshop?'WORKSHOP / LIVE APPEARANCE PREVIEW':lounge?'YOUR LOUNGE / '+(data.agents?.length||0)+' AGENTS':document.getElementById('campus-location').textContent;
  if(workshop)document.getElementById('campus-motion-status').textContent='Your draft · choose a look and bring it to life';
  if(lounge)document.getElementById('campus-motion-status').textContent=data.agents?.length?'Your actual agents · select a teammate to open its workspace':'A place for every agent you create';
}
function renderRooms(){
  if(!roomsReady){roomsReady=true;fillCreator(true);let saved;try{saved=sessionStorage.getItem('bac-studio-room');}catch{}setRoom(data.profile?(roomCopy[saved]?saved:'lounge'):'workshop');}
  renderRoomVisibility();
  const agents=data.agents||[];el('lounge-count').textContent=agents.length?agents.length+' personal agent'+(agents.length===1?'':'s'):'Your personal agents';
  el('gateway-state').textContent=runtime.testFixture?'Test fixture · no live gateway':runtime.gateway?'Gateway connected':'Waiting for your Spark host';
  el('model-state').textContent=runtime.testFixture?'Test fixture · no live model':runtime.model?'Local model connected':'Start Qwen or Gemma on Spark';
  el('shell-state').textContent=runtime.openshell||'Optional · not configured';
  if(data.profile){const a=data.profile.avatar||{};el('portrait').dataset.body=a.body||'classic';el('portrait').dataset.accessory=a.accessory||'antenna';el('portrait').style.setProperty('--avatar-accent',appearanceColors[a.color]||appearanceColors.green);}
  window.BacCampus?.setCollection(agents,agentId);
  renderPolicySelector();
}
function agentForm(creating=false){if(creating&&(data.agents?.length||0)>=(data.agentLimit||12)){alert('Your lounge is full. You can customize any of your existing agents.');return;}fillCreator(creating);setRoom('workshop');el('room-heading').scrollIntoView({behavior:'smooth',block:'start'});}
el('color-picker').innerHTML=Object.entries(appearanceColors).map(([name,color])=>`<button type="button" data-avatar-color="${name}" style="--swatch:${color}" aria-label="${name[0].toUpperCase()+name.slice(1)}" aria-pressed="false"></button>`).join('');
el('body-picker').onclick=e=>{const b=e.target.closest('[data-body]');if(b){draftAvatar.body=b.dataset.body;updateDraft();}};
el('color-picker').onclick=e=>{const b=e.target.closest('[data-avatar-color]');if(b){draftAvatar.color=b.dataset.avatarColor;updateDraft();}};
el('accessory').onchange=updateDraft;el('name').addEventListener('input',updateDraft);
root.querySelectorAll('[data-persona]').forEach(button=>button.onclick=()=>{persona=button.dataset.persona;root.querySelectorAll('[data-persona]').forEach(b=>b.setAttribute('aria-pressed',b===button));updateDraft();});
el('rooms').onclick=e=>{const b=e.target.closest('[data-room]');if(b)setRoom(b.dataset.room);};
root.addEventListener('bac:world-room',e=>setRoom(e.detail.room,{fromWorld:true}));
el('room-action').onclick=()=>room==='mission'?crewForm():room==='lounge'?agentForm(true):setRoom('lounge');
el('edit-agent').onclick=()=>agentForm(false);el('add-agent').onclick=()=>agentForm(true);el('empty-create').onclick=()=>agentForm(true);el('cancel-create').onclick=()=>setRoom('lounge');
el('delete-agent').onclick=()=>{
  if(!data.profile||pendingWrites||changingAgent||removingAgent)return;
  const target=agentId,name=data.profile.name,agent=data.agents.find(a=>a.key===target);
  if(agent?.pending){
    dialog('FINISH THE MISSION FIRST',`<h3>${escape(name)} still has work in progress.</h3><p>Finish or cancel its pending missions before deleting it. This includes scheduled follow-ups and work assigned by another crew.</p><button class="studio-primary" id="studio-delete-view-work">View pending work ↗</button>`);
    el('delete-view-work').onclick=()=>{el('dialog').close();if(data.assignments?.length)el('assigned-crew').click();else{const job=data.jobs.find(j=>['running','stopping','queued','waiting'].includes(j.status));selectedJob=job?.id;render();if(job?.kind==='crew'){showBoard(true);el('board').scrollIntoView({behavior:'smooth'});}else{setRoom('lounge');el('workspace').scrollIntoView({behavior:'smooth'});}}};
    return;
  }
  dialog('YOUR COLLECTION',`<div class="studio-delete-identity">${avatarBadge(data.profile.avatar)}<span>REMOVE A TEAMMATE</span></div><h3>Delete ${escape(name)}?</h3><p>Remove this agent, its conversation, saved memory and workspace files from your studio. Its Telegram connection will also be removed.</p><p class="studio-muted">You cannot undo this in the app. Completed crew packages saved by other agents and messages already sent to Telegram remain. OpenClaw may move native files to the host’s Trash.</p><p id="studio-delete-error" role="alert" hidden></p><div class="studio-delete-actions"><button class="studio-secondary" id="studio-delete-cancel" autofocus>Keep agent</button><button class="studio-danger" id="studio-delete-confirm">Delete ${escape(name)}</button></div>`);
  el('delete-cancel').onclick=()=>el('dialog').close();el('delete-cancel').focus();
  el('delete-confirm').onclick=async()=>{
    if(target!==agentId)return;
    removingAgent=true;++refreshVersion;
    const preventClose=e=>e.preventDefault();el('dialog').addEventListener('cancel',preventClose);
    el('delete-confirm').disabled=true;el('delete-cancel').disabled=true;el('dialog-close').disabled=true;el('delete-confirm').textContent='Deleting…';
    try{
      const result=await api('delete-agent',{name},target);
      const state=await api('state',undefined,result.agentId);
      openAgentState(state);fillCreator(true);setRoom(data.profile?'lounge':'workshop');el('dialog').close();
      alert(name+' was deleted. Your other agents are unchanged.');el('room-action').hidden?el('name').focus():el('room-action').focus();
    }catch(error){el('delete-error').hidden=false;el('delete-error').textContent=error.message;el('delete-confirm').textContent='Retry deletion';el('delete-confirm').disabled=false;el('delete-cancel').disabled=false;}
    finally{removingAgent=false;el('dialog-close').disabled=false;el('dialog').removeEventListener('cancel',preventClose);refresh();}
  };
};
el('connection-setup').onclick=setup;el('connection-security').onclick=()=>setRoom('policies');
el('onboarding').onsubmit=async e=>{
  e.preventDefault();const mode=draftMode,target=draftOwner,first=!data.agents?.length;
  const payload={name:el('name').value,persona,skills:[...el('skill-picker').querySelectorAll('input:checked')].map(x=>x.value),avatar:{...draftAvatar},protection:el('onboarding').querySelector('[name=protection]:checked').value};
  el('create').disabled=true;
  try{
    const result=await api(mode==='edit'?'profile':first?'onboard':'agents',payload,target);
    if(mode==='new'&&!first)await switchAgent(result.agentId);else await refresh();
    setRoom('lounge');el('room-heading').scrollIntoView({behavior:'smooth',block:'start'});
    alert(mode==='edit'?'Your agent’s look, persona and skills are saved.':payload.name+' has joined your lounge. Give your new teammate a mission.');
  }catch(error){alert(error.message);}finally{el('create').disabled=draftMode==='new'&&(data.agents?.length||0)>=(data.agentLimit||12);}
};
root.addEventListener('bac:collection-select',async e=>{if(worldOpen)await leaveWorld();await switchAgent(e.detail);setRoom('lounge');el('passport').scrollIntoView({behavior:'smooth',block:'center'});});
// Useful in file-only UI review too; live status is supplied by boot().
fillCreator(true);setRoom('workshop');
