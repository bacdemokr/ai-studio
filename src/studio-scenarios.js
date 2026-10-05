// Card selection follows BB's scenario picker; each card now owns a durable team.
// Add new scenarios here and to scripts/scenarios.py with an explicit workflow.
const stageScenarios=[
 {id:'event-brief',title:'Event Brief',eyebrow:'A guided team demo',icon:'▤',description:'Turn an event brief into demo ideas, a staffing plan and an event page.',team:'Casey · Dylan · Alex · Morgan',action:'Open Event Brief'},
 {id:'plan',title:'Plan',eyebrow:'Your task, the right team',icon:'✦',description:'Give Casey a /plan request. The captain chooses specialists to research, analyze, build or review.',team:'Casey + specialists chosen for your task',action:'Open Plan'}
];
const scenarioSelector=document.createElement('section');scenarioSelector.id='studio-scenarios';scenarioSelector.hidden=true;scenarioSelector.setAttribute('aria-labelledby','studio-scenarios-title');
scenarioSelector.innerHTML='<button type="button" class="studio-secondary scenario-return" data-scenario-return>← Agent lounge</button><div class="scenario-heading"><span class="studio-kicker">STAGE 03</span><h2 id="studio-scenarios-title">What will your team do?</h2><p>Choose a scenario. Your previous work stays here.</p></div><div class="scenario-cards"></div>';
layout.append(scenarioSelector);
const scenarioButton=document.createElement('button');scenarioButton.type='button';scenarioButton.className='studio-secondary studio-scenario-back';scenarioButton.textContent='← Scenarios';crewActions.prepend(scenarioButton);
scenarioButton.onclick=()=>{if(scenarioSwitching||pendingWrites||crewChatSending||crewDocumentUpload){alert('Wait for the current save to finish.');return;}closeSurface();scenarioChoosing=true;renderRoomVisibility();};
function renderScenarioSelector(){
 const visible=room==='mission'&&scenarioChoosing&&root.dataset.worldOverview!=='true';
 scenarioSelector.hidden=!visible;root.dataset.scenarioChoosing=String(visible);
 root.dataset.scenario=selectedScenario;
 scenarioButton.disabled=scenarioSwitching;
 if(!visible)return;
 const markup=stageScenarios.map(s=>{
  const saved=data.scenarios?.find(item=>item.id===s.id),hasWork=saved?.hasWork;
  return '<button type="button" class="scenario-card" data-scenario="'+s.id+'" '+(scenarioSwitching?'disabled':'')+'><span class="scenario-icon" aria-hidden="true">'+s.icon+'</span><small>'+s.eyebrow+'</small><h3>'+s.title+'</h3><p>'+s.description+'</p><span class="scenario-team">'+s.team+'</span><span class="scenario-card-footer"><strong>'+(hasWork?'Continue':s.action)+' <span aria-hidden="true">↗</span></strong><span class="scenario-saved">'+(saved?.busy?'● In progress':hasWork?'Saved work':'New workspace')+'</span></span></button>';
 }).join('');
 const cards=scenarioSelector.querySelector('.scenario-cards');if(cards.innerHTML!==markup)cards.innerHTML=markup;
}
const scenarioDraftEpochs=new Map();
async function chooseScenario(id){
 if(!stageScenarios.some(s=>s.id===id)||scenarioSwitching)return;
 if(pendingWrites||crewChatSending||crewDocumentUpload||changingAgent||removingAgent){alert('Wait for the current save to finish before changing scenarios.');return;}
 const previous=selectedScenario,previousData=data;
 if(crewChatKey)crewDrafts.set(crewChatKey,el('crew-prompt').value);
 scenarioDraftEpochs.set(previous,crewResetEpoch);
 closeSurface();el('dialog').close();++dialogRevision;++eventPreviewVersion;++refreshVersion;
 scenarioSwitching=true;selectedScenario=id;scenarioRoles();renderScenarioSelector();
 try{
  const state=await api('state');
  data=state;selectedJob=null;resultKey='';selectedCrewRole=0;crewChatKey='';crewChatSignature='';
  crewResetEpoch=scenarioDraftEpochs.get(id)||id+':'+(state.crewChatReset?.epoch||'');
  teamModelDrafts.clear();teamModelDialog.hidden=true;
  eventPackageKey='';audienceReport=null;audienceJob='';previewCleanup();
  if(eventPreviewUrl){URL.revokeObjectURL(eventPreviewUrl);eventPreviewUrl='';}
  scenarioChoosing=false;scenarioSwitching=false;
  try{sessionStorage.setItem('bac-stage3-scenario',id);}catch{}
  setRoom('mission',{resume:true});render();el('crew-prompt').focus({preventScroll:true});
 }catch(error){selectedScenario=previous;data=previousData;scenarioRoles();scenarioSwitching=false;alert(error.message);render();}
 finally{scenarioSwitching=false;renderRoomVisibility();}
}
scenarioSelector.onclick=event=>{if(event.target.closest('[data-scenario-return]')){if(scenarioSwitching)return;setRoom('lounge');return;}const card=event.target.closest('[data-scenario]');if(card)chooseScenario(card.dataset.scenario);};

new MutationObserver(renderScenarioSelector).observe(root,{attributes:true,attributeFilter:['data-world-overview']});
