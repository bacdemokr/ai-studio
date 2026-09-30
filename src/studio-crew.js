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
function webpageButtons(files,jobId){
 const pages=[...new Set(files||[])].filter(path=>/\.html$/i.test(path));
 return pages.length?'<div class="chat-webpages">'+pages.map((path,index)=>'<button type="button" class="studio-secondary" data-preview-file="'+escape(path)+'" data-preview-job="'+escape(jobId)+'">Preview webpage'+(pages.length>1?' '+(index+1):'')+' <span aria-hidden="true">↗</span></button>').join('')+'</div>':'';
}
root.addEventListener('click',event=>{const page=event.target.closest('[data-preview-file]');if(page)openFile(page.dataset.previewFile,page.dataset.previewJob);});
// The latest saved plan owns the visible team, including after a refresh.
function stageCollaboration(job){
 render();
 showCollaboration();
}
// Keep this visit's chosen team visible until a newer event mission/reset.
function currentCollaboration(){
 const latest=(data.crewChats||[]).filter(j=>j.payload.collaboration&&j.created>=(data.crewChatReset?.at||0)).sort((a,b)=>b.created-a.created)[0];
 const event=crewMission();
 return latest&&(!event||latest.created>=event.created)?latest:null;
}
// Mission Control can inspect saved plans without replaying their stage animation.
function missionControlPlan(){
 const latest=(data.crewChats||[]).filter(j=>j.payload.collaboration&&j.created>=(data.crewChatReset?.at||0)).sort((a,b)=>b.created-a.created)[0];
 const event=crewMission();
 return latest&&(!event||latest.created>=event.created)?latest:null;
}
function renderStandbySpecialists(agents,crew){
 const occupied=new Set(agents.flatMap((agent,i)=>agent.displayed?[i]:[]));
 if(!currentCollaboration()&&crew&&['queued','running','waiting','stopping'].includes(crew.status))
  (crew.payload.enabledRoles||[]).forEach(role=>occupied.add(role));
 const available=window.BacCrewCatalog.map((member,role)=>({...member,roleIndex:role}))
  .filter(member=>member.planEligible!==false);
 el('standby-count').textContent=String(available.length);
 const busyTeam=(data.crewChats||[]).some(j=>['queued','running','waiting','stopping'].includes(j.status))||data.bacResetting;
 const markup=available.map(member=>'<li data-standby-role="'+member.roleIndex+'"><div><strong>'+escape(member.name)+'</strong><span>'+escape(member.collaboration.title)+(occupied.has(member.roleIndex)?' · With team':'')+'</span></div><select data-team-model="'+member.roleIndex+'" aria-label="Model for '+escape(member.name)+'" '+(busyTeam?'disabled':'')+'>'+(runtime.teamModels||[]).map(model=>'<option value="'+escape(model.id)+'" '+(model.id===teamModel(member.roleIndex)?.id?'selected':'')+'>'+escape(model.label)+'</option>').join('')+'</select></li>').join('');
 if(!el('standby-list').contains(document.activeElement)&&el('standby-list').innerHTML!==markup)el('standby-list').innerHTML=markup;
}
root.addEventListener('change',async event=>{
 const select=event.target.closest('[data-team-model]');if(!select)return;
 select.disabled=true;
 try{await api('team-model',{role:Number(select.dataset.teamModel),model:select.value});await refresh();}
 catch(error){alert(error.message);}
 finally{select.blur();render();}
});

