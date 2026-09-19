// One persistent floor plan. Room changes move the camera, never swap worlds.
const studioRooms={
  workshop:{group:workshopRoom,x:-22,title:'Workshop',verb:'Create & connect',number:'01'},
  lounge:{group:loungeRoom,x:0,title:'Agent lounge',verb:'Meet your agents',number:'02'},
  mission:{group:missionRoom,x:24,title:'Mission room',verb:'Work as a crew',number:'03'}
};
Object.entries(studioRooms).forEach(([id,entry])=>{entry.group.position.x=entry.x;entry.group.visible=true;entry.group.userData.studioRoom=id;});
let overview=false,journey=null,viewHalfHeight=0;
const corridors=[],doorways=[],overviewLabels=[];
const navigationLayer=document.createElement('div');navigationLayer.className='world-navigation';viewport.append(navigationLayer);
const overviewButton=document.createElement('button');overviewButton.type='button';overviewButton.className='world-overview-button';overviewButton.dataset.worldOverview='';overviewButton.textContent='⌑ See the whole studio';overviewButton.setAttribute('aria-pressed','false');navigationLayer.append(overviewButton);
const journeyNote=document.createElement('div');journeyNote.className='world-journey';journeyNote.setAttribute('role','status');journeyNote.setAttribute('aria-live','polite');journeyNote.hidden=true;navigationLayer.append(journeyNote);
const roomMap=document.createElement('nav');roomMap.className='world-room-map';roomMap.setAttribute('aria-label','Connected studio rooms');
roomMap.innerHTML='<span class="world-map-caption">ONE STUDIO</span><div>'+Object.entries(studioRooms).map(([id,r])=>'<button type="button" data-world-room="'+id+'"><i>'+r.number+'</i><span>'+r.title+'</span></button>').join('')+'</div>';
navigationLayer.append(roomMap);
function goToRoom(next){
  const restoreFocus=navigationLayer.contains(document.activeElement);
  root.dispatchEvent(new CustomEvent('bac:world-room',{detail:{room:next}}));
  if(restoreFocus)roomMap.querySelector('[data-world-room="'+next+'"]').focus({preventScroll:true});
}
roomMap.onclick=e=>{const button=e.target.closest('[data-world-room]');if(button)goToRoom(button.dataset.worldRoom);};
overviewButton.onclick=()=>overview?goToRoom(room):showOverview();

