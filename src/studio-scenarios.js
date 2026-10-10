// The same catalog lays out the 3D floors, map and accessible WebGL fallback.
// A new scenario also needs an explicit backend workflow in scripts/scenarios.py.
const scenarioSelector=document.createElement('section');scenarioSelector.id='studio-scenarios';scenarioSelector.hidden=true;scenarioSelector.setAttribute('aria-labelledby','studio-scenarios-title');
scenarioSelector.innerHTML='<div class="scenario-heading"><span class="studio-kicker">STAGE 03</span><h2 id="studio-scenarios-title">Multi-Agent spaces</h2></div><div class="scenario-cards"></div>';
layout.append(scenarioSelector);
// The scene and Studio Map provide navigation. Keep a back control only when WebGL is unavailable.
const scenarioButton=document.createElement('button');scenarioButton.type='button';scenarioButton.className='studio-secondary studio-scenario-back';scenarioButton.textContent='← Scenarios';scenarioButton.hidden=true;crewActions.prepend(scenarioButton);
scenarioButton.onclick=()=>{if(scenarioSwitching||pendingWrites>backgroundWrites||crewChatSending||crewDocumentUpload){alert('Wait for the current save to finish.');return;}closeSurface();scenarioChoosing=true;setRoom('mission');};
function renderScenarioSelector(){
 const visible=room==='mission'&&scenarioChoosing&&['fallback','lost'].includes(root.dataset.renderer);
 scenarioButton.hidden=room!=='mission'||scenarioChoosing||!['fallback','lost'].includes(root.dataset.renderer);
 scenarioSelector.hidden=!visible;root.dataset.scenarioChoosing=String(room==='mission'&&scenarioChoosing);
 root.dataset.scenario=selectedScenario;
 if(!scenarioSwitching)window.BacCampus?.setScenario(selectedScenario);
 window.BacCampus?.setScenarioStatus(data.scenarios||[],scenarioSwitching);
 scenarioButton.disabled=scenarioSwitching;
 if(!visible)return;
 const markup=stageScenarios.map(s=>{
  const saved=data.scenarios?.find(item=>item.id===s.id),hasWork=saved?.hasWork;
  return '<button type="button" class="scenario-card" data-scenario="'+s.id+'" '+(scenarioSwitching?'disabled':'')+'><small>'+s.number+' · '+s.eyebrow+'</small><h3>'+s.title+'</h3><p>'+s.description+'</p><span class="scenario-team">'+s.team+'</span><span class="scenario-card-footer"><strong>'+(hasWork?'Continue':s.action)+' ↗</strong><span class="scenario-saved">'+(saved?.busy?'In progress':hasWork?'Saved work':'')+'</span></span></button>';
 }).join('');
 const cards=scenarioSelector.querySelector('.scenario-cards');if(cards.innerHTML!==markup)cards.innerHTML=markup;
}
const scenarioDraftEpochs=new Map();
async function chooseScenario(id){
 if(!stageScenarios.some(s=>s.id===id)||scenarioSwitching)return;
 if(pendingWrites>backgroundWrites||crewChatSending||crewDocumentUpload||changingAgent||removingAgent){alert('Wait for the current save to finish before changing scenarios.');return;}
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
  window.BacCampus?.setScenario(id);
  try{sessionStorage.setItem('bac-stage3-scenario',id);}catch{}
  setRoom('mission',{resume:true});render();el('crew-prompt').focus({preventScroll:true});
 }catch(error){selectedScenario=previous;data=previousData;scenarioRoles();scenarioSwitching=false;alert(error.message);render();}
 finally{scenarioSwitching=false;renderRoomVisibility();}
}
scenarioSelector.onclick=event=>{if(event.target.closest('[data-scenario-return]')){if(scenarioSwitching)return;setRoom('lounge');return;}const card=event.target.closest('[data-scenario]');if(card)chooseScenario(card.dataset.scenario);};

root.addEventListener('bac:world-scenario',event=>chooseScenario(event.detail.id));
new MutationObserver(renderScenarioSelector).observe(root,{attributes:true,attributeFilter:['data-renderer']});