function eventExpectationMarkup(job,role){
 const p=job?.payload,h=p?.handoffs?.[role],name=p?.roster?.[role]?.name||defaultNames[role];
 const assignment=p?.assignments?.find(a=>a.name===name)?.task;
 if(!h?.task&&!assignment)return '';
 return '<div class="mission-expectation"><small>Expected contribution</small><div>'+messageMarkup(assignment||h.task)+'</div>'+(assignment&&h?.task?'<details><summary>Full assignment</summary><div>'+messageMarkup(h.task)+'</div></details>':'')+'</div>';
}
// Reconstruct the visible trace from saved handoffs, contributions and checkpoints.
// Planned-but-uncalled roles are never presented as completed execution steps.
function collaborationRoleOrder(plan){
 const tasks=(plan.tasks||[]).map(task=>Number(task.role));
 const handoffs=Object.keys(plan.handoffs||{}).map(Number).sort((a,b)=>{
  const first=plan.handoffs[a]?.started,last=plan.handoffs[b]?.started;
  return first&&last?first-last:tasks.indexOf(a)-tasks.indexOf(b);
 });
 return [...new Set([...(plan.calledRoles||[]).map(Number),...handoffs,...tasks,...Object.keys(plan.outputs||{}).map(Number)])]
  .filter(role=>Number.isInteger(role)&&role>0&&defaultNames[role]);
}
// Presence follows the approved plan; execution still follows calledRoles/handoffs.
function collaborationTeam(plan){
 // Keep the seated team while Casey is still deciding the next assignment.
 const previous=!Array.isArray(plan.tasks)?(data.crewChats||[]).filter(j=>j.payload.collaboration!==plan&&Array.isArray(j.payload.collaboration?.tasks)&&j.created>=(data.crewChatReset?.at||0)).sort((a,b)=>b.created-a.created)[0]?.payload.collaboration:null;
 const selected=Array.isArray(plan.tasks)?plan.tasks.map(task=>task.role):previous?previous.tasks.map(task=>task.role):(plan.calledRoles||[]);
 return [0,...new Set(selected.filter(role=>Number.isInteger(role)&&role>0&&defaultNames[role]))];
}
function collaborationAnswer(job){return job.result?.answer||job.payload.collaboration.finalAnswer||'';}
function missionControlTraceMarkup(job){
 const plan=job.payload.collaboration,active=['queued','running','waiting','stopping'].includes(job.status),tasks=plan.tasks||[],checks=plan.checks||[];
 let sequence=0;
 const row=(kind,name,status,content,attrs='',recorded=true,state='')=>'<article class="mission-plan-step" data-trace-key="'+escape(kind+':'+attrs)+'" data-trace-kind="'+kind+'" data-step-state="'+state+'" '+attrs+'><header><small>'+(recorded?String(++sequence).padStart(2,'0')+' · '+({plan:'PLAN',contribution:'CONTRIBUTION',review:'REVIEW',revision:'REVISION REQUEST','revision-work':'REVISION',response:'RESPONSE',stopped:'STOPPED'}[kind]||kind.toUpperCase()):kind==='skipped'?'NOT CALLED':'PLANNED')+'</small><h4>'+escape(name)+'</h4><span>'+escape(status)+'</span></header><div class="mission-plan-content">'+content+'</div></article>';
 const detail=(key,label,content)=>'<details class="mission-trace-detail" data-trace-details="'+key+'"><summary>'+escape(label)+'</summary><div class="chat-prose">'+content+'</div></details>';
 let markup=row('plan','Casey',plan.summary?'Plan ready':active?'Planning':'No plan saved','<strong>Approach</strong><div>'+messageMarkup(plan.summary||(active?'Casey is deciding which expertise this request needs.':'No plan was saved before the work stopped.'))+'</div>','data-plan-role="0"',true,plan.summary?'done':active?'working':'');
 const called=tasks.filter(task=>plan.handoffs?.[task.role]||plan.outputs?.[task.role]||plan.calledRoles?.includes(task.role));
 const calledOrder=collaborationRoleOrder(plan);
 called.sort((a,b)=>calledOrder.indexOf(Number(a.role))-calledOrder.indexOf(Number(b.role)));
 for(const task of called){
  const role=task.role,h=plan.handoffs?.[role],output=plan.outputs?.[role],working=active&&plan.activeRole===role;
  const recovery=plan.handoffRecovery?.role===role?plan.handoffRecovery:null;
  const missing=output?.handoffStatus==='missing';
  const status=missing?(working&&recovery?.status==='working'?'Saving missing handoff':'Handoff incomplete'):output?.incomplete?'Partial work saved':output?'Delivered':working?(job.status==='stopping'?'Stopping':'Working'):active?'Started':'Incomplete';
  const expected=h?.expected||task.expected;
  const assignment='<strong>Casey’s assignment</strong><div>'+messageMarkup(h?.task||task.task)+'</div>'+(expected?'<div class="mission-expectation"><small>Expected result</small><div>'+messageMarkup(expected)+'</div></div>':'')+(h?'<small class="mission-plan-inputs">Received: '+escape(['Casey’s brief',...(h.receivedFrom||[]).map(i=>defaultNames[Number(i)]+"’s contribution")].join(' · '))+'</small>':'');
  const recoveryNote=recovery?'<p class="mission-plan-inputs">'+escape(recovery.status==='delivered'?'A missing handoff was saved and verified in one repair before continuing.':recovery.status==='working'?'Required files are missing. One repair is using the existing research; later specialists are waiting.':'The required handoff could not be recovered. Later specialists were not started.')+'</p>':'';
  markup+=row('contribution',defaultNames[role],status,assignment+recoveryNote+(output?detail('output-'+role,defaultNames[role]+'’s result',messageMarkup(output.answer||'No response text was saved.')+webpageButtons(output.files,job.id)):''),'data-plan-role="'+role+'"',true,missing?(working?'working':''):output?'done':working?'working':'');
  const reviews=checks.filter(check=>!check.afterRevision&&Number(check.afterRole)===role);
  for(const check of reviews){
   const status=check.done?(check.outcome==='partial'?'Partial result':check.outcome==='unavailable'?'Capability unavailable':'Enough to finish'):'More work needed';
   markup+=row('review','Casey',status,'<strong>After '+escape(defaultNames[role])+'’s result</strong><div>'+messageMarkup(check.reason)+'</div>'+(check.done?'<small class="mission-plan-inputs">No additional agents will be called.</small>':''),'data-after-role="'+role+'"',true,'done');
  }
  if(output&&!reviews.length&&active&&plan.activeRole===0&&!plan.responseReady&&task===called.at(-1)&&!plan.revision)
   markup+=row('review','Casey',job.status==='stopping'?'Stopping':'Reviewing','<strong>After '+escape(defaultNames[role])+'’s result</strong><p>Checking the contribution against the request before deciding what comes next.</p>','data-after-role="'+role+'"',true,'working');
 }
 for(const task of tasks.filter(task=>!called.includes(task))){
  const skipped=plan.skippedRoles?.includes(task.role),uncalled=skipped||!active||plan.responseReady;
  markup+=row(uncalled?'skipped':'planned',defaultNames[task.role],uncalled?'Not called':'Waiting for Casey',detail('assignment-'+task.role,'Planned assignment',messageMarkup(task.task)+(task.expected?'<div class="mission-expectation"><small>Expected result</small>'+messageMarkup(task.expected)+'</div>':''))+'<small class="mission-plan-inputs">'+(skipped?'Casey ended the plan before calling this agent.':uncalled?'This assignment was not started.':'Casey will decide whether this assignment is still needed.')+'</small>','data-plan-role="'+task.role+'"',false,uncalled?'skipped':'planned');
 }
 if(plan.revision){
  const r=plan.revision,output=r.output,working=active&&r.status==='working';
  markup+=row('revision','Casey','One targeted revision','<strong>Why repair is needed</strong><div>'+messageMarkup(r.reason)+'</div><div>'+messageMarkup(r.issue)+'</div>','data-revision-request',true,'done');
  markup+=row('revision-work',defaultNames[r.role],output?'Revised result delivered':working?'Revising':active&&r.status==='requested'?'Requested':r.status==='failed'?'Revision failed':'Not completed',collaborationRevisionBody(r,job.id),'data-revision-role="'+r.role+'"',true,output?'done':working?'working':'');
  for(const check of checks.filter(check=>check.afterRevision))
   markup+=row('review','Casey',check.outcome==='partial'?'Partial result':'Final verification','<div>'+messageMarkup(check.reason)+'</div><small>No further specialist calls.</small>','data-after-revision',true,'done');
  if(output&&!checks.some(check=>check.afterRevision)&&active&&!plan.responseReady)
   markup+=row('review','Casey','Verifying revision','<p>Checking the repaired result and remaining limitations. No further specialist calls.</p>','data-after-revision',true,'working');
 }
 const answer=collaborationAnswer(job);
 if(answer)markup+=row('response','Casey',plan.outcome==='partial'?'Partial result':plan.outcome==='unavailable'?'Capability unavailable':'Response ready',detail('response','Final team response',messageMarkup(answer)+(plan.outcome==='partial'&&plan.remaining?.length?'<strong>Still needed</strong><ul>'+plan.remaining.map(item=>'<li>'+escape(item)+'</li>').join('')+'</ul>':'')+webpageButtons(Object.values(plan.webpages||{}).flat(),job.id)),'',true,'done');
 else if(!active)markup+=row('stopped','Casey',job.status==='cancelled'?'Stopped':'Needs attention','<div>'+messageMarkup(job.result?.error||(job.status==='cancelled'?'The work stopped before a final response was ready.':'No final response was saved.'))+'</div>');
 return markup;
}
function updateMissionControlTrace(lanes,jobId,markup){
 const sameJob=lanes.dataset.traceJob===jobId;
 if(sameJob&&lanes._traceMarkup===markup)return;
 const template=document.createElement('template');template.innerHTML=markup;
 const incoming=[...template.content.children],keys=new Set(incoming.map(node=>node.dataset.traceKey));
 const old=new Map(sameJob?[...lanes.children].map(node=>[node.dataset.traceKey,node]):[]);
 if(!sameJob)lanes.replaceChildren();
 else for(const node of [...lanes.children])if(!keys.has(node.dataset.traceKey))node.remove();
 let cursor=lanes.firstElementChild;
 const retained=new Set();
 for(const fresh of incoming){
  const previous=old.get(fresh.dataset.traceKey),source=fresh.outerHTML;
  const node=previous?._traceMarkup===source?previous:fresh;
  if(previous&&node!==previous){
   const expanded=new Set([...previous.querySelectorAll('[data-trace-details][open]')].map(item=>item.dataset.traceDetails));
   for(const item of node.querySelectorAll('[data-trace-details]'))item.open=expanded.has(item.dataset.traceDetails);
   // Replace in place so later unchanged cards never move through the DOM.
   if(cursor===previous)cursor=node;
   previous.replaceWith(node);
  }
  node._traceMarkup=source;
  // Retain unchanged cards, including their focused links/buttons and selection.
  if(node!==cursor)lanes.insertBefore(node,cursor);
  cursor=node.nextElementSibling;retained.add(node);
 }
 for(const node of [...lanes.children])if(!retained.has(node))node.remove();
 lanes.dataset.traceJob=jobId;lanes._traceMarkup=markup;
}
function renderMissionControl(){
 const job=missionControlPlan(),intro=el('board').querySelector('.studio-board-intro');
 el('lanes').classList.toggle('studio-plan-control',!!job);
 el('board').classList.toggle('has-plan',!!job);
 intro.querySelector('h3').textContent=job?'Execution trace':'Different roles. Shared evidence.';
 intro.querySelector('p').textContent=job?job.payload.collaboration.task:'Each specialist receives the brief and previous deliverables. Recorded assignments appear with each stage.';
 el('board-shared').textContent=job?'View team conversation':'Inspect shared state & handoffs';
 if(!job){delete el('lanes').dataset.traceJob;delete el('lanes')._traceMarkup;return;}
 updateMissionControlTrace(el('lanes'),job.id,missionControlTraceMarkup(job));
}
// /plan is a real Captain-led job; contributions come from completed model calls.
function collaborationRevisionBody(revision,jobId){
 return '<strong>Casey’s revision assignment</strong><div>'+messageMarkup(revision.task)+'</div><div class="mission-expectation"><small>Expected result</small>'+messageMarkup(revision.expected)+'</div>'+(revision.output?'<details class="mission-trace-detail" data-trace-details="revision-output"><summary>Revised contribution</summary><div class="chat-prose">'+messageMarkup(revision.output.answer)+'</div>'+webpageButtons(revision.output.files,jobId)+collaborationFileButtons(revision.output.files,jobId)+'</details>':'')+(revision.status==='failed'?'<p>The revision did not finish. Previous contributions are preserved.</p>':'');
}
function collaborationRevisionMarkup(job){
 const r=job.payload.collaboration.revision;if(!r)return '';
 return '<section class="chat-message chat-handoff" data-plan-revision><small>Casey · One targeted revision</small><div class="chat-prose">'+messageMarkup(r.reason)+'</div><p>'+escape(r.issue)+'</p><small>'+escape(defaultNames[r.role])+' · '+(r.output?'Revised contribution':r.status==='working'&&['running','stopping'].includes(job.status)?'Revising':'Revision '+r.status)+'</small>'+collaborationRevisionBody(r,job.id)+'</section>'+collaborationDecisionMarkup({...job.payload.collaboration,checks:(job.payload.collaboration.checks||[]).filter(check=>check.afterRevision)});
}
function collaborationDecisionMarkup(plan){
 const checks=plan.checks||[];
 if(plan.summary&&Array.isArray(plan.tasks)&&!plan.tasks.length)return '<div class="chat-message chat-handoff" data-plan-decision><small>Casey · '+(plan.outcome==='partial'?'Partial result - no agents called':plan.outcome==='unavailable'?'Required expertise unavailable - no agents called':'No additional agents needed')+'</small><div class="chat-prose">'+messageMarkup(plan.summary)+'</div></div>';
 return checks.map(check=>'<div class="chat-message chat-handoff" data-plan-decision><small>Casey · '+(check.done?(check.outcome==='partial'?'Partial result - stopping here':check.outcome==='unavailable'?'Required expertise unavailable - no additional agents will be called':'Enough to finish - no additional agents will be called'):'More work needed')+'</small><div class="chat-prose">'+messageMarkup(check.reason)+'</div></div>').join('');
}
// Keep the final reply self-contained, including saved plans whose answer omitted
// the Captain's separately recorded stopping reason. Never invent a rationale.
function collaborationCompletionMarkup(plan,answer){
 if(!answer)return '';
 const decision=(plan.checks||[]).filter(check=>check.done).at(-1)||(plan.outcome==='partial'?{outcome:'partial',reason:plan.summary,remaining:plan.remaining}:null);
 if(!decision)return '';
 const skipped=(plan.skippedRoles||[]).map(role=>defaultNames[role]).filter(Boolean);
 const reason=decision.reason&&!answer.includes(decision.reason)?messageMarkup(decision.reason):'';
 const remaining=decision.outcome==='partial'?(decision.remaining||plan.remaining||[]):[];
 if(!reason&&!skipped.length&&!remaining.length)return '';
 return '<div class="collaboration-completion" data-plan-completion><strong>'+ (decision.outcome==='partial'?'Partial result - what remains':decision.outcome==='unavailable'?'Why the team stopped':'Why this result is sufficient')+'</strong>'+reason+(remaining.length?'<ul>'+remaining.map(item=>'<li>'+escape(item)+'</li>').join('')+'</ul>':'')+(skipped.length?'<p class="studio-muted">Not called: '+escape(skipped.join(', '))+'. Their planned work was not performed.</p>':'')+'</div>';
}
function collaborationFileButtons(files,jobId,label='Open supporting file'){
 const paths=[...new Set((files||[]).filter(path=>typeof path==='string'&&!/\.html$/i.test(path)))];
 return paths.map((path,index)=>'<button type="button" class="studio-secondary" data-plan-file="'+escape(path)+'" data-plan-job="'+escape(jobId)+'">'+escape(label)+(paths.length>1?' '+(index+1):'')+'</button>').join('');
}
function livePlanActivityMarkup(plan,role,jobId){
 const activity=plan.liveActivity;
 if(!activity||(role!==0&&role!==activity.role))return '';
 const labels={web_fetch:'Read webpage',web_search:'Search web',read:'Read file',write:'Save file',edit:'Edit file',apply_patch:'Update files',exec:'Run tool',tool:'Tool call'};
 const statuses={started:'Started',running:'Running',completed:'Completed',failed:'Failed'};
 const busy=activity.calls.some(call=>['started','running'].includes(call.status));
 const waiting=!activity.available?'Waiting for runtime activity':busy?'Waiting for tool completion':'Waiting for agent response';
 return '<section class="plan-live-activity" aria-label="Observed activity"><strong>'+escape(defaultNames[activity.role])+' · Live activity</strong><ol>'+activity.calls.map(call=>'<li><span>'+escape(labels[call.tool]||'Tool call')+(call.target?' · '+escape(call.target):'')+'</span><small>'+escape(statuses[call.status]||'Started')+'</small></li>').join('')+'</ol><p>'+waiting+' · '+'<span data-plan-elapsed="'+escape(jobId)+'">'+Number(activity.elapsed)+'</span>s since request</p></section>';
}
function collaborationMarkup(job,role){
 const plan=job.payload.collaboration,pending=['queued','running','waiting','stopping'].includes(job.status);
 const held=shieldReplyHeld(job,role),piece=plan.outputs?.[role],captain=role===0;
 const finalAnswer=collaborationAnswer(job),answer=captain?(finalAnswer||job.result?.error||''):piece?.answer||'';
 const uncalled=!captain&&!piece&&!plan.handoffs?.[role]&&(!pending||plan.responseReady||plan.skippedRoles?.includes(role));
 const status=uncalled?'Casey did not call '+defaultNames[role]+' for this plan.':job.status==='cancelled'?'Stopped.':job.status==='stopping'?'Stopping after the current call…':job.events?.at(-1)?.title||'Waiting for the Captain…';
 const summary=captain&&plan.summary?'<div class="chat-message chat-handoff"><small>Captain’s plan</small><div class="chat-prose">'+messageMarkup(plan.summary)+'</div><ol>'+plan.tasks.map(t=>'<li><strong>'+escape(defaultNames[t.role])+' · '+escape(window.BacCrewCatalog[t.role].collaboration.title)+'</strong>: '+escape(t.task)+(plan.skippedRoles?.includes(t.role)?' <small>Not called - '+(plan.outcome==='partial'?'plan ended with unfinished work':plan.outcome==='unavailable'?'required expertise unavailable':'no longer needed')+'</small>':'')+'</li>').join('')+'</ol></div>':'';
 const outputRoles=collaborationRoleOrder(plan).filter(i=>plan.outputs?.[i]);
 const contributions=captain?outputRoles.map(i=>{const p=plan.outputs[i];return '<details class="crew-tool-activity" data-contribution-role="'+i+'"><summary>'+escape(p.name)+' · Contribution</summary>'+customSkillMarkup(p.activity)+'<div class="chat-prose">'+messageMarkup(p.answer)+'</div>'+collaborationFileButtons(p.files,job.id)+'</details>'+collaborationDecisionMarkup({...plan,checks:(plan.checks||[]).filter(check=>!check.afterRevision&&Number(check.afterRole)===i)});}).join(''):'';
 const handoff=!captain&&plan.handoffs?.[role]?'<div class="chat-message chat-handoff"><small>Casey → '+escape(defaultNames[role])+'</small><div class="chat-prose">'+messageMarkup(plan.handoffs[role].task)+'</div><small>Received: '+escape(['Captain’s task',...plan.handoffs[role].receivedFrom.map(i=>defaultNames[Number(i)]+"’s contribution")].join(' · '))+'</small></div>':'';
 return '<article class="chat-turn" data-collaboration-job="'+escape(job.id)+'">'+(captain||plan.origin?.role===role?'<div class="chat-message chat-user"><small>You</small><div>'+escape(job.payload.prompt).replace(/\n/g,'<br>')+imageHistoryMarkup(job.payload.images,job.id)+'</div></div>':'')+(held?shieldReplyWait:summary+handoff+contributions+livePlanActivityMarkup(plan,role,job.id)+(captain?collaborationRevisionMarkup(job):'')+(captain&&!outputRoles.length?collaborationDecisionMarkup(plan):'')+'<div class="chat-message chat-agent"><small>'+escape(defaultNames[role])+' · '+(captain?'BaC collaboration':'Specialist contribution')+'</small><div class="chat-prose">'+messageMarkup(answer||status)+'</div>'+(captain?collaborationCompletionMarkup(plan,finalAnswer):'')+'</div>')+(!held&&!captain&&plan.revision?.role===role?collaborationRevisionMarkup(job):'')+(pending?'<div class="chat-progress" role="status">'+escape(status)+(job.status!=='stopping'?'<button type="button" data-crew-chat-stop="'+escape(job.id)+'">'+(plan.responseReady?'Stop reactions':'Stop')+'</button>':'')+'</div>':'')+(held?'':webpageButtons(captain?Object.values(plan.webpages||{}).flat():piece?.files,job.id))+(!held?collaborationFileButtons(captain?(job.result?.files||[]).filter(path=>path==='artifacts/plan-'+job.id+'.md'):piece?.files,job.id,captain?'Open team response':'Open supporting file'):'')+(captain&&!held?roundtableMarkup(job):'')+'</article>';
}
function collaborationHistoryMarkup(job){
 const held=shieldReplyHeld(job,0),pending=['queued','running','waiting','stopping'].includes(job.status);
 const answer=collaborationAnswer(job)||job.result?.error||(pending?'The BaC team is collaborating…':job.status==='cancelled'?'Stopped.':'No final reply was returned.');
 return '<article class="chat-turn" data-collaboration-history="'+escape(job.id)+'"><div class="chat-message chat-user"><small>You</small><div>'+messageMarkup(job.payload.prompt)+'</div></div><div class="chat-message chat-agent"><small>Casey · BaC collaboration</small>'+(held?shieldReplyWait:'<div class="chat-prose">'+messageMarkup(answer)+'</div>'+collaborationCompletionMarkup(job.payload.collaboration,collaborationAnswer(job)))+(held?'':collaborationDecisionMarkup(job.payload.collaboration)+webpageButtons(job.result?.files||Object.values(job.payload.collaboration.webpages||{}).flat(),job.id))+'<button type="button" class="studio-secondary" data-open-collaboration>View team conversation</button></div></article>';
}
function showCollaboration(){selectedCrewRole=0;setRoom('mission');root.dataset.crewDetails='true';renderCrewPassport();}
function teamReady(){return runtime.teamReady??runtime.ready;}
function teamModel(role){const id=data.teamSelections?.find(row=>row.role===role)?.id;return runtime.teamModels?.find(model=>model.id===id)||runtime.teamModels?.[role===0?0:1];}
function syncCrewComposer(){
 const blocked=!teamReady()||!!data.bacResetting;
 el('crew-prompt').disabled=blocked;el('crew-send').disabled=blocked||crewChatSending;
 el('crew-chat-connection').hidden=!blocked;
 el('crew-chat-connection').textContent=data.bacResetting?'Stopping BaC work and resetting…':!(runtime.teamModel??runtime.model)?'Connect the dedicated Multi-Agent Demo API on the host.':'Reconnect the agent runtime in Settings to message your crew.';
}
function renderCrewPassport(){
 const epoch=data.crewChatReset?.epoch||'';
 if(epoch!==crewResetEpoch){
  crewResetEpoch=epoch;crewDrafts.clear();crewChatKey='';crewChatSignature='';el('crew-prompt').value='';
  for(const key of chatImageDrafts.keys())if(key.includes(':crew:'))chatImageDrafts.delete(key);
 }
 if(room!=='mission')return;
 const i=selectedCrewRole,name=defaultNames[i],role=window.BacCrewCatalog[i].collaboration.title,crew=crewMission();
 const avatar=window.BacCampus?.inspect().crewAvatars?.[i]||{};
 el('crew-number').textContent=String(i+1).padStart(2,'0')+' / '+roles.length;
 el('crew-name').textContent=name;el('crew-role').textContent=role;
 const model=teamModel(i);el('crew-model').textContent=model?.label||'';el('crew-model').title=model?.id||'';el('crew-model').hidden=!model;
 const portrait=el('crew-portrait');portrait.dataset.body=avatar.body||'classic';portrait.dataset.accessory=avatar.accessory||'antenna';portrait.style.setProperty('--avatar-accent',appearanceColors[avatar.color]||appearanceColors.green);
 const skills=[];
 const skillLabels={...titles,'event-tools':'Event tools','event-scheduling':'Presenter scheduling'};
 el('crew-policy').hidden=window.BacCrewCatalog[i].protection!=='openshell';
 syncPolicyBadges();
 const markup=skills.map(s=>'<span>'+escape(skillLabels[s]||s)+'</span>').join('');if(el('crew-skills').innerHTML!==markup)el('crew-skills').innerHTML=markup;
 const key=agentId+':'+i,switched=key!==crewChatKey;
 if(switched){if(crewChatKey)crewDrafts.set(crewChatKey,el('crew-prompt').value);crewChatKey=key;el('crew-prompt').value=crewDrafts.get(key)||'';el('crew-chat-error').hidden=true;}
 renderImageDrafts(true);
 el('crew-prompt').placeholder='Message '+name+'… or /plan a task with the BaC team';syncCrewComposer();
 const turns=(data.crewChats||[]).filter(j=>j.payload.crewRole===i||(j.payload.collaboration&&(j.payload.collaboration.origin?.role===i||j.payload.collaboration.handoffs?.[i]||j.payload.collaboration.tasks?.some(t=>t.role===i)||j.payload.collaboration.activeRole===i))).map(j=>({...j,direct:true}));
 for(const j of data.jobs||[])if(j.kind==='crew'&&j.created>=(data.crewChatReset?.at||0)&&(i===0||j.payload.handoffs?.[i]||j.payload.outputs?.[i]))turns.push({...j,direct:false});
 turns.sort((a,b)=>a.created-b.created);
 const signature=JSON.stringify([key,turns.map(j=>[j.id,j.status,j.result,j.payload.collaboration?.liveActivity?{...j.payload.collaboration,liveActivity:{...j.payload.collaboration.liveActivity,elapsed:0}}:j.payload.collaboration,j.events?.at(-1),shieldReplyHeld(j,i),j.direct?null:[j.payload.outputs?.[i],j.payload.website,i===3?j.payload.socialDraft:null,j.payload.activity?.[i],i===0?j.payload.handoffs:j.payload.handoffs?.[i],i===0?[crewBriefMessage(j),j.payload.roundtable]:null]])]);
 for(const job of turns){const timer=el('crew-conversation').querySelector('[data-plan-elapsed="'+job.id+'"]');if(timer&&job.payload.collaboration?.liveActivity)timer.textContent=Number(job.payload.collaboration.liveActivity.elapsed);}
 if(signature===crewChatSignature)return;
 crewChatSignature=signature;const log=el('crew-conversation'),follow=switched||log.scrollHeight-log.scrollTop-log.clientHeight<70,top=log.scrollTop;
 log.innerHTML=turns.length?turns.map(j=>{
 if(j.payload.collaboration)return i!==0&&j.payload.collaboration.origin?.role===i&&!j.payload.collaboration.handoffs?.[i]?collaborationHistoryMarkup(j):collaborationMarkup(j,i);
 const held=shieldReplyHeld(j,i),pending=['queued','running','waiting','stopping'].includes(j.status);
 const answer=j.direct?(j.result?.answer||j.result?.error||''):(j.payload.outputs?.[i]||j.payload.stageErrors?.[i]||(j.status==='error'&&Number(j.payload.stage)===i?j.result?.error:''));
 const webpage=!j.direct&&i===3&&j.payload.website?.authored?'<button class="studio-secondary" data-crew-webpage="'+escape(j.id)+'">Open webpage</button>':'';
 const social=!j.direct&&i===3&&j.payload.socialDraft?.status==='ready'?'<div class="chat-message chat-agent"><small>Morgan · LinkedIn draft · not published</small><div class="chat-prose">'+messageMarkup(j.payload.socialDraft.text)+'</div></div>':'';
 const handoffs=j.direct?'':crewHandoffMessages(j,i);
 const request=j.direct?(j.payload.prompt||'Describe the attached image.'):i===0?crewBriefMessage(j):'';
 const status={queued:'Waiting to start…',running:'Working on your message…',waiting:'Waiting for a decision.',stopping:'Stopping…',cancelled:'Stopped.',error:'This message could not finish.'}[j.status];
 return '<article class="chat-turn">'+(i!==0?handoffs:'')+(request?'<div class="chat-message chat-user"><small>You</small><div>'+escape(request).replace(/\n/g,'<br>')+imageHistoryMarkup(j.payload.images,j.id)+'</div></div>':'')+(held?'':social)+'<div class="chat-message chat-agent"><small>'+escape(name)+(j.direct?'':' · Event mission')+'</small>'+(held?shieldReplyWait:customSkillMarkup(j.direct?j.result?.activity:j.payload.activity?.[i])+'<div class="chat-prose">'+messageMarkup(answer||(!j.direct&&pending?(i===0?'Your event brief is with the crew.':(i===3&&j.payload.socialDraft?.status==='ready'?'LinkedIn draft ready. Writing the webpage…':'Working on the assigned task…')):status)||'No text reply was returned.')+'</div>'+crewActivityMarkup(j,i)+webpage+(j.direct?webpageButtons(j.result?.files,j.id):'')+(j.direct&&pending?'<div class="chat-progress"><button type="button" data-crew-chat-stop="'+escape(j.id)+'" '+(j.status==='stopping'?'disabled':'')+'>Stop</button></div>':''))+'</div>'+(i===0?handoffs+roundtableMarkup(j):'')+'</article>';
 }).join(''):'<p class="chat-empty">'+escape(currentCollaboration()?window.BacCrewCatalog[i].collaboration.description:roles[i][2])+'</p>';
 loadChatImages(log,agentId);
 if(follow)log.scrollTop=log.scrollHeight;else log.scrollTop=top;
}
el('crew-policy').onclick=()=>openPolicy(selectedCrewRole);
el('crew-chat').onsubmit=async e=>{
 e.preventDefault();syncCrewComposer();if(el('crew-send').disabled)return;
 const owner=agentId,index=selectedCrewRole,key=owner+':'+index,draft=captureChatDraft(true);
 crewChatSending=true;syncCrewComposer();el('crew-chat-error').hidden=true;
 try{const result=await api('jobs',{kind:'crew-chat',crewRole:index,prompt:draft.prompt,images:draft.images},owner);acknowledgeChatDraft(draft);await refresh();if(result.collaboration)stageCollaboration(result);}
 catch(error){if(crewChatKey===key){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}}
 finally{crewChatSending=false;syncCrewComposer();}
};
el('crew-prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!el('crew-send').disabled)el('crew-chat').requestSubmit(el('crew-send'));}});
el('crew-conversation').onclick=async e=>{const file=e.target.closest('[data-plan-file]');if(file){await openFile(file.dataset.planFile,file.dataset.planJob);return;}const page=e.target.closest('[data-crew-webpage]');if(page){selectedJob=page.dataset.crewWebpage;openSurface('deliverables','webpage');return;}const button=e.target.closest('[data-crew-chat-stop]');if(!button)return;try{await api('decision',{id:button.dataset.crewChatStop,action:'cancel'});await refresh();}catch(error){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}};

function roundtableMarkup(job){
 const meeting=job.payload.roundtable,plan=job.payload.collaboration;if((!meeting?.members?.length&&!meeting?.skipped?.length)||(plan&&(!plan.responseReady||plan.outcome==='unavailable')))return '';
 const intro=plan?'Personal reactions to the result, in each agent’s own voice. Opinions, not independent tests.':meeting.status==='invited'?'Your hired agents are joining the table. Their reactions follow the finished package.':'Personal reactions to this event · opinions, not independent tests.';
 return '<section class="crew-roundtable-log"><h4>Your agents’ take</h4><p>'+(meeting.members.length?intro:'No personal agents are joining this event.')+'</p>'+(meeting.skipped||[]).map(m=>'<p class="studio-muted" data-roundtable-skipped="'+escape(m.key)+'">'+escape(m.name)+' · Skipped: '+escape(m.detail)+'</p>').join('')+meeting.members.map(member=>{const reply=meeting.replies?.[member.key]||{},text=reply.answer||reply.error||((meeting.status==='cancelled'||job.status==='cancelled')?'Roundtable stopped before this reaction.':reply.status==='running'?'Considering the plan…':'Waiting for the results.');return '<article class="chat-message chat-agent" data-roundtable-reply="'+escape(member.key)+'"><small>'+escape(member.name)+' · '+escape(member.tonePrompt||member.tone||'')+'</small>'+customSkillMarkup(reply.activity)+'<div class="chat-prose">'+messageMarkup(text)+'</div>'+(reply.status==='error'&&job.status==='done'?'<button type="button" class="studio-secondary" data-retry-reaction="'+escape(member.key)+'" data-reaction-job="'+escape(job.id)+'">Retry this reaction</button>':'')+'</article>'}).join('')+'</section>';
}

root.addEventListener('click',async event=>{
 const button=event.target.closest('[data-retry-reaction]');if(!button)return;
 button.disabled=true;
 try{await api('retry-reaction',{id:button.dataset.reactionJob,member:button.dataset.retryReaction});await refresh();}
 catch(error){alert(error.message);button.disabled=false;}
});

el('crew-conversation').addEventListener('click',event=>{if(event.target.closest('[data-open-collaboration]'))showCollaboration();});
