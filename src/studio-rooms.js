// Three places in one studio: creation, a growing personal collection, and crew work.
let editingInPlace=false,hiringArrival=false,draftNameEdited=false;
const appearanceColors={green:'#76b900',cyan:'#55bfff',amber:'#f4b34f',coral:'#ff8873',violet:'#b49aff',ice:'#cbddea'};
const appearanceNames={classic:'Jinny',round:'Orbit',rover:'Scout',operative:'Smith',claw:'Pixel',crab:'Sage'};
const roomCopy={
  workshop:'Hiring',
  lounge:'Agent lounge',
  mission:'Multi-Agent demo'
};
function avatarBadge(avatar={}){return `<span class="studio-avatar tiny" aria-hidden="true" data-body="${escape(avatar.body||'classic')}" data-accessory="${escape(avatar.accessory||'antenna')}" style="--avatar-accent:${appearanceColors[avatar.color]||appearanceColors.green}"><i></i><i></i></span>`;}
// Presets and custom text edit the same two fields; no hidden tone overrides.
function creatorPrompt(){
  const text=el('purpose').value.trim();
  const tone=text.match(/^[ \t]*(?:-[ \t]+)?Tone:[ \t]*([^]*?)(?=^[ \t]*(?:-[ \t]+)?Role:|$(?![^]))/im);
  const role=text.match(/^[ \t]*(?:-[ \t]+)?Role:[ \t]*([^]*?)(?=^[ \t]*(?:-[ \t]+)?Tone:|$(?![^]))/im);
  return {tonePrompt:tone?tone[1].trim():'',purpose:role?role[1].trim():tone?'':text};
}
function writeCreatorPrompt(tone,role){el('purpose').value='- Tone: '+tone+'\n- Role: '+role;}
function tonePromptLabel(key){return tones[key][0]+' ('+tones[key][1]+')';}
function matchesTonePrompt(key,text){return [tones[key][0],tonePromptLabel(key)].some(value=>value.toLowerCase()===text.toLowerCase());}
function savedTonePrompt(profile){return profile.tonePrompt??tonePromptLabel(profile.tone||'kind');}
function syncCreatorTone(){
  const tone=creatorPrompt().tonePrompt.toLowerCase();
  draftTone=Object.keys(tones).find(key=>matchesTonePrompt(key,tone))||'kind';
}
function availableAgentName(body){
  const baseName=appearanceNames[body]||'Agent';let name=baseName,number=2;
  while(data.agents?.some(a=>a.name.toLowerCase()===name.toLowerCase()))name=baseName+'_'+number++;
  return name;
}
function updateDraft(){
  root.querySelectorAll('[data-body]').forEach(b=>{if(b.tagName==='BUTTON')b.setAttribute('aria-pressed',b.dataset.body===draftAvatar.body);});
  root.querySelectorAll('[data-avatar-color]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.avatarColor===draftAvatar.color));
  draftAvatar.accessory=el('accessory').value;
  const verbosity='balanced';
  root.querySelectorAll('[data-tone]').forEach(b=>b.setAttribute('aria-pressed',matchesTonePrompt(b.dataset.tone,creatorPrompt().tonePrompt)));
  window.BacCampus?.setDraft({name:el('name').value.trim()||'Your new agent',...creatorPrompt(),persona,tone:draftTone,verbosity,protection:el('onboarding').querySelector('[name=protection]:checked')?.value||'standard',avatar:{...draftAvatar}});
}
function fillCreator(creating){
  draftMode=creating?'new':'edit';draftOwner=agentId;
  const n=data.agents?.length||0;
  const used=new Set((data.agents||[]).map(a=>[a.avatar?.body,a.avatar?.color,a.avatar?.accessory].join(':')));
  let defaults;
  for(let offset=0;offset<12;offset++){const index=n+offset,body=['classic','round','rover','operative','claw','crab'][index%6];defaults={body,color:Object.keys(appearanceColors)[index%6],accessory:'none'};if(!used.has([defaults.body,defaults.color,defaults.accessory].join(':')))break;}
  const name=availableAgentName(defaults.body);
  const p=creating?{name,persona:'guide',purpose:roleTemplates[0].purpose,skills:[...roleTemplates[0].skills],avatar:defaults}:data.profile;
  if(!p)return fillCreator(true);
  draftNameEdited=!creating;
  el('name').value=p.name;writeCreatorPrompt(savedTonePrompt(p),p.purpose||(creating?'':personas[p.persona]));persona=p.persona;draftAvatar={...(p.avatar||defaults)};el('accessory').value=draftAvatar.accessory;
  draftTone=p.tone||'kind';
  el('role-templates').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(roleTemplates[Number(b.dataset.roleTemplate)]?.purpose===p.purpose)));
  el('role-hint').textContent='Buttons fill the prompt. Edit either line freely.';
  el('skill-picker').querySelectorAll('input').forEach(i=>i.checked=p.skills.includes(i.value));
  el('onboarding').querySelectorAll('[name=protection]').forEach(i=>i.checked=i.value===(p.protection||'standard'));
  el('onboarding').querySelector('.studio-protection-picker').hidden=!creating;
  el('onboarding').querySelectorAll('[name=protection]').forEach(i=>i.disabled=!creating);
  el('creator-title').textContent=creating?'Hire your own Agent.':'Edit '+p.name;
  el('creator-note').hidden=creating;
  el('creator-note').textContent=creating?'':'Update its look, working style, voice and abilities. Memory and files stay with this agent.';
  el('create').textContent=creating?'Hire my agent':'Save my agent';el('cancel-create').hidden=!data.profile;el('create').disabled=creating&&n>=(data.agentLimit||12);
  updateDraft();el('workshop').scrollTop=0;
}
function setRoom(next,options={}){
  const openPolicies=next==='policies';if(openPolicies)next='lounge';
  if(!roomCopy[next])return;
  const before=options.fromWorld&&!worldOpen?worldViewport.getBoundingClientRect().top:null;
  if(next!==room){closeSurface();if(next==='mission'&&!options.resume)scenarioChoosing=true;}
  if(next==='mission'&&options.fromWorld&&!options.resume){closeSurface();scenarioChoosing=true;}
  if(next!=='mission')scenarioChoosing=true;
  editingInPlace=false;room=next;if(next!=='mission')board=false;
  root.dataset.room=next;worldViewport.setAttribute('aria-label',roomCopy[next]+'. Drag to orbit, scroll to zoom. Press Enter to toggle full screen.');if(roomsReady)try{sessionStorage.setItem('bac-studio-room',next);}catch{}
  if(next==='mission')renderCrew();renderRoomVisibility();
  runtimeBadge();
  if(next==='mission'&&scenarioChoosing)window.BacCampus?.scenarios({instant:!roomsReady});
  else window.BacCampus?.setRoom(next,{instant:!roomsReady});
  if(openPolicies)openSurface('policies');
  if(before!==null)window.scrollBy(0,worldViewport.getBoundingClientRect().top-before);
}
function renderRoomVisibility(){
  if(el('compare'))el('compare').hidden=room!=='lounge'||!comparison;
  syncComposer();
  const workshop=room==='workshop',lounge=room==='lounge',mission=room==='mission';
  el('workshop').hidden=!(workshop||editingInPlace);el('passport').hidden=!lounge||editingInPlace;el('crew-passport').hidden=!mission||scenarioChoosing;el('connections').hidden=!workshop;el('policies').hidden=false;el('policy-panel').hidden=!lounge;
  el('collection').hidden=!lounge||!data.profile;
  layout.hidden=false;el('board').hidden=true;
  el('experiences').hidden=!lounge;el('workspace').hidden=workshop||(mission?!currentCollaboration():(!current()&&!data.files?.length));el('safety-bar').hidden=true;
  const action=el('room-action');action.hidden=!mission||scenarioChoosing||selectedScenario!=='event-brief';action.textContent='Plan an event';action.onclick=crewForm;action.disabled=!!data.bacResetting||eventTeamWorking();
  document.getElementById('campus-roster').hidden=!mission||scenarioChoosing;
  renderScenarioSelector();
  const activeScenario=stageScenarios.find(s=>s.id===selectedScenario);
  document.getElementById('campus-location').textContent=workshop?'HIRING / MEET YOUR NEXT AGENT':lounge?'LOUNGE / Current Agents: '+(data.agents?.length||0):(activeScenario?.number.replace(/^0/,'')||'03')+' / '+(activeScenario?.title||'Multi-Agent demo');
  syncSurface();
  if(workshop)document.getElementById('campus-motion-status').textContent='';
  if(lounge)document.getElementById('campus-motion-status').textContent='';
}
function renderRooms(){
  if(!roomsReady){roomsReady=true;fillCreator(true);let saved;try{saved=sessionStorage.getItem('bac-studio-room');}catch{}setRoom(data.profile?(roomCopy[saved]?saved:'lounge'):'workshop');window.BacCampus?.overview({instant:true});}
  renderRoomVisibility();
  const agents=data.agents||[];
  el('gateway-state').textContent=runtime.testFixture?'Test fixture · no live gateway':gatewayLabel();
  el('model-state').textContent=runtime.testFixture?'Test fixture · no live model':runtime.model?'Connected':'Not connected';
  el('shell-state').textContent=runtime.openshell||'Optional · not configured';
  if(data.profile){const a=data.profile.avatar||{};el('portrait').dataset.body=a.body||'classic';el('portrait').dataset.accessory=a.accessory||'antenna';el('portrait').style.setProperty('--avatar-accent',appearanceColors[a.color]||appearanceColors.green);}
  window.BacCampus?.setCollection(agents,agentId);
  renderPolicySelector();
}
function agentForm(creating=false){if(creating&&(data.agents?.length||0)>=(data.agentLimit||12)){alert('Your lounge is full. You can edit any of your existing agents.');return;}fillCreator(creating);if(creating)setRoom('workshop');else{editingInPlace=true;renderRoomVisibility();}el('workshop').scrollTop=0;}
el('color-picker').innerHTML=Object.entries(appearanceColors).map(([name,color])=>`<button type="button" data-avatar-color="${name}" style="--swatch:${color}" aria-label="${name[0].toUpperCase()+name.slice(1)}" aria-pressed="false"></button>`).join('');
el('body-picker').onclick=e=>{const b=e.target.closest('[data-body]');if(b){draftAvatar.body=b.dataset.body;if(draftMode==='new'&&!draftNameEdited)el('name').value=availableAgentName(draftAvatar.body);updateDraft();}};
el('color-picker').onclick=e=>{const b=e.target.closest('[data-avatar-color]');if(b){draftAvatar.color=b.dataset.avatarColor;updateDraft();}};
el('accessory').onchange=updateDraft;el('name').addEventListener('input',()=>{draftNameEdited=true;updateDraft();});
const roleTemplates=[
  {label:'Weather buddy',summary:'Current weather and practical outdoor advice.',purpose:'Check current weather and help me decide what to wear or whether to go outside. Keep advice short and practical.',skills:['weather']},
  {label:'Tech Radar',summary:'One technical discovery every 30 seconds.',purpose:'Every 30 seconds, share one unread technical article or announcement from NVIDIA or Hugging Face blogs in my chosen tone. Include older articles; never repeat. Skip politics, stocks and earnings.',skills:['radar']},
  {label:'Arxivbot',summary:'Three relevant papers on a topic you choose.',purpose:'When I give you a research topic, find three relevant arXiv papers. Summarize each paper’s main idea, include its title, authors, date and link, and briefly compare them in my chosen tone. Ask for a topic if none is given.',skills:['web']},
  {label:'Slack Announcer',summary:'Emoji-led updates in your chosen voice.',purpose:'Answer in the style of a concise Slack announcement: an emoji-led headline and short, useful lines. Keep my chosen tone and the supplied facts. Draft only; never send or publish.',skills:['writer']},
];
el('role-templates').innerHTML=roleTemplates.map((t,i)=>`<button type="button" data-role-template="${i}" aria-pressed="false">${t.label}</button>`).join('');
function selectRoleSkills(skills){
  el('skill-picker').querySelectorAll('input').forEach(input=>input.checked=skills.includes(input.value));
  el('role-hint').textContent=skills.length?'Suggested skills selected. Adjust them below.':'No matching skills found. Choose below.';
  updateDraft();
}
el('role-templates').onclick=e=>{const button=e.target.closest('[data-role-template]');if(!button)return;const template=roleTemplates[Number(button.dataset.roleTemplate)];writeCreatorPrompt(creatorPrompt().tonePrompt,template.purpose);el('role-templates').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));selectRoleSkills(template.skills);};
el('purpose').addEventListener('input',()=>{el('role-templates').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed','false'));el('role-hint').textContent='Apply to suggest skills. Your prompt is also saved when you hire.';syncCreatorTone();updateDraft();});
el('apply-prompt').onclick=()=>{
  syncCreatorTone();
  const role=creatorPrompt().purpose.toLowerCase();
  const rules={radar:/heartbeat|tech radar|technical feeds|하트비트|기술.*소식/,weather:/weather|forecast|travel|trip|날씨|여행/,web:/research|paper|arxiv|논문|search|online|web|travel|trip|cafe|restaurant|리서치|조사|검색|웹|여행|맛집|카페/,documents:/takeaway|three points|meeting|notes|회의|메모|document|report|pdf|ppt|slides|deck|summar|요약|슬라이드|csv|spreadsheet|문서|보고서|자료|엑셀/,builder:/app|game|prototype|code|website|앱|게임|코딩|개발|웹사이트/,writer:/slack|announcement|공지|message|email|메시지|메일|writ|draft|content|invitation|social|campaign|marketing|copy|작성|글쓰기|초대|마케팅|콘텐츠/,memory:/remember|memor|preference|기억|선호/};
  selectRoleSkills(Object.entries(rules).filter(([skill,rule])=>rule.test(role)).map(([skill])=>skill));
};
el('onboarding').querySelectorAll('[name=protection]').forEach(input=>input.onchange=updateDraft);
el('tone-picker').onclick=e=>{const button=e.target.closest('[data-tone]');if(button){draftTone=button.dataset.tone;writeCreatorPrompt(tonePromptLabel(draftTone),creatorPrompt().purpose);updateDraft();}};
root.addEventListener('bac:world-room',e=>setRoom(e.detail.room,{fromWorld:true}));

el('edit-agent').onclick=()=>agentForm(false);el('cancel-create').onclick=()=>{if(editingInPlace){editingInPlace=false;fillCreator(true);renderRoomVisibility();}else setRoom('lounge');};
function forgetDeletedAgent(target){
  stateCache.clear();
  personalDrafts.delete(target);
  for(const key of chatImageDrafts.keys())if(key.startsWith(target+':'))chatImageDrafts.delete(key);
  for(const key of crewDrafts.keys())if(key.startsWith(target+':'))crewDrafts.delete(key);
  try{const layout=JSON.parse(localStorage.getItem('bac-lounge-layout-v1')||'{}');delete layout[target];localStorage.setItem('bac-lounge-layout-v1',JSON.stringify(layout));}catch{}
}
async function deleteAgentAndWait(target,name,onWaiting=()=>{}){
  const result=await api('delete-agent',{name},target);
  if(!result.deleting){forgetDeletedAgent(target);return result;}
  return waitForAgentDeletion(target,name,onWaiting);
}
async function waitForAgentDeletion(target,name,onWaiting=()=>{}){
  onWaiting();
  while(true){
    await new Promise(resolve=>setTimeout(resolve,1000));
    // Query the collection without the removed identity so deletion cannot turn polling into a 404.
    const state=await api('state',undefined,'');
    const agent=state.agents.find(a=>a.key===target);
    if(!agent){forgetDeletedAgent(target);return {deleted:target,agentId:state.agentId};}
    if(!agent.deletionWaiting)throw new Error('Cleanup could not finish for '+name+'. Retry Delete agent.');
    onWaiting(agent);
  }
}
el('delete-agent').onclick=()=>{
  if(!data.profile||pendingWrites||changingAgent||removingAgent)return;
  const target=agentId,name=data.profile.name;
  dialog('YOUR COLLECTION',`<div class="studio-delete-identity">${avatarBadge(data.profile.avatar)}<span>REMOVE A TEAMMATE</span></div><h3>Delete ${escape(name)}?</h3><p>Permanently delete this agent, its chats, memory and files.</p><p class="studio-muted">Pending and scheduled tasks will be cancelled, and any running task involving this agent will stop.</p><p id="studio-delete-error" role="alert" hidden></p><div class="studio-delete-actions"><button class="studio-secondary" id="studio-delete-cancel" autofocus>Keep agent</button><button class="studio-danger" id="studio-delete-confirm">Delete ${escape(name)}</button></div>`);
  el('delete-cancel').onclick=()=>el('dialog').close();el('delete-cancel').focus();
  el('delete-confirm').onclick=async()=>{
    if(target!==agentId)return;
    removingAgent=true;++refreshVersion;
    el('dialog').close();
    el('delete-agent').disabled=true;
    try{
      const result=await deleteAgentAndWait(target,name,agent=>{
        // The durable server fence is in place. Release navigation while native
        // cleanup continues; never turn an acknowledgement into "deleted".
        removingAgent=false;
        if(target===agentId){data.deleting=true;const row=data.agents.find(a=>a.key===target);if(row)Object.assign(row,{deleting:true,deletionWaiting:true,deletionProgress:agent?.deletionProgress||'Queued for cleanup'});render();}
      });
      if(target===agentId&&!changingAgent){
        const state=await api('state',undefined,result.agentId);
        if(target===agentId&&!changingAgent){const viewingRoom=room;openAgentState(state);fillCreator(true);setRoom(viewingRoom==='lounge'?(data.profile?'lounge':'workshop'):viewingRoom);}
      }
      alert(name+' was deleted.');root.querySelector('.world-room-map [data-world-room="'+room+'"]')?.focus({preventScroll:true});
    }catch(error){alert(error.message);}
    finally{removingAgent=false;render();refresh();}
  };
};
el('connection-setup').onclick=setup;el('connection-security').onclick=()=>setRoom('policies');
el('onboarding').onsubmit=async e=>{
  e.preventDefault();if(hiringArrival)return;syncCreatorTone();const mode=draftMode,target=mode==='new'?agentId:draftOwner,first=!data.agents?.length;
  const payload={name:el('name').value,...creatorPrompt(),persona,tone:draftTone,verbosity:'balanced',skills:[...el('skill-picker').querySelectorAll('input:checked')].map(x=>x.value),avatar:{...draftAvatar},protection:el('onboarding').querySelector('[name=protection]:checked').value};
  hiringArrival=true;el('create').disabled=true;el('onboarding').inert=true;
  try{
    const result=await api(mode==='edit'?'profile':first?'onboard':'agents',payload,mode==='new'&&!first?'':target);
    // Bind the arrival to this response, never to a changing workspace selection.
    const createdId=mode==='new'&&!first?result.agentId:target;
    if(mode==='new'){++refreshVersion;openAgentState(await api('state',undefined,createdId));}else await refresh();
    if(mode==='new'&&room==='workshop'){hiringArrival=true;el('create').textContent='Joining your lounge…';await window.BacCampus?.welcomeAgent(createdId);if(room!=='workshop'||root.dataset.worldOverview==='true'){fillCreator(true);return;}}
    const stayHere=mode==='edit'&&editingInPlace;editingInPlace=false;fillCreator(true);if(stayHere)renderRoomVisibility();else setRoom('lounge');el('workshop').scrollTop=0;
    alert(mode==='edit'?'Your agent’s look, working style, voice and abilities are saved.':(data.profile?.name||payload.name)+' has joined your lounge. Give your new teammate a mission.');
  }catch(error){alert(error.message);}finally{hiringArrival=false;el('onboarding').inert=false;el('create').disabled=draftMode==='new'&&(data.agents?.length||0)>=(data.agentLimit||12);}
};
// Selecting a resident updates its workspace without moving the visitor's view.
root.addEventListener('bac:collection-select',e=>{if(hiringArrival)return;editingInPlace=false;renderRoomVisibility();switchAgent(e.detail);});
// Useful in file-only UI review too; live status is supplied by boot().
fillCreator(true);setRoom('workshop');window.BacCampus?.overview({instant:true});
