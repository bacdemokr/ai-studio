function planNames(plan){return defaultNames.map((name,role)=>plan?.visitorBindings?.[role]?.name||name);}
function assignedVisitor(role){return selectedScenario==='plan'?currentCollaboration()?.payload.collaboration.visitorBindings?.[role]:null;}
function visitorAvailable(visitor){return !!visitor&&(data.agents||[]).some(agent=>agent.key===visitor.key&&!agent.deleting);}
// Each specialist has a durable direct conversation, separate from crew execution.
const defaultCrewPrompt=role=>selectedScenario==='plan'&&role===0?'/goal ':'';
const crewDrafts=new Map();let crewChatKey='',crewChatSignature='',crewChatSending=false,crewResetEpoch='';
// A fresh page starts with the built-in team; room changes keep the visitor's choice.
let openTaskTeamMode='builtin';
function taskTeamMode(job){return job?.payload.teamMode||(job?.payload.includeHiredAgents??!!job?.payload.roster?.length?'mixed':'builtin');}
function effectiveTeamMode(){const active=(data.crewChats||[]).find(j=>j.payload?.collaboration&&['queued','running','waiting','stopping'].includes(j.status));return active?taskTeamMode(active):openTaskTeamMode;}
el('crew-team-mode').onclick=event=>{const button=event.target.closest('[data-team-mode]');if(!button||button.disabled)return;openTaskTeamMode=button.dataset.teamMode;el('crew-chat-error').hidden=true;render();};
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
function webpageButtons(files,jobId){
 const pages=[...new Set(files||[])].filter(path=>/\.html$/i.test(path));
 return pages.length?'<div class="chat-webpages">'+pages.map((path,index)=>'<button type="button" class="studio-secondary" data-preview-file="'+escape(path)+'" data-preview-job="'+escape(jobId)+'">Preview webpage'+(pages.length>1?' '+(index+1):'')+' <span aria-hidden="true">↗</span></button>').join('')+'</div>':'';
}
root.addEventListener('click',event=>{const page=event.target.closest('[data-preview-file]');if(page)openFile(page.dataset.previewFile,page.dataset.previewJob);});
// The latest saved plan owns the visible team, including after a refresh.
async function stageCollaboration(job){
 if(selectedScenario!=='plan')await chooseScenario('plan');
 scenarioChoosing=false;render();showCollaboration();scenarioChoosing=false;renderRoomVisibility();
}
// Keep this visit’s chosen team visible until a newer plan or reset.
function currentCollaboration(){
 if(selectedScenario!=='plan')return null;
 const latest=(data.crewChats||[]).filter(j=>j.payload.collaboration&&j.created>=(data.crewChatReset?.at||0)).sort((a,b)=>b.created-a.created)[0];
 return latest||null;
}
// Mission Control can inspect saved plans without replaying their stage animation.
function missionControlPlan(){
 const latest=(data.crewChats||[]).filter(j=>j.payload.collaboration&&j.created>=(data.crewChatReset?.at||0)).sort((a,b)=>b.created-a.created)[0];
 return latest||null;
}
function renderStandbySpecialists(agents){
 const occupied=new Set(agents.flatMap((agent,i)=>agent.displayed&&!assignedVisitor(i)?[i]:[]));
 const available=window.BacCrewCatalog.map((member,role)=>({...member,roleIndex:role}))
  .filter(member=>member.planEligible!==false&&(effectiveTeamMode()!=='hired'||member.roleIndex===0));
 el('standby-count').textContent=String(available.length);
 const perAgent=data.teamConnection?.shared?data.teamConnection.effectiveSource==='api'&&runtime.modelConnections?.connections?.api?.provider==='nvidia':data.teamConnection?.provider!=='local'&&runtime.teamModel;
 const locked=modelPickerSaving||!teamRuntime().teamReady||data.bacResetting||(data.crewChats||[]).some(j=>['queued','running','waiting','stopping'].includes(j.status));
 const markup=available.map(member=>'<li data-standby-role="'+member.roleIndex+'"><div><strong>'+escape(member.name)+'</strong><span>'+escape(member.collaboration.title)+(occupied.has(member.roleIndex)?' · With team':'')+'</span></div>'+(perAgent?'<button type="button" class="studio-specialist-model specialist-model-edit" data-standby-model="'+member.roleIndex+'" aria-label="Change '+escape(member.name)+' model" '+(locked?'disabled':'')+'>':'<span class="studio-specialist-model">')+escape(teamModel(member.roleIndex)?.label||'Choose model')+(perAgent?' <span aria-hidden="true">⌕</span></button>':'</span>')+'<p class="studio-specialist-summary">'+escape(member.collaboration.summary||member.collaboration.description)+'</p></li>').join('');
 if(!el('standby-list').contains(document.activeElement)&&el('standby-list').innerHTML!==markup)el('standby-list').innerHTML=markup;
 if(el('standby').open)requestAnimationFrame(fitStandbyPanel);
}
const teamModelDialog=document.createElement('section');
teamModelDialog.hidden=true;
teamModelDialog.className='team-model-dialog';
teamModelDialog.setAttribute('aria-labelledby','team-model-heading');
teamModelDialog.innerHTML='<header><div><h3 id="team-model-heading">Choose a model</h3><p id="team-model-member"></p></div><button type="button" data-model-close>← Back</button></header><input type="search" aria-label="Search API models" placeholder="Search models or providers…" autocomplete="off"><p class="team-model-count" aria-live="polite"></p><div class="team-model-results"></div><p class="team-model-error" role="alert" hidden></p>';
// Open Task model choices save directly from the specialist list.
let modelPickerRole=0,modelPickerSaving=false,modelPickerDraft=null,modelPickerOwner=null,modelPickerScenario=null;
function renderModelResults(){
 teamModelDialog.querySelector('[data-model-close]').disabled=modelPickerSaving;
 teamModelDialog.querySelector('input').disabled=modelPickerSaving;
 const query=teamModelDialog.querySelector('input').value.trim().toLowerCase();
 const selected=modelPickerDraft;
 const models=(runtime.teamModels||[]).filter(m=>(m.id+' '+m.label).toLowerCase().includes(query));
 models.sort((a,b)=>Number(b.id===selected)-Number(a.id===selected));
 teamModelDialog.querySelector('.team-model-count').textContent=models.length?(models.length+' models'+(models.length>40?' · Showing the first 40. Refine your search.':'')):'No matching models';
 teamModelDialog.querySelector('.team-model-results').innerHTML=models.slice(0,40).map(m=>'<button type="button" data-model-choice="'+escape(m.id)+'" aria-pressed="'+(m.id===selected)+'" '+(modelPickerSaving?'disabled':'')+'><span><strong>'+escape(m.label.split('/').at(-1))+'</strong><small>'+escape(m.id)+'</small></span><span aria-hidden="true">'+(m.id===selected?'✓':'')+'</span></button>').join('');

}
root.addEventListener('click',event=>{
 const button=event.target.closest('[data-standby-model]');if(!button||button.disabled||modelPickerSaving||!teamModelDialog.hidden)return;
 modelPickerRole=Number(button.dataset.standbyModel);modelPickerDraft=teamModel(modelPickerRole)?.id;modelPickerOwner=agentId;modelPickerScenario=selectedScenario;
 teamModelDialog.querySelector('#team-model-member').textContent=defaultNames[modelPickerRole]+' · NVIDIA Inference';
 teamModelDialog.querySelector('input').value='';teamModelDialog.querySelector('.team-model-error').hidden=true;
 renderModelResults();
 dialog(defaultNames[modelPickerRole]+' · Model','');
 el('dialog-body').append(teamModelDialog);teamModelDialog.hidden=false;
 el('dialog').scrollTop=0;teamModelDialog.querySelector('.team-model-results').scrollTop=0;
 teamModelDialog.querySelector('input').focus({preventScroll:true});
});
teamModelDialog.querySelector('input').addEventListener('input',renderModelResults);
function closeTeamModelPicker(){
 if(modelPickerSaving)return;
 teamModelDialog.hidden=true;el('dialog').close();
}
teamModelDialog.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&!teamModelDialog.hidden){event.preventDefault();event.stopPropagation();closeTeamModelPicker();}
});
el('dialog').addEventListener('cancel',event=>{
 if(!teamModelDialog.hidden&&teamModelDialog.isConnected){event.preventDefault();closeTeamModelPicker();}
});
el('dialog').addEventListener('close',()=>{teamModelDialog.hidden=true;});
teamModelDialog.addEventListener('click',async event=>{
 if(event.target.closest('[data-model-close]')){closeTeamModelPicker();return;}
 if(modelPickerSaving)return;
 const choice=event.target.closest('[data-model-choice]');
 if(choice){
  modelPickerDraft=choice.dataset.modelChoice;
  if(agentId!==modelPickerOwner||selectedScenario!==modelPickerScenario){closeTeamModelPicker();return;}
  teamModelDialog.querySelector('.team-model-error').hidden=true;
  const pickerRevision=dialogRevision;
  const saved=await applyTeamModel();
  // The presenter may close this picker and open another dialog while saving.
  if(pickerRevision!==dialogRevision||teamModelDialog.hidden||!teamModelDialog.isConnected)return;
  if(saved)closeTeamModelPicker();else renderModelResults();return;
 }

});
async function applyTeamModel(){
 const target=modelPickerOwner,scenario=modelPickerScenario,role=modelPickerRole,model=modelPickerDraft;
 const current=()=>agentId===target&&selectedScenario===scenario;
 modelPickerSaving=true;
 if(!teamModelDialog.hidden)renderModelResults();
 try{
  const result=await api('team-model',{role,model},target);
  if(current()){
   // A poll started before this write must not restore the previous model.
   ++refreshVersion;stateCache.delete(target);busy=false;
   data={...data,teamSelections:result.teamSelections};render();
  }
  return true;
 }catch(error){
  if(current()&&!teamModelDialog.hidden){const notice=teamModelDialog.querySelector('.team-model-error');notice.textContent=error.message;notice.hidden=false;}
  else alert('Model changes could not be applied. '+error.message);
  return false;
 }finally{
  modelPickerSaving=false;render();
  if(!teamModelDialog.hidden)renderModelResults();
 }
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
 return [0,...new Set(selected.filter(role=>Number.isInteger(role)&&role>0&&defaultNames[role]&&window.BacCrewCatalog[role].planEligible!==false))];
}
function collaborationAnswer(job){return job.result?.answer||job.payload.collaboration.finalAnswer||'';}
// Wall-clock time includes queueing, planning, all specialists and final review.
function collaborationTime(job,now=Date.now()/1000){
 const active=['queued','running','waiting','stopping'].includes(job.status);
 const start=Number(job.created),end=active?now:Number(job.updated);
 if(!Number.isFinite(start)||!Number.isFinite(end)||start<=0||end<=0)return '';
 const seconds=Math.max(0,Math.floor(end-start)),hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60);
 const duration=hours?hours+'h '+minutes+'m '+seconds%60+'s':minutes?minutes+'m '+seconds%60+'s':seconds+'s';
 return (active?'Total elapsed: ':'Total time: ')+duration;
}
function collaborationTimeMarkup(job){
 const label=collaborationTime(job);
 return label?'<p class="mission-plan-inputs" data-plan-total="'+escape(job.id)+'" title="From submission to completion, including queueing, planning, specialists and review.">'+escape(label)+'</p>':'';
}
function missionControlTraceMarkup(job){
 const defaultNames=planNames(job.payload.collaboration);
 const plan=job.payload.collaboration,active=['queued','running','waiting','stopping'].includes(job.status),tasks=plan.tasks||[],checks=plan.checks||[];
 let sequence=-1;
 const row=(kind,name,status,content,attrs='',recorded=true,state='')=>'<article class="mission-plan-step" data-trace-key="'+escape(kind+':'+attrs)+'" data-trace-kind="'+kind+'" data-step-state="'+state+'" '+attrs+'><header><small>'+(recorded?String(++sequence).padStart(2,'0')+' · '+({plan:'PLAN',contribution:'CONTRIBUTION',review:'REVIEW',revision:'REVISION REQUEST','revision-work':'REVISION',response:'RESPONSE',stopped:'STOPPED'}[kind]||kind.toUpperCase()):kind==='skipped'?'NOT CALLED':'PLANNED')+'</small><h4>'+escape(name)+'</h4><span>'+escape(status)+'</span></header><div class="mission-plan-content">'+content+'</div></article>';
 const detail=(key,label,content)=>'<details class="mission-trace-detail" data-trace-details="'+key+'"><summary>'+escape(label)+'</summary><div class="chat-prose">'+content+'</div></details>';
 const question=String(plan.task||job.payload.prompt||'').replace(/^\s*\/(?:goals?|plans?)(?=\s|$)/i,'').trim();
 let markup=row('user','User','Submitted','<strong>Request</strong><div class="chat-prose">'+messageMarkup(question)+'</div>','',true,'done');
 markup+=row('plan','Casey',plan.summary?'Plan ready':active?'Planning':'No plan saved','<strong>Approach</strong><div>'+messageMarkup(plan.summary||(active?'Casey is deciding which expertise this request needs.':'No plan was saved before the work stopped.'))+'</div>','data-plan-role="0"',true,plan.summary?'done':active?'working':'');
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
 else if(!active)markup+=row('stopped','Casey',job.status==='cancelled'?'Stopped':'Error','<div>'+messageMarkup(job.result?.error||(job.status==='cancelled'?'The work stopped before a final response was ready.':'No final response was saved.'))+'</div>');
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
 if(selectedScenario==='event-brief')return;
 const job=missionControlPlan(),intro=el('board').querySelector('.studio-board-intro');
 el('lanes').classList.toggle('studio-plan-control',!!job);
 el('board').classList.toggle('has-plan',!!job);
 intro.querySelector('h3').textContent=job?'Execution trace':'No active plan';
 intro.querySelector('[data-mission-total]').textContent=job?collaborationTime(job):'';
 intro.querySelector('p').textContent=job?job.payload.collaboration.task:'Send /goal to Casey to start.';
 if(!job){el('lanes').innerHTML='';delete el('lanes').dataset.traceJob;delete el('lanes')._traceMarkup;return;}
 updateMissionControlTrace(el('lanes'),job.id,missionControlTraceMarkup(job));
}
// /goal is a real Captain-led job; contributions come from completed model calls.
function collaborationRevisionBody(revision,jobId){
 return '<strong>Casey’s revision assignment</strong><div>'+messageMarkup(revision.task)+'</div><div class="mission-expectation"><small>Expected result</small>'+messageMarkup(revision.expected)+'</div>'+(revision.output?'<details class="mission-trace-detail" data-trace-details="revision-output"><summary>Revised contribution</summary><div class="chat-prose">'+messageMarkup(revision.output.answer)+'</div>'+webpageButtons(revision.output.files,jobId)+collaborationFileButtons(revision.output.files,jobId)+'</details>':'')+(revision.status==='failed'?'<p>The revision did not finish. Previous contributions are preserved.</p>':'');
}
function collaborationRevisionMarkup(job){
 const defaultNames=planNames(job.payload.collaboration);
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
 const defaultNames=planNames(plan);
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
 const defaultNames=planNames(plan);
 const activity=plan.liveActivity;
 if(!activity||(role!==0&&role!==activity.role))return '';
 const labels={web_fetch:'Read webpage',web_search:'Search web',read:'Read file',write:'Save file',edit:'Edit file',apply_patch:'Update files',exec:'Run tool',tool:'Tool call'};
 const statuses={started:'Started',running:'Running',completed:'Completed',failed:'Failed'};
 const busy=activity.calls.some(call=>['started','running'].includes(call.status));
 const waiting=!activity.available?'Waiting for runtime activity':busy?'Waiting for tool completion':'Waiting for agent response';
 return '<section class="plan-live-activity" aria-label="Observed activity"><strong>'+escape(defaultNames[activity.role])+' · Live activity</strong><ol>'+activity.calls.map(call=>'<li data-activity-status="'+escape(call.status)+'"><span>'+escape(labels[call.tool]||'Tool call')+(call.target?' · '+escape(call.target):'')+'</span><small>'+escape((statuses[call.status]||'Started')+(call.status==='failed'&&call.errorLabel?' ('+call.errorLabel+')':''))+'</small></li>').join('')+'</ol><p>'+waiting+' · '+'<span data-plan-elapsed="'+escape(jobId)+'">'+Number(activity.elapsed)+'</span>s since request</p></section>';
}
function collaborationMarkup(job,role){
 const defaultNames=planNames(job.payload.collaboration);
 const plan=job.payload.collaboration,pending=['queued','running','waiting','stopping'].includes(job.status);
 const held=shieldReplyHeld(job,role),piece=plan.outputs?.[role],captain=role===0;
 const finalAnswer=collaborationAnswer(job),answer=captain?(finalAnswer||job.result?.error||''):piece?.answer||'';
 const uncalled=!captain&&!piece&&!plan.handoffs?.[role]&&(!pending||plan.responseReady||plan.skippedRoles?.includes(role));
 const status=uncalled?'Casey did not call '+defaultNames[role]+' for this plan.':job.status==='queued'?'Queued - waiting for current studio work to finish.':job.status==='cancelled'?'Stopped.':job.status==='stopping'?'Stopping after the current call…':job.events?.at(-1)?.title||'Waiting for the Captain…';
 const summary=captain&&plan.summary?'<div class="chat-message chat-handoff"><small>Captain’s plan</small><div class="chat-prose">'+messageMarkup(plan.summary)+'</div><ol>'+plan.tasks.map(t=>'<li><strong>'+escape(defaultNames[t.role])+' · '+escape(window.BacCrewCatalog[t.role].collaboration.title)+'</strong>: '+escape(t.task)+(plan.skippedRoles?.includes(t.role)?' <small>Not called - '+(plan.outcome==='partial'?'plan ended with unfinished work':plan.outcome==='unavailable'?'required expertise unavailable':'no longer needed')+'</small>':'')+'</li>').join('')+'</ol></div>':'';
 const outputRoles=collaborationRoleOrder(plan).filter(i=>plan.outputs?.[i]);
 const contributions=captain?outputRoles.map(i=>{const p=plan.outputs[i];return '<details class="crew-tool-activity" data-contribution-role="'+i+'"><summary>'+escape(p.name)+' · Contribution</summary>'+customSkillMarkup(p.activity)+'<div class="chat-prose">'+messageMarkup(p.answer)+'</div>'+collaborationFileButtons(p.files,job.id)+'</details>'+collaborationDecisionMarkup({...plan,checks:(plan.checks||[]).filter(check=>!check.afterRevision&&Number(check.afterRole)===i)});}).join(''):'';
 const handoff=!captain&&plan.handoffs?.[role]?'<div class="chat-message chat-handoff"><small>Casey → '+escape(defaultNames[role])+'</small><div class="chat-prose">'+messageMarkup(plan.handoffs[role].task)+'</div><small>Received: '+escape(['Captain’s task',...plan.handoffs[role].receivedFrom.map(i=>defaultNames[Number(i)]+"’s contribution")].join(' · '))+'</small></div>':'';
 return '<article class="chat-turn" data-collaboration-job="'+escape(job.id)+'">'+(captain||plan.origin?.role===role?'<div class="chat-message chat-user"><small>You</small><div>'+escape(job.payload.prompt).replace(/\n/g,'<br>')+imageHistoryMarkup(job.payload.images,job.id)+'</div></div>':'')+(captain?collaborationTimeMarkup(job):'')+(held?shieldReplyWait:summary+handoff+contributions+livePlanActivityMarkup(plan,role,job.id)+(captain?collaborationRevisionMarkup(job):'')+(captain&&!outputRoles.length?collaborationDecisionMarkup(plan):'')+'<div class="chat-message chat-agent"><small>'+escape(defaultNames[role])+' · '+(captain?'BaC collaboration':'Specialist contribution')+'</small><div class="chat-prose">'+messageMarkup(answer||status)+'</div>'+(captain?collaborationCompletionMarkup(plan,finalAnswer):'')+'</div>')+(!held&&!captain&&plan.revision?.role===role?collaborationRevisionMarkup(job):'')+(pending?'<div class="chat-progress" role="status">'+escape(status)+(job.status!=='stopping'?chatStopButton(job.id,true,false,plan.responseReady?'Stop reactions':'Stop'):'')+'</div>':'')+(held?'':webpageButtons(captain?Object.values(plan.webpages||{}).flat():piece?.files,job.id))+(!held?collaborationFileButtons(captain?(job.result?.files||[]).filter(path=>path==='artifacts/plan-'+job.id+'.md'):piece?.files,job.id,captain?'Open team response':'Open supporting file'):'')+(captain&&!held?roundtableMarkup(job):'')+'</article>';
}
function collaborationHistoryMarkup(job){
 const held=shieldReplyHeld(job,0),pending=['queued','running','waiting','stopping'].includes(job.status);
 const answer=collaborationAnswer(job)||job.result?.error||(pending?'The BaC team is collaborating…':job.status==='cancelled'?'Stopped.':'No final reply was returned.');
 return '<article class="chat-turn" data-collaboration-history="'+escape(job.id)+'"><div class="chat-message chat-user"><small>You</small><div>'+messageMarkup(job.payload.prompt)+'</div></div><div class="chat-message chat-agent"><small>Casey · BaC collaboration</small>'+collaborationTimeMarkup(job)+(held?shieldReplyWait:'<div class="chat-prose">'+messageMarkup(answer)+'</div>'+collaborationCompletionMarkup(job.payload.collaboration,collaborationAnswer(job)))+(held?'':collaborationDecisionMarkup(job.payload.collaboration)+webpageButtons(job.result?.files||Object.values(job.payload.collaboration.webpages||{}).flat(),job.id))+'<button type="button" class="studio-secondary" data-open-collaboration>View team conversation</button></div></article>';
}
function showCollaboration(){selectedCrewRole=0;setRoom('mission');root.dataset.crewDetails='true';renderCrewPassport();}
function teamRuntime(){if(data.teamConnection?.shared)return {...runtime,teamModel:data.teamConnection.ready,teamReady:data.teamConnection.ready&&!!runtime.gateway};return data.teamConnection?.provider==='local'?{...runtime,teamModel:!!data.teamConnection.local?.model,teamReady:!!data.teamConnection.local?.model&&!!runtime.gateway}:runtime;}
function teamReady(){return teamRuntime().teamReady??runtime.ready;}
function teamModel(role){if(data.teamConnection?.shared){const source=data.teamConnection.effectiveSource,connections=runtime.modelConnections?.connections;if(selectedScenario==='event-brief'||source==='local'||connections?.api?.provider!=='nvidia'){const id=data.teamConnection.model;return id?{id,label:id}:null;}}if(data.teamConnection?.provider==='local'){const id=data.teamConnection.local?.model;return id?{id,label:id}:null;}const id=data.teamSelections?.find(row=>row.role===role)?.id;return runtime.teamModels?.find(model=>model.id===id)||(id?{id,label:id}:runtime.teamModels?.[[0,5,7].includes(role)?0:1]);}
let crewDocumentUpload=false;
const crewDocumentSelections=new Map();
function excludedCrewDocuments(){
 const epoch=data.crewChatReset?.epoch||'';
 let selection=crewDocumentSelections.get(selectedScenario);
 if(!selection||selection.epoch!==epoch){selection={epoch,excluded:new Set()};crewDocumentSelections.set(selectedScenario,selection);}
 return selection.excluded;
}
function renderCrewDocuments(){
 const files=data.crewDocuments||[],paths=new Set(files.map(f=>f.path)),excluded=excludedCrewDocuments();
 const docs=files.filter(f=>/\.(pdf|pptx|xlsx|txt|md|csv)$/i.test(f.path)&&!/^(?:plan-input|plan|chat)-[0-9a-f]{24}(?:-|\.)/.test(f.path.split('/').at(-1))&&!(/\.(pdf|pptx|xlsx)\.txt$/i.test(f.path)&&paths.has(f.path.slice(0,-4))));
 const box=el('crew-documents');box.hidden=selectedCrewRole!==0||(!docs.length&&!crewDocumentUpload);
 box.innerHTML=docs.map(f=>'<label><input type="checkbox" data-crew-document="'+escape(f.path)+'" '+(excluded.has(f.path)?'':'checked')+' '+(crewDocumentUpload?'disabled':'')+'><span>'+escape(f.path.slice(6))+'</span></label>').join('')+(crewDocumentUpload?'<small role="status">Adding document…</small>':'');
 return docs.filter(f=>!excluded.has(f.path));
}
el('crew-documents').addEventListener('change',event=>{const path=event.target.dataset.crewDocument;if(path){const excluded=excludedCrewDocuments();if(event.target.checked)excluded.delete(path);else excluded.add(path);}});
el('crew-document-add').onclick=()=>el('crew-document-input').click();
el('crew-document-input').onchange=async event=>{await uploadCrewDocuments([...event.target.files]);event.target.value='';};
async function uploadCrewDocuments(files){
 if(selectedCrewRole!==0||crewDocumentUpload||el('crew-document-add').disabled)return;
 const target=agentId;crewDocumentUpload=true;syncCrewComposer();renderCrewDocuments();
 try{
  for(const file of files){
   if(file.size>10*1024*1024)throw new Error(file.name+': Choose a file of 10 MB or smaller.');
   const binary=/\.(pdf|pptx|xlsx)$/i.test(file.name);let content;
   if(binary){const bytes=new Uint8Array(await file.arrayBuffer());let raw='';for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));content=btoa(raw);}
   else content=await documentText(file);
   await api('upload',{crewRole:0,name:file.name,content,...(binary?{encoding:'base64'}:{})},target);
  }
  await refresh();
 }catch(error){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}
 finally{crewDocumentUpload=false;syncCrewComposer();renderCrewDocuments();}
}
for(const type of ['dragover','drop'])el('crew-chat').addEventListener(type,event=>{
 if(![...event.dataTransfer.types].includes('Files')||selectedCrewRole!==0)return;
 event.preventDefault();if(type==='drop')uploadCrewDocuments([...event.dataTransfer.files]);
});
function syncCrewComposer(){
 const activePlan=(data.crewChats||[]).find(j=>j.payload?.collaboration&&['queued','running','waiting','stopping'].includes(j.status));
 const captainPlanning=selectedCrewRole===0&&!!activePlan;
 const visitor=assignedVisitor(selectedCrewRole);
 const visitorMissing=visitor&&!visitorAvailable(visitor);
 const memberWorking=!!visitor&&(data.agents||[]).some(a=>a.key===visitor.key&&a.pending>0)||(data.crewChats||[]).some(j=>['queued','running','waiting','stopping'].includes(j.status)&&(j.payload?.collaboration?(['running','stopping'].includes(j.status)&&j.payload.collaboration.activeRole===selectedCrewRole):j.payload?.crewRole===selectedCrewRole));
 const eventWorking=eventTeamWorking(['crew']);
 const eventPreparing=selectedScenario==='event-brief'&&['queued','running','stopping'].includes(data.preparation?.status);
 const blocked=scenarioChoosing||scenarioSwitching||visitorMissing||(visitor?!personalReady(visitor):!teamReady())||!!visitor?.skills?.includes('radar')||!!data.bacResetting||captainPlanning||memberWorking||eventWorking||eventPreparing||crewDocumentUpload;
 el('crew-document-add').hidden=selectedCrewRole!==0||selectedScenario==='event-brief';el('crew-document-add').disabled=blocked;
 renderCrewDocuments();
 const commandOnly=selectedScenario==='plan'&&selectedCrewRole===0&&/^\s*\/(?:goals?|plans?)\s*$/i.test(el('crew-prompt').value);
 el('crew-prompt').disabled=blocked;el('crew-send').disabled=blocked||crewChatSending||commandOnly;
 el('crew-hired-option').hidden=selectedScenario!=='plan'||selectedCrewRole!==0;
 const teamMode=effectiveTeamMode(),teamLocked=!!activePlan||crewChatSending||!!data.bacResetting||scenarioSwitching||scenarioChoosing;
 el('crew-team-mode').querySelectorAll('[data-team-mode]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.teamMode===teamMode));button.disabled=teamLocked;});
 const noHires=teamMode==='hired'&&!(data.agents||[]).some(a=>!a.deleting);
 el('crew-team-hint').hidden=!noHires;el('crew-team-hint').textContent=noHires?'Hire a Coder or Web researcher to get started.':'';
 el('crew-chat-connection').hidden=!blocked;
 el('crew-chat-connection').textContent=visitorMissing?'This agent was removed. Start a new task with Casey.':visitor?.skills?.includes('radar')?'Tech Radar uses Heartbeat. Manual chat is disabled.':crewDocumentUpload?'Adding document…':data.bacResetting?'Stopping '+(stageScenarios.find(s=>s.id===selectedScenario)?.title||'the scenario')+' and resetting…':eventWorking?'Event plan in progress. Messaging resumes when the team finishes.':eventPreparing?'Preparing the Event Brief team…':captainPlanning?'Plan in progress · Casey is coordinating the team. Messaging resumes when the plan ends.':memberWorking?'Task in progress · Messaging resumes when this agent finishes.':!(visitor?personalModel(visitor).connected:(teamRuntime().teamModel??runtime.model))?(visitor?personalModelNotice(visitor):'Model not connected. Enable Local or External Endpoint in Settings.'):'Run ./bac start on this computer to connect the team runtime.';
}
function renderCrewPassport(){
 syncFileButtons();
 const epoch=selectedScenario+':'+(data.crewChatReset?.epoch||'');
 if(epoch!==crewResetEpoch){
  const resetChanged=crewResetEpoch.split(':')[0]===selectedScenario;crewResetEpoch=epoch;if(resetChanged){if(selectedScenario==='plan')openTaskTeamMode='builtin';for(const key of crewDrafts.keys())if(key.startsWith(selectedScenario+':'))crewDrafts.delete(key);}crewChatKey='';crewChatSignature='';el('crew-prompt').value=defaultCrewPrompt(selectedCrewRole);
  for(const key of chatImageDrafts.keys())if(key.includes(':crew:')&&key.includes(':'+selectedScenario+':'))chatImageDrafts.delete(key);
 }
 if(room!=='mission')return;
 if(selectedScenario==='event-brief')return renderEventCrewPassport();
 const i=selectedCrewRole,visitor=assignedVisitor(i),name=visitor?.name||defaultNames[i],role=window.BacCrewCatalog[i].collaboration.title;
 const avatar=visitor?.avatar||window.BacCampus?.inspect().crewAvatars?.[i]||{};
 el('crew-number').textContent=String(i+1).padStart(2,'0')+' / '+roles.length;
 el('crew-name').textContent=name;syncTeamTotalTime();el('crew-role').textContent=role;
 const model=visitor?personalModel(visitor):teamModel(i);el('crew-model').textContent=model?.label||'';el('crew-model').title=model?.id||'';el('crew-model').hidden=!model;
 const portrait=el('crew-portrait');portrait.dataset.body=avatar.body||'classic';portrait.dataset.accessory=avatar.accessory||'antenna';portrait.style.setProperty('--avatar-accent',appearanceColors[avatar.color]||appearanceColors.green);
 const skills=[];
 const skillLabels={...titles,'event-tools':'Event tools','event-scheduling':'Presenter scheduling'};
 el('crew-policy').hidden=(visitor&&!visitorAvailable(visitor))||(visitor?.protection||window.BacCrewCatalog[i].protection)!=='openshell';
 syncPolicyBadges();
 const markup=skills.map(s=>'<span>'+escape(skillLabels[s]||s)+'</span>').join('');if(el('crew-skills').innerHTML!==markup)el('crew-skills').innerHTML=markup;
 const key=crewDraftKey(i),switched=key!==crewChatKey;
 if(switched){if(crewChatKey)crewDrafts.set(crewChatKey,el('crew-prompt').value);crewChatKey=key;el('crew-prompt').value=crewDrafts.get(key)??defaultCrewPrompt(i);el('crew-chat-error').hidden=true;}
 renderImageDrafts(true);
 el('crew-prompt').placeholder='Message '+name+'…'+(i===0?' or /goal a task with the BaC team':'');
 el('crew-prompt').dataset.planEnabled=String(i===0);syncCrewComposer();
 const turns=(data.crewChats||[]).filter(j=>j.payload.crewRole===i||(j.payload.collaboration&&(j.payload.collaboration.origin?.role===i||j.payload.collaboration.handoffs?.[i]||j.payload.collaboration.tasks?.some(t=>t.role===i)||j.payload.collaboration.activeRole===i))).map(j=>({...j,direct:true}));
 turns.sort((a,b)=>a.created-b.created);
 const signature=JSON.stringify([key,[...pendingChatStops],turns.map(j=>[j.id,j.status,j.result,j.payload.collaboration?.liveActivity?{...j.payload.collaboration,liveActivity:{...j.payload.collaboration.liveActivity,elapsed:0}}:j.payload.collaboration,j.events?.at(-1),shieldReplyHeld(j,i)])]);
 for(const job of turns){const total=el('crew-conversation').querySelector('[data-plan-total="'+job.id+'"]');if(total)total.textContent=collaborationTime(job);const timer=el('crew-conversation').querySelector('[data-plan-elapsed="'+job.id+'"]');if(timer&&job.payload.collaboration?.liveActivity)timer.textContent=Number(job.payload.collaboration.liveActivity.elapsed);}
 if(signature===crewChatSignature)return;
 crewChatSignature=signature;const log=el('crew-conversation'),follow=switched||log.scrollHeight-log.scrollTop-log.clientHeight<70,top=log.scrollTop;
 log.innerHTML=turns.length?turns.map(j=>{
 if(j.payload.collaboration)return i!==0&&j.payload.collaboration.origin?.role===i&&!j.payload.collaboration.handoffs?.[i]?collaborationHistoryMarkup(j):collaborationMarkup(j,i);
 const held=shieldReplyHeld(j,i),pending=['queued','running','waiting','stopping'].includes(j.status);
 const answer=j.result?.answer||j.result?.error||'';
 const request=j.payload.prompt||'Describe the attached image.';
 const status={queued:'Waiting to start…',running:'Working on your message…',waiting:'Waiting for a decision.',stopping:'Stopping…',cancelled:'Stopped.',error:'This message could not finish.'}[j.status];
 return '<article class="chat-turn"><div class="chat-message chat-user"><small>You</small><div>'+escape(request).replace(/\n/g,'<br>')+imageHistoryMarkup(j.payload.images,j.id)+'</div></div><div class="chat-message chat-agent"><small>'+escape(name)+'</small>'+(held?shieldReplyWait:customSkillMarkup(j.result?.activity)+'<div class="chat-prose">'+messageMarkup(answer||status||'No text reply was returned.')+'</div>'+crewActivityMarkup(j,i)+webpageButtons(j.result?.files,j.id)+(pending?'<div class="chat-progress">'+chatStopButton(j.id,true,j.status==='stopping')+'</div>':''))+'</div>'+(i===0?roundtableMarkup(j):'')+'</article>';
 }).join(''):'<p class="chat-empty">'+escape(currentCollaboration()?window.BacCrewCatalog[i].collaboration.description:roles[i][2])+'</p>';
 loadChatImages(log,agentId);
 if(follow)log.scrollTop=log.scrollHeight;else log.scrollTop=top;
}
el('crew-policy').onclick=async()=>{const visitor=assignedVisitor(selectedCrewRole);if(visitor){await switchAgent(visitor.key);if(agentId===visitor.key)openPolicy();}else openPolicy(selectedCrewRole);};
el('crew-chat').onsubmit=async e=>{
 e.preventDefault();syncCrewComposer();if(el('crew-send').disabled)return;
 const owner=agentId,index=selectedCrewRole,key=crewDraftKey(index),draft=captureChatDraft(true),teamChoice=openTaskTeamMode;
 if(isPlanCommand(draft.prompt)&&(selectedScenario!=='plan'||index!==0)){
  el('crew-chat-error').textContent=selectedScenario==='event-brief'?eventPlanLocationHint:planLocationHint;
  el('crew-chat-error').hidden=false;return;
 }
 let requestPrompt=draft.prompt;
 if(index===0){const docs=renderCrewDocuments();if(docs.length)requestPrompt+='\n\nAttached documents (use these files):\n'+docs.map(f=>f.path.slice(6)).join('\n');}
 crewChatSending=true;syncCrewComposer();el('crew-chat-error').hidden=true;
 try{const visitor=assignedVisitor(index);const result=await api('jobs',visitor?{kind:'chat',prompt:requestPrompt,images:draft.images}:{kind:'crew-chat',crewRole:index,prompt:requestPrompt,images:draft.images,...(selectedScenario==='plan'&&index===0&&isPlanCommand(draft.prompt)?{teamMode:teamChoice}:{})},visitor?.key||owner);acknowledgeChatDraft(draft);if(visitor){await switchAgent(visitor.key);setRoom('lounge');}await refresh();if(result.collaboration)stageCollaboration(result);}
 catch(error){if(crewChatKey===key){el('crew-chat-error').textContent=error.message;el('crew-chat-error').hidden=false;}}
 finally{crewChatSending=false;syncCrewComposer();}
};
el('crew-prompt').addEventListener('input',()=>{clearPlanLocationHint(true);syncCrewComposer();});
el('crew-prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!el('crew-send').disabled)el('crew-chat').requestSubmit(el('crew-send'));}});
el('crew-conversation').onclick=async e=>{const file=e.target.closest('[data-plan-file]');if(file){await openFile(file.dataset.planFile,file.dataset.planJob);return;}const button=e.target.closest('[data-crew-chat-stop]');if(!button||button.disabled)return;await stopChat(button.dataset.crewChatStop,true);};

function roundtableMarkup(job){
 const meeting=job.payload.roundtable,plan=job.payload.collaboration;if((!meeting?.members?.length&&!meeting?.skipped?.length)||(plan&&(!plan.responseReady||plan.outcome==='unavailable')))return '';
 const intro=plan?'Personal reactions, not independent reviews.':meeting.status==='invited'?'Your agents will react when the results are ready.':'Personal reactions, not independent reviews.';
 return '<section class="crew-roundtable-log"><h4>Your agents’ take</h4><p>'+(meeting.members.length?intro:'No personal agents are joining this event.')+'</p>'+(meeting.skipped||[]).map(m=>'<p class="studio-muted" data-roundtable-skipped="'+escape(m.key)+'">'+escape(m.name)+' · Skipped: '+escape(m.detail)+'</p>').join('')+meeting.members.map(member=>{const reply=meeting.replies?.[member.key]||{},text=reply.answer||reply.error||reply.reason||meeting.reason||((meeting.status==='cancelled'||job.status==='cancelled')?'Roundtable stopped before this reaction.':['done','error'].includes(job.status)?'No personal reaction was recorded for this completed task.':reply.status==='running'?'Considering the plan…':'Waiting for the results.');return '<article class="chat-message chat-agent" data-roundtable-reply="'+escape(member.key)+'"><small>'+escape(member.name)+' · '+escape(member.tonePrompt||member.tone||'')+'</small>'+customSkillMarkup(reply.activity)+'<div class="chat-prose">'+messageMarkup(text)+'</div>'+(reply.status==='error'&&job.status==='done'?'<button type="button" class="studio-secondary" data-retry-reaction="'+escape(member.key)+'" data-reaction-job="'+escape(job.id)+'">Retry this reaction</button>':'')+'</article>'}).join('')+'</section>';
}

root.addEventListener('click',async event=>{
 const button=event.target.closest('[data-retry-reaction]');if(!button)return;
 button.disabled=true;
 try{await api('retry-reaction',{id:button.dataset.reactionJob,member:button.dataset.retryReaction});await refresh();}
 catch(error){alert(error.message,'error');button.disabled=false;}
});

el('crew-conversation').addEventListener('click',event=>{if(event.target.closest('[data-open-collaboration]'))showCollaboration();});
