// Visual substitutions never create/delete agents or delay model execution.
let deskAssignments=[0,1,2,3],exchangeTeamKey='event:0,1,2,3';
function deskRole(slot){return deskAssignments[slot];}
function settleCrewExchange(){
  robots.forEach((r,i)=>{r.robot.visible=r.wanted;r.robot.position.copy(r.wanted?r.home:exchangeExit);r.path=[];r.exchange=null;labels[i].hidden=!r.wanted;r.halo.visible=r.wanted&&i===activeSelection;});
  exchangePanel.position.y=1.3;exchangeGlow.material.emissiveIntensity=.4;
}
function enterCrew(r){
  r.robot.visible=true;r.robot.position.copy(exchangeExit);r.exchange='entering';
  r.path=[exchangeEntry.clone(),new THREE.Vector3(r.home.x,.05,0),r.home.clone()];
}
function placeTeam(){
  const selected=state.agents.map((a,i)=>a.displayed===false?null:i).filter(i=>i!==null),key=(state.crewMission?.kind==='plan'?'plan:':'event:')+selected.join();
  if(key!==exchangeTeamKey){
    exchangeTeamKey=key;
    // Keep returning specialists at their existing desks, fill only free seats.
    if(state.crewMission?.kind!=='plan')deskAssignments=[0,1,2,3];
    deskAssignments=deskAssignments.map((role,slot)=>slot===0?0:selected.includes(role)?role:null);
    for(const role of selected.filter(i=>i>0))if(!deskAssignments.includes(role)){
      const free=deskAssignments.indexOf(null);if(free>=0)deskAssignments[free]=role;
    }
    robots.forEach((r,i)=>{
      r.wanted=selected.includes(i);
      const slot=deskAssignments.indexOf(i);
      r.home.copy(slot>=0?originalHomes[slot]:exchangeExit);
      if(i===0)return;
      if(!r.wanted){
        if(r.robot.visible){r.exchange='leaving';r.path=[new THREE.Vector3(r.robot.position.x,.05,0),exchangeEntry.clone(),exchangeExit.clone()];}
        else{r.exchange=null;r.path=[];}
      }else if(!r.robot.visible){r.exchange='queued';r.path=[];}
      else if(r.exchange==='leaving'){r.exchange='entering';r.path=[new THREE.Vector3(r.robot.position.x,.05,0),new THREE.Vector3(r.home.x,.05,0),r.home.clone()];}
    });
    if(!motion||reduced.matches)settleCrewExchange();
  }
}
function animateCrewExchange(dt){
  if(!motion||reduced.matches){if(robots.some(r=>r.exchange))settleCrewExchange();return;}
  for(const r of robots){
    if(r.exchange==='leaving'&&!r.path.length){r.robot.visible=false;r.exchange=null;}
    if(r.exchange==='entering'&&!r.path.length)r.exchange=null;
  }
  // Outgoing members clear the doorway before incoming members appear.
  if(!robots.some(r=>r.exchange==='leaving'||r.exchange==='entering'&&r.robot.position.distanceTo(exchangeExit)<1.8)){
    const next=robots.find(r=>r.exchange==='queued');if(next)enterCrew(next);
  }
  const exchanging=robots.some(r=>r.exchange),target=exchanging?3.75:1.3;
  exchangePanel.position.y=THREE.MathUtils.lerp(exchangePanel.position.y,target,Math.min(1,dt*6));
  exchangeGlow.material.emissiveIntensity=exchanging?1.1:.4;
}
