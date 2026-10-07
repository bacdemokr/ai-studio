// Keep live panels (and their event handlers) inside the fullscreen root.
const surfaceStore=document.createElement('div');surfaceStore.id='studio-surface-store';surfaceStore.hidden=true;root.append(surfaceStore);
const surfaceDialog=document.createElement('dialog');surfaceDialog.id='studio-surface';surfaceDialog.setAttribute('aria-labelledby','studio-surface-title');
surfaceDialog.innerHTML='<header><h2 id="studio-surface-title"></h2><button type="button" class="studio-secondary" id="studio-surface-close" aria-label="Close panel">×</button></header><div id="studio-surface-body"></div>';
root.append(surfaceDialog);
let activeSurface=null;
const planResults=document.createElement('section');planResults.id='studio-plan-results';planResults.className='studio-plan-results';planResults.hidden=true;surfaceStore.append(planResults);
planResults.onclick=event=>{const file=event.target.closest('[data-plan-file]');if(file)openFile(file.dataset.planFile,file.dataset.planJob);};
function renderPlanResults(job){
 if(!job){planResults.innerHTML='';delete planResults.dataset.key;return;}
 const plan=job.payload.collaboration,answer=collaborationAnswer(job);
 const total=planResults.querySelector('[data-plan-total]');if(total)total.textContent=collaborationTime(job);
 const files=[...new Set([...(job.result?.files||[]),...Object.values(plan.webpages||{}).flat(),...Object.values(plan.outputs||{}).flatMap(output=>output.files||[]),...(plan.revision?.output?.files||[])])];
 const key=JSON.stringify([job.id,job.status,answer,files,plan]);
 if(planResults.dataset.key===key)return;
 planResults.dataset.key=key;
 const status=['queued','running','waiting','stopping'].includes(job.status)?'Work is in progress. Saved results appear here as the team finishes.':job.status==='error'?'This request did not finish. Any saved files are available below.':'No final response was saved for this request.';
 planResults.innerHTML='<h3>Team results</h3>'+collaborationTimeMarkup(job)+'<p>'+escape(plan.task||job.payload.prompt||'')+'</p><div class="chat-prose">'+messageMarkup(answer||status)+'</div>'+collaborationCompletionMarkup(plan,answer)+webpageButtons(files,job.id)+collaborationFileButtons(files,job.id,'Open saved file');
}

