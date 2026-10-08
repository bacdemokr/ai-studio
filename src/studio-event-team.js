// Fixed Event Brief team, restored from archive/bac-planning.
function crewMission(){return selectedScenario==='event-brief'?(data.jobs.find(j=>j.id===selectedJob&&j.kind==='crew')||data.jobs.find(j=>j.kind==='crew')):null;}
function crewAssignments(){
    return `<fieldset class="studio-crew-assignments"><legend>Choose your crew</legend><div class="studio-crew-toggles">${roles.slice(0,4).map((r,i)=>`<label><input type="checkbox" name="crewRole" value="${i}" checked ${i===0?'disabled':''}><span>${avatarBadge(window.BacCampus?.inspect().crewAvatars?.[i]||{})}<strong>${escape(defaultNames[i])}${i===0?'<em class="crew-required">Required</em>':''}</strong><small>${escape(r[1])}</small></span></label>`).join('')}</div><small id="studio-crew-selection-note">4 selected</small></fieldset>`;
  }
function crewGroups(crew){
    const enabled=crew?.payload.enabledRoles||[0,1,2,3];
    const groups=crew?.payload.workflow==='showcase'||!crew?[[0],[1,2],[3]]:crew.payload.brief?.schema===2?[[0],[1,2],[3],[4],[5]]:roles.map((_,i)=>[i]);
    return groups.map(g=>g.filter(i=>enabled.includes(i))).filter(g=>g.length);
  }
