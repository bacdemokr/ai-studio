// Each specialist has a durable direct conversation, separate from crew execution.
const crewDrafts=new Map();let crewChatKey='',crewChatSignature='',crewChatSending=false,crewResetEpoch='';
// Reconstruct the submitted request from the saved brief, including after a refresh.
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
function customSkillMarkup(activity){
 if(!activity?.available||!Array.isArray(activity.calls))return '';
 const skills=new Map();
 for(const call of activity.calls){
  const skill=call.customSkill;
  if(call.tool==='read'&&call.status==='completed'&&/^bac-[a-z0-9-]+$/.test(skill?.id||'')&&typeof skill.label==='string')skills.set(skill.id,skill.label);
 }
 if(!skills.size)return '';
 return '<div class="chat-custom-skills" aria-label="Custom skills loaded">'+[...skills.values()].map(label=>'<span class="chat-custom-skill" title="Skill instructions read during this reply"><span>Custom skill</span><strong>'+escape(label)+'</strong></span>').join('')+'</div>';
}
function crewActivityMarkup(job,role){
 const activity=job.direct?job.result?.activity:job.payload.activity?.[role];
 if(!activity)return '';
 if(!activity.available)return '<p class="studio-muted">Tool activity could not be retrieved from the runtime.</p>';
 const labels={read:'Read file',write:'Wrote file',edit:'Edited file',web_fetch:'Read webpage',web_search:'Searched the web',exec:'Executed tool'};
 return '<details class="crew-tool-activity"><summary>Activity · '+activity.calls.length+' tool calls</summary><ol>'+activity.calls.map(call=>'<li><strong>'+escape(call.action?({search:'Searched NVIDIA Blog',read:'Read source articles',schedule:'Validated & exported timetable'}[call.action]||call.action):labels[call.tool]||call.tool)+'</strong><span>'+escape(call.status)+'</span><small>'+escape(call.target||'')+'</small></li>').join('')+'</ol><small>Observed OpenClaw tool calls</small></details>';
}
// Assignment records come from dispatched handoffs, not a generated conversation.
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
// /plan is a real Captain-led job; contributions come from completed model calls.
function collaborationMarkup(job,role){
 const plan=job.payload.collaboration,pending=['queued','running','waiting','stopping'].includes(job.status);
 const held=shieldReplyHeld(job,role),piece=plan.outputs?.[role],captain=role===0;
 const answer=captain?(job.result?.answer||job.result?.error||''):piece?.answer||'';
 const status=job.status==='cancelled'?'Stopped.':job.status==='stopping'?'Stopping after the current call…':job.events?.at(-1)?.title||'Waiting for the Captain…';
 const summary=captain&&plan.summary?'<div class="chat-message chat-handoff"><small>Captain’s plan</small><div class="chat-prose">'+messageMarkup(plan.summary)+'</div><ol>'+plan.tasks.map(t=>'<li><strong>'+escape(defaultNames[t.role])+'</strong>: '+escape(t.task)+'</li>').join('')+'</ol></div>':'';
 const contributions=captain?Object.values(plan.outputs||{}).map(p=>'<details class="crew-tool-activity"><summary>'+escape(p.name)+' · Contribution</summary>'+customSkillMarkup(p.activity)+'<div class="chat-prose">'+messageMarkup(p.answer)+'</div></details>').join(''):'';
 const handoff=!captain&&plan.handoffs?.[role]?'<div class="chat-message chat-handoff"><small>Casey → '+escape(defaultNames[role])+'</small><div class="chat-prose">'+messageMarkup(plan.handoffs[role].task)+'</div><small>Received: '+escape(['Captain’s task',...plan.handoffs[role].receivedFrom.map(i=>defaultNames[Number(i)]+"’s contribution")].join(' · '))+'</small></div>':'';
 return '<article class="chat-turn" data-collaboration-job="'+escape(job.id)+'">'+(captain?'<div class="chat-message chat-user"><small>You</small><div>'+escape(job.payload.prompt).replace(/\n/g,'<br>')+imageHistoryMarkup(job.payload.images,job.id)+'</div></div>':'')+(held?shieldReplyWait:summary+handoff+contributions+'<div class="chat-message chat-agent"><small>'+escape(defaultNames[role])+' · '+(captain?'BaC collaboration':'Specialist contribution')+'</small><div class="chat-prose">'+messageMarkup(answer||status)+'</div></div>')+(pending?'<div class="chat-progress" role="status">'+escape(status)+(job.status!=='stopping'?'<button type="button" data-crew-chat-stop="'+escape(job.id)+'">Stop</button>':'')+'</div>':'')+(captain?(job.result?.files||[]).map(path=>'<button type="button" class="studio-secondary" data-plan-file="'+escape(path)+'">Open team response</button>').join(''):'')+'</article>';
}
function showCollaboration(){selectedCrewRole=0;setRoom('mission');root.dataset.crewDetails='true';renderCrewPassport();}
function syncCrewComposer(){
 const blocked=!runtime.ready||!!data.deleting;
 el('crew-prompt').disabled=blocked;el('crew-send').disabled=blocked||crewChatSending;
 el('crew-chat-connection').hidden=!blocked;
 el('crew-chat-connection').textContent=data.deleting?'This workspace is being deleted.':!runtime.model?'Connect a model in Settings to message your crew.':'Reconnect the agent runtime in Settings to message your crew.';
}
function renderCrewPassport(){
 const epoch=data.crewChatReset?.epoch||'';
 if(epoch!==crewResetEpoch){
  crewResetEpoch=epoch;crewDrafts.clear();crewChatKey='';crewChatSignature='';el('crew-prompt').value='';
  for(const key of chatImageDrafts.keys())if(key.includes(':crew:'))chatImageDrafts.delete(key);
 }
 if(room!=='mission')return;
 const i=selectedCrewRole,name=defaultNames[i],role=roles[i][1],crew=crewMission();
 const avatar=window.BacCampus?.inspect().crewAvatars?.[i]||{};
 el('crew-number').textContent=String(i+1).padStart(2,'0')+' / 4';
 el('crew-name').textContent=name;el('crew-role').textContent=role;
 const portrait=el('crew-portrait');portrait.dataset.body=avatar.body||'classic';portrait.dataset.accessory=avatar.accessory||'antenna';portrait.style.setProperty('--avatar-accent',appearanceColors[avatar.color]||appearanceColors.green);
 const skills=window.BacCrewCatalog[i].skills;
 const skillLabels={...titles,'event-tools':'Event tools','event-scheduling':'Presenter scheduling'};
 el('crew-policy').hidden=window.BacCrewCatalog[i].protection!=='openshell';
 syncPolicyBadges();
 const markup=skills.map(s=>'<span>'+escape(skillLabels[s]||s)+'</span>').join('');if(el('crew-skills').innerHTML!==markup)el('crew-skills').innerHTML=markup;
 const key=agentId+':'+i,switched=key!==crewChatKey;
 if(switched){if(crewChatKey)crewDrafts.set(crewChatKey,el('crew-prompt').value);crewChatKey=key;el('crew-prompt').value=crewDrafts.get(key)||'';el('crew-chat-error').hidden=true;}
 renderImageDrafts(true);
 el('crew-prompt').placeholder='Message '+name+'… or /plan a task with the BaC team';syncCrewComposer();
 const turns=(data.crewChats||[]).filter(j=>j.payload.crewRole===i||(j.payload.collaboration&&(j.payload.collaboration.handoffs?.[i]||j.payload.collaboration.activeRole===i))).map(j=>({...j,direct:true}));
 for(const j of data.jobs||[])if(j.kind==='crew'&&j.created>=(data.crewChatReset?.at||0)&&(i===0||j.payload.handoffs?.[i]||j.payload.outputs?.[i]))turns.push({...j,direct:false});
 turns.sort((a,b)=>a.created-b.created);
 const signature=JSON.stringify([key,turns.map(j=>[j.id,j.status,j.result,j.payload.collaboration,j.events?.at(-1),shieldReplyHeld(j,i),j.direct?null:[j.payload.outputs?.[i],j.payload.website,i===3?j.payload.socialDraft:null,j.payload.activity?.[i],i===0?j.payload.handoffs:j.payload.handoffs?.[i],i===0?[crewBriefMessage(j),j.payload.roundtable]:null]])]);
 if(signature===crewChatSignature)return;
 crewChatSignature=signature;const log=el('crew-conversation'),follow=switched||log.scrollHeight-log.scrollTop-log.clientHeight<70,top=log.scrollTop;
 log.innerHTML=turns.length?turns.map(j=>{
 if(j.payload.collaboration)return collaborationMarkup(j,i);
 const held=shieldReplyHeld(j,i),pending=['queued','running','waiting','stopping'].includes(j.status);
 const answer=j.direct?(j.result?.answer||j.result?.error||''):(j.payload.outputs?.[i]||j.payload.stageErrors?.[i]||(j.status==='error'&&Number(j.payload.stage)===i?j.result?.error:''));
 const webpage=!j.direct&&i===3&&j.payload.website?.authored?'<button class="studio-secondary" data-crew-webpage="'+escape(j.id)+'">Open webpage</button>':'';
 const social=!j.direct&&i===3&&j.payload.socialDraft?.status==='ready'?'<div class="chat-message chat-agent"><small>Morgan · LinkedIn draft · not published</small><div class="chat-prose">'+messageMarkup(j.payload.socialDraft.text)+'</div></div>':'';
 const handoffs=j.direct?'':crewHandoffMessages(j,i);
 const request=j.direct?(j.payload.prompt||'Describe the attached image.'):i===0?crewBriefMessage(j):'';
 const status={queued:'Waiting to start…',running:'Working on your message…',waiting:'Waiting for a decision.',stopping:'Stopping…',cancelled:'Stopped.',error:'This message could not finish.'}[j.status];
 return '<article class="chat-turn">'+(i!==0?handoffs:'')+(request?'<div class="chat-message chat-user"><small>You</small><div>'+escape(request).replace(/\n/g,'<br>')+imageHistoryMarkup(j.payload.images,j.id)+'</div></div>':'')+(held?'':social)+'<div class="chat-message chat-agent"><small>'+escape(name)+(j.direct?'':' · Event mission')+'</small>'+(held?shieldReplyWait:customSkillMarkup(j.direct?j.result?.activity:j.payload.activity?.[i])+'<div class="chat-prose">'+messageMarkup(answer||(!j.direct&&pending?(i===0?'Your event brief is with the crew.':(i===3&&j.payload.socialDraft?.status==='ready'?'LinkedIn draft ready. Writing the webpage…':'Working on the assigned task…')):status)||'No text reply was returned.')+'</div>'+crewActivityMarkup(j,i)+webpage+(j.direct&&pending?'<div class="chat-progress"><button type="button" data-crew-chat-stop="'+escape(j.id)+'" '+(j.status==='stopping'?'disabled':'')+'>Stop</button></div>':''))+'</div>'+(i===0?handoffs+roundtableMarkup(j):'')+'</article>';
 }).join(''):'<p class="chat-empty">'+escape(roles[i][2])+'</p>';
 loadChatImages(log,agentId);
 if(follow)log.scrollTop=log.scrollHeight;else log.scrollTop=top;
}
el('crew-policy').onclick=()=>openPolicy(selectedCrewRole);
el('crew-chat').onsubmit=async e=>{
 e.preventDefault();syncCrewComposer();if(el('crew-send').disabled)return;
 const owner=agentId,index=selectedCrewRole,key=owner+':'+index,draft=captureChatDraft(true);
 crewChatSending=true;syncCrewComposer();el('crew-chat-error').hidden=true;
 try{const result=await api('jobs',{kind:'crew-chat',crewRole:index,prompt:draft.prompt,images:draft.images},owner);acknowledgeChatDraft(draft);await refresh();if(result.collaboration)showCollaboration();}
 catch(error){if(crewChatKey===key){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}}
 finally{crewChatSending=false;syncCrewComposer();}
};
el('crew-prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!el('crew-send').disabled)el('crew-chat').requestSubmit(el('crew-send'));}});
el('crew-conversation').onclick=async e=>{const file=e.target.closest('[data-plan-file]');if(file){await openFile(file.dataset.planFile);return;}const page=e.target.closest('[data-crew-webpage]');if(page){selectedJob=page.dataset.crewWebpage;openSurface('deliverables','webpage');return;}const button=e.target.closest('[data-crew-chat-stop]');if(!button)return;try{await api('decision',{id:button.dataset.crewChatStop,action:'cancel'});await refresh();}catch(error){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}};

function roundtableMarkup(job){
 const meeting=job.payload.roundtable;if(!meeting?.members?.length&&!meeting?.skipped?.length)return '';
 const intro=meeting.status==='invited'?'Your hired agents are joining the table. Their reactions follow the finished package.':'Personal reactions to this event · opinions, not independent tests.';
 return '<section class="crew-roundtable-log"><h4>Your agents’ take</h4><p>'+(meeting.members.length?intro:'No personal agents are joining this event.')+'</p>'+(meeting.skipped||[]).map(m=>'<p class="studio-muted" data-roundtable-skipped="'+escape(m.key)+'">'+escape(m.name)+' · Skipped: '+escape(m.detail)+'</p>').join('')+meeting.members.map(member=>{const reply=meeting.replies?.[member.key]||{},text=reply.answer||reply.error||(meeting.status==='cancelled'?'Roundtable stopped before this reaction.':reply.status==='running'?'Considering the plan…':'Waiting for the results.');return '<article class="chat-message chat-agent" data-roundtable-reply="'+escape(member.key)+'"><small>'+escape(member.name)+' · '+escape(member.tonePrompt||member.tone||'')+'</small>'+customSkillMarkup(reply.activity)+'<div class="chat-prose">'+messageMarkup(text)+'</div>'+(reply.status==='error'&&job.status==='done'?'<button type="button" class="studio-secondary" data-retry-reaction="'+escape(member.key)+'" data-reaction-job="'+escape(job.id)+'">Retry this reaction</button>':'')+'</article>'}).join('')+'</section>';
}

root.addEventListener('click',async event=>{
 const button=event.target.closest('[data-retry-reaction]');if(!button)return;
 button.disabled=true;
 try{await api('retry-reaction',{id:button.dataset.reactionJob,member:button.dataset.retryReaction});await refresh();}
 catch(error){alert(error.message);button.disabled=false;}
});
