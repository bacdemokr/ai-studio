// One persistent floor plan. Room changes move the camera, never swap worlds.
const studioRooms={
  workshop:{group:workshopRoom,x:0,z:18,title:'Onboarding',verb:'Create & connect',number:'01'},
  lounge:{group:loungeRoom,x:0,z:0,title:'Agent lounge',verb:'Meet your agents',number:'02'},
  mission:{group:missionRoom,x:24,z:0,title:'BaC mission room',verb:'Work as a crew',number:'03'}
};
Object.entries(studioRooms).forEach(([id,entry])=>{entry.group.position.set(entry.x,0,entry.z);entry.group.visible=true;entry.group.userData.studioRoom=id;});
let overview=false,journey=null,viewHalfHeight=0;
const corridors=[],doorways=[],overviewLabels=[];
const navigationLayer=document.createElement('div');navigationLayer.className='world-navigation';viewport.append(navigationLayer);
const overviewButton=document.createElement('button');overviewButton.type='button';overviewButton.className='world-overview-button';overviewButton.dataset.worldOverview='';overviewButton.textContent='⌑ See the whole studio';overviewButton.setAttribute('aria-pressed','false');navigationLayer.append(overviewButton);
const journeyNote=document.createElement('div');journeyNote.className='world-journey';journeyNote.setAttribute('role','status');journeyNote.setAttribute('aria-live','polite');journeyNote.hidden=true;navigationLayer.append(journeyNote);
const roomMap=document.createElement('nav');roomMap.className='world-room-map';roomMap.setAttribute('aria-label','Connected studio rooms');
roomMap.innerHTML='<span class="world-map-caption">STUDIO MAP</span><div><svg viewBox="0 0 280 62" aria-hidden="true"><path d="M12 12 H164 V50 H12 Z"/></svg>'+['lounge','mission','workshop'].map(id=>'<button type="button" data-world-room="'+id+'"><i>'+studioRooms[id].number+'</i><span>'+(id==='mission'?'BaC':studioRooms[id].title)+'</span></button>').join('')+'</div>';
navigationLayer.append(roomMap);
function goToRoom(next){
  const restoreFocus=navigationLayer.contains(document.activeElement);
  root.dispatchEvent(new CustomEvent('bac:world-room',{detail:{room:next}}));
  if(restoreFocus)roomMap.querySelector('[data-world-room="'+next+'"]').focus({preventScroll:true});
}
roomMap.onclick=e=>{const button=e.target.closest('[data-world-room]');if(button)goToRoom(button.dataset.worldRoom);};
overviewButton.onclick=()=>overview?goToRoom(room):showOverview();

