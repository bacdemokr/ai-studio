// Ambient personality vignettes, not model responses or evidence of tool use.
// All timing runs on the scene clock: no requests, timers or background jobs.
const loungePersonalities={
  guide:{title:'Guide',speed:.70,rest:[2.8,5.2],intro:name=>`Hey, I'm ${name}. Happy to help.`,lines:[
    'Small steps. We’ll figure it out.',
    'I like making tricky things feel simple.',
    'New here? You’re in good company.',
    'Ask away. There’s no silly question.',
    'A little encouragement goes a long way.'
  ]},
  maker:{title:'Maker',speed:1.02,rest:[1.2,3.0],intro:name=>`I'm ${name}. What should we build?`,lines:[
    'I learn best by making things.',
    'What if we tried something a little different?',
    'Give me an idea. I’ll bring the curiosity.',
    'My favorite question? “What if?”',
    'Small experiments. Plenty of possibilities.'
  ]},
  analyst:{title:'Analyst',speed:.57,rest:[3.8,6.5],intro:name=>`I'm ${name}. Let’s look a little closer.`,lines:[
    'I like a good question — and clear evidence.',
    'Details are kind of my thing.',
    'First, understand. Then, decide.',
    'A fresh perspective can change the picture.',
    'Curious, careful, and always asking why.'
  ]}
};
const loungeBounds={left:-7.1,right:7.1,back:-2.7,front:4.4};
let loungeTime=0,loungeSpeaker=null,lastLoungeSpeaker='',nextLoungeSpeech=.9;
function residentRandom(r){r.seed=(Math.imul(r.seed,1664525)+1013904223)>>>0;return r.seed/4294967296;}
function residentSeed(key){let seed=2166136261;for(const c of key)seed=Math.imul(seed^c.charCodeAt(0),16777619)>>>0;return seed;}
function loungeSpawn(){
  const spots=[[0,1.4],[-4.4,1.4],[4.4,1.4],[-2.2,-1.7],[2.2,-1.7],[-6.3,-1.7],[6.3,-1.7],[-6,4.1],[-2,4.1],[2,4.1],[6,4.1],[0,-.3]];
  const distance=([x,z])=>Math.min(...residents.map(r=>Math.hypot(r.group.position.x-x,r.group.position.z-z)));
  if(!residents.length)return spots[0];
  let best=spots.reduce((best,p)=>distance(p)>distance(best)?p:best,spots[0]);
  if(distance(best)<1.4)for(let x=-6.4;x<=6.4;x+=1.6)for(let z=-2.4;z<=4;z+=1.6)if(distance([x,z])>distance(best))best=[x,z];
  return best;
}
function endLoungeSpeech(){
  if(!loungeSpeaker)return;
  const r=loungeSpeaker;r.speechText='';r.node.dataset.speaking='false';r.node.querySelector('.world-resident-speech').hidden=true;
  r.node.removeAttribute('aria-describedby');r.node.removeAttribute('title');r.activity=r.pending?'assigned':'resting';r.waitUntil=loungeTime+1.1+residentRandom(r);loungeSpeaker=null;nextLoungeSpeech=loungeTime+2.7;
}
function setCollection(agents,key){
  collection=agents||[];selectedResident=key;residentLayer.dataset.dense=collection.length>6;
  // Reconcile by identity so polling, edits and new arrivals never teleport the crew.
  for(let i=residents.length-1;i>=0;i--){
    const r=residents[i];if(collection.some(a=>a.key===r.key))continue;
    if(loungeSpeaker===r)endLoungeSpeech();
    residentPods.remove(r.mount);clearGeometry(r.mount);r.node.remove();residents.splice(i,1);
  }
  collection.forEach((a,index)=>{
    const avatar={...avatarDefaults[index%5],...a.avatar};let r=residents.find(r=>r.key===a.key);
    if(!r){
      const [x,z]=loungeSpawn(),rig=createCharacter(avatar),mount=new THREE.Group();rig.group.scale.setScalar(1.3);rig.group.position.set(x,.015,z);mount.add(rig.group);residentPods.add(mount);
      const halo=ring(mount,x,.045,z,.65,rig.color);
      const node=document.createElement('button');node.type='button';node.className='world-resident';node.dataset.resident=a.key;node.dataset.speaking='false';node.innerHTML='<b></b><small></small><span class="world-resident-speech" hidden></span>';residentLayer.append(node);
      const speech=node.querySelector('.world-resident-speech');speech.id='lounge-speech-'+a.key;
      r={...rig,key:a.key,mount,node,halo,seed:residentSeed(a.key),target:null,waitUntil:loungeTime+.25+index*.4,activity:'resting',hovered:false,focused:false,saidIntro:false,line:0,speechText:'',blockedFor:0};residents.push(r);
      node.onclick=()=>root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:r.key}));
      node.onpointerenter=()=>r.hovered=true;node.onpointerleave=()=>r.hovered=false;
      node.onfocus=()=>r.focused=true;node.onblur=()=>r.focused=false;
    }else if(['body','color','accessory'].some(field=>r.appearance[field]!==avatar[field])){
      const old=r.group,rig=createCharacter(avatar);rig.group.scale.setScalar(1.3);rig.group.position.copy(old.position);rig.group.rotation.copy(old.rotation);
      r.mount.remove(old);clearGeometry(old);r.mount.add(rig.group);Object.assign(r,rig);r.halo.material=mat(rig.color,true);
    }
    if(r.persona!==a.persona||r.name!==a.name){if(loungeSpeaker===r)endLoungeSpeech();r.saidIntro=false;}
    r.name=a.name;r.persona=loungePersonalities[a.persona]?a.persona:'guide';r.pending=!!a.pending;
    if(r.pending&&loungeSpeaker===r)endLoungeSpeech();
    if(r.pending)r.activity='assigned';
    r.node.setAttribute('aria-label','Open '+a.name+'’s workspace');r.node.setAttribute('aria-pressed',r.key===key);r.node.style.setProperty('--resident-color','#'+r.color.toString(16).padStart(6,'0'));r.node.querySelector('b').textContent=a.name;
    r.node.querySelector('small').textContent=r.pending?'Mission assigned':loungePersonalities[r.persona].title+' · '+(a.skills||[]).length+' skills';
    r.halo.visible=r.key===key||r.pending||loungeSpeaker===r;
  });
  residentMeshes.length=0;residents.forEach(r=>r.group.traverse(o=>{if(o.isMesh){o.userData.resident=r.key;residentMeshes.push(o);}}));
  if(!residents.length){lastLoungeSpeaker='';nextLoungeSpeech=loungeTime+.9;}
}
function chooseLoungeTarget(r){
  const p=r.group.position;
  for(let attempt=0;attempt<24;attempt++){
    const angle=residentRandom(r)*Math.PI*2,length=2.2+residentRandom(r)*3.6;
    const x=THREE.MathUtils.clamp(p.x+Math.sin(angle)*length,loungeBounds.left,loungeBounds.right),z=THREE.MathUtils.clamp(p.z+Math.cos(angle)*length,loungeBounds.back,loungeBounds.front);
    if(Math.hypot(x-p.x,z-p.z)<1.6||residents.some(o=>o!==r&&Math.hypot(o.group.position.x-x,o.group.position.z-z)<1.7))continue;
    r.target=new THREE.Vector3(x,p.y,z);r.blockedFor=0;return;
  }
  r.waitUntil=loungeTime+.7;
}
function turnResident(r,angle,dt){const delta=Math.atan2(Math.sin(angle-r.group.rotation.y),Math.cos(angle-r.group.rotation.y));r.group.rotation.y+=delta*Math.min(1,dt*5);}
function moveResident(r,dt){
  const mood=loungePersonalities[r.persona],p=r.group.position;
  r.activity=r.pending?'assigned':loungeSpeaker===r?'speaking':'resting';
  if(r.pending||r.hovered||r.focused||loungeSpeaker===r)return false;
  if(!r.target&&loungeTime>=r.waitUntil)chooseLoungeTarget(r);
  if(!r.target)return false;
  const delta=r.target.clone().sub(p),distance=delta.length();
  if(distance<.18){r.target=null;r.waitUntil=loungeTime+mood.rest[0]+residentRandom(r)*(mood.rest[1]-mood.rest[0]);return false;}
  const steering=delta.normalize();
  residents.forEach(other=>{
    if(other===r)return;const away=p.clone().sub(other.group.position),gap=away.length();
    if(gap>0&&gap<1.95)steering.addScaledVector(away.normalize(),(1.95-gap)*1.5);
  });
  steering.normalize();const next=p.clone().addScaledVector(steering,Math.min(distance,dt*mood.speed));
  next.x=THREE.MathUtils.clamp(next.x,loungeBounds.left,loungeBounds.right);next.z=THREE.MathUtils.clamp(next.z,loungeBounds.back,loungeBounds.front);
  if(residents.some(o=>o!==r&&next.distanceTo(o.group.position)<1.18)||next.distanceTo(p)<.001){
    r.blockedFor+=dt;if(r.blockedFor>.75){r.target=null;r.waitUntil=loungeTime+.2+residentRandom(r)*.6;}return false;
  }
  r.blockedFor=0;p.copy(next);turnResident(r,Math.atan2(steering.x,steering.z),dt);r.activity='walking';return true;
}
function startLoungeSpeech(){
  if(loungeSpeaker||loungeTime<nextLoungeSpeech||overview||journey||room!=='lounge'||drag)return;
  const eligible=residents.filter(r=>!r.pending&&!r.hovered&&!r.focused);if(!eligible.length)return;
  const start=(residents.findIndex(r=>r.key===lastLoungeSpeaker)+1)%Math.max(1,residents.length);
  const ordered=[...residents.slice(start),...residents.slice(0,start)].filter(r=>eligible.includes(r));
  const r=ordered.find(r=>!r.saidIntro)||ordered[0],mood=loungePersonalities[r.persona];
  r.speechText=r.saidIntro?mood.lines[r.line++%mood.lines.length]:mood.intro(r.name);r.saidIntro=true;
  const speech=r.node.querySelector('.world-resident-speech');speech.textContent=r.speechText;speech.hidden=false;r.node.dataset.speaking='true';r.node.setAttribute('aria-describedby',speech.id);
  r.node.title='Personality vignette · select to open this agent’s workspace';r.speechUntil=loungeTime+5.8;r.target=null;
  loungeSpeaker=r;lastLoungeSpeaker=r.key;
  // Measure at the cue itself; observer notifications can lag room/fullscreen changes.
  const view=viewport.getBoundingClientRect();
  if(view.width&&view.height&&view.right>0&&view.left<innerWidth&&view.bottom>0&&view.top<innerHeight)studioSound.speak(r.persona,r.group.position.x/24);
}
function placeResident(r){
  positionLabel(r.node,loungeRoom.localToWorld(r.group.position.clone().add(new THREE.Vector3(0,2.2,0))));
  const x=parseFloat(r.node.style.left),y=parseFloat(r.node.style.top),half=r.node.offsetWidth/2,w=viewport.clientWidth,h=viewport.clientHeight;
  r.node.style.left=THREE.MathUtils.clamp(x,half+12,w-half-12)+'px';
  if(loungeSpeaker===r){
    // Leave navigation and the map unobstructed; the bubble replaces its own name tag.
    const top=Math.min(h-104,Math.max(114+r.node.offsetHeight,y));r.node.style.top=top+'px';
    r.node.style.setProperty('--speech-tail',THREE.MathUtils.clamp(x-parseFloat(r.node.style.left)+half,18,r.node.offsetWidth-18)+'px');
  }
}
function animateLounge(dt){
  if(motion){
    loungeTime+=dt;
    if(loungeSpeaker&&loungeTime>=loungeSpeaker.speechUntil&&!loungeSpeaker.hovered&&!loungeSpeaker.focused)endLoungeSpeech();
    startLoungeSpeech();
  }
  residents.forEach((r,index)=>{
    if(motion){
      const walking=moveResident(r,dt),speaking=loungeSpeaker===r,beat=loungeTime*(walking?8:1.7)+index;
      if(speaking)turnResident(r,azimuth,dt);
      else if(!walking&&!r.hovered&&!r.focused)turnResident(r,Math.sin(loungeTime*.4+index)*.35,dt);
      r.body.position.y=walking?Math.abs(Math.sin(beat))*.035:Math.sin(beat)*.018;
      r.legs.forEach((leg,j)=>leg.rotation.x=walking?Math.sin(beat+j*Math.PI)*.32:0);
      r.arms.forEach((arm,j)=>{arm.rotation.x=Math.sin(beat+j*Math.PI)*(walking?.27:.065);arm.rotation.z=speaking&&j===0?(r.persona==='guide'?-1.9+Math.sin(loungeTime*5)*.16:r.persona==='maker'?-1.15+Math.sin(loungeTime*4)*.2:-.48):0;});
    }
    r.halo.position.set(r.group.position.x,.045,r.group.position.z);r.halo.visible=r.key===selectedResident||r.pending||loungeSpeaker===r;
    placeResident(r);
  });
}
