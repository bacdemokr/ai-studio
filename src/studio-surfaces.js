// Keep live panels (and their event handlers) inside the fullscreen root.
const surfaceStore=document.createElement('div');surfaceStore.id='studio-surface-store';surfaceStore.hidden=true;root.append(surfaceStore);
const surfaceDialog=document.createElement('dialog');surfaceDialog.id='studio-surface';surfaceDialog.setAttribute('aria-labelledby','studio-surface-title');
surfaceDialog.innerHTML='<header><h2 id="studio-surface-title"></h2><button type="button" class="studio-secondary" id="studio-surface-close" aria-label="Close panel">×</button></header><div id="studio-surface-body"></div>';
root.append(surfaceDialog);
let activeSurface=null;
const surfaceDefinitions={
  missions:{title:'Try a mission',ids:['experiences']},
  results:{title:'Results & files',ids:['workspace']},
  compare:{title:'Agent comparison',ids:['compare']},
  policies:{title:'Approved websites',ids:['policy-panel']},
  control:{title:'Mission Control',ids:['board']},
  deliverables:{title:'Results',ids:['event-package','workspace']}
};
for(const id of ['board','event-package','workspace','experiences','policy-panel','connections'])surfaceStore.append(el(id));
el('passport').prepend(el('collection'));
el('collection-note').hidden=true;
const loungeActions=document.createElement('div');loungeActions.className='studio-panel-actions';loungeActions.innerHTML='<button type="button" class="studio-secondary" id="studio-compare-open" data-surface="compare" hidden>Compare replies</button>';
el('passport').append(loungeActions);
for(const node of [el('companion').querySelector('.studio-agent-extras'),el('companion').querySelector('.studio-native-note')])surfaceStore.append(node);
const crewActions=document.createElement('div');crewActions.className='studio-team-actions';crewActions.setAttribute('aria-label','Team actions');
el('crew-passport').prepend(crewActions);crewActions.append(el('room-action'));
el('crew-passport').append(document.getElementById('campus-roster'));
const controlButton=document.createElement('button');controlButton.type='button';controlButton.className='studio-secondary';controlButton.dataset.surface='control';controlButton.textContent='Mission Control';crewActions.append(controlButton);
const resultsButton=document.createElement('button');resultsButton.type='button';resultsButton.className='studio-primary';resultsButton.dataset.surface='deliverables';resultsButton.textContent='Results';resultsButton.hidden=true;crewActions.append(resultsButton);
function syncSurface(){
  resultsButton.hidden=!crewMission();
  el('compare-open').hidden=!comparison;
  if(!activeSurface)return;
  for(const id of surfaceDefinitions[activeSurface].ids){
    const node=el(id);if(!node)continue;
    node.hidden=activeSurface==='deliverables'&&id==='workspace'?crewMission()?.payload.brief?.schema===2:id==='event-package'?crewMission()?.payload.brief?.schema!==2:id==='compare'?!comparison:false;
  }
}
function closeSurface(){if(surfaceDialog.open)surfaceDialog.close();}
surfaceDialog.addEventListener('close',()=>{
  // A new surface may already have opened before this queued close event arrives.
  if(surfaceDialog.open)return;
  for(const node of [...el('surface-body').children])surfaceStore.append(node);
  el('policy-panel').open=false;activeSurface=null;board=false;
});
function openSurface(name,contribution='all'){
  const definition=surfaceDefinitions[name];if(!definition)return;
  el('mission-skill-notice')?.remove();
  if(name==='deliverables')selectEventContribution(contribution);
  for(const node of [...el('surface-body').children])surfaceStore.append(node);
  if(['control','deliverables'].includes(name)&&crewMission()){selectedJob=crewMission().id;render();}
  activeSurface=name;board=name==='control';el('surface-title').textContent=definition.title;
  for(const id of definition.ids){const node=el(id);if(node)el('surface-body').append(node);}
  if(name==='policies'){el('policy-panel').open=true;loadPolicy();}
  syncSurface();el('surface-body').scrollTop=0;
  if(!surfaceDialog.open)surfaceDialog.showModal();
  if(name==='deliverables')navigateShowcaseContribution();
}
el('surface-close').onclick=closeSurface;
root.addEventListener('click',e=>{const button=e.target.closest('[data-surface]');if(button)openSurface(button.dataset.surface);});