function crewBriefMessage(job){
 const b=job.payload.brief||{},lines=['Plan a Build-a-Claw event.'];
 const fields=[['City',b.city],['Venue',b.venue],['Event start date',b.startDate],['Event end date',b.endDate],['Total attendees',b.attendees],['Event days',b.days],['Minutes per day',b.duration],['Daily start',b.startTime],['People per group',b.groupSize],['Preferred demo length',b.session==null?null:b.session+' minutes'],['Maximum booths',b.boothLimit]];
 for(const [label,value] of fields)if(value!=null&&value!=='')lines.push(label+': '+value);
 if(b.themeCount)lines.push('Themes to research: '+b.themeCount+' · one booth per theme');
 else if(b.topics?.length)lines.push('Topics: '+b.topics.map(id=>eventCatalog?.topics?.[id]?.title||id).join(', '));
 if(b.harnesses?.length)lines.push('Harnesses: '+b.harnesses.map(id=>eventCatalog?.harnesses?.[id]||id).join(', '));
 lines.push('Crew: '+(job.payload.enabledRoles||roles.map((_,i)=>i)).map(i=>defaultNames[i]).join(', '));
 if(job.payload.prompt)lines.push(job.payload.prompt);
 return lines.join('\n');
}
// Shared by Lounge, crew chat, event replies and roundtable reactions.
function crewHandoffMessages(job,role){
 const p=job.payload,roster=p.roster||[],name=i=>roster[i]?.name||defaultNames[i];
 return Object.entries(p.handoffs||{}).filter(([stage,h])=>{
  const target=Number(stage),sender=h.senderRole===undefined?((p.enabledRoles||roles.map((_,i)=>i)).includes(0)?0:null):h.senderRole;
  return target!==0&&h.started&&(role===target||(role===0&&sender===0));
 }).sort((a,b)=>a[1].started-b[1].started).map(([stage,h])=>{
  const target=Number(stage),sender=h.senderRole===undefined?((p.enabledRoles||roles.map((_,i)=>i)).includes(0)?0:null):h.senderRole;
  const recipient=h.recipientName||name(target),from='App workflow';
  const task=h.task||p.assignments?.find(a=>a.name===recipient)?.task||'Received the event brief and available deliverables.';
  const summary=p.assignments?.find(a=>a.name===recipient)?.task||task.split(/\.\s/)[0];
  const received=h.receivedFrom||[],inputs=['Event brief',...received.map(i=>name(Number(i))+'’s deliverable')];
  const details='<details><summary>View full task &amp; received inputs</summary><div class="chat-prose">'+messageMarkup(task)+'</div>'+(h.sharedState?'<pre>'+escape(JSON.stringify(h.sharedState,null,2))+'</pre>':'')+received.map(i=>'<details><summary>'+escape(name(Number(i)))+'’s deliverable</summary><div class="chat-prose">'+messageMarkup(p.outputs?.[i]||'Saved output unavailable.')+'</div></details>').join('')+'</details>';
  return '<div class="chat-message chat-handoff" data-assignment-to="'+target+'"><small>'+escape(from)+' → '+escape(recipient)+' · '+(role===target?'Task received':'Task assigned')+' · '+new Date(h.started*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+'</small><div class="chat-prose">'+messageMarkup(summary)+'</div><p class="handoff-inputs">'+escape(inputs.join(' · '))+'</p>'+details+'</div>';
 }).join('');
}
function renderEventCrew(){
    window.BacSound?.observeJobs(agentId,data.jobs);
    const crew=crewMission(), stage=crew?.payload.stage??-1;
    if(selectedCrewRole>3)selectedCrewRole=0;
    el('board').classList.remove('has-plan');el('lanes').classList.remove('studio-plan-control');delete el('lanes').dataset.traceJob;delete el('lanes')._traceMarkup;
    const intro=el('board').querySelector('.studio-board-intro');intro.querySelector('h3').textContent='Event Brief';intro.querySelector('p').textContent='Riley briefs the fixed team. Dylan and Alex prepare their contributions, then Morgan assembles the event page.';intro.querySelector('[data-mission-total]').textContent='';
    syncDemoPreparation();
    roles.forEach((r,i)=>r[0]=crew?.payload.roster?.[i]?.name||(i===0&&room!=='mission'?data.profile?.name:null)||defaultNames[i]);
    const groups=crewGroups(crew).map(group=>group.filter(i=>i<4)).filter(group=>group.length);el('lanes').style.setProperty('--crew-groups',groups.length);
    el('lanes').innerHTML=groups.map(group=>`<section class="studio-work-group ${group.length>1?'is-parallel':''}">${group.length>1?'<div class="studio-parallel-caption">In parallel <span>Both finish before the next handoff</span></div>':''}<div class="studio-work-group-cards">${group.map(i=>{const [name,role,description]=roles[i],done=!!crew?.payload.outputs?.[i],working=['running','stopping'].includes(crew?.status)&&(crew?.payload.activeStages||[stage]).includes(i),waiting=crew?.status==='waiting'&&i===2;return `<article class="studio-lane" data-state="${waiting?'waiting':done?'done':working?'running':'ready'}"><span>${waiting?'NEEDS YOU':done?'DELIVERED':working?(crew?.status==='stopping'?'STOPPING':'WORKING'):crew?'WAITING':'READY'}</span><h4>${escape(name)}</h4><strong>${escape(role)}</strong><p>${escape(description)}</p>${hasCrewDeliverable(crew,i)?'<button data-role-output="'+i+'">Open deliverable</button>':''}</article>`;}).join('')}</div></section>`).join('');
    const active=room==='mission'?(crew&&['running','stopping','waiting'].includes(crew.status)?crew:null):data.jobs.find(j=>['running','stopping'].includes(j.status))||data.jobs.find(j=>j.status==='waiting');
    const s=window.BacDemo.snapshot();
    const a=roles.map(([name,role,description],i)=>({...s.agents[i],name,role,persona:description,skills:i===0?['Shared brief']:i===1?['Demo design']:i===2?['Capacity planning']:i===3?['Campaign writing']:i===4?['Evidence review']:['Event page studio'],lane:0,status:'Ready',task:description,permission:'Scoped workspace',displayed:i<4,included:i<4&&(crew?.payload.enabledRoles||[0,1,2,3]).includes(i)}));
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
    const b=crew?.payload.brief;
    window.BacCampus?.setLive({...s,live:true,crewMission:crew?{id:crew.id,status:crew.status,failed:Object.keys(crew.payload.stageErrors||{}).length>0,activeStages:['running','stopping'].includes(crew.status)?(crew.payload.activeStages||[crew.payload.stage]):[],count:crew.payload.roster?.length||5,enabledRoles:crew.payload.enabledRoles||roles.map((_,i)=>i),roundtable:crew.payload.roundtable,completed:Object.keys(crew.payload.outputs||{}).map(Number)}:null,phase,jobId:active?.id,missionSkill:active?.payload.skill,revision:data.jobs.length,agents:a,selected:room==='mission'?selectedCrewRole:selected,flow,gap:active?.status==='waiting',brief:b?{...b,location:b.city}:null,calc:crew?.payload.capacity||null,policy:null});
    document.getElementById('campus-motion-status').textContent=active?flow[0]:'Meet your specialists · give the lead an event brief';
    renderCrewPassport();
  }

function renderEventCrewPassport(){
 if(room!=='mission')return;
 const i=selectedCrewRole,name=defaultNames[i],role=roles[i][1],crew=crewMission();
 const avatar=window.BacCampus?.inspect().crewAvatars?.[i]||{};
 el('crew-number').textContent=String(i+1).padStart(2,'0')+' / 4';
 el('crew-name').textContent=name;el('crew-role').textContent=role;syncTeamTotalTime();const model=teamModel(i);el('crew-model').textContent=model?.label||'';el('crew-model').title=model?.id||'';el('crew-model').hidden=!model;
 const portrait=el('crew-portrait');portrait.dataset.body=avatar.body||'classic';portrait.dataset.accessory=avatar.accessory||'antenna';portrait.style.setProperty('--avatar-accent',appearanceColors[avatar.color]||appearanceColors.green);
 const skills=window.BacCrewCatalog[i].skills;
 const skillLabels={...titles,'event-tools':'Event tools','event-scheduling':'Presenter scheduling'};
 el('crew-policy').hidden=window.BacCrewCatalog[i].protection!=='openshell';
 syncPolicyBadges();
 const markup=skills.map(s=>'<span>'+escape(skillLabels[s]||s)+'</span>').join('');if(el('crew-skills').innerHTML!==markup)el('crew-skills').innerHTML=markup;
 const key=crewDraftKey(i),switched=key!==crewChatKey;
 if(switched){if(crewChatKey)crewDrafts.set(crewChatKey,el('crew-prompt').value);crewChatKey=key;el('crew-prompt').value=crewDrafts.get(key)||'';el('crew-chat-error').hidden=true;}
 renderImageDrafts(true);
 el('crew-prompt').placeholder='Message '+name+'…';el('crew-prompt').dataset.planEnabled='false';syncCrewComposer();
 const turns=(data.crewChats||[]).filter(j=>j.payload.crewRole===i).map(j=>({...j,direct:true}));
 for(const j of data.jobs||[])if(j.kind==='crew'&&j.created>=(data.crewChatReset?.at||0)&&(i===0||j.payload.handoffs?.[i]||j.payload.outputs?.[i]))turns.push({...j,direct:false});
 turns.sort((a,b)=>a.created-b.created);
 const signature=JSON.stringify([key,turns.map(j=>[j.id,j.status,j.result,shieldReplyHeld(j,i),j.direct?null:[j.payload.outputs?.[i],j.payload.stageErrors?.[i],j.payload.website,i===3?j.payload.socialDraft:null,j.payload.activity?.[i],i===0?j.payload.handoffs:j.payload.handoffs?.[i],i===0?[crewBriefMessage(j),j.payload.roundtable]:null]])]);
 if(signature===crewChatSignature)return;
 crewChatSignature=signature;const log=el('crew-conversation'),follow=switched||log.scrollHeight-log.scrollTop-log.clientHeight<70,top=log.scrollTop;
 log.innerHTML=turns.length?turns.map(j=>{
 const held=shieldReplyHeld(j,i),pending=['queued','running','waiting','stopping'].includes(j.status);
 const answer=j.direct?(j.result?.answer||j.result?.error||''):(j.payload.outputs?.[i]||j.payload.stageErrors?.[i]||(j.status==='error'&&Number(j.payload.stage)===i?j.result?.error:''));
 const webpage=!j.direct&&i===3&&j.payload.website?.authored?'<button class="studio-secondary" data-crew-webpage="'+escape(j.id)+'">Open webpage</button>':'';
 const social=!j.direct&&i===3&&j.payload.socialDraft?.status==='ready'?'<div class="chat-message chat-agent"><small>Morgan · LinkedIn draft · not published</small><div class="chat-prose">'+messageMarkup(j.payload.socialDraft.text)+'</div></div>':'';
 const handoffs=j.direct?'':crewHandoffMessages(j,i);
 const request=j.direct?(j.payload.prompt||'Describe the attached image.'):i===0?crewBriefMessage(j):'';
 const status={queued:'Waiting to start…',running:'Working on your message…',waiting:'Waiting for a decision.',stopping:'Stopping…',cancelled:'Stopped.',error:'This message could not finish.'}[j.status];
 return '<article class="chat-turn">'+(i!==0?handoffs:'')+(request?'<div class="chat-message chat-user"><small>You</small><div>'+escape(request).replace(/\n/g,'<br>')+imageHistoryMarkup(j.payload.images,j.id)+'</div></div>':'')+(held?'':social)+'<div class="chat-message chat-agent"><small>'+escape(name)+(j.direct?'':' · Event mission')+'</small>'+(held?shieldReplyWait:customSkillMarkup(j.direct?j.result?.activity:j.payload.activity?.[i])+'<div class="chat-prose">'+messageMarkup(answer||(!j.direct&&pending?(i===0?'Your event brief is with the crew.':(i===3&&j.payload.socialDraft?.status==='ready'?'LinkedIn draft ready. Writing the webpage…':'Working on the assigned task…')):status)||'No text reply was returned.')+'</div>'+crewActivityMarkup(j,i)+webpage+(j.direct&&pending?'<div class="chat-progress">'+chatStopButton(j.id,true,j.status==='stopping')+'</div>':''))+'</div>'+(i===0?handoffs+roundtableMarkup(j):'')+'</article>';
 }).join(''):'<p class="chat-empty">'+escape(roles[i][2])+'</p>';
 loadChatImages(log,agentId);
 if(follow)log.scrollTop=log.scrollHeight;else log.scrollTop=top;
}

el('crew-conversation').addEventListener('click',event=>{const button=event.target.closest('[data-crew-webpage]');if(button){selectedJob=button.dataset.crewWebpage;openSurface('deliverables',3);}});
