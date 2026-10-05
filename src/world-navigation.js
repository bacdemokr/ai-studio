// One persistent floor plan. Room changes move the camera, never swap worlds.
const studioRooms={
  workshop:{group:workshopRoom,x:0,z:18,title:roomTitles.workshop,verb:'Meet your next agent',number:'01'},
  lounge:{group:loungeRoom,x:0,z:0,title:roomTitles.lounge,verb:'Meet your agents',number:'02'},
  mission:{group:missionRoom,x:24,z:0,title:roomTitles.mission,verb:'Meet your team',number:'03'}
};
Object.entries(studioRooms).forEach(([id,entry])=>{entry.group.position.set(entry.x,0,entry.z);entry.group.visible=true;entry.group.userData.studioRoom=id;});
let overview=false,journey=null,viewHalfHeight=0;
const corridors=[],doorways=[],overviewLabels=[];
const navigationLayer=document.createElement('div');navigationLayer.className='world-navigation';viewport.append(navigationLayer);
navigationLayer.dataset.scenarioDensity=scenarioFloors.length>2?'compact':'normal';
const overviewButton=document.createElement('button');overviewButton.type='button';overviewButton.className='world-overview-button';overviewButton.dataset.worldOverview='';overviewButton.textContent='⌑ See the whole studio';overviewButton.setAttribute('aria-pressed','false');navigationLayer.append(overviewButton);
const journeyNote=document.createElement('div');journeyNote.className='world-journey';journeyNote.setAttribute('role','status');journeyNote.setAttribute('aria-live','polite');journeyNote.hidden=true;navigationLayer.append(journeyNote);
const roomMap=document.createElement('nav');roomMap.className='world-room-map';roomMap.setAttribute('aria-label','Connected studio rooms');
roomMap.classList.add('world-scenario-map');
roomMap.innerHTML='<span class="world-map-caption">STUDIO MAP</span><div class="world-map-stages">'+['workshop','lounge'].map(id=>'<button type="button" data-world-room="'+id+'"><i>'+studioRooms[id].number+'</i><span>'+studioRooms[id].title+'</span></button>').join('')+'<section class="world-map-scenarios"><button type="button" data-world-room="mission"><i>03</i><span>Multi-Agent</span></button><div>'+scenarioFloors.map(s=>'<button type="button" data-world-scenario="'+s.id+'" style="--scenario-accent:'+s.accent+'"><span class="world-scenario-dot" aria-hidden="true"></span>'+escape(s.title)+'</button>').join('')+'</div></section></div>';
navigationLayer.append(roomMap);
const roomGuides={
  workshop:{label:'ROOM 01 / QUICK GUIDE',title:'Hiring',anchor:new THREE.Vector3(-.85,2.12,-3.92),intro:'Create a personal <button type="button" class="world-paper-term" data-paper-term="agent">agent</button> with a recognizable identity and a clear job to do.',points:['Choose its appearance, name, working style and voice.','Choose each <button type="button" class="world-paper-term" data-paper-term="skill">skill</button> that fits the role you want it to perform.','Choose whether OpenShell protection should isolate its tools and file access.'],note:'Hiring saves an independent profile and workspace. Agents can respond to your requests; Tech Radar can also run scheduled Heartbeat updates.'},
  lounge:{label:'ROOM 02 / QUICK GUIDE',title:'Agent Lounge',anchor:new THREE.Vector3(3.75,2.12,-5.78),intro:'Meet your hired agents and give each one work in its own context.',points:['Select an agent to open its conversation, memory and files.','Run a suggested mission or write a request of your own.','Review visible activity, results and OpenShell policy decisions before trusting the outcome.'],note:'Each agent keeps its own persona, skills and workspace. Ready and Busy describe observed work, not model capability.'},
  mission:{label:'ROOM 03 / QUICK GUIDE',title:'Multi-Agent demo',anchor:new THREE.Vector3(2.45,4.02,-6.98),intro:'Choose how your team works together.',points:['Event Brief uses Casey, Dylan, Alex and Morgan to prepare demos, staffing and an event page.','Open Task lets Casey choose specialists for your /plan request.','Each space keeps its own conversations and results. Click its floor or Studio Map entry to continue.'],note:'Model responses and saved contributions appear in Mission Control. Access is enforced by the runtime and OpenShell policies.'},
};
const termGuides={
  agent:{title:'Agent : a definition',body:['An agent is a software worker powered by a language model and configured for a particular purpose.','In Build-a-Claw, each agent combines an identity, instructions, selected skills, memory and a separate workspace. It can reason about a request and use the tools allowed by its runtime policy.','An agent is not a person or an independent authority. It can respond to requests or run configured scheduled work. Review its actions and results.']},
  skill:{title:'Skill : What is it',body:['A skill is a reusable set of instructions that teaches an agent how to approach a particular kind of work.','Equipping a skill makes that guidance available to the agent. It does not bypass permissions or guarantee that the skill was used in every answer.','Runtime activity and result evidence show what the agent actually read or used while completing a task.']}
};
const roomPaper=document.createElement('aside');roomPaper.className='world-room-paper';roomPaper.hidden=true;roomPaper.setAttribute('role','dialog');roomPaper.setAttribute('aria-modal','false');roomPaper.setAttribute('aria-labelledby','world-room-paper-title');
roomPaper.innerHTML='<button type="button" class="world-room-paper-close" aria-label="Close room information">×</button><small></small><h2 id="world-room-paper-title"></h2><p class="world-room-paper-intro"></p><ol></ol><p class="world-room-paper-note"></p><footer>BUILD-A-CLAW · STUDIO NOTES</footer>';
navigationLayer.append(roomPaper);
const termPaper=document.createElement('aside');termPaper.className='world-room-paper world-term-paper';termPaper.hidden=true;termPaper.setAttribute('role','dialog');termPaper.setAttribute('aria-modal','false');termPaper.setAttribute('aria-labelledby','world-term-paper-title');
termPaper.innerHTML='<button type="button" class="world-room-paper-close" aria-label="Close definition">×</button><small>FIELD NOTES / GLOSSARY</small><h2 id="world-term-paper-title"></h2><div class="world-term-paper-body"></div><footer>BUILD-A-CLAW · STUDIO NOTES</footer>';
navigationLayer.append(termPaper);
let roomInfoReturn=null,termInfoReturn=null;
function closeTermInfo(restoreFocus=true){
  if(termPaper.hidden)return;
  termPaper.hidden=true;navigationLayer.dataset.termOpen='false';
  const target=termInfoReturn;termInfoReturn=null;
  if(restoreFocus)target?.focus({preventScroll:true});
}
function closeRoomInfo(restoreFocus=true){
  if(roomPaper.hidden)return;
  closeTermInfo(false);
  roomPaper.hidden=true;
  const target=roomInfoReturn;roomInfoReturn=null;
  if(restoreFocus)target?.focus({preventScroll:true});
}
function openRoomInfo(id,trigger){
  const guide=roomGuides[id];if(!guide)return;
  closeTermInfo(false);
  roomInfoReturn=trigger;roomPaper.querySelector('small').textContent=guide.label;
  roomPaper.querySelector('h2').textContent=guide.title;
  roomPaper.querySelector('.world-room-paper-intro').innerHTML=guide.intro;
  roomPaper.querySelector('ol').innerHTML=guide.points.map(point=>'<li>'+point+'</li>').join('');
  roomPaper.querySelector('.world-room-paper-note').textContent=guide.note;
  roomPaper.hidden=false;roomPaper.querySelector('.world-room-paper-close').focus({preventScroll:true});
}
function openTermInfo(id,trigger){
  const guide=termGuides[id];if(!guide)return;
  termInfoReturn=trigger;termPaper.querySelector('h2').textContent=guide.title;
  termPaper.querySelector('.world-term-paper-body').innerHTML=guide.body.map(paragraph=>'<p>'+paragraph+'</p>').join('');
  termPaper.hidden=false;navigationLayer.dataset.termOpen='true';
  termPaper.querySelector('.world-room-paper-close').focus({preventScroll:true});
}
roomPaper.querySelector('.world-room-paper-close').onclick=()=>closeRoomInfo();
roomPaper.onclick=e=>{const term=e.target.closest('[data-paper-term]');if(term)openTermInfo(term.dataset.paperTerm,term);};
roomPaper.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeRoomInfo();}};
termPaper.querySelector('.world-room-paper-close').onclick=()=>closeTermInfo();
termPaper.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeTermInfo();}};
root.addEventListener('pointerdown',e=>{if(!roomPaper.hidden&&!e.target.closest('.world-room-paper,[data-room-info]'))closeRoomInfo(false);},true);
const roomInfoMarkers=Object.keys(roomGuides).map(id=>{
  const node=document.createElement('button');node.type='button';node.className='world-room-info';node.dataset.roomInfo=id;
  node.textContent='I';node.setAttribute('aria-label','About '+studioRooms[id].title);node.title='About '+studioRooms[id].title;
  node.onclick=()=>openRoomInfo(id,node);navigationLayer.append(node);return {id,node};
});
function goToRoom(next){
  const restoreFocus=navigationLayer.contains(document.activeElement);
  root.dispatchEvent(new CustomEvent('bac:world-room',{detail:{room:next}}));
  if(restoreFocus)roomMap.querySelector('[data-world-room="'+next+'"]')?.focus({preventScroll:true});
}
function goToScenario(id){if(!scenarioPending)root.dispatchEvent(new CustomEvent('bac:world-scenario',{detail:{id}}));}
roomMap.onclick=e=>{const scenario=e.target.closest('[data-world-scenario]');if(scenario){goToScenario(scenario.dataset.worldScenario);return;}const button=e.target.closest('[data-world-room]');if(button)goToRoom(button.dataset.worldRoom);};
overviewButton.onclick=()=>scenarioGallery?showOverview():overview?goToRoom(room):showOverview();

