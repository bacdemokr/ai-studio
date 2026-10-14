// Open Task is the only Stage 3 destination. Ignore old saved scenario selection.
function renderScenarioSelector(){
 scenarioChoosing=false;root.dataset.scenarioChoosing='false';root.dataset.scenario='plan';
 window.BacCampus?.setScenario('plan');
 window.BacCampus?.setScenarioStatus(data.scenarios||[],false);
}
async function chooseScenario(id){
 if(id!=='plan')return;
 closeSurface();el('dialog').close();scenarioChoosing=false;
 setRoom('mission',{resume:true});render();el('crew-prompt').focus({preventScroll:true});
}
root.addEventListener('bac:world-scenario',event=>chooseScenario(event.detail.id));
new MutationObserver(renderScenarioSelector).observe(root,{attributes:true,attributeFilter:['data-renderer']});
