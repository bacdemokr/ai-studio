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
for(const id of ['board','workspace','experiences','policy-panel','connections'])surfaceStore.append(el(id));
el('passport').prepend(el('collection'));
el('collection-note').hidden=true;
const loungeActions=document.createElement('div');loungeActions.className='studio-panel-actions';loungeActions.innerHTML='<button type="button" class="studio-secondary" id="studio-compare-open" data-surface="compare" hidden>Compare replies</button>';
el('passport').append(loungeActions);
for(const node of [el('companion').querySelector('.studio-agent-extras'),el('companion').querySelector('.studio-native-note')])surfaceStore.append(node);
const crewActions=document.createElement('div');crewActions.className='studio-team-actions';crewActions.setAttribute('aria-label','Team actions');
el('crew-passport').prepend(crewActions);crewActions.append(el('room-action'));
el('crew-passport').append(document.getElementById('campus-roster'));
const controlButton=document.createElement('button');controlButton.type='button';controlButton.className='studio-secondary';controlButton.dataset.surface='control';controlButton.textContent='Mission Control';crewActions.append(controlButton);
const teamResetButton=document.createElement('button');teamResetButton.type='button';teamResetButton.id='studio-bac-reset';teamResetButton.className='studio-secondary';teamResetButton.textContent='Reset';teamResetButton.setAttribute('aria-label','Reset Multi-Agent Demo');teamResetButton.title='Stop active team work and clear team chats, files and the board';teamResetButton.onclick=()=>confirmTeamReset(teamResetButton);crewActions.append(teamResetButton);
const teamResetStatus=document.createElement('p');teamResetStatus.id='studio-team-reset-status';teamResetStatus.className='studio-muted';teamResetStatus.setAttribute('role','status');teamResetStatus.hidden=true;crewActions.after(teamResetStatus);
const resultsButton=document.createElement('button');resultsButton.type='button';resultsButton.className='studio-primary';resultsButton.dataset.surface='deliverables';resultsButton.textContent='Results';resultsButton.hidden=true;crewActions.append(resultsButton);
const teamTotalTime=document.createElement('div');teamTotalTime.id='studio-team-total-time';teamTotalTime.hidden=true;teamTotalTime.setAttribute('role','timer');teamTotalTime.title='Total process time, including queueing, planning, specialists and review';teamTotalTime.setAttribute('popover','manual');root.append(teamTotalTime);
const teamConnectionBar=document.createElement('div');teamConnectionBar.className='studio-team-connection-bar';teamConnectionBar.innerHTML='<span><i aria-hidden="true"></i><span id="studio-team-connection-label">Team API</span></span><button type="button" class="studio-secondary" id="studio-team-setup">API &amp; models ↗</button>';crewActions.after(teamConnectionBar);el('team-setup').onclick=openTeamSettings;
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
// A manual popover stays in the browser top layer, above dialogs and fullscreen.
function syncTeamTotalTime(raise=false){
  const timer=el('team-total-time'),plan=currentCollaboration();
  const label=plan?collaborationTime(plan):'';
  if(timer.textContent!==label)timer.textContent=label;
  if(!label){if(timer.hidePopover&&timer.matches(':popover-open'))timer.hidePopover();timer.hidden=true;return;}
  timer.hidden=false;
  if(timer.showPopover){
    if(raise&&timer.matches(':popover-open'))timer.hidePopover();
    if(!timer.matches(':popover-open'))timer.showPopover();
  }
}
new MutationObserver(records=>{
  if(records.some(record=>record.target.tagName==='DIALOG'))syncTeamTotalTime(true);
}).observe(root,{subtree:true,attributes:true,attributeFilter:['open']});
document.addEventListener('fullscreenchange',()=>syncTeamTotalTime(true));
setInterval(()=>syncTeamTotalTime(),1000);
function syncSurface(){
  teamConnectionBar.dataset.connected=String(!!runtime.teamReady);
  el('team-connection-label').textContent=runtime.teamReady?'Team API connected':runtime.teamModel?'Team runtime offline':'Team API not connected';
  teamResetButton.disabled=!!data.bacResetting||removingAgent;
  const plan=currentCollaboration();
  syncTeamTotalTime();
  resultsButton.hidden=!plan;
  if(activeSurface==='deliverables')renderPlanResults(plan);
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