// Each pair has its own physical path. The third bridge bends around the courtyard.
const connections=[
  {from:'lounge',to:'mission',points:[[9,3],[15,3]]},
  {from:'lounge',to:'workshop',points:[[0,6.3],[0,13.75]]},
  {from:'workshop',to:'mission',points:[[6,21],[24,21],[24,6.3]]}
];
function hallRail(parent,x,z,length){
  box(parent,x,.055,z,length,.035,.045,0x76b900,true);
  box(parent,x,.48,z,length,.055,.065,0x617b90);
  for(let p=-length/2+.12;p<length/2;p+=Math.max(.25,(length-.24)/Math.max(1,Math.ceil(length/4))))box(parent,x+p,.24,z,.055,.48,.055,0x617b90);
}
for(const connection of connections){
  const {points}=connection,segments=[];let length=0;
  for(let i=1;i<points.length;i++){
    const [sx,sz]=points[i-1],[ex,ez]=points[i],distance=Math.hypot(ex-sx,ez-sz),angle=-Math.atan2(ez-sz,ex-sx);
    const hall=new THREE.Group();hall.position.set(sx,0,sz);hall.rotation.y=angle;scene.add(hall);
    // Stop at the turn platform, leaving the inside of the bend open to walk through.
    const start=i>1?1.2:0,end=distance-(i<points.length-1?1.2:0),width=end-start,x=(start+end)/2;
    box(hall,x,-.18,0,width,.36,2.4,0x172330);box(hall,x,.015,0,width,.04,2.25,0x35485a);
    for(const z of [-1.14,1.14])hallRail(hall,x,z,width);
    for(let p=start+.6;p<end-.2;p+=1.05)box(hall,p,.043,0,.38,.015,.1,0x92b4c9);
    segments.push({sx,sz,ex,ez,distance,offset:length,angle});length+=distance;
  }
  for(let i=1;i<points.length-1;i++){
    const [x,z]=points[i],corner=new THREE.Group();corner.position.set(x,0,z);scene.add(corner);
    box(corner,0,-.18,0,2.4,.36,2.4,0x172330);box(corner,0,.015,0,2.25,.04,2.25,0x35485a);
    // The incoming/outgoing directions identify the two open sides of this junction.
    const open=points.filter((_,j)=>j===i-1||j===i+1).map(([px,pz])=>[Math.sign(px-x),Math.sign(pz-z)]);
    for(const [dx,dz] of [[-1,0],[1,0],[0,-1],[0,1]])if(!open.some(([ox,oz])=>dx===ox&&dz===oz)){
      const edge=new THREE.Group();corner.add(edge);edge.rotation.y=dx?Math.PI/2:0;hallRail(edge,0,dx?dx*1.14:dz*1.14,2.4);
    }
    cylinder(corner,0,.045,0,.12,.025,0x92b4c9,16);
  }
  const pulse=box(scene,0,.11,0,.48,.035,1.7,0x96d52b,true);pulse.visible=false;
  corridors.push({...connection,segments,length,pulse});
}
function doorway(from,to,x,z,rotation=0){
  const group=new THREE.Group();group.position.set(x,0,z);group.rotation.y=rotation;studioRooms[from].group.add(group);group.userData.destination=to;
  box(group,0,.055,0,.65,.1,2.35,0x3d5265);
  for(const z of [-1.1,1.1]){box(group,0,1.1,z,.18,2.2,.18,0x627e93);box(group,.105,1.14,z,.03,1.94,.045,0x96d52b,true);}
  box(group,0,2.2,0,.22,.18,2.4,0x344d60);box(group,.13,2.2,0,.026,.09,2.04,0x96d52b,true);
  const node=document.createElement('button');node.type='button';node.className='world-doorway';node.dataset.doorwayFrom=from;node.dataset.worldRoom=to;
  node.innerHTML='<span>WALK THROUGH</span><b>'+studioRooms[to].title+' <i>↗</i></b>';
  node.setAttribute('aria-label','Walk to '+studioRooms[to].title);node.onclick=()=>goToRoom(to);navigationLayer.append(node);
  doorways.push({from,to,group,node,point:new THREE.Vector3(0,2.55,0)});
}
doorway('lounge','mission',8.8,3);doorway('mission','lounge',-8.8,3);
doorway('lounge','workshop',0,6.1,Math.PI/2);doorway('workshop','lounge',0,-4.05,Math.PI/2);
doorway('workshop','mission',5.8,3);doorway('mission','workshop',0,6.1,Math.PI/2);
Object.entries(studioRooms).forEach(([id,r])=>{
  const node=document.createElement('button');node.type='button';node.className='world-campus-room';node.dataset.worldRoom=id;
  node.innerHTML='<span>'+r.number+' / '+r.verb+'</span><b>'+r.title+' ↗</b>';node.onclick=()=>goToRoom(id);navigationLayer.append(node);overviewLabels.push({id,node,group:r.group});
});
function roomHeight(id){
  const aspect=viewport.clientWidth/Math.max(1,viewport.clientHeight);
  return id==='workshop'?Math.max(6.8,8/aspect):aspect<1?12.5:aspect<1.5?10.2:8.5;
}
function overviewHeight(){return Math.max(22,27/(viewport.clientWidth/Math.max(1,viewport.clientHeight)));}
function roomFocus(id){return new THREE.Vector3(studioRooms[id].x,id==='workshop'?1.0:.25,studioRooms[id].z+.6);}
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
  travelTo({focus:roomFocus(room),azimuth:a,elevation:e,zoom:z,height:roomHeight(room),overview:false,from:previous,to:next},options.instant);
}
function showOverview(){
  rememberCamera();overview=true;journeyNote.textContent='Opening your connected studio';
  travelTo({focus:new THREE.Vector3(12,.2,8),azimuth:.08,elevation:.94,zoom:1,height:overviewHeight(),overview:true});
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
  const offset=d.group.position.x<0?-42:d.group.position.x>0?20:0;
  d.node.style.left=Math.max(half+12,Math.min(w-half-12,parseFloat(d.node.style.left)+offset))+'px';
  // In the short phone preview, keep the rear-door card beside the avatar's face.
  if(w<700&&h<500&&d.from==='workshop'&&d.to==='lounge')d.node.style.left=(w-half-12)+'px';
  d.node.style.top=Math.max(116+d.node.offsetHeight,Math.min(h-120,parseFloat(d.node.style.top)))+'px';
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
  // Highlight only the bridge for the current trip, in the direction of travel.
  corridors.forEach(c=>{
    const target=journey?.target,forward=target?.from===c.from&&target?.to===c.to,backward=target?.from===c.to&&target?.to===c.from;
    c.pulse.visible=!!journey&&!reduced.matches&&(forward||backward);
    if(!c.pulse.visible)return;
    const t=Math.min(1,(now-journey.began)/journey.duration),distance=(forward?t:1-t)*c.length;
    const s=c.segments.find(s=>distance<=s.offset+s.distance)||c.segments[c.segments.length-1],p=(distance-s.offset)/s.distance;
    c.pulse.position.set(THREE.MathUtils.lerp(s.sx,s.ex,p),.11,THREE.MathUtils.lerp(s.sz,s.ez,p));c.pulse.rotation.y=s.angle;
  });
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
function navigationInfo(){return {overview,travelling:!!journey,focus:focus.toArray(),rooms:Object.fromEntries(Object.entries(studioRooms).map(([id,r])=>[id,r.group.position.toArray()])),visibleRooms:Object.keys(studioRooms).filter(id=>studioRooms[id].group.visible),doorways:doorways.map(d=>({from:d.from,to:d.to})),corridors:corridors.map(c=>({from:c.from,to:c.to,points:c.points,active:c.pulse.visible}))};}
reduced.addEventListener('change',()=>{if(reduced.matches)finishJourney();});
focus.copy(roomFocus(room));viewHalfHeight=roomHeight(room);refreshNavigation();
