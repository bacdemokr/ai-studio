(() => {
  const root = document.getElementById('agent-campus');
  const el = name => document.getElementById('studio-' + name);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const titles = {'nvidia-webpage':'NVIDIA event page','nvidia-social':'NVIDIA social copy','nvidia-research':'NVIDIA theme research','event-page':'Event page studio',radar:'Tech Radar',weather:'Live weather',web:'Research & papers',documents:'Three Takeaways',builder:'App builder',writer:'Slack announcements',memory:'Personal memory'};
  const personas = {guide:'Explains ideas and turns them into practical plans.',maker:'Turns ideas into drafts, prototypes and small apps.',analyst:'Researches questions and compares the evidence.'};
  const tones={kind:['Kind','Warm & encouraging'],direct:['Direct','Clear & candid'],playful:['Playful','Light & witty'],cynical:['Cynical','Dry humor & skepticism']};
  const verbosityLabels={brief:'Brief',balanced:'Balanced',verbose:'Detailed'};
  const capabilities={
    radar:['Tech Radar','Technical articles and announcements → a short summary','Every 30 seconds · never repeats a shared article'],
    builder:['Build an interactive app','An idea → a playable HTML app','Try: a reaction-time game'],
    documents:['Three Takeaways','Any question or document → three clear points','Always: 1. · 2. · 3. — including event reactions'],
    web:['Research & papers','Recent papers → dated sources and a comparison','Try: find 3 recent arXiv papers on RAG'],
    writer:['Slack announcements','Emoji-led updates in your chosen voice','Emoji-led replies · extra lines when useful · draft only'],
    memory:['Remember what matters','A preference → a saved note used next time','Try: remember my diet, then suggest a meal'],
    weather:['Live weather','A city → timestamped weather and a forecast','Try: choose a time for an outdoor break']
  };
  const roles = window.BacCrewCatalog.map(({name,role,description})=>[name,role,description]);
  const defaultNames=roles.map(r=>r[0]);
  const personaLabels={guide:'Helper',maker:'Creator',analyst:'Researcher'};
  function toneSummary(profile){
    const custom=(profile.tonePrompt||'').trim().replace(/\s+/g,' ');
    const preset=custom?Object.keys(tones).find(key=>matchesTonePrompt(key,custom)):(profile.tone||'kind');
    if(tones[preset])return tones[preset].join(' · ');
    // Keep custom tone wording faithful; its full text remains available on hover.
    return custom.match(/^[\s\S]*?[.!?。！？](?=\s|$)/)?.[0]||custom||tones.kind.join(' · ');
  }
  function voiceSummary(p){return (p.tonePrompt||tones[p.tone]?.[0]||'Kind')+' · '+(verbosityLabels[p.verbosity]||'Balanced')+' answers';}
  const missions = [
    {id:'radar',icon:'◷',title:'Discover something new',sub:'One unread technical article at a time',tag:'HEARTBEAT',color:'#99c8e3',prompt:''},
    {id:'builder',icon:'⌘',title:'Make something playable',sub:'An idea → a tiny working app',tag:'CREATE',color:'#b4dc83',prompt:'Build a polished reaction-time game as a single self-contained HTML file. Use a dark NVIDIA-inspired style, green action buttons, keyboard and touch controls, and a personal best score. Explain how to play. Save it in artifacts/.'},
    {id:'weather',icon:'☀',title:'Do I need an umbrella?',sub:'Live weather → one practical decision',tag:'EXPLORE',color:'#e8cd80',prompt:'Check the current weather in Zurich. For a short walk now, do I need an umbrella or a jacket? Give the observation time, temperature and precipitation, then one practical recommendation. Keep it to 4 short bullets and cite your sources. Do not generate a file.'},
    {id:'documents',icon:'▤',title:'Find three takeaways',sub:'PDF or PPTX → 3 key points with sources',tag:'UNDERSTAND',color:'#99c8e3',prompt:'Read the most recently uploaded document in inbox/. For PDF or PPTX use its .txt companion. Give exactly 3 numbered takeaways, under 150 words. Include any next step within point 3. Cite the filename and page or slide number for each takeaway, or quote the source if it has no page markers. Do not infer missing images, charts or numbers. No generated file.'},
    {id:'web',icon:'⌕',title:'Find recent papers',sub:'arXiv → dates, sources and a comparison',tag:'RESEARCH',color:'#adbbe8',prompt:'Find three recent arXiv preprints about retrieval-augmented generation using the arXiv API in your research skill. Sort by submission date. Include title, publication date, authors and abstract URL. Use one compact table with one sentence per paper, then suggest one to read first. Keep the comparison under 180 words; no generated file. State the query and retrieval date, and label them as preprints. If access fails, say so instead of inventing papers.'},
    {id:'writer',icon:'✎',title:'Draft a Slack announcement',sub:'An emoji headline and a few useful lines',tag:'COMMUNICATE',color:'#e6af8e',prompt:'Turn this note into a Slack-style announcement in your chosen tone, under 80 words. Use a short emoji-led headline and a few useful lines. Preserve the facts and do not invent a date, venue or signup link: We are planning a Build-a-Claw hands-on session in Zurich. You can create your own agent and see a team of agents plan an event. Details will follow. Would you like to join? Return only the draft; do not send it or generate a file.'},
    {id:'memory',icon:'▧',title:'Teach it your style',sub:'A preference → a lasting memory',tag:'PERSONALIZE',color:'#c3ace9',prompt:'Please remember that I prefer concise English answers with three practical bullets, and I like vegetarian food. Save this preference to MEMORY.md. Tell me exactly what you saved.'},
  ];
  let csrf = '', data = {profile:null,jobs:[],files:[],memory:''}, runtime = {}, persona = 'guide', skill = null, selectedJob = null, resultKey = '', board = false, connected = false, busy = false;
  let agentId='',changingAgent=false,removingAgent=false,pendingWrites=0,refreshVersion=0,collectionKey='';
  let room='workshop',roomsReady=false,draftMode='new',draftOwner='',draftAvatar={body:'classic',color:'green',accessory:'antenna'};
  let draftTone='kind';
  let policySnapshot=null,policyVersion=0,policyLoading=false,policySaving=false;
  let selectedCrewRole=0;
  let comparison=null,comparisonSending=false,comparisonTimer=null;
  root.classList.add('studio-enabled');
  const layout = root.querySelector('.campus-layout');
  layout.before(el('safety-bar'));
  el('safety-bar').after(el('collection'));
  layout.append(el('workshop'),el('passport'),el('crew-passport'));layout.after(el('connections'));
  layout.after(el('board'));
  el('board').after(el('experiences'));
  el('experiences').after(el('workspace'));
  el('collection').after(layout);layout.after(el('safety-bar'));el('safety-bar').after(el('connections'));layout.after(el('collection'));
  el('collection').after(el('policies'));
  const policyPanel=document.createElement('details');policyPanel.id='studio-policy-panel';policyPanel.className='studio-inline-panel';policyPanel.innerHTML='<summary>OpenShell Policy</summary>';el('policies').before(policyPanel);policyPanel.append(el('policies'));policyPanel.ontoggle=()=>{if(policyPanel.open)loadPolicy();};
  el('workspace').append(el('reset'));el('reset').className='studio-secondary';

  const demoSkills=['weather','radar','web','writer'],extraSkills=['documents','builder','memory'];
  const skillCards=keys=>keys.map(key=>{const [title,detail,example]=capabilities[key];return `<label><input type="checkbox" value="${key}"><span><strong>${title}</strong><small>${detail}</small><em>${example}</em></span></label>`;}).join('');
  el('skill-picker').innerHTML=skillCards(demoSkills)+'<div hidden>'+skillCards(extraSkills)+'</div>';
  el('tone-picker').innerHTML=Object.entries(tones).map(([key,[title,detail]])=>`<button type="button" data-tone="${key}" aria-pressed="${key==='kind'}"><strong>${title}</strong><small>${detail}</small></button>`).join('');
  const missionCards=keys=>keys.map(key=>{const m=missions.find(m=>m.id===key);return `<button class="studio-mission" data-studio-mission="${m.id}" aria-pressed="false" style="--mission-color:${m.color}"><span>${m.icon}</span><em>${m.tag}</em><strong>${m.title}</strong><small>${m.sub}</small></button>`;}).join('');
  el('missions').innerHTML=missionCards(demoSkills)+'<details class="studio-extra-skills"><summary>More scenarios</summary><div class="studio-missions">'+missionCards(extraSkills)+'</div></details>';
  let alertTimer=null;
  function dismissAlert(){clearTimeout(alertTimer);alertTimer=null;el('alert').hidden=true;}
  function alert(message) {
    clearTimeout(alertTimer);
    el('alert').querySelector('span').textContent=message;el('alert').hidden=false;
    alertTimer=setTimeout(dismissAlert,5000);
  }
  el('alert').querySelector('button').onclick=dismissAlert;
  const credentialSession=Array.from(crypto.getRandomValues(new Uint8Array(24)),b=>b.toString(16).padStart(2,'0')).join('');
  window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
  setInterval(()=>{if(connected)api('credential-session',{}).catch(()=>{});},20000);
  window.addEventListener('pagehide',()=>{document.querySelectorAll('input[type=password]').forEach(input=>input.value='');if(connected)fetch('/api/credential-session',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-BaC-CSRF':csrf,'X-BaC-Key-Session':credentialSession},body:JSON.stringify({end:true})}).catch(()=>{});});
  // State polling is frequent; reuse unchanged snapshots without rebuilding the UI.
  // This cache is tab-local and scoped by agent, never stored on disk.
  const stateCache=new Map();
  async function api(path, payload, target=agentId) {
    // Presence renewals belong to the tab, not an editable agent workspace.
    const workspaceWrite=payload!==undefined&&path!=='credential-session';
    if(workspaceWrite&&changingAgent)throw new Error('Wait for your agent’s workspace to open.');
    const headers={'X-BaC-Key-Session':credentialSession,...(target?{'X-BaC-Agent':target}:{})};
    const conditional=path==='state'&&payload===undefined,cached=conditional?stateCache.get(target):null;
    if(cached)headers['If-None-Match']=cached.etag;
    const options = payload===undefined ? {headers} : {method:'POST',headers:{...headers,'Content-Type':'application/json','X-BaC-CSRF':csrf},body:JSON.stringify(payload)};
    const readTimeout=payload===undefined?(['session','state'].includes(path)?30000:/^(?:agent-policy|crew-policy)(?:\?|$)/.test(path)?45000:0):0;
    const controller=readTimeout?new AbortController():null;
    const timeout=controller?setTimeout(()=>controller.abort(),readTimeout):null;
    if(controller)options.signal=controller.signal;
    if(workspaceWrite)pendingWrites++;
    try {
    let response;
    try {response=await fetch('/api/'+path,options);} catch {if(controller?.signal.aborted)throw new Error('The studio took too long to respond. Please try again.');throw new Error('Cannot reach the studio. Check ./bac status; use ./bac restart to restart its services.');}
    if(response.status===304&&cached)return cached.value;
    let result;
    try {result=await response.json();} catch {if(controller?.signal.aborted)throw new Error('The studio took too long to respond. Please try again.');throw new Error('The app server did not return a valid response. Refresh after updating the app.');}
    if(!response.ok){const error=new Error(result.error||'The request could not be completed.');error.status=response.status;throw error;}
    if(conditional&&response.headers.get('ETag')){
      stateCache.set(target,{etag:response.headers.get('ETag'),value:result});
      if(stateCache.size>16)stateCache.delete(stateCache.keys().next().value);
    }
    return result;
    }finally{clearTimeout(timeout);if(workspaceWrite)pendingWrites--;}
  }
  function rememberSelection(){try{sessionStorage.setItem('bac-selected-agent',agentId);}catch{}}
  function openAgentState(state){
    restorePersonalDraft(state.agentId,state.agents||[]);
    agentId=state.agentId;data=state;rememberSelection();selectedJob=null;resultKey='';skill=null;
    el('upload').value='';el('chat-error').hidden=true;dismissAlert();
    el('missions').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed','false'));
    if('speechSynthesis' in window)window.speechSynthesis.cancel();
    render();
    if(!data.profile){fillCreator(true);setRoom('workshop');}
  }
  async function switchAgent(next){
    if(next===agentId)return;
    if(changingAgent||pendingWrites||removingAgent){alert('Wait for the current save to finish before switching agents.');return;}
    changingAgent=true;++refreshVersion;
    try{
      const state=await api('state',undefined,next);
      openAgentState(state);
    }catch(error){alert(error.message);}finally{changingAgent=false;busy=false;warmCrewOnOpen();}
  }
  function renderCollection(){
    el('collection').hidden=!data.profile;
    const key=JSON.stringify([agentId,data.agents]);
    if(key===collectionKey)return;collectionKey=key;
    el('agent-list').innerHTML=(data.agents||[]).map(a=>`<button class="studio-agent-card" data-agent-key="${a.key}" data-personality="${a.persona}" aria-pressed="${a.key===agentId}">${avatarBadge(a.avatar)}<span><strong>${escape(a.name)}</strong><small>${escape(a.purpose||'Personal agent')} · ${a.skills.length} skills${a.deleting?' · Deletion pending':a.activity?' · Busy':' · Ready'}</small></span><em>${a.key===agentId?'SELECTED':'OPEN'}</em></button>`).join('');
    el('collection-note').textContent=`${data.agents?.length||0} / ${data.agentLimit||12} agents · Each keeps its own conversation, memory and files. Assign them to roles when launching a crew.`;
  }
  el('agent-list').onclick=e=>{const b=e.target.closest('[data-agent-key]');if(b)switchAgent(b.dataset.agentKey);};
  let dialogRevision=0;
  function dialog(kicker, html) {dialogRevision++;el('dialog').classList.remove('studio-agent-documents');el('dialog').classList.toggle('studio-page-preview',['EVENT PAGE','WEBPAGE PREVIEW'].includes(kicker));el('dialog-kicker').textContent=kicker;el('dialog-body').innerHTML=html;if(!el('dialog').open)el('dialog').showModal();}
  el('dialog').addEventListener('close',()=>{dialogRevision++;});
  el('dialog-close').onclick=()=>el('dialog').close();
  el('dialog').addEventListener('click',e=>{if(e.target===el('dialog')&&!removingAgent){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  function setup() {
    dialog('CONNECTIONS',`<h3>Connections</h3><div class="studio-runtime-grid"><div><b>Model</b><small>${runtime.model?'Connected':'Not connected'}</small></div><div><b>OpenClaw</b><small>${gatewayLabel()}</small></div><div><b>OpenShell</b><small>${escape(runtime.openshell||'Not configured')}</small></div></div>`);
  }
  const modelBadge=root.querySelector('.campus-sim');
  function gatewayState(){return runtime.gatewayState||(runtime.gateway?'ready':'unavailable');}
  function gatewayLabel(){return gatewayState()==='slow'?'Agent runtime responding slowly':gatewayState()==='ready'?'Ready':'Agent runtime unavailable';}
  function openModelSettings(){if(!runtime.model&&!runtime.testFixture&&!settingsButton.hidden)settingsButton.click();}
  let runtimeRetrying=false;
  async function retryRuntime(){
    if(runtimeRetrying)return;
    runtimeRetrying=true;runtimeBadge();
    try{runtime=await api('runtime?retry=1');}
    catch{alert('Could not reach the app server. Check that it is running, then retry.');}
    finally{runtimeRetrying=false;runtimeBadge();}
  }
  function connectionAction(){if(!runtime.gateway)retryRuntime();else openModelSettings();}
  modelBadge.onclick=e=>{e.stopPropagation();if(modelBadge.dataset.actionable==='true')connectionAction();};
  modelBadge.onkeydown=e=>{if(modelBadge.dataset.actionable==='true'&&(e.key==='Enter'||e.key===' ')){e.preventDefault();e.stopPropagation();connectionAction();}};
  function runtimeBadge(){
    syncDemoPreparation();syncEventLaunch();syncCrewComposer();
    const state=gatewayState(),slow=state==='slow',ready=!!runtime.ready&&!runtime.testFixture;
    const actionable=!runtime.testFixture&&!runtimeRetrying&&(!runtime.gateway||(!runtime.model&&!settingsButton.hidden));
    modelBadge.textContent=runtime.testFixture?'TEST FIXTURE · NO REAL MODEL':runtimeRetrying?'Checking connection…':slow?'◷ '+gatewayLabel():!runtime.gateway?'⚠ Agent runtime unavailable · Retry connection':!runtime.model?'○ Model not connected':'● Ready';
    modelBadge.dataset.warning=String(!runtime.testFixture&&!slow&&!runtime.ready);
    modelBadge.dataset.slow=String(!runtime.testFixture&&slow);
    modelBadge.dataset.ready=String(ready&&!slow);modelBadge.dataset.actionable=String(actionable);
    modelBadge.setAttribute('role',actionable?'button':'status');modelBadge.tabIndex=actionable?0:-1;
    modelBadge.setAttribute('aria-live','polite');
    modelBadge.title=runtimeRetrying?'Checking the local agent runtime':!runtime.gateway?'Retry connection':slow?'Checking automatically. Tasks already running are not cancelled.':actionable?'Open model settings':'Agent runtime ready';
    if(roomsReady)renderRooms();syncComposer();syncDemoPreparation();
  }

  function current(){return data.jobs.find(j=>j.id===selectedJob)||data.jobs[0];}
  function crewMission(){return current()?.kind==='crew'?current():data.jobs.find(j=>j.kind==='crew');}
  function render() {
    const profile=data.profile, job=current();
    window.BacCampus?.observeProtection(data.protectionEvents||[]);
    if(profile)roles[0][0]=profile.name;
    renderCollection();syncDemoPreparation();
    el('onboarding').hidden=false;el('companion').hidden=!profile;el('lounge-empty').hidden=!!profile;
    if(profile){el('agent-name').textContent=profile.name;el('personality').textContent=toneSummary(profile);el('personality').title=profile.tonePrompt||toneSummary(profile);el('agent-skills').innerHTML=profile.skills.map(s=>'<span class="studio-skill-badge" title="'+escape(capabilities[s]?.[1]||titles[s]||s)+'"><i aria-hidden="true">'+escape(missions.find(m=>m.id===s)?.icon||'◇')+'</i>'+escape(titles[s]||capabilities[s]?.[0]||s)+'</span>').join('');el('agent-skills').hidden=!profile.skills.length;el('equipped').innerHTML=profile.skills.map(s=>{const c=capabilities[s];return c?'<button type="button" data-try-skill="'+s+'"><strong>'+escape(c[0])+'</strong><small>'+escape(c[1])+'</small></button>':'<span>'+escape(titles[s])+'</span>';}).join('');el('memory').hidden=!profile.skills.includes('memory');}
    const personalJobs=data.jobs.filter(j=>!['crew','crew-chat','prepare'].includes(j.kind));
    const active=personalJobs.find(j=>['running','stopping'].includes(j.status))||personalJobs.find(j=>['queued','waiting'].includes(j.status));
    el('task-state').textContent=active?'Busy':'Ready';
    el('task-summary').textContent=active?(active.kind==='crew'?'Your specialists are building the event plan.':active.payload.prompt.slice(0,135)):'Give your agent a task.';
    const assignment=data.assignments?.find(a=>a.role!=='Event roundtable');el('assigned-crew').hidden=!assignment;
    if(assignment){el('assigned-crew').textContent='Open '+assignment.name+'’s crew';if(!active){el('task-state').textContent='Busy';el('task-summary').textContent=assignment.role+' for '+assignment.name+' · '+assignment.status+'. Follow the handoffs in the lead’s workspace.';}}
    const cleanup=data.agents.find(a=>a.key===agentId);
    el('delete-agent').textContent=cleanup?.deletionWaiting?'Deleting…':data.deleting?'Retry deletion':'Delete agent';
    el('delete-agent').disabled=!!cleanup?.deletionWaiting;
    let cleanupNotice=el('cleanup-notice');if(!cleanupNotice){cleanupNotice=document.createElement('p');cleanupNotice.id='studio-cleanup-notice';cleanupNotice.className='studio-delete-progress';cleanupNotice.setAttribute('role','status');el('companion').prepend(cleanupNotice);}
    cleanupNotice.hidden=!data.deleting;
    const cleanupLabel=cleanup?.deletionWaiting?'Deleting '+(profile?.name||'agent'):'Cleanup paused. Retry deletion.';
    cleanupNotice.textContent=data.deleting?cleanupLabel+' · You can use another agent while cleanup continues.':'';
    if(data.deleting){el('task-state').textContent=cleanup?.deletionWaiting?'Deleting':'Cleanup paused';el('task-summary').textContent=cleanupLabel;}
    el('agent-policy').hidden=profile?.protection!=='openshell';
    el('agent-policy').disabled=!!data.deleting;
    let monitor=el('radar-monitor');if(!monitor){monitor=document.createElement('div');monitor.id='studio-radar-monitor';monitor.className='studio-radar-monitor';el('agent-policy').after(monitor);}
    const watch=data.techRadar;monitor.hidden=!watch;
    if(watch){monitor.innerHTML='<span><b>Heartbeat</b> · '+escape(watch.paused?'Paused':watch.state)+'<small>One unread article every 30 seconds'+(watch.lastChecked?' · Last checked '+new Date(watch.lastChecked*1000).toLocaleTimeString(): '')+'</small></span><button type="button" class="studio-secondary">'+(watch.paused?'Resume':'Pause')+'</button>';const button=monitor.querySelector('button');button.disabled=!!data.deleting;button.onclick=async()=>{button.disabled=true;try{await api('heartbeat',{paused:!watch.paused});await refresh();}catch(error){alert(error.message);button.disabled=false;}};}

    el('edit-agent').disabled=!!data.deleting;el('send').disabled=!!data.deleting;
    if(data.deleting){const waiting=data.agents?.find(a=>a.key===agentId)?.deletionWaiting;el('task-state').textContent=waiting?'DELETING':'DELETION NEEDS ATTENTION';el('task-summary').textContent=waiting?'Stopping work. This agent will be removed automatically after the current call ends.':'Cleanup could not finish. Retry Delete agent.';}

    const taskFailed=!active&&!assignment&&!data.deleting&&personalJobs[0]?.status==='error';
    if(taskFailed){el('task-state').textContent='MISSION NEEDS ATTENTION';el('task-summary').textContent=personalJobs[0].result?.error||'Open Results & files to review this mission.';}
    el('task-state').parentElement.hidden=!(active||assignment||data.deleting||taskFailed);

    el('files').innerHTML=data.files.length?data.files.map(f=>`<button data-studio-file="${escape(f.path)}">${f.path.endsWith('.html')?'⌘':'▤'} ${escape(f.path.split('/').pop())}<span>${Math.ceil(f.size/1024)} KB</span></button>`).join(''):'<p class="studio-muted">Uploaded documents and deliverables live here.</p>';
    el('job-history').innerHTML=data.jobs.slice(0,12).map((j,i)=>`<button data-studio-job="${j.id}" aria-pressed="${job?.id===j.id}">${j.kind==='crew'?'Crew':j.kind==='reminder'?'Follow-up':'Mission'} ${data.jobs.length-i} · ${escape(j.status)}</button>`).join('');
    if(job){
      const events=[...job.events].reverse();
      el('events').innerHTML=events.length?events.map(e=>`<li><b>${escape(e.title)}</b><small>${new Date(e.time*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})} · ${escape(e.detail)}</small></li>`).join(''):'<li><b>Waiting in the shared queue</b><small>All agents share one model. Scheduled jobs run when their time arrives.</small></li>';
      const key=job.id+job.status+job.events.length;
      if(key!==resultKey){
        resultKey=key;el('result-title').textContent=job.status==='done'?'Your agent made this.':job.status==='error'?'This mission needs attention.':job.kind==='crew'?'Your crew is building the plan.':'From request to result.';
        el('read-aloud').hidden=!job.result.answer;
        el('result').replaceChildren();
        if(job.status==='waiting'){
          const box=document.createElement('div');box.className='studio-waiting';box.innerHTML='The plan needs '+job.payload.capacity.spark+' demo devices and '+job.payload.capacity.workstation+' workstations. Your available equipment does not cover it.<br><button class="studio-primary" data-decision="approve-equipment">Plan additional equipment</button><button class="studio-secondary" data-decision="cancel">Cancel and revise</button>';el('result').append(box);
        }
        const answer=document.createElement('div');answer.textContent=job.result.answer||job.result.error||Object.values(job.payload.outputs||{}).slice(-1)[0]||(job.status==='queued'?'Your mission is saved in the queue.':job.status==='cancelled'?'This mission was cancelled.':'The agent is working. Actual handoffs and saved files appear in the evidence panel.');el('result').append(answer);
        const apps=(job.result.files||[]).filter(f=>f.endsWith('.html'));
        if(apps.length){const preview=document.createElement('div');preview.className='studio-app-preview';preview.innerHTML='<strong>Your mini app is ready to try.</strong>'+apps.map(path=>`<button class="studio-primary" data-studio-file="${escape(path)}">Play your app</button>`).join('');el('result').prepend(preview);}
        if(job.status==='queued'){const cancel=document.createElement('button');cancel.className='studio-secondary';cancel.dataset.decision='cancel';cancel.textContent='Cancel queued task';el('result').append(cancel);}
      }
    }
    if(!job){resultKey='';el('result-title').textContent='Results';el('result').textContent='';el('events').innerHTML='<li><b>No mission on this board.</b><small>Real handoffs and results will appear here.</small></li>';el('read-aloud').hidden=true;}
    renderCrew();renderSafety();renderRooms();renderEventPackage();renderConversation();
    root.dispatchEvent(new Event('bac:state-rendered'));
  }
  el('assigned-crew').onclick=async()=>{const a=data.assignments?.[0];if(!a)return;await switchAgent(a.lead);if(agentId===a.lead){selectedJob=a.job;render();showBoard(true);}};
  function renderCrew(){
    window.BacSound?.observeJobs(agentId,data.jobs);
    const crew=crewMission(), stage=crew?.payload.stage??-1;
    roles.forEach((r,i)=>r[0]=crew?.payload.roster?.[i]?.name||(i===0&&room!=='mission'?data.profile?.name:null)||defaultNames[i]);
    const groups=crewGroups(crew).map(group=>group.filter(i=>i<4)).filter(group=>group.length);el('lanes').style.setProperty('--crew-groups',groups.length);
    el('lanes').innerHTML=groups.map(group=>`<section class="studio-work-group ${group.length>1?'is-parallel':''}">${group.length>1?'<div class="studio-parallel-caption">In parallel <span>Both finish before the next handoff</span></div>':''}<div class="studio-work-group-cards">${group.map(i=>{const [name,role,description]=roles[i],done=!!crew?.payload.outputs?.[i],working=['running','stopping'].includes(crew?.status)&&(crew?.payload.activeStages||[stage]).includes(i),waiting=crew?.status==='waiting'&&i===2;return `<article class="studio-lane" data-state="${waiting?'waiting':done?'done':working?'running':'ready'}"><span>${waiting?'NEEDS YOU':done?'DELIVERED':working?(crew?.status==='stopping'?'STOPPING':'WORKING'):crew?'WAITING':'READY'}</span><h4>${escape(name)}</h4><strong>${escape(role)}</strong><p>${escape(description)}</p>${eventExpectationMarkup(crew,i)}${hasCrewDeliverable(crew,i)?'<button data-role-output="'+i+'">Open deliverable</button>':''}</article>`;}).join('')}</div></section>`).join('');
    renderMissionControl();
    const active=room==='mission'?(crew&&['running','stopping','waiting'].includes(crew.status)?crew:null):data.jobs.find(j=>['running','stopping'].includes(j.status))||data.jobs.find(j=>j.status==='waiting');
    const s=window.BacDemo.snapshot();
    const a=roles.map(([name,role,description],i)=>({...s.agents[i],name,role,persona:description,skills:i===0?['Shared brief']:i===1?['Demo design']:i===2?['Capacity planning']:i===3?['Campaign writing']:i===4?['Evidence review']:['Event page studio'],lane:0,status:'Ready',task:description,permission:'Scoped workspace',displayed:i<4,included:(crew?.payload.enabledRoles||[0,1,2,3]).includes(i)}));
    crew?.payload.roster?.forEach((m,i)=>{a[i].persona=m.purpose||personas[m.persona];a[i].skills=m.skills.map(x=>titles[x]);a[i].avatar=m.avatar;a[i].protection=m.protection;});
    let phase=-1,selected=0,flow=['Your campus is ready','Choose a mission or launch a crew.','Start'];
    if(active?.kind==='crew'){
      selected=active.status==='waiting'?2:Math.min(roles.length-1,active.payload.stage);phase=active.status==='waiting'?2:selected;
      a[selected].lane=active.status==='waiting'?2:0;a[selected].status=active.status==='waiting'?'Decision required':active.status==='stopping'?'Stopping after active call':'Running in OpenClaw';a[selected].task=active.events.at(-1)?.detail||roles[selected][2];
      const simultaneous=active.status==='waiting'?[2]:(active.payload.activeStages||[selected]);
      simultaneous.forEach(i=>{if(a[i]){a[i].lane=active.status==='waiting'?2:1;a[i].status='Running in OpenClaw';}});
      flow=[simultaneous.map(i=>roles[i][0]).join(' + ')+(simultaneous.length>1?' · Working in parallel':' · '+a[selected].status),a[selected].task,'Open mission'];
    }else if(active){
      phase=0;a[0].name=data.profile?.name||'My agent';a[0].role='Your personal agent';a[0].persona=personas[data.profile?.persona]||'';a[0].skills=(data.profile?.skills||[]).map(x=>titles[x]);a[0].lane=1;a[0].status=active.status==='stopping'?'Stopping after active call':'Running in OpenClaw';a[0].task=active.payload.prompt;flow=[a[0].name+' is working',active.payload.prompt,'Open mission'];
    }else if(data.profile&&room!=='mission'){a[0].name=data.profile.name;a[0].role='Your personal agent';a[0].persona=personas[data.profile.persona];a[0].skills=data.profile.skills.map(x=>titles[x]);}
    if(data.profile&&!crew&&room!=='mission')a[0].avatar=data.profile.avatar;
    if(active?.payload.roundtable?.status==='reviewing')flow=['Your agents’ roundtable','The package is ready. Your agents are sharing their personal takes.','Open mission'];
    const collaboration=currentCollaboration(),planning=collaboration&&!collaboration.payload.collaboration.responseReady&&['running','stopping'].includes(collaboration.status)?collaboration:null;
    if(collaboration){
      const plan=collaboration.payload.collaboration,chosen=[0,...(plan.calledRoles||(plan.tasks||[]).map(t=>t.role))];
      a.forEach((agent,i)=>{const expertise=window.BacCrewCatalog[i].collaboration;agent.name=defaultNames[i];agent.role=expertise.title;agent.persona=expertise.description;agent.skills=[];agent.lane=0;agent.included=chosen.includes(i);agent.displayed=chosen.length>1?chosen.includes(i):i<4;agent.task=plan.tasks?.find(t=>t.role===i)?.task||expertise.description;agent.status=plan.outputs?.[i]?'Done':agent.included?'Selected':'Ready';});
    }
    if(!a[selectedCrewRole]?.displayed)selectedCrewRole=0;
    renderStandbySpecialists(a,crew);
    a.forEach((agent,i)=>{agent.protection=window.BacCrewCatalog[i].protection||'standard';});
    if(planning){const role=planning.payload.collaboration.activeRole??0;phase=role;a[role].lane=1;a[role].status=planning.status==='stopping'?'Stopping':'Collaborating';a[role].task=planning.events?.at(-1)?.title||'Working with the BaC team';flow=[a[role].name+' · '+a[role].status,a[role].task,'Open mission'];}
    const planRoundtable=collaboration?.payload.collaboration.tasks&&collaboration.payload.collaboration.outcome!=='unavailable'?collaboration.payload.roundtable:null;
    if(planRoundtable?.status==='reviewing'&&['running','stopping'].includes(collaboration.status))flow=['Your agents’ take','The result is ready. Your agents are sharing their personal reactions.','Open mission'];
    const b=crew?.payload.brief;
    window.BacCampus?.setLive({...s,live:true,crewMission:collaboration?{id:collaboration.id,kind:'plan',status:collaboration.status,roundtable:planRoundtable,activeStages:planning?[planning.payload.collaboration.activeRole??0]:[],count:roles.length,enabledRoles:[0,...(collaboration.payload.collaboration.calledRoles||(collaboration.payload.collaboration.tasks||[]).map(t=>t.role))],completed:Object.keys(collaboration.payload.collaboration.outputs||{}).map(Number)}:crew?{id:crew.id,status:crew.status,failed:Object.keys(crew.payload.stageErrors||{}).length>0,activeStages:['running','stopping'].includes(crew.status)?(crew.payload.activeStages||[crew.payload.stage]):[],count:crew.payload.roster?.length||5,enabledRoles:crew.payload.enabledRoles||roles.map((_,i)=>i),roundtable:crew.payload.roundtable,completed:Object.keys(crew.payload.outputs||{}).map(Number)}:null,phase,jobId:active?.id,missionSkill:active?.payload.skill,revision:data.jobs.length,agents:a,selected:room==='mission'?selectedCrewRole:selected,flow,gap:active?.status==='waiting',brief:b?{...b,location:b.city}:null,calc:crew?.payload.capacity||null,policy:null});
    document.getElementById('campus-motion-status').textContent=planning||active?flow[0]:'Meet your specialists · use /plan to assemble a team';
    renderCrewPassport();
  }
  /* STUDIO_CREW */
  async function refresh(){if(changingAgent||removingAgent||!connected)return;const version=++refreshVersion,target=agentId;busy=true;try{const state=await api('state',undefined,target);if(version===refreshVersion&&target===agentId&&!changingAgent&&state!==data){data=state;render();}}catch(error){if(version===refreshVersion){if(error.status===404){try{const state=await api('state',undefined,'');if(version===refreshVersion&&!changingAgent){el('dialog').close();openAgentState(state);alert('This agent was deleted in another tab. Your collection is up to date.');}}catch(recovery){alert(recovery.message);}}else if(!document.hidden)alert(error.message);}}finally{if(version===refreshVersion)busy=false;warmCrewOnOpen();}}
  el('equipped').onclick=e=>{const button=e.target.closest('[data-try-skill]');if(button)el('missions').querySelector('[data-studio-mission="'+button.dataset.trySkill+'"]')?.click();};
  el('missions').onclick=e=>{const button=e.target.closest('[data-studio-mission]');if(!button)return;const mission=missions.find(m=>m.id===button.dataset.studioMission);if(!data.profile){alert('Hire an agent first.');agentForm(true);el('name').focus();return;}if(!data.profile.skills.includes(mission.id)){
      let notice=el('mission-skill-notice');if(!notice){notice=document.createElement('div');notice.id='studio-mission-skill-notice';notice.className='studio-mission-skill-notice';el('missions').before(notice);}
      const target=agentId;notice.innerHTML='<p>'+escape(data.profile.name)+' needs '+escape(titles[mission.id])+' for this mission.</p><button type="button" class="studio-primary">Add skill &amp; use mission</button><small>OpenShell permissions stay unchanged.</small>';
      notice.querySelector('button').onclick=async()=>{const action=notice.querySelector('button');action.disabled=true;try{if(agentId!==target)throw new Error('The selected agent changed. Choose a mission again.');await api('profile',{...data.profile,skills:[...new Set([...data.profile.skills,mission.id])]},target);await refresh();notice.remove();if(agentId===target)button.click();}catch(error){notice.querySelector('p').textContent=error.message;action.disabled=false;}};
      notice.scrollIntoView({block:'nearest'});return;
    }el('mission-skill-notice')?.remove();closeSurface();setRoom('lounge');if(mission.id==='radar'){el('radar-monitor')?.scrollIntoView({block:'nearest'});return;}skill=mission.id;const city=runtime.location?.city||'Zurich';el('prompt').value=['weather','writer'].includes(mission.id)?mission.prompt.replaceAll('Zurich',city):mission.prompt;el('missions').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',b===button));if(mission.id==='documents'&&!data.files.some(f=>f.kind==='inbox')){sampleDocument();}el('prompt').focus({preventScroll:true});};
  el('chat').onsubmit=async e=>{e.preventDefault();if(!runtime.ready||data.deleting||chatSending||comparisonSending||documentUploadTarget===agentId){syncComposer();return;}el('chat-error').hidden=true;if(e.submitter?.id==='studio-send-all')return askAllAgents();const draft=captureChatDraft();chatSending=true;syncComposer();try{const result=await api('jobs',{kind:'chat',prompt:draft.prompt,skill,images:draft.images});selectedJob=result.id;acknowledgeChatDraft(draft);await refresh();if(result.collaboration)stageCollaboration(result);el('conversation').scrollTop=el('conversation').scrollHeight;}catch(error){el('chat-error').textContent=error.message;el('chat-error').hidden=false;}finally{chatSending=false;syncComposer();}};
  el('prompt').addEventListener('input',()=>{skill=null;});
  function sampleDocument(){dialog('Upload notes','<h3>Give your agent something to read.</h3><p>Use your own PDF, PPTX, XLSX, CSV, Markdown or text file, or try a clearly labeled sample meeting note.</p><div class="studio-dialog-actions"><button class="studio-secondary" id="studio-own-document">Upload my file</button><button class="studio-primary" id="studio-sample-document">Use sample notes</button></div>');el('own-document').onclick=()=>{el('dialog').close();el('upload').click();};el('sample-document').onclick=async()=>{try{await api('upload',{name:'sample-meeting-notes.md',content:'# Sample meeting notes — fictional demo data\n\nWe agreed to keep the agent demo to 10 minutes.\nDylan will check the weather-demo endpoint by Thursday.\nMorgan will draft a short invitation; no deadline was agreed.\nWe still need someone to confirm the venue.\nDo not send invitations until the venue is confirmed.\n'});el('dialog').close();await refresh();}catch(e){alert(e.message);}};}
  el('attach').onclick=()=>el('upload').click();
  el('upload').onchange=()=>{const files=[...el('upload').files];el('upload').value='';uploadDocuments(files);};
  el('refresh-files').onclick=refresh;
  el('memory').onclick=()=>{dialog('PERSISTENT MEMORY',`<h3>What ${escape(data.profile.name)} remembers.</h3><p>This is the actual MEMORY.md in your agent’s workspace. Ask your agent to remember, correct or forget a preference.</p><pre>${escape(data.memory||'No saved preferences yet.')}</pre><p>Try refreshing this page, then ask “What do you remember about me?”</p><button class="studio-primary" id="studio-recall">Ask my agent</button>`);el('recall').onclick=()=>{el('dialog').close();el('prompt').value='What do you remember about my preferences? Read MEMORY.md and apply my preferred response style.';skill='memory';el('prompt').focus();};};
  el('schedule').onclick=()=>{dialog('PERSISTENT FOLLOW-UP',`<h3>Give it something to come back to.</h3><p>The app keeps this task across refreshes and app restarts. It runs through OpenClaw when due; the result appears in this workspace. The server must stay on.</p><form id="studio-schedule-form"><label for="studio-followup">Task</label><textarea id="studio-followup" rows="3" required>Read my saved preferences and suggest one useful next task for me to try.</textarea><label for="studio-delay">Run in</label><select id="studio-delay"><option value="60">1 minute · demo</option><option value="300">5 minutes</option><option value="3600">1 hour</option></select><div class="studio-dialog-actions"><button class="studio-primary">Schedule follow-up</button></div></form>`);el('schedule-form').onsubmit=async e=>{e.preventDefault();try{const job=await api('jobs',{kind:'reminder',prompt:el('followup').value,delay:Number(el('delay').value)});selectedJob=job.id;el('dialog').close();await refresh();}catch(error){alert(error.message);}};};
  function crewAssignments(){
    return `<fieldset class="studio-crew-assignments"><legend>Choose your crew</legend><div class="studio-crew-toggles">${roles.slice(0,4).map((r,i)=>`<label><input type="checkbox" name="crewRole" value="${i}" checked ${i===0?'disabled':''}><span>${avatarBadge(window.BacCampus?.inspect().crewAvatars?.[i]||{})}<strong>${escape(defaultNames[i])}${i===0?'<em class="crew-required">Required</em>':''}</strong><small>${escape(r[1])}</small></span></label>`).join('')}</div><small id="studio-crew-selection-note">4 selected</small></fieldset>`;
  }
  function crewGroups(crew){
    const enabled=crew?.payload.enabledRoles||[0,1,2,3];
    const groups=crew?.payload.workflow==='showcase'||!crew?[[0],[1,2],[3]]:crew.payload.brief?.schema===2?[[0],[1,2],[3],[4],[5]]:roles.map((_,i)=>[i]);
    return groups.map(g=>g.filter(i=>enabled.includes(i))).filter(g=>g.length);
  }
  /* STUDIO_JSON */
  /* STUDIO_EVENTS */
  root.addEventListener('bac:world-skill',async e=>{const id=e.detail;if(id==='crew')crewForm();else if(id==='security')securityLab();else if(id==='runtime')setup();else{el('missions').querySelector('[data-studio-mission="'+id+'"]')?.click();}});
  /* STUDIO_WORLD */
  /* STUDIO_TELEMETRY */
  /* STUDIO_POLICIES */
  /* STUDIO_SURFACES */
  /* STUDIO_CHAT */
  /* STUDIO_ROOMS */
  /* STUDIO_IDENTITY */
  function showBoard(value){setRoom('mission');if(value)openSurface('control');else closeSurface();}
  el('lanes').onclick=e=>{const b=e.target.closest('[data-role-output]');if(!b)return;const role=Number(b.dataset.roleOutput);if(hasCrewDeliverable(crewMission(),role))openSurface('deliverables',role);};
  root.addEventListener('bac:live-select',e=>{
    if(room!=='mission'||!Number.isInteger(e.detail)||!roles[e.detail])return;
    selectedCrewRole=e.detail;root.dataset.crewDetails='true';
    renderCrewPassport();
  });
  async function openFile(path,jobId=''){
    const target=agentId,revision=dialogRevision;
    try{
      const file=await api('file?path='+encodeURIComponent(path)+(jobId?'&job='+encodeURIComponent(jobId):''));
      if(target!==agentId||revision!==dialogRevision)return;
      if(file.encoding==='base64'){downloadBytes(Uint8Array.from(atob(file.content),c=>c.charCodeAt(0)),file.mime,path.split('/').pop());return;}
      const html=/\.html$/i.test(path),eventPage=path.endsWith('-event-page.html');
      dialog(html?(eventPage?'EVENT PAGE':'WEBPAGE PREVIEW'):'WORKSPACE FILE',
        (html?'<div class="studio-page-toolbar"><div role="group" aria-label="Preview width"><button type="button" data-preview-width="desktop" aria-pressed="true">Desktop</button><button type="button" data-preview-width="mobile" aria-pressed="false">Mobile</button></div><button class="studio-primary" id="studio-download">Download HTML</button></div><div class="studio-page-canvas"><span class="studio-preview-loading" role="status">Loading preview…</span><iframe id="studio-app-frame" title="Generated page preview" sandbox="allow-scripts"></iframe></div>':
        '<h3>'+escape(path.split('/').pop())+'</h3><pre>'+escape(file.content)+'</pre><div class="studio-dialog-actions"><button class="studio-primary" id="studio-download">Download file</button></div>'));
      const protection='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data: blob:; font-src data:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'">';
      if(html){
        const frame=el('app-frame');
        frame.onload=()=>requestAnimationFrame(()=>requestAnimationFrame(()=>{if(!frame.isConnected)return;frame.dataset.ready='true';frame.previousElementSibling.hidden=true;}));
        frame.srcdoc=protection+file.content;
        el('dialog-body').querySelectorAll('[data-preview-width]').forEach(button=>button.onclick=()=>{
          el('dialog-body').querySelector('.studio-page-canvas').dataset.width=button.dataset.previewWidth;
          el('dialog-body').querySelectorAll('[data-preview-width]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
        });
      }
      el('download').onclick=()=>{const blob=new Blob([(html?protection:'')+file.content],{type:html?'text/html':'text/plain'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=path.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    }catch(error){alert(error.message);}
  }
  root.addEventListener('click',async e=>{const file=e.target.closest('[data-studio-file]');if(file){openFile(file.dataset.studioFile);return;}const history=e.target.closest('[data-studio-job]');if(history){selectedJob=history.dataset.studioJob;render();return;}const choice=e.target.closest('[data-decision]');if(choice){try{await api('decision',{id:current().id,action:choice.dataset.decision});await refresh();}catch(error){alert(error.message);}}});
  el('read-aloud').onclick=()=>{if(!('speechSynthesis' in window)){alert('This browser does not support speech playback.');return;}window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance((current()?.result.answer||'').slice(0,4000));utterance.lang='en-US';window.speechSynthesis.speak(utterance);el('read-aloud').textContent='Browser voice · playing';utterance.onend=()=>el('read-aloud').textContent='▷ Hear the answer';};
  /* STUDIO_SAFETY */
  /* STUDIO_COMPARE */
  /* STUDIO_SETTINGS */
  el('home').onclick=async()=>{
    closeSurface();el('dialog').close();await leaveWorld();
    board=false;layout.hidden=false;window.BacCampus?.overview();
    window.scrollTo({top:0,left:0,behavior:'smooth'});
  };
  async function boot(){try{const session=await api('session');csrf=session.csrf;settingsButton.hidden=!session.canConfigure;runtime=session.runtime;data=session;agentId=session.agentId;connected=true;runtimeBadge();render();let saved;try{saved=sessionStorage.getItem('bac-selected-agent');}catch{}if(saved&&saved!==agentId&&session.agents.some(a=>a.key===saved))await switchAgent(saved);else rememberSelection();crewStartupReady=true;warmCrewOnOpen();delete root.dataset.boot;root.setAttribute('aria-busy','false');}catch(error){connected=false;runtimeBadge();alert(error.message);el('create').disabled=true;root.dataset.boot='error';root.setAttribute('aria-busy','false');root.querySelector('.studio-boot-status span').textContent='Could not open the studio. Please try again.';root.querySelector('.studio-boot-status button').hidden=false;}}
  boot();setInterval(()=>{if(!document.hidden&&!busy)refresh();},1500);setInterval(async()=>{if(connected&&!document.hidden){try{const nextRuntime=await api('runtime');if(runtime.instance&&nextRuntime.instance!==runtime.instance){demoPreparationId=null;if(!nextRuntime.model)alert('Server restarted. Your agents and results are saved; reconnect the model to continue.');}runtime=nextRuntime;runtimeBadge();}catch{}}},10000);
  window.BacStudio={refresh,inspect:()=>({profile:data.profile,agentId,agents:data.agents,jobs:data.jobs,runtime,board,room}),showBoard,setRoom};
})();
