(() => {
  const root = document.getElementById('agent-campus');
  const el = name => document.getElementById('studio-' + name);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const titles = {weather:'Weather lookout',web:'Web explorer',documents:'Document detective',builder:'Mini app maker',writer:'Campaign studio',memory:'Remember me'};
  const personas = {guide:'Warm, patient and clear.',maker:'Inventive, practical and curious.',analyst:'Precise, evidence-led and careful.'};
  const roles = [['Milo','Event lead','Turns an idea into a shared brief.'],['Nova','Demo producer','Designs participant actions and visible outcomes.'],['Atlas','Operations planner','Sizes equipment and staffing; surfaces gaps.'],['Momo','Campaign writer','Uses the approved plan to draft invitations.'],['Pico','Evidence reviewer','Checks the work of the other specialists.']];
  const defaultNames=roles.map(r=>r[0]);
  const personaLabels={guide:'Guide',maker:'Maker',analyst:'Analyst'};
  const missions = [
    {id:'builder',icon:'⌘',title:'Make something playable',sub:'An idea → a tiny working app',tag:'CREATE',color:'#b4dc83',prompt:'Build a polished reaction-time game as a single self-contained HTML file. Use a dark NVIDIA-inspired style, green action buttons, keyboard and touch controls, and a personal best score. Explain how to play. Save it in artifacts/.'},
    {id:'weather',icon:'☀',title:'Plan around the weather',sub:'Live conditions → useful advice',tag:'EXPLORE',color:'#e8cd80',prompt:'Check the current weather in Zurich using your weather skill. Tell me when the observation was made and whether I should bring a jacket for a walk before BaC. Cite the actual source.'},
    {id:'documents',icon:'▤',title:'Ask your documents',sub:'Your file → an answer with evidence',tag:'UNDERSTAND',color:'#99c8e3',prompt:'Read the documents in inbox/. Summarize the key points, identify three useful follow-up actions, and cite the exact filename and supporting text for each. Separate facts from assumptions.'},
    {id:'web',icon:'⌕',title:'Explore the web',sub:'A website → a sourced briefing',tag:'RESEARCH',color:'#adbbe8',prompt:'Read https://www.zuerich.com/en/visit and suggest three ideas for an attendee with two free hours in Zurich. Cite the pages you actually read and mark opening hours or prices you could not verify.'},
    {id:'writer',icon:'✎',title:'Launch your next idea',sub:'An event brief → a campaign',tag:'COMMUNICATE',color:'#e6af8e',prompt:'Draft an English invitation and three short social posts for a Build a Claw event in Zurich. 120 attendees, 180 minutes, hands-on demos in groups of five for 15 minutes. Leave date, venue and registration URL as placeholders. Save the drafts in artifacts/.'},
    {id:'memory',icon:'▧',title:'Teach it your style',sub:'A preference → a lasting memory',tag:'PERSONALIZE',color:'#c3ace9',prompt:'Please remember that I prefer concise English answers with three practical bullets, and I like vegetarian food. Save this preference to MEMORY.md. Tell me exactly what you saved.'},
  ];
  let csrf = '', data = {profile:null,jobs:[],files:[],memory:'',phone:false}, runtime = {}, persona = 'guide', skill = null, selectedJob = null, resultKey = '', board = false, connected = false, busy = false;
  let agentId='',changingAgent=false,removingAgent=false,pendingWrites=0,refreshVersion=0,collectionKey='';
  let room='workshop',roomsReady=false,draftMode='new',draftOwner='',draftAvatar={body:'classic',color:'green',accessory:'antenna'};
  let policySnapshot=null,policyVersion=0,policyLoading=false,policySaving=false;
  let selectedCrewRole=0;
  root.classList.add('studio-enabled');
  root.querySelector('.campus-heading h2').textContent='Your ideas. An agent that gets them done.';
  root.querySelector('.campus-heading .quiet').textContent='Make it yours. Give it useful skills. Watch one agent become a team.';
  root.querySelector('.campus-eyebrow').innerHTML='<span></span> BUILD A CLAW / AGENT STUDIO';
  const layout = root.querySelector('.campus-layout');
  root.querySelector('.campus-heading').after(el('journey'));
  el('journey').after(el('rooms'));el('rooms').after(el('room-heading'));el('room-heading').after(root.querySelector('.studio-viewbar'));
  root.querySelector('.studio-viewbar').after(el('safety-bar'));
  el('safety-bar').after(el('collection'));
  layout.append(el('workshop'),el('passport'),el('crew-passport'));layout.after(el('connections'));
  layout.after(el('board'));
  el('board').after(el('experiences'));
  el('experiences').after(el('workspace'));
  el('workspace').after(root.querySelector('.studio-crew-invite'));el('collection').after(layout);layout.after(el('safety-bar'));el('safety-bar').after(el('connections'));root.querySelector('.campus-heading').append(el('runtime'));el('journey').hidden=true;layout.after(el('collection'));
  el('collection').after(el('policies'));
  el('skill-picker').innerHTML=Object.entries(titles).map(([key,title])=>`<label><input type="checkbox" value="${key}" checked>${title}</label>`).join('');
  el('missions').innerHTML=missions.map(m=>`<button class="studio-mission" data-studio-mission="${m.id}" aria-pressed="false" style="--mission-color:${m.color}"><span>${m.icon}</span><em>${m.tag}</em><strong>${m.title}</strong><small>${m.sub}</small></button>`).join('');
  let alertTimer=null;
  function dismissAlert(){clearTimeout(alertTimer);alertTimer=null;el('alert').hidden=true;}
  function alert(message) {
    clearTimeout(alertTimer);
    el('alert').querySelector('span').textContent=message;el('alert').hidden=false;
    alertTimer=setTimeout(dismissAlert,5000);
  }
  el('alert').querySelector('button').onclick=dismissAlert;
  async function api(path, payload, target=agentId) {
    if(payload!==undefined&&changingAgent)throw new Error('Wait for your agent’s workspace to open.');
    const headers=target?{'X-BaC-Agent':target}:{};
    const options = payload===undefined ? {headers} : {method:'POST',headers:{...headers,'Content-Type':'application/json','X-BaC-CSRF':csrf},body:JSON.stringify(payload)};
    if(payload!==undefined)pendingWrites++;
    try {
    let response;
    try {response=await fetch('/api/'+path,options);} catch {throw new Error('Open this demo through ./start.sh or ./bac app start. The agent API needs the local app server.');}
    let result;
    try {result=await response.json();} catch {throw new Error('The app server did not return a valid response. Refresh after updating the app.');}
    if(!response.ok){const error=new Error(result.error||'The request could not be completed.');error.status=response.status;throw error;}
    return result;
    }finally{if(payload!==undefined)pendingWrites--;}
  }
  function rememberSelection(){try{sessionStorage.setItem('bac-selected-agent',agentId);}catch{}}
  function openAgentState(state){
    agentId=state.agentId;data=state;rememberSelection();selectedJob=null;resultKey='';skill=null;
    el('prompt').value='';el('upload').value='';dismissAlert();
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
    }catch(error){alert(error.message);}finally{changingAgent=false;busy=false;}
  }
  function renderCollection(){
    el('collection').hidden=!data.profile;
    const key=JSON.stringify([agentId,data.agents]);
    if(key===collectionKey)return;collectionKey=key;
    el('agent-list').innerHTML=(data.agents||[]).map(a=>`<button class="studio-agent-card" data-agent-key="${a.key}" data-personality="${a.persona}" aria-pressed="${a.key===agentId}">${avatarBadge(a.avatar)}<span><strong>${escape(a.name)}</strong><small>${personaLabels[a.persona]} · ${a.skills.length} skills${a.deleting?' · Deletion pending':a.pending?' · '+a.pending+' pending':''}</small></span><em>${a.key===agentId?'SELECTED':'OPEN ↗'}</em></button>`).join('');
    el('add-agent').disabled=(data.agents||[]).length>=data.agentLimit;
    el('collection-note').textContent=`${data.agents?.length||0} / ${data.agentLimit||12} agents · Each keeps its own conversation, memory and files. Assign them to roles when launching a crew.`;
  }
  el('agent-list').onclick=e=>{const b=e.target.closest('[data-agent-key]');if(b)switchAgent(b.dataset.agentKey);};
  function dialog(kicker, html) {el('dialog-kicker').textContent=kicker;el('dialog-body').innerHTML=html;if(!el('dialog').open)el('dialog').showModal();}
  el('dialog-close').onclick=()=>el('dialog').close();
  el('dialog').addEventListener('click',e=>{if(e.target===el('dialog')&&!removingAgent){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  function setup() {
    dialog('ONE SPARK / ONE SHARED MODEL',`<h3>Your agent’s engine room.</h3><p>The app, OpenClaw and the model are separate. Updating the experience keeps your model weights, agent memories and files.</p><div class="studio-runtime-grid"><div><b>Shared local model</b><small>${runtime.model?'Connected · bac-local':'Waiting for the host to start vLLM'}<br>One model for every role · one active task at a time</small></div><div><b>OpenClaw ${escape(runtime.version||'2026.9.4')}</b><small>${runtime.gateway?'Gateway connected':'Gateway not connected'}<br>Native identities, skills, tools and conversation state</small></div><div><b>OpenShell</b><small>${escape(runtime.openshell||'Not configured')}<br>Separate sandbox backend. A UI approval is not sandbox enforcement.</small></div><div><b>Telegram</b><small>${runtime.telegram?'Host bot configured · pair your own chat':'Optional · host bot setup required'}<br>Web and phone share the same agent conversation.</small></div></div><pre>./bac llm start qwen\n./bac runtime setup\n./bac runtime start\n./bac app start\n\n# Later UI updates:\n./bac update\n\n# Optional:\n./bac telegram configure\n./bac openshell enable</pre><p>Qwen and Gemma are host-wide alternatives. Set up the model once with <code>./bac llm setup qwen</code> (or <code>gemma</code>) before starting it. These commands run on your Spark.</p>`);
  }
  el('runtime').onclick=()=>{setRoom('workshop');el('connections').scrollIntoView({behavior:'smooth',block:'center'});};
  function runtimeBadge(){el('runtime').textContent=runtime.testFixture?'TEST FIXTURE · no real model':runtime.ready?'● OpenClaw connected · shared Spark model':'○ Connect your Spark runtime';el('runtime').dataset.ready=!!runtime.ready;root.querySelector('.campus-sim').textContent=runtime.testFixture?'TEST FIXTURE · NO REAL MODEL':runtime.ready?'OPENCLAW · LIVE TASK EVENTS':'CAMPUS PREVIEW · RUNTIME OFFLINE';if(roomsReady)renderRooms();}
  function current(){return data.jobs.find(j=>j.id===selectedJob)||data.jobs[0];}
  function crewMission(){return current()?.kind==='crew'?current():data.jobs.find(j=>j.kind==='crew');}
  function render() {
    const profile=data.profile, job=current();
    if(profile)roles[0][0]=profile.name;
    renderCollection();
    el('onboarding').hidden=false;el('companion').hidden=!profile;el('lounge-empty').hidden=!!profile;
    if(profile){el('agent-name').textContent=profile.name;el('personality').textContent=personas[profile.persona];el('equipped').innerHTML=profile.skills.map(s=>'<span>'+escape(titles[s])+'</span>').join('');}
    const active=data.jobs.find(j=>['running','stopping'].includes(j.status))||data.jobs.find(j=>['queued','waiting'].includes(j.status));
    el('task-state').textContent=active?({'running':'WORKING ON YOUR MISSION','stopping':'STOPPING AFTER THE ACTIVE CALL','queued':active.due>Date.now()/1000?'FOLLOW-UP SCHEDULED':'IN THE SHARED MODEL QUEUE','waiting':'YOUR DECISION IS NEEDED'}[active.status]):'READY FOR A MISSION';
    el('task-summary').textContent=active?(active.kind==='crew'?'Your specialists are building the event plan.':active.payload.prompt.slice(0,135)):'Choose a mission below, or ask for something of your own.';
    const assignment=data.assignments?.[0];el('assigned-crew').hidden=!assignment;
    if(assignment){el('assigned-crew').textContent='Open '+assignment.name+'’s crew ↗';if(!active){el('task-state').textContent='ASSIGNED TO A CREW';el('task-summary').textContent=assignment.role+' for '+assignment.name+' · '+assignment.status+'. Follow the handoffs in the lead’s workspace.';}}
    el('delete-agent').textContent=data.deleting?'Retry deletion':'Delete agent';
    el('agent-policy').textContent='◇ OpenShell '+(profile?.protection==='openshell'?'on':'off')+' · View policies ↗';
    el('edit-agent').disabled=!!data.deleting;el('send').disabled=!!data.deleting;
    if(data.deleting){el('task-state').textContent='DELETION NEEDS ATTENTION';el('task-summary').textContent='This agent is paused. Ask the host to check cleanup, then retry deletion.';}

    el('files').innerHTML=data.files.length?data.files.map(f=>`<button data-studio-file="${escape(f.path)}">${f.path.endsWith('.html')?'⌘':'▤'} ${escape(f.path.split('/').pop())}<span>${Math.ceil(f.size/1024)} KB ↗</span></button>`).join(''):'<p class="studio-muted">Uploaded documents and deliverables live here.</p>';
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
          const box=document.createElement('div');box.className='studio-waiting';box.innerHTML='The plan needs '+job.payload.capacity.spark+' Sparks and '+job.payload.capacity.workstation+' workstations. Your available equipment does not cover it.<br><button class="studio-primary" data-decision="approve-equipment">Plan additional equipment</button><button class="studio-secondary" data-decision="cancel">Cancel and revise</button>';el('result').append(box);
        }
        const answer=document.createElement('div');answer.textContent=job.result.answer||job.result.error||Object.values(job.payload.outputs||{}).slice(-1)[0]||(job.status==='queued'?'Your mission is saved in the queue.':job.status==='cancelled'?'This mission was cancelled.':'The agent is working. Actual handoffs and saved files appear in the evidence panel.');el('result').append(answer);
        const apps=(job.result.files||[]).filter(f=>f.endsWith('.html'));
        if(apps.length){const preview=document.createElement('div');preview.className='studio-app-preview';preview.innerHTML='<strong>Your mini app is ready to try.</strong>'+apps.map(path=>`<button class="studio-primary" data-studio-file="${escape(path)}">Play your app ↗</button>`).join('');el('result').prepend(preview);}
        if(job.status==='queued'){const cancel=document.createElement('button');cancel.className='studio-secondary';cancel.dataset.decision='cancel';cancel.textContent='Cancel queued task';el('result').append(cancel);}
      }
    }
    if(!job){resultKey='';el('result-title').textContent='Your next mission starts here.';el('result').textContent='Choose a skill or give your crew a new brief. Your agent, memory and saved files are preserved.';el('events').innerHTML='<li><b>No mission on this board.</b><small>Real handoffs and results will appear here.</small></li>';el('read-aloud').hidden=true;}
    renderCrew();renderSafety();renderRooms();
  }
  el('assigned-crew').onclick=async()=>{const a=data.assignments?.[0];if(!a)return;await switchAgent(a.lead);if(agentId===a.lead){selectedJob=a.job;render();showBoard(true);}};
  function renderCrew(){
    window.BacSound?.observeJobs(agentId,data.jobs);
    const crew=crewMission(), stage=crew?.payload.stage??-1;
    roles.forEach((r,i)=>r[0]=crew?.payload.roster?.[i]?.name||(i===0&&room!=='mission'?data.profile?.name:null)||defaultNames[i]);
    el('lanes').innerHTML=roles.map(([name,role,description],i)=>{const done=!!crew?.payload.outputs?.[i],working=['running','stopping'].includes(crew?.status)&&stage===i,waiting=crew?.status==='waiting'&&i===2;return `<article class="studio-lane" data-state="${waiting?'waiting':done?'done':working?'running':'ready'}"><span>0${i+1} / ${waiting?'NEEDS YOU':done?'DELIVERED':working?(crew?.status==='stopping'?'STOPPING':'WORKING'):'READY'}</span><h4>${escape(name)}</h4><strong>${role}</strong><p>${description}</p>${done?'<button data-role-output="'+i+'">Open deliverable ↗</button>':''}</article>`;}).join('');
    const active=room==='mission'?(crew&&['running','stopping','waiting'].includes(crew.status)?crew:null):data.jobs.find(j=>['running','stopping'].includes(j.status))||data.jobs.find(j=>j.status==='waiting');
    const s=window.BacDemo.snapshot();
    const a=roles.map(([name,role,description],i)=>({...s.agents[i],name,role,persona:description,skills:i===0?['Shared brief']:i===1?['Demo design']:i===2?['Capacity planning']:i===3?['Campaign writing']:['Evidence review'],lane:0,status:'Ready',task:description,permission:'Scoped workspace · shared local model'}));
    crew?.payload.roster?.forEach((m,i)=>{a[i].persona=personas[m.persona];a[i].skills=m.skills.map(x=>titles[x]);a[i].avatar=m.avatar;});
    let phase=-1,selected=0,flow=['Your campus is ready','Choose a mission or launch a crew.','Start'];
    if(active?.kind==='crew'){
      selected=active.status==='waiting'?2:Math.min(4,active.payload.stage);phase=active.status==='waiting'?2:selected;
      a[selected].lane=active.status==='waiting'?2:1;a[selected].status=active.status==='waiting'?'Decision required':active.status==='stopping'?'Stopping after active call':'Running in OpenClaw';a[selected].task=active.events.at(-1)?.detail||roles[selected][2];
      flow=[roles[selected][0]+' · '+a[selected].status,a[selected].task,'Open mission'];
    }else if(active){
      phase=0;a[0].name=data.profile?.name||'My agent';a[0].role='Your personal agent';a[0].persona=personas[data.profile?.persona]||'';a[0].skills=(data.profile?.skills||[]).map(x=>titles[x]);a[0].lane=1;a[0].status=active.status==='stopping'?'Stopping after active call':'Running in OpenClaw';a[0].task=active.payload.prompt;flow=[a[0].name+' is working',active.payload.prompt,'Open mission'];
    }else if(data.profile&&room!=='mission'){a[0].name=data.profile.name;a[0].role='Your personal agent';a[0].persona=personas[data.profile.persona];a[0].skills=data.profile.skills.map(x=>titles[x]);}
    if(data.profile&&!crew&&room!=='mission')a[0].avatar=data.profile.avatar;
    const b=crew?.payload.brief;
    window.BacCampus?.setLive({...s,live:true,phase,jobId:active?.id,missionSkill:active?.payload.skill,revision:data.jobs.length,agents:a,selected:room==='mission'?selectedCrewRole:selected,flow,gap:active?.status==='waiting',brief:b?{...b,location:b.city}:null,calc:crew?.payload.capacity||null,policy:null});
    document.getElementById('campus-motion-status').textContent=active?flow[0]:'Explore your crew · movement is ambient until a task runs';
    renderCrewPassport();
  }
  /* STUDIO_CREW */
  async function refresh(){if(changingAgent||removingAgent||!connected)return;const version=++refreshVersion,target=agentId;busy=true;try{const state=await api('state',undefined,target);if(version===refreshVersion&&target===agentId&&!changingAgent){data=state;render();}}catch(error){if(version===refreshVersion){if(error.status===404){try{const state=await api('state',undefined,'');if(version===refreshVersion&&!changingAgent){el('dialog').close();openAgentState(state);alert('This agent was deleted in another tab. Your collection is up to date.');}}catch(recovery){alert(recovery.message);}}else if(!document.hidden)alert(error.message);}}finally{if(version===refreshVersion)busy=false;}}
  el('missions').onclick=e=>{const button=e.target.closest('[data-studio-mission]');if(!button)return;const mission=missions.find(m=>m.id===button.dataset.studioMission);if(!data.profile){alert('Give your agent a name and click “Bring my agent to life” first.');agentForm(true);el('name').focus();return;}if(!data.profile.skills.includes(mission.id)){alert('This starter agent did not equip '+titles[mission.id]+'. Its current skills are shown in the passport.');return;}setRoom('lounge');skill=mission.id;el('prompt').value=mission.id==='web'&&runtime.search?'Search the web for three useful places to visit in Zurich before BaC. Compare options and cite the sources you actually used.':mission.prompt;el('missions').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',b===button));if(mission.id==='documents'&&!data.files.some(f=>f.kind==='inbox')){sampleDocument();}el('prompt').focus();el('passport').scrollIntoView({behavior:'smooth',block:'center'});};
  el('chat').onsubmit=async e=>{e.preventDefault();el('send').disabled=true;try{const result=await api('jobs',{kind:'chat',prompt:el('prompt').value,skill});selectedJob=result.id;await refresh();el('workspace').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){alert(error.message);}finally{el('send').disabled=false;}};
  el('prompt').addEventListener('input',()=>{skill=null;});
  function sampleDocument(){dialog('DOCUMENT DETECTIVE','<h3>Give your agent something to read.</h3><p>Use your own text, Markdown or CSV file, or try a clearly labeled sample event brief.</p><div class="studio-dialog-actions"><button class="studio-secondary" id="studio-own-document">Upload my file</button><button class="studio-primary" id="studio-sample-document">Use sample brief</button></div>');el('own-document').onclick=()=>{el('dialog').close();el('upload').click();};el('sample-document').onclick=async()=>{try{await api('upload',{name:'sample-bac-brief.md',content:'# Sample event brief — fictional workshop data\n\nCity: Zurich. Region: Europe / EMEA. Event language: English.\nAttendance: 120. Duration: 180 minutes.\nEach participant joins one interest-based session, with 5 people per group for 15 minutes.\nInterests: agent onboarding 40%, collaboration 35%, creative tools 25%.\nWelcome and breaks: 30 minutes. Turnaround: 5 minutes.\nAvailable devices: 2 DGX Sparks, 1 workstation.\nStaffing assumption: 1 presenter per station, 1 assistant per 30 people, and 1 lead.\nVenue, date and registration URL are unconfirmed.\n'});el('dialog').close();await refresh();}catch(e){alert(e.message);}};}
  el('attach').onclick=()=>el('upload').click();
  el('upload').onchange=async()=>{const target=agentId,file=el('upload').files[0];if(!file)return;if(file.size>100000){alert('Choose a text, Markdown or CSV file smaller than 100 KB.');return;}try{const result=await api('upload',{name:file.name,content:await file.text()},target);await refresh();alert(result.path+' is ready for your agent.');}catch(error){alert(error.message);}finally{el('upload').value='';}};
  el('refresh-files').onclick=refresh;
  el('memory').onclick=()=>{dialog('PERSISTENT MEMORY',`<h3>What ${escape(data.profile.name)} remembers.</h3><p>This is the actual MEMORY.md in your agent’s workspace. Ask your agent to remember, correct or forget a preference.</p><pre>${escape(data.memory||'No saved preferences yet.')}</pre><p>Try refreshing this page, then ask “What do you remember about me?”</p><button class="studio-primary" id="studio-recall">Ask my agent ↗</button>`);el('recall').onclick=()=>{el('dialog').close();el('prompt').value='What do you remember about my preferences? Read MEMORY.md and apply my preferred response style.';skill='memory';el('prompt').focus();};};
  el('phone').onclick=async()=>{try{const pair=await api('pair',{});dialog('SAME AGENT / ANOTHER CHANNEL',`<h3>Your agent. Now on your phone.</h3><p>Open Telegram and tap Start. This link pairs ${escape(data.profile.name)} only and expires in five minutes. Switching agents on this page does not change your phone pairing. Pairing another agent moves this private chat to that agent. Messages use the same OpenClaw conversation as this page.</p><p><a href="${escape(pair.url)}" target="_blank" rel="noreferrer">Connect my Telegram chat ↗</a></p><p>Then ask: “What do you remember about me?” Your phone tasks will also appear in this workspace. Send /stop in Telegram to disconnect.</p>`);}catch(error){alert(error.message);}};
  el('schedule').onclick=()=>{dialog('PERSISTENT FOLLOW-UP',`<h3>Give it something to come back to.</h3><p>The app keeps this task across refreshes and app restarts. It runs through OpenClaw when due; the result appears in this workspace. The Spark host must stay on.</p><form id="studio-schedule-form"><label for="studio-followup">Task</label><textarea id="studio-followup" rows="3" required>Read my saved preferences and suggest one useful next task for me to try.</textarea><label for="studio-delay">Run in</label><select id="studio-delay"><option value="60">1 minute · demo</option><option value="300">5 minutes</option><option value="3600">1 hour</option></select><div class="studio-dialog-actions"><button class="studio-primary">Schedule follow-up ↗</button></div></form>`);el('schedule-form').onsubmit=async e=>{e.preventDefault();try{const job=await api('jobs',{kind:'reminder',prompt:el('followup').value,delay:Number(el('delay').value)});selectedJob=job.id;el('dialog').close();await refresh();}catch(error){alert(error.message);}};};
  function crewAssignments(){
    return `<fieldset class="studio-crew-assignments"><legend>Choose your crew</legend><p>Milo, Nova, Atlas, Momo and Pico are ready to run without OpenShell. You can also invite your personal agents with their own skills and policies.</p><label class="studio-crew-personal"><input type="checkbox" name="personalLead" ${!data.profile?'disabled':''}> Let ${escape(data.profile?.name||'my personal agent')} lead instead of Milo</label><div class="studio-form-grid">${roles.slice(1).map((r,index)=>`<label>${r[1]}<select name="member${index+1}" aria-label="${r[1]}"><option value="">${defaultNames[index+1]} · ready-made specialist</option>${(data.agents||[]).filter(a=>a.key!==agentId).map(a=>`<option value="${a.key}">${escape(a.name)} · ${personaLabels[a.persona]}</option>`).join('')}</select></label>`).join('')}</div><small>Five roles share one brief. Completed outputs are handed to the next role and saved in the lead’s workspace.</small></fieldset>`;
  }
  function crewForm(){dialog('LAUNCH A CREW MISSION',`<h3>Where will your next BaC happen?</h3><p>Five distinct OpenClaw agents share the brief and hand over real outputs. They run in sequence on one local model; the reviewer checks the specialists’ work.</p><form id="studio-crew-form">${crewAssignments()}<div class="studio-form-grid"><div><label>City<input name="city" value="Zurich" maxlength="80" required></label></div><div><label>Region<input name="region" value="Europe / EMEA" maxlength="80" required></label></div><div><label>Event language<select name="language"><option>English</option><option>German</option><option>French</option><option>Korean</option><option>Japanese</option></select></label></div>${[['attendees','Attendees',120,1,3000],['duration','Event length · minutes',180,30,1440],['groupSize','People per group',5,1,30],['session','Demo · minutes',15,5,120],['common','Welcome & breaks · minutes',30,0,600],['turnover','Turnaround · minutes',5,0,30],['spark','Available DGX Sparks',4,0,300],['workstation','Available workstations',2,0,300]].map(([key,label,value,min,max])=>`<div><label>${label}<input type="number" name="${key}" value="${value}" min="${min}" max="${max}" required></label></div>`).join('')}<div class="wide"><label>Interest split · agent / multi-agent / creative (%)</label><div class="studio-form-grid"><input aria-label="Personal agent share" name="share0" type="number" value="40" min="0" max="100" required><input aria-label="Multi-agent share" name="share1" type="number" value="35" min="0" max="100" required><input aria-label="Creative share" name="share2" type="number" value="25" min="0" max="100" required></div></div></div><p>One session per attendee. Station sizing is a planning calculation, not a GPU throughput benchmark. Invitations remain drafts.</p><div class="studio-dialog-actions"><button class="studio-primary">Give the brief to my crew ↗</button></div></form>`);el('crew-form').addEventListener('change',e=>{if(!e.target.name.startsWith('member'))return;if(e.target.value)el('crew-form').elements.personalLead.checked=true;const selects=[...el('crew-form').querySelectorAll('[name^=member]')],selected=selects.map(x=>x.value).filter(Boolean);selects.forEach(select=>[...select.options].forEach(option=>option.disabled=!!option.value&&option.value!==select.value&&selected.includes(option.value)));});el('crew-form').onsubmit=async e=>{e.preventDefault();const form=e.target,brief={};const members={};for(const [key,value] of new FormData(form)){if(key==='personalLead')continue;if(key.startsWith('member')){if(value)members[key.slice(6)]=value;}else brief[key]=['city','region','language'].includes(key)?value:Number(value);}brief.shares=[brief.share0,brief.share1,brief.share2];try{const job=await api('jobs',{kind:'crew',brief,members,preset:!form.elements.personalLead.checked});selectedJob=job.id;el('dialog').close();await refresh();showBoard(false);}catch(error){alert(error.message);}};}
  el('plan').onclick=crewForm;
  root.addEventListener('bac:world-skill',async e=>{const id=e.detail;if(!data.profile&&!['runtime','security'].includes(id))await leaveWorld();if(id==='crew')crewForm();else if(id==='security')securityLab();else if(id==='runtime')setup();else if(id==='telegram'){if(!data.profile){alert('Create your agent first to connect a phone.');return;}el('phone').click();}else{await leaveWorld();el('missions').querySelector('[data-studio-mission="'+id+'"]')?.click();}});
  /* STUDIO_WORLD */
  /* STUDIO_POLICIES */
  /* STUDIO_ROOMS */
  function showBoard(value){board=value;setRoom('mission');}
  el('campus-tab').onclick=()=>showBoard(false);el('board-tab').onclick=()=>showBoard(true);
  el('lanes').onclick=e=>{const b=e.target.closest('[data-role-output]');if(!b)return;const crew=crewMission();dialog('REAL AGENT DELIVERABLE','<h3>'+roles[b.dataset.roleOutput][1]+'</h3><pre>'+escape(crew.payload.outputs[b.dataset.roleOutput])+'</pre>');};
  root.addEventListener('bac:live-select',e=>{
    if(room!=='mission'||!Number.isInteger(e.detail)||!roles[e.detail])return;
    const changed=selectedCrewRole!==e.detail;selectedCrewRole=e.detail;root.dataset.crewDetails='true';
    if(changed){el('crew-deliverable').open=false;el('crew-passport').firstElementChild.scrollTop=0;}
    renderCrewPassport();
  });
  async function openFile(path){const target=agentId;try{const file=await api('file?path='+encodeURIComponent(path));if(target!==agentId)return;const html=path.endsWith('.html');dialog(html?'PLAY YOUR MINI APP':'WORKSPACE FILE',`<h3>${escape(path.split('/').pop())}</h3>${html?'<p>Interactive preview · scripts run in an isolated frame with network access blocked.</p><iframe id="studio-app-frame" title="Generated mini app" sandbox="allow-scripts"></iframe>':'<pre>'+escape(file.content)+'</pre>'}<div class="studio-dialog-actions"><button class="studio-primary" id="studio-download">Download file ↓</button></div>`);const protection='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'">';if(html)el('app-frame').srcdoc=protection+file.content;el('download').onclick=()=>{const blob=new Blob([(html?protection:'')+file.content],{type:html?'text/html':'text/plain'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=path.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};}catch(error){alert(error.message);}}
  root.addEventListener('click',async e=>{const file=e.target.closest('[data-studio-file]');if(file){openFile(file.dataset.studioFile);return;}const history=e.target.closest('[data-studio-job]');if(history){selectedJob=history.dataset.studioJob;render();return;}const choice=e.target.closest('[data-decision]');if(choice){try{await api('decision',{id:current().id,action:choice.dataset.decision});await refresh();}catch(error){alert(error.message);}}});
  el('read-aloud').onclick=()=>{if(!('speechSynthesis' in window)){alert('This browser does not support speech playback.');return;}window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance((current()?.result.answer||'').slice(0,4000));utterance.lang='en-US';window.speechSynthesis.speak(utterance);el('read-aloud').textContent='Browser voice · playing';utterance.onend=()=>el('read-aloud').textContent='▷ Hear the answer';};
  /* STUDIO_SAFETY */
  async function boot(){try{const session=await api('session');csrf=session.csrf;runtime=session.runtime;data=session;agentId=session.agentId;connected=true;runtimeBadge();render();let saved;try{saved=sessionStorage.getItem('bac-selected-agent');}catch{}if(saved&&saved!==agentId&&session.agents.some(a=>a.key===saved))await switchAgent(saved);else rememberSelection();}catch(error){runtimeBadge();alert(error.message);el('create').disabled=true;}}
  boot();setInterval(()=>{if(!document.hidden&&!busy)refresh();},1500);setInterval(async()=>{if(connected&&!document.hidden){try{runtime=await api('runtime');runtimeBadge();}catch{}}},10000);
  window.BacStudio={refresh,inspect:()=>({profile:data.profile,agentId,agents:data.agents,jobs:data.jobs,runtime,board,room}),showBoard,setRoom};
})();