const surfaceDefinitions={
  missions:{title:'Try a mission',ids:['experiences']},
  results:{title:'Results & files',ids:['workspace']},
  compare:{title:'Agent comparison',ids:['compare']},
  policies:{title:'OpenShell Policy',ids:['policy-panel']},
  control:{title:'Mission Control',ids:['board']},
  deliverables:{title:'Results',ids:['plan-results']}
};
for(const id of ['event-package','board','workspace','experiences','policy-panel','connections'])surfaceStore.append(el(id));
el('passport').prepend(el('collection'));
el('collection-note').hidden=true;
const loungeActions=document.createElement('div');loungeActions.className='studio-panel-actions';loungeActions.innerHTML='<button type="button" class="studio-secondary" id="studio-compare-open" data-surface="compare" hidden>Compare replies</button>';
el('passport').append(loungeActions);
for(const node of [el('companion').querySelector('.studio-agent-extras'),el('companion').querySelector('.studio-native-note')])surfaceStore.append(node);
const crewActions=document.createElement('div');crewActions.className='studio-team-actions';crewActions.setAttribute('aria-label','Team actions');
el('crew-passport').prepend(crewActions);crewActions.append(el('room-action'));el('room-action').classList.add('studio-team-start');
el('crew-passport').append(document.getElementById('campus-roster'));
const controlButton=document.createElement('button');controlButton.type='button';controlButton.className='studio-secondary';controlButton.dataset.surface='control';controlButton.textContent='Mission Control';crewActions.append(controlButton);
const teamResetButton=document.createElement('button');teamResetButton.type='button';teamResetButton.id='studio-bac-reset';teamResetButton.className='studio-team-utility';teamResetButton.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 7a6 6 0 1 1-.2 5M4 3v4h4"/></svg><span>Reset</span>';teamResetButton.setAttribute('aria-label','Reset current scenario');teamResetButton.title='Stop this scenario’s work and clear its chats, documents and results';teamResetButton.onclick=()=>confirmTeamReset(teamResetButton);
const teamResetStatus=document.createElement('p');teamResetStatus.id='studio-team-reset-status';teamResetStatus.className='studio-muted';teamResetStatus.setAttribute('role','status');teamResetStatus.hidden=true;crewActions.after(teamResetStatus);
const resultsButton=document.createElement('button');resultsButton.type='button';resultsButton.className='studio-secondary';resultsButton.dataset.surface='deliverables';resultsButton.textContent='Results';resultsButton.hidden=true;crewActions.append(resultsButton);
const teamTotalTime=document.createElement('div');teamTotalTime.id='studio-team-total-time';teamTotalTime.hidden=true;teamTotalTime.setAttribute('role','timer');teamTotalTime.title='Total process time, including queueing, planning, specialists and review';el('crew-name').parentElement.classList.add('studio-captain-heading');el('crew-name').after(teamTotalTime);
const teamConnectionBar=document.createElement('div');teamConnectionBar.className='studio-team-connection-bar';teamConnectionBar.innerHTML='<span class="studio-team-connection-state" role="status"><i aria-hidden="true"></i><span id="studio-team-connection-label">Team API</span></span><div class="studio-team-utilities"><button type="button" class="studio-team-utility" id="studio-team-setup" aria-haspopup="dialog"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 6h3m4 0h7M3 14h7m4 0h3"/><circle cx="8" cy="6" r="2"/><circle cx="12" cy="14" r="2"/></svg><span>API &amp; models</span></button></div>';teamConnectionBar.querySelector('.studio-team-utilities').append(teamResetButton);crewActions.after(teamConnectionBar);el('team-setup').onclick=openTeamSettings;
const standbyPanel=document.createElement('details');standbyPanel.id='studio-standby';
standbyPanel.innerHTML='<summary>Standby specialists <span id="studio-standby-count"></span></summary><div class="studio-standby-content"><ul id="studio-standby-list"></ul></div>';
teamConnectionBar.after(standbyPanel);
function fitStandbyPanel(){
 if(!standbyPanel.open)return;
 const top=standbyPanel.querySelector('.studio-standby-content').getBoundingClientRect().top;
 const composer=el('crew-chat').getBoundingClientRect();
 standbyPanel.style.setProperty('--standby-space',Math.max(60,Math.min(340,composer.top-top-12))+'px');
}
standbyPanel.addEventListener('toggle',fitStandbyPanel);
window.addEventListener('resize',fitStandbyPanel);
// Capture outside clicks even when another control stops event propagation.
document.addEventListener('click',event=>{
  if(standbyPanel.open&&!standbyPanel.contains(event.target))standbyPanel.open=false;
},true);
standbyPanel.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&standbyPanel.open){
    standbyPanel.open=false;standbyPanel.querySelector('summary').focus();event.stopPropagation();
  }
});
// Total process time belongs beside Casey's name, not over page controls.
function syncTeamTotalTime(){
  const timer=el('team-total-time'),plan=currentCollaboration();
  const label=plan&&selectedCrewRole===0?collaborationTime(plan):'';
  if(timer.textContent!==label)timer.textContent=label;
  timer.hidden=!label;
}
setInterval(()=>syncTeamTotalTime(),1000);
function syncSurface(){
  teamConnectionBar.dataset.connected=String(!!runtime.teamReady);
  el('team-connection-label').textContent=runtime.teamReady?'API connected':runtime.teamModel?'Runtime offline':'API not connected';
  syncResetButtons();
  const plan=currentCollaboration();
  syncTeamTotalTime();
  standbyPanel.hidden=selectedScenario==='event-brief';
  const event=crewMission();resultsButton.hidden=selectedScenario==='event-brief'?!event:!plan;
  surfaceDefinitions.deliverables.ids=selectedScenario==='event-brief'?['event-package']:['plan-results'];
  if(activeSurface==='deliverables'){if(selectedScenario==='event-brief')renderEventPackage();else renderPlanResults(plan);}
  el('compare-open').hidden=!comparison;
  if(!activeSurface)return;
  for(const id of surfaceDefinitions[activeSurface].ids){
    const node=el(id);if(!node)continue;
    node.hidden=id==='plan-results'?!plan:id==='compare'?!comparison:false;
  }
}
function closeSurface(){if(surfaceDialog.open)surfaceDialog.close();}
surfaceDialog.addEventListener('close',()=>{
  // A new surface may already have opened before this queued close event arrives.
  if(surfaceDialog.open)return;
  for(const node of [...el('surface-body').children])surfaceStore.append(node);
  el('policy-panel').open=false;clearTimeout(policyRefreshTimer);policyRefreshTimer=null;activeSurface=null;board=false;
});
function openSurface(name,contribution='all'){
  if(name==='deliverables'&&selectedScenario==='event-brief')selectEventContribution(contribution);
  const definition=surfaceDefinitions[name];if(!definition)return;
  if(name!=='policies'){el('policy-panel').open=false;clearTimeout(policyRefreshTimer);policyRefreshTimer=null;}
  el('mission-skill-notice')?.remove();
  for(const node of [...el('surface-body').children])surfaceStore.append(node);
  activeSurface=name;board=name==='control';el('surface-title').textContent=definition.title;
  for(const id of definition.ids){const node=el(id);if(node)el('surface-body').append(node);}
  if(name==='policies'){el('policy-panel').open=true;loadPolicy();}
  syncSurface();el('surface-body').scrollTop=0;
  if(!surfaceDialog.open)surfaceDialog.showModal();
}
el('surface-close').onclick=closeSurface;
root.addEventListener('click',e=>{const button=e.target.closest('[data-surface]');if(button)openSurface(button.dataset.surface);});