// Low railings and continuous green floor lights make the connections tangible.
for(const [from,to,start,end] of [['workshop','lounge',-16,-9],['lounge','mission',9,15]]){
  const hall=new THREE.Group();scene.add(hall);
  const x=(start+end)/2,w=end-start;
  box(hall,x,-.18,3,w,.36,2.4,0x172330);box(hall,x,.015,3,w,.04,2.25,0x35485a);
  for(const z of [1.86,4.14]){
    box(hall,x,.055,z,w,.035,.045,0x76b900,true);
    box(hall,x,.48,z,w,.055,.065,0x617b90);
    for(const post of [start+.2,end-.2])box(hall,post,.24,z,.055,.48,.055,0x617b90);
  }
  for(let p=start+.65;p<end;p+=1.05)box(hall,p,.043,3,.38,.015,.1,0x92b4c9);
  const pulse=box(hall,start,.11,3,.48,.035,1.7,0x96d52b,true);pulse.visible=false;
  corridors.push({from,to,start,end,pulse});
}
function doorway(from,to,x){
  const group=new THREE.Group();group.position.set(x,0,3);studioRooms[from].group.add(group);group.userData.destination=to;
  box(group,0,.055,0,.65,.1,2.35,0x3d5265);
  for(const z of [-1.1,1.1]){box(group,0,1.1,z,.18,2.2,.18,0x627e93);box(group,.105,1.14,z,.03,1.94,.045,0x96d52b,true);}
  box(group,0,2.2,0,.22,.18,2.4,0x344d60);box(group,.13,2.2,0,.026,.09,2.04,0x96d52b,true);
  const node=document.createElement('button');node.type='button';node.className='world-doorway';node.dataset.doorwayFrom=from;node.dataset.worldRoom=to;
  node.innerHTML='<span>WALK THROUGH</span><b>'+studioRooms[to].title+' <i>'+(studioRooms[to].x>studioRooms[from].x?'→':'←')+'</i></b>';
  node.setAttribute('aria-label','Walk to '+studioRooms[to].title);node.onclick=()=>goToRoom(to);navigationLayer.append(node);
  doorways.push({from,to,group,node,point:new THREE.Vector3(0,2.55,0)});
}
doorway('workshop','lounge',5.8);doorway('lounge','workshop',-8.8);doorway('lounge','mission',8.8);doorway('mission','lounge',-8.8);
Object.entries(studioRooms).forEach(([id,r])=>{
  const node=document.createElement('button');node.type='button';node.className='world-campus-room';node.dataset.worldRoom=id;
  node.innerHTML='<span>'+r.number+' / '+r.verb+'</span><b>'+r.title+' ↗</b>';node.onclick=()=>goToRoom(id);navigationLayer.append(node);overviewLabels.push({id,node,group:r.group});
});
function roomHeight(id){
  const aspect=viewport.clientWidth/Math.max(1,viewport.clientHeight);
  return id==='workshop'?Math.max(6.8,8/aspect):aspect<1?12.5:aspect<1.5?10.2:8.5;
}
function overviewHeight(){return Math.max(12.5,34/(viewport.clientWidth/Math.max(1,viewport.clientHeight)));}
function roomFocus(id){return new THREE.Vector3(studioRooms[id].x,id==='workshop'?1.0:.25,.6);}
function refreshNavigation(){
  navigationLayer.dataset.overview=String(overview);navigationLayer.dataset.travelling=String(!!journey);
  root.dataset.worldOverview=String(overview);root.dataset.worldTravelling=String(!!journey);
  hotspotLayer.hidden=room!=='mission'||overview||!!journey;el('labels').hidden=room!=='mission'||overview||!!journey;residentLayer.hidden=room!=='lounge'||overview||!!journey;
  overviewButton.textContent=overview?'↙ Return to '+studioRooms[room].title:'⌑ See the whole studio';overviewButton.setAttribute('aria-pressed',String(overview));
  overviewButton.setAttribute('aria-label',overview?'Return to '+studioRooms[room].title:'See the whole studio');
  roomMap.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-current',b.dataset.worldRoom===room?'location':'false');b.classList.toggle('selected',b.dataset.worldRoom===room);});
  doorways.forEach(d=>d.node.hidden=overview||!!journey||d.from!==room);
  overviewLabels.forEach(r=>{r.node.hidden=!overview||!!journey;r.node.setAttribute('aria-current',r.id===room?'location':'false');});
  journeyNote.hidden=!journey&&!overview;
  if(!journey&&overview)journeyNote.textContent='Three connected rooms. Choose where to go.';
}
function rememberCamera(){if(!overview&&!journey)roomCameras[room]=[azimuth,elevation,zoom];}
function travelTo(target,instant=false){
  drag=null;
  const start={focus:focus.clone(),azimuth,elevation,zoom,height:viewHalfHeight||roomHeight(room)};
  const delta=Math.atan2(Math.sin(target.azimuth-azimuth),Math.cos(target.azimuth-azimuth));target.azimuth=azimuth+delta;
  journey={start,target,began:performance.now(),duration:1050,lift:target.overview?0:Math.min(7,start.focus.distanceTo(target.focus)*.22)};
  refreshNavigation();
  if(instant||reduced.matches)finishJourney();
}
function finishJourney(){
  if(!journey)return;const target=journey.target;
  focus.copy(target.focus);azimuth=target.azimuth;elevation=target.elevation;zoom=target.zoom;viewHalfHeight=target.height;journey=null;
  refreshNavigation();frame();renderer.render(scene,camera);
}
function setRoom(next,options={}){
  if(!studioRooms[next])return;
  if(next===room&&!overview&&!journey){resize();return;}
  const previous=room;rememberCamera();room=next;overview=false;
  const [a,e,z]=roomCameras[room];
  journeyNote.textContent=previous===next?'Returning to '+studioRooms[next].title:studioRooms[previous].title+' → '+studioRooms[next].title;
  travelTo({focus:roomFocus(room),azimuth:a,elevation:e,zoom:z,height:roomHeight(room),overview:false},options.instant);
}
function showOverview(){
  rememberCamera();overview=true;journeyNote.textContent='Opening your connected studio';
  travelTo({focus:new THREE.Vector3(2,.2,0),azimuth:.08,elevation:.94,zoom:1,height:overviewHeight(),overview:true});
}
function resetNavigation(){
  roomCameras[room]=room==='workshop'?[.34,.64,1]:[.43,.76,1];
  if(overview){showOverview();return;}
  const [a,e,z]=roomCameras[room];journeyNote.textContent='Returning to '+studioRooms[room].title;
  travelTo({focus:roomFocus(room),azimuth:a,elevation:e,zoom:z,height:roomHeight(room),overview:false});
}
function resizeNavigation(){
  if(journey)journey.target.height=overview?overviewHeight():roomHeight(room);
  else viewHalfHeight=overview?overviewHeight():roomHeight(room);
}
function placeDoorway(d){
  positionLabel(d.node,d.group.localToWorld(d.point.clone()));
  const half=d.node.offsetWidth/2,w=viewport.clientWidth,h=viewport.clientHeight;
  const offset=studioRooms[d.to].x<studioRooms[d.from].x?-42:20;
  d.node.style.left=Math.max(half+12,Math.min(w-half-12,parseFloat(d.node.style.left)+offset))+'px';
  d.node.style.top=(w<700?Math.max(116+d.node.offsetHeight,h-96):Math.max(116+d.node.offsetHeight,Math.min(h-94,parseFloat(d.node.style.top))))+'px';
}
function animateNavigation(now){
  if(journey){
    const t=Math.min(1,(now-journey.began)/journey.duration),p=t*t*(3-2*t),{start,target}=journey;
    focus.lerpVectors(start.focus,target.focus,p);
    azimuth=THREE.MathUtils.lerp(start.azimuth,target.azimuth,p);elevation=THREE.MathUtils.lerp(start.elevation,target.elevation,p);zoom=THREE.MathUtils.lerp(start.zoom,target.zoom,p);
    viewHalfHeight=THREE.MathUtils.lerp(start.height,target.height,p)+Math.sin(Math.PI*t)*journey.lift;
    frame();if(t===1)finishJourney();
  }
  scene.updateMatrixWorld();
  doorways.forEach(d=>{if(!d.node.hidden)placeDoorway(d);});
  overviewLabels.forEach(r=>{
    if(r.node.hidden)return;
    positionLabel(r.node,r.group.localToWorld(new THREE.Vector3(0,4.5,-1.7)));
    const controlsBottom=Math.max(overviewButton.offsetTop+overviewButton.offsetHeight,journeyNote.offsetHeight?journeyNote.offsetTop+journeyNote.offsetHeight:0);
    r.node.style.top=Math.max(controlsBottom+12+r.node.offsetHeight,parseFloat(r.node.style.top))+'px';
  });
  corridors.forEach(c=>{c.pulse.visible=!!journey&&!reduced.matches;if(c.pulse.visible)c.pulse.position.x=c.start+((now*.001)%1)*(c.end-c.start);});
}
function navigationTargets(){
  if(overview)return Object.values(studioRooms).map(r=>r.group);
  return [...doorways.filter(d=>d.from===room).map(d=>d.group),...(room==='mission'?hitTargets:roomHitTargets())];
}
function selectNavigationObject(object){
  for(let node=object;node;node=node.parent){
    if(overview&&node.userData.studioRoom){goToRoom(node.userData.studioRoom);return true;}
    if(!overview&&node.userData.destination){goToRoom(node.userData.destination);return true;}
  }
  return false;
}
function navigationInfo(){return {overview,travelling:!!journey,focus:focus.toArray(),rooms:Object.fromEntries(Object.entries(studioRooms).map(([id,r])=>[id,r.group.position.toArray()])),visibleRooms:Object.keys(studioRooms).filter(id=>studioRooms[id].group.visible),doorways:doorways.map(d=>({from:d.from,to:d.to}))};}
reduced.addEventListener('change',()=>{if(reduced.matches)finishJourney();});
focus.copy(roomFocus(room));viewHalfHeight=roomHeight(room);refreshNavigation();