// Hiring and BaC connect through the lounge; no long outer bridge.
const connections=[
  ...scenarioFloors.map(s=>({from:'lounge',to:'mission',scenario:s.id,points:scenarioPath(s.id)})),
  {from:'lounge',to:'workshop',points:[[0,6.3],[0,13.75]]}
];
function hallRail(parent,x,z,length){
  box(parent,x,.055,z,length,.035,.045,0x76b900,true);
  box(parent,x,.48,z,length,.055,.065,0x617b90);
  for(let p=-length/2+.12;p<length/2;p+=Math.max(.25,(length-.24)/Math.max(1,Math.ceil(length/4))))box(parent,x+p,.24,z,.055,.48,.055,0x617b90);
}
// Split shared paths at junctions so rails never fence off another scenario.
const junctions=new Map(),hallEdges=new Map();
const pointKey=([x,z])=>x.toFixed(3)+':'+z.toFixed(3);
for(const c of connections)for(const point of c.points)junctions.set(pointKey(point),{point,neighbors:new Set()});
for(const c of connections){
  const segments=[];let length=0;
  for(let i=1;i<c.points.length;i++){
    const [sx,sz]=c.points[i-1],[ex,ez]=c.points[i],distance=Math.hypot(ex-sx,ez-sz),angle=-Math.atan2(ez-sz,ex-sx);
    segments.push({sx,sz,ex,ez,distance,offset:length,angle});length+=distance;
    const onSegment=[...junctions.values()].filter(({point:[x,z]})=>Math.abs((x-sx)*(ez-sz)-(z-sz)*(ex-sx))<.001&&x>=Math.min(sx,ex)-.001&&x<=Math.max(sx,ex)+.001&&z>=Math.min(sz,ez)-.001&&z<=Math.max(sz,ez)+.001).sort((a,b)=>Math.hypot(a.point[0]-sx,a.point[1]-sz)-Math.hypot(b.point[0]-sx,b.point[1]-sz));
    for(let j=1;j<onSegment.length;j++){
      const a=onSegment[j-1],b=onSegment[j],ak=pointKey(a.point),bk=pointKey(b.point);
      if(ak===bk)continue;a.neighbors.add(bk);b.neighbors.add(ak);hallEdges.set([ak,bk].sort().join('|'),[a,b]);
    }
  }
  const pulse=box(scene,0,.11,0,.48,.035,1.7,0x96d52b,true);pulse.visible=false;
  corridors.push({...c,segments,length,pulse});
}
for(const [a,b] of hallEdges.values()){
  const [sx,sz]=a.point,[ex,ez]=b.point,distance=Math.hypot(ex-sx,ez-sz),angle=-Math.atan2(ez-sz,ex-sx);
  const hall=new THREE.Group();hall.position.set(sx,0,sz);hall.rotation.y=angle;scene.add(hall);
  const start=a.neighbors.size>1?Math.min(1.2,distance/2-.02):0,end=distance-(b.neighbors.size>1?Math.min(1.2,distance/2-.02):0),width=end-start,x=(start+end)/2;
  box(hall,x,-.18,0,width,.36,2.4,0x172330);box(hall,x,.015,0,width,.04,2.25,0x35485a);
  for(const z of [-1.14,1.14])hallRail(hall,x,z,width);
  for(let p=start+.5;p<end-.2;p+=1.05)box(hall,p,.043,0,.38,.015,.1,0x92b4c9);
}
for(const junction of junctions.values()){
  if(junction.neighbors.size<2)continue;
  const [x,z]=junction.point,corner=new THREE.Group();corner.position.set(x,0,z);scene.add(corner);
  box(corner,0,-.18,0,2.4,.36,2.4,0x172330);box(corner,0,.015,0,2.25,.04,2.25,0x35485a);
  const open=[...junction.neighbors].map(key=>{const [px,pz]=junctions.get(key).point;return [Math.sign(px-x),Math.sign(pz-z)];});
  for(const [dx,dz] of [[-1,0],[1,0],[0,-1],[0,1]])if(!open.some(([ox,oz])=>dx===ox&&dz===oz)){
    const edge=new THREE.Group();corner.add(edge);edge.rotation.y=dx?Math.PI/2:0;hallRail(edge,0,dx?dx*1.14:dz*1.14,2.4);
  }
  ring(corner,0,.055,0,.32,0x96d52b);
}
function doorway(from,to,x,z,rotation=0,parent=studioRooms[from].group){
  const group=new THREE.Group();group.position.set(x,0,z);group.rotation.y=rotation;parent.add(group);
  box(group,0,.055,0,.65,.1,2.35,0x3d5265);
  for(const z of [-1.1,1.1]){box(group,0,1.1,z,.18,2.2,.18,0x627e93);box(group,.105,1.14,z,.03,1.94,.045,0x96d52b,true);}
  box(group,0,2.2,0,.22,.18,2.4,0x344d60);box(group,.13,2.2,0,.026,.09,2.04,0x96d52b,true);
  doorways.push({from,to,group});
}
doorway('lounge','mission',8.8,0);doorway('mission','lounge',-10.6,0);
scenarioFloors.forEach(s=>doorway('scenario:'+s.id,'lounge',-10.6,0,0,s.group));
doorway('lounge','workshop',0,6.1,Math.PI/2);doorway('workshop','lounge',0,-4.05,Math.PI/2);
for(const [id,r] of Object.entries(studioRooms).filter(([id])=>id!=='mission')){
  const node=document.createElement('button');node.type='button';node.className='world-campus-room';node.dataset.worldRoom=id;
  node.innerHTML='<span>'+r.number+' / '+r.verb+'</span><b>'+r.title+'</b>';node.onclick=()=>goToRoom(id);navigationLayer.append(node);overviewLabels.push({id,node,group:r.group});
}
for(const r of scenarioFloors){
  const node=document.createElement('button');node.type='button';node.className='world-campus-room world-scenario-label';node.dataset.worldScenario=r.id;
  node.style.setProperty('--scenario-accent',r.accent);node.title=r.description;
  node.innerHTML='<span>03 / MULTI-AGENT</span><b>'+escape(r.title)+'</b><small>'+escape(r.description)+'</small><em class="world-scenario-status"></em>';
  node.onclick=()=>goToScenario(r.id);navigationLayer.append(node);overviewLabels.push({id:r.id,scenario:r.id,node,group:r.group});
}
function refreshScenarioLabels(){
  for(const item of overviewLabels.filter(r=>r.scenario)){
    const saved=scenarioStatus.find(s=>s.id===item.scenario),node=item.node.querySelector('.world-scenario-status');
    const text=saved?.busy?'In progress · Open ↗':saved?.hasWork?'Continue ↗':'Enter ↗';
    if(node.textContent!==text)node.textContent=text;
    item.node.classList.toggle('has-work',!!saved?.hasWork);item.node.disabled=scenarioPending;
  }
  roomMap.querySelectorAll('[data-world-scenario]').forEach(node=>{
    node.disabled=scenarioPending;node.classList.toggle('selected',room==='mission'&&!scenarioGallery&&node.dataset.worldScenario===activeScenario);
    node.setAttribute('aria-current',room==='mission'&&!scenarioGallery&&node.dataset.worldScenario===activeScenario?'location':'false');
  });
}
function roomHeight(id){
  const aspect=viewport.clientWidth/Math.max(1,viewport.clientHeight);
  return id==='workshop'?Math.max(6.8,8/aspect):(aspect<1?12.5:aspect<1.5?10.2:8.5)*(id==='mission'?1.1:1);
}
function overviewHeight(){return campusFrame(scenarioGallery).height;}
function roomFocus(id){return new THREE.Vector3(studioRooms[id].x,id==='workshop'?1.0:.25,studioRooms[id].z+.6);}
function refreshNavigation(){
  navigationLayer.dataset.overview=String(overview);navigationLayer.dataset.travelling=String(!!journey);
  root.dataset.worldOverview=String(overview);root.dataset.worldTravelling=String(!!journey);root.dataset.scenarioGallery=String(scenarioGallery);refreshScenarioLabels();
  hotspotLayer.hidden=room!=='mission'||overview||!!journey;el('labels').hidden=room!=='mission'||overview||!!journey;residentLayer.hidden=room!=='lounge'||overview||!!journey;
  overviewButton.textContent=scenarioGallery?'← Whole studio':overview?'↙ Return to '+studioRooms[room].title:'⌑ See the whole studio';overviewButton.setAttribute('aria-pressed',String(overview));
  overviewButton.setAttribute('aria-label',scenarioGallery?'See the whole studio':overview?'Return to '+studioRooms[room].title:'See the whole studio');
  roomMap.querySelectorAll('[data-world-room]').forEach(b=>{b.setAttribute('aria-current',b.dataset.worldRoom===room?'location':'false');b.classList.toggle('selected',b.dataset.worldRoom===room);});
  overviewLabels.forEach(r=>{r.node.hidden=!overview||!!journey||(scenarioGallery&&!r.scenario);r.node.setAttribute('aria-current',r.scenario?room==='mission'&&r.scenario===activeScenario?'location':'false':r.id===room?'location':'false');});
  roomInfoMarkers.forEach(marker=>marker.node.hidden=!!journey||overview||marker.id!==room);
  journeyNote.hidden=!journey&&!overview;
  if(!journey&&overview)journeyNote.textContent=scenarioGallery?'Choose a space to begin or continue.':'Choose a space in your studio.';
}
function rememberCamera(){if(!overview&&!journey)roomCameras[room]=[azimuth,elevation,zoom];}
function travelTo(target,instant=false,remaining=[]){
  endResidentDrag(true);drag=null;
  const start={focus:focus.clone(),azimuth,elevation,zoom,height:viewHalfHeight||roomHeight(room)};
  const delta=Math.atan2(Math.sin(target.azimuth-azimuth),Math.cos(target.azimuth-azimuth));target.azimuth=azimuth+delta;
  journey={start,target,began:performance.now(),duration:800,remaining,lift:target.overview?0:Math.min(.6,start.focus.distanceTo(target.focus)*.025)};
  refreshNavigation();
  if(instant||reduced.matches)finishJourney(true);
}
function finishJourney(instant=false){
  if(!journey)return;const {target,remaining}=journey;
  focus.copy(target.focus);azimuth=target.azimuth;elevation=target.elevation;zoom=target.zoom;viewHalfHeight=target.height;journey=null;
  if(remaining.length){travelTo(remaining[0],instant,remaining.slice(1));return;}
  refreshNavigation();frame();renderer.render(scene,camera);
}
function setRoom(next,options={}){
  closeRoomInfo(false);
  if(arrival)finishArrival();
  if(!studioRooms[next])return;
  if(next===room&&!overview&&!journey&&!scenarioMoved){resize();return;}
  scenarioMoved=false;scenarioGallery=false;
  // Finish the current corridor before rerouting rapid clicks; never cut across the courtyard.
  const inFlight=!overview&&journey?.target.to?journey.target:null;
  const previous=inFlight?.to||room;rememberCamera();room=next;overview=false;
  const stops=previous!==next&&previous!=='lounge'&&next!=='lounge'?['lounge',next]:previous!==next?[next]:[];
  const targets=inFlight?[inFlight]:[];
  let from=previous;
  for(const to of stops){
    const [a,e,z]=roomCameras[to];
    targets.push({focus:roomFocus(to),azimuth:a,elevation:e,zoom:z,height:roomHeight(to),overview:false,from,to,scenario:activeScenario});from=to;
  }
  if(!targets.length){const [a,e,z]=roomCameras[next];targets.push({focus:roomFocus(next),azimuth:a,elevation:e,zoom:z,height:roomHeight(next),overview:false,from:previous,to:next,scenario:activeScenario});}
  journeyNote.textContent=[previous,...stops].map(id=>studioRooms[id].title).join(' → ');
  travelTo(targets[0],options.instant,targets.slice(1));
}
function showOverview(options={}){
  closeRoomInfo(false);closeTermInfo(false);
  if(arrival)finishArrival();
  rememberCamera();overview=true;scenarioGallery=false;journeyNote.textContent='Opening your connected studio';
  travelTo({...campusFrame(),azimuth:.43,elevation:.64,zoom:1,overview:true},!!options.instant);
}
function showScenarios(options={}){
  closeRoomInfo(false);closeTermInfo(false);if(arrival)finishArrival();
  rememberCamera();room='mission';overview=true;scenarioGallery=true;
  journeyNote.textContent='Multi-Agent spaces';
  travelTo({...campusFrame(true),azimuth:.43,elevation:.64,zoom:1,overview:true},!!options.instant);
}
function resetNavigation(){
  roomCameras[room]=room==='workshop'?[.34,.64,1]:[.43,.76,1];
  if(overview){scenarioGallery?showScenarios():showOverview();return;}
  const [a,e,z]=roomCameras[room];journeyNote.textContent='Returning to '+studioRooms[room].title;
  travelTo({focus:roomFocus(room),azimuth:a,elevation:e,zoom:z,height:roomHeight(room),overview:false});
}
function resizeNavigation(){
  if(journey){for(const target of [journey.target,...journey.remaining])target.height=target.overview?overviewHeight():roomHeight(target.to||room);}
  else viewHalfHeight=overview?overviewHeight():roomHeight(room);
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
  overviewLabels.forEach(r=>{
    if(r.node.hidden)return;
    positionLabel(r.node,r.group.localToWorld(new THREE.Vector3(0,r.id==='workshop'?1:r.scenario?4.8:4.5,r.id==='workshop'?3:r.scenario?-5.8:-1.7)));
    const controlsBottom=Math.max(overviewButton.offsetTop+overviewButton.offsetHeight,journeyNote.offsetHeight?journeyNote.offsetTop+journeyNote.offsetHeight:0);
    r.node.style.top=Math.max(controlsBottom+12+r.node.offsetHeight,parseFloat(r.node.style.top))+'px';
  });
  // Keep every entrance clickable when rows are added or the desktop narrows.
  const placed=[];
  for(const {node} of overviewLabels.filter(r=>!r.node.hidden).sort((a,b)=>parseFloat(a.node.style.top)-a.node.offsetHeight-(parseFloat(b.node.style.top)-b.node.offsetHeight))){
    const width=node.offsetWidth,height=node.offsetHeight;
    const left=THREE.MathUtils.clamp(parseFloat(node.style.left)-width/2,12,viewport.clientWidth-width-12);
    let top=parseFloat(node.style.top)-height;
    for(const other of placed)if(left<other.right+10&&left+width>other.left-10&&top<other.bottom+10&&top+height>other.top-10)top=other.bottom+10;
    top=Math.min(top,viewport.clientHeight-height-12);
    node.style.left=(left+width/2)+'px';node.style.top=(top+height)+'px';
    placed.push({left,right:left+width,top,bottom:top+height});
  }
  roomInfoMarkers.forEach(marker=>{
    if(marker.node.hidden)return;
    positionLabel(marker.node,studioRooms[marker.id].group.localToWorld(roomGuides[marker.id].anchor.clone()));
    const half=marker.node.offsetWidth/2;
    marker.node.style.left=THREE.MathUtils.clamp(parseFloat(marker.node.style.left),half+12,viewport.clientWidth-half-12)+'px';
    marker.node.style.top=THREE.MathUtils.clamp(parseFloat(marker.node.style.top),half+12,viewport.clientHeight-half-12)+'px';
  });
  // Highlight only the bridge for the current trip, in the direction of travel.
  corridors.forEach(c=>{
    const target=journey?.target,matching=!c.scenario||c.scenario===activeScenario,forward=matching&&target?.from===c.from&&target?.to===c.to,backward=matching&&target?.from===c.to&&target?.to===c.from;
    c.pulse.visible=!!journey&&!reduced.matches&&(forward||backward);
    if(!c.pulse.visible)return;
    const t=Math.min(1,(now-journey.began)/journey.duration),distance=(forward?t:1-t)*c.length;
    const s=c.segments.find(s=>distance<=s.offset+s.distance)||c.segments[c.segments.length-1],p=(distance-s.offset)/s.distance;
    c.pulse.position.set(THREE.MathUtils.lerp(s.sx,s.ex,p),.11,THREE.MathUtils.lerp(s.sz,s.ez,p));c.pulse.rotation.y=s.angle;
  });
}
function navigationTargets(){
  if(overview)return [...(scenarioGallery?[]:[workshopRoom,loungeRoom]),missionRoom,...scenarioFloors.filter(s=>s.group.visible).map(s=>s.group)];
  return room==='mission'?hitTargets.filter(o=>robots[o.userData.agent]?.robot.visible):roomHitTargets();
}
function selectNavigationObject(object){
  for(let node=object;node;node=node.parent){
    if(overview&&node.userData.scenario){goToScenario(node.userData.scenario);return true;}
    if(overview&&node.userData.studioRoom){goToRoom(node.userData.studioRoom);return true;}
  }
  return false;
}
function navigationInfo(){return {overview,scenarioGallery,activeScenario,scenarios:scenarioFloors.map(s=>{const p=new THREE.Vector3(s.x+8,.03,s.z+5).project(camera);return {id:s.id,x:s.x,z:s.z,active:s.id===activeScenario,screenEntry:[(p.x*.5+.5)*viewport.clientWidth,(-p.y*.5+.5)*viewport.clientHeight]};}),travelling:!!journey,route:journey?[journey.target,...journey.remaining].map(t=>({from:t.from,to:t.to})):[],focus:focus.toArray(),rooms:Object.fromEntries(Object.entries(studioRooms).map(([id,r])=>[id,r.group.position.toArray()])),visibleRooms:Object.keys(studioRooms).filter(id=>studioRooms[id].group.visible),doorways:doorways.map(d=>({from:d.from,to:d.to})),corridors:corridors.map(c=>({from:c.from,to:c.to,points:c.points,active:c.pulse.visible}))};}
reduced.addEventListener('change',()=>{if(reduced.matches)finishJourney(true);});
focus.copy(roomFocus(room));viewHalfHeight=roomHeight(room);refreshNavigation();
