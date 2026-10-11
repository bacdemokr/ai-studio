// Adapt Paul's Lounge-to-Open-Task arrival to selected, persistent visitors.
// These scene-only actors never start requests or delay the actual assignment.
const visitorTravel=new Map();
const visitorLayer=document.createElement('div');visitorLayer.className='world-roundtable';viewport.append(visitorLayer);
function visitorRoute(v,points,phase){
  v.route=[v.group.position.clone(),...points.map(p=>p.clone())].filter((p,i,all)=>!i||p.distanceTo(all[i-1])>.001);
  v.segment=0;v.travel=0;v.phase=phase;
  v.length=v.route.slice(1).reduce((sum,p,i)=>sum+p.distanceTo(v.route[i]),0);
}
function disposeVisitor(v){
  visitorTravel.delete(v.key);scene.remove(v.group);clearGeometry(v.group);v.node.remove();
}
function visitorHomeRoute(v){
  return v.phase==='returning'?v.route.slice(v.segment+1):[...v.route.slice(0,v.segment+1).reverse(),...(v.homeTail||[])];
}
function returnVisitor(v){
  if(v.phase==='returning')return;
  // Retrace only the part already walked, including cancellation mid-corridor.
  visitorRoute(v,visitorHomeRoute(v),'returning');
}
function syncVisitorResidents(){
  for(const r of residents){
    r.atOpenTask=visitorTravel.has(r.key);
    if(r.atOpenTask){if(loungeSpeaker===r)endLoungeSpeech();if(drag?.resident===r)endResidentDrag(true);r.target=null;}
    r.mount.visible=!r.atOpenTask&&!r.atRoundtable&&arrival?.key!==r.key;
    r.node.hidden=!r.mount.visible;
  }
}
function syncVisitorCollection(){
  for(const v of visitorTravel.values()){
    const member=collection.find(a=>a.key===v.key);
    if(!member||member.deleting){disposeVisitor(v);continue;}
    // Event Brief has a separate snapshot. The shared activity still tells us
    // when an offscreen Open Task finished, reset, or was cancelled.
    if(activeScenario!=='plan'&&member.activity?.job!==v.job)returnVisitor(v);
  }
  syncVisitorTeam();syncVisitorResidents();
}
function syncVisitorTeam(){
  if(activeScenario!=='plan')return;
  const job=state.crewMission;
  const active=job?.kind==='plan'&&job.visitorsActive;
  const selected=new Map(active?state.agents.flatMap((a,role)=>a.visitorKey&&a.displayed!==false?[[a.visitorKey,{...a,taskTitle:a.role,role}]]:[]):[]);
  for(const v of visitorTravel.values())if(!selected.has(v.key))returnVisitor(v);
  scene.updateMatrixWorld(true);
  for(const [key,member] of selected){
    const resident=residents.find(r=>r.key===key&&!r.deleting);
    if(!resident)continue;
    let v=visitorTravel.get(key);
    const target=missionRoom.localToWorld(robots[member.role].home.clone());
    if(!v){
      if(arrival?.key===key)finishArrival();
      const rig=createCharacter({...member.avatar,protection:member.protection||'standard'});
      rig.group.scale.setScalar(1.3);rig.group.position.copy(loungeRoom.localToWorld(resident.group.position.clone()));scene.add(rig.group);
      const node=document.createElement('button');node.type='button';node.className='campus-agent-label';node.dataset.visitorAgent=key;
      node.innerHTML='<b></b><small></small>';visitorLayer.append(node);
      v={...rig,key,node,job:job.id,role:member.role,target};visitorTravel.set(key,v);
      node.onclick=()=>{if(activeScenario==='plan'&&state.agents[v.role]?.visitorKey===key)choose(v.role);else root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:key}));};
      visitorRoute(v,[...scenarioPath('plan').map(([x,z])=>new THREE.Vector3(x,.05,z)),missionRoom.localToWorld(new THREE.Vector3(-8.8,.05,0)),missionRoom.localToWorld(new THREE.Vector3(robots[v.role].home.x,.05,0)),target],'entering');
    }else if(v.job!==job.id||v.role!==member.role||v.phase==='returning'){
      // Reassignment during the walk home reverses smoothly, without a clone.
      const home=visitorHomeRoute(v);
      const back=v.phase==='returning'?v.route.slice(0,v.segment+1).reverse():[];
      visitorRoute(v,[...back,target],'entering');v.homeTail=home;v.job=job.id;v.role=member.role;v.target=target;
    }
    const avatar={...member.avatar,protection:member.protection||'standard'};
    if(['body','color','accessory','protection'].some(field=>v.appearance[field]!==avatar[field])){
      const rig=createCharacter(avatar);v.group.remove(v.body);clearGeometry(v.body);v.group.add(rig.body);
      v.body=rig.body;v.arms=rig.arms;v.legs=rig.legs;v.appearance=rig.appearance;
    }
    v.name=member.name;v.title=member.taskTitle;
    v.working=(job.activeStages||[]).includes(member.role);
    v.node.querySelector('b').textContent=v.name;
    v.node.setAttribute('aria-label','Select '+v.name);
  }
  syncVisitorResidents();
}
function animateVisitors(dt){
  for(const v of visitorTravel.values()){
    const walking=v.phase!=='working';
    if(walking){
      v.travel+=dt;
      const fraction=!motion||reduced.matches?1:Math.min(1,v.travel/4);
      let distance=fraction*v.length;v.segment=0;
      while(v.segment<v.route.length-2){const length=v.route[v.segment].distanceTo(v.route[v.segment+1]);if(distance<length)break;distance-=length;v.segment++;}
      const a=v.route[v.segment],b=v.route[v.segment+1]||a;
      v.group.position.lerpVectors(a,b,Math.min(1,distance/Math.max(.001,a.distanceTo(b))));
      v.group.rotation.y=Math.atan2(b.x-a.x,b.z-a.z);
      if(fraction===1){
        if(v.phase==='returning'){disposeVisitor(v);continue;}
        v.phase='working';v.segment=v.route.length-1;v.group.position.copy(v.target);
      }
    }
    const stepping=v.phase!=='working'&&motion&&!reduced.matches,working=v.phase==='working'&&v.working;
    if(!stepping)v.group.rotation.y=working?Math.PI:0;
    v.body.position.y=stepping?Math.abs(Math.sin(clock*9))*.04:0;
    v.legs.forEach((leg,j)=>leg.rotation.x=stepping?Math.sin(clock*9+j*Math.PI)*.4:0);
    v.arms.forEach((arm,j)=>arm.rotation.x=stepping?Math.sin(clock*9+j*Math.PI)*.3:working?-.7:0);
    v.node.querySelector('small').textContent=v.phase==='returning'?'Returning to Lounge':v.phase==='entering'?'Joining Open Task':working?'Working':v.title;
    v.node.classList.toggle('working',working);v.node.classList.toggle('selected',activeScenario==='plan'&&activeSelection===v.role);
    v.node.hidden=!(overview||journey||room==='mission'&&activeScenario==='plan'||room==='lounge'&&v.phase!=='working');
    positionLabel(v.node,v.group.position.clone().add(new THREE.Vector3(0,2.2,0)));
  }
  syncVisitorResidents();
}
function crewPresentation(role){
  const v=visitorTravel.get(state.agents[role]?.visitorKey);
  if(!v)return robots[role];
  const position=missionRoom.worldToLocal(v.group.position.clone());
  return {robot:{visible:true,position},home:robots[role].home,path:[],exchange:v.phase==='working'?null:v.phase};
}
function visitorTravelInfo(){return [...visitorTravel.values()].map(v=>({key:v.key,name:v.name,job:v.job,role:v.role,phase:v.phase,avatar:v.appearance,position:v.group.position.toArray(),destination:v.route.at(-1).toArray()}));}
