// Three.js is bundled above. The scene consumes the same workflow state as the board.
const app = document.getElementById('bac-planner');
const root = document.getElementById('agent-campus');
const el = name => document.getElementById('campus-' + name);
const api = window.BacDemo;
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors = [0xa3dc53, 0x75b6e7, 0xe3b85d, 0xf18f73, 0xc1a2ed];
const hex = i => '#' + colors[i].toString(16);
let snapshot = api.snapshot(), selected = 0, playing = false, timer = null, lastEvent = '', lastPhase = -2;
let sceneView = null;
const entries = [];
function log(message, detail) {
  entries.unshift({message, detail}); entries.splice(7);
  el('log').innerHTML = entries.map((item,i) => `<li>${escape(item.message)}<small>${i===0?'LATEST · ':''}${escape(item.detail)}</small></li>`).join('');
}
function stop() { playing=false; clearTimeout(timer); timer=null; updatePlay(); }
function updatePlay() { el('play').textContent = playing ? 'Ⅱ Pause the crew' : snapshot.phase===6 ? '✓ Plan complete' : snapshot.phase<0 ? '▶ Run the crew' : '▶ Continue the crew'; el('play').disabled=snapshot.phase===6; }
function schedule() {
  clearTimeout(timer);
  if (!playing) return;
  if ((snapshot.phase===2&&snapshot.gap)||snapshot.phase===5||snapshot.phase===6) { stop(); return; }
  timer=setTimeout(()=>{ api.act('next'); schedule(); },4500);
}
function run() {
  if (playing) {stop();return;}
  if (snapshot.phase===6) return;
  playing=true;
  if (snapshot.phase<0) api.begin();
  if (snapshot.phase<0) {stop();api.showMode('crew');return;}
  updatePlay(); schedule();
}
function choose(i) {selected=i;api.select(i);render();}
function render() {
  const a=snapshot.agents[selected], b=snapshot.brief;
  el('agent-number').textContent=String(selected+1).padStart(2,'0')+' / 05';
  el('agent-name').textContent=a.name; el('agent-role').textContent=a.role;
  el('portrait').style.setProperty('--agent-color',hex(selected));
  el('persona').textContent='“'+a.persona+'”';
  el('skills').innerHTML=a.skills.map(skill=>'<span>'+escape(skill)+'</span>').join('');
  el('task').textContent=a.task; el('agent-status').textContent=a.status;el('access').textContent=a.permission;
  el('roster').innerHTML=snapshot.agents.map((agent,i)=>`<button data-campus-agent="${i}" data-lane="${agent.lane}" aria-pressed="${i===selected}"><b><span class="status-dot"></span>${escape(agent.name)}</b><small>${escape(agent.role)}</small></button>`).join('');
  el('location').textContent=b ? (b.location+' / '+b.region).toUpperCase() : 'ZURICH / SWITZERLAND';
  el('revision').textContent=b?'BRIEF V'+snapshot.revision:'READY';
  el('flow-title').textContent=snapshot.flow[0]; el('flow-text').textContent=snapshot.flow[1];
  el('metrics').innerHTML=b?`<span><strong>${b.attendees}</strong> attendees</span><span><strong>${b.duration}</strong> minutes</span><span><strong>${b.groupSize} / ${b.session} min</strong> group / session</span>`:'<span><strong>120</strong> attendees</span><span><strong>180</strong> minutes</span><span><strong>English</strong> event language</span>';
  el('progress').innerHTML=['Brief','Demos','Resources','Copy','Review','Access','Ready'].map((label,i)=>`<span class="${i<snapshot.phase?'done':i===snapshot.phase?'active':''}">${label}</span>`).join('');
  el('step').textContent=snapshot.phase<0?'Start planning →':snapshot.flow[2]+' →';
  el('step').disabled=snapshot.phase===5||(snapshot.phase===2&&snapshot.gap);
  el('choices').replaceChildren();
  if(snapshot.phase===2&&snapshot.gap) {
    el('choices').innerHTML=`<p>Atlas found a capacity gap. The crew is waiting for your decision.</p>${snapshot.calc.minDuration&&snapshot.calc.minDuration<=1440?'<button data-campus-decision="extend">Extend to '+snapshot.calc.minDuration+' minutes</button>':''}<button data-campus-decision="extra-gear">Plan extra equipment</button>`;
  } else if(snapshot.phase===5) {
    el('choices').innerHTML='<p>Delivery is blocked at the access boundary. This is a policy simulation, not live OpenShell enforcement.</p><button data-campus-decision="approve">Simulate allow once</button><button data-campus-decision="deny">Keep drafts local</button>';
  }
  updatePlay();
  if(sceneView) sceneView.update(snapshot,selected);
}
app.addEventListener('bac:crew-state',event=>{
  snapshot=event.detail;
  const key=[snapshot.revision,snapshot.phase,snapshot.gap,snapshot.policy].join(':');
  if(key!==lastEvent) {
    if(snapshot.phase>=0) log(snapshot.flow[0],snapshot.flow[1]);
    if(snapshot.phase!==lastPhase) selected=snapshot.selected;
    lastPhase=snapshot.phase;lastEvent=key;
    if(playing&&((snapshot.phase===2&&snapshot.gap)||snapshot.phase===5||snapshot.phase===6))stop();
  }
  render();
});
el('roster').addEventListener('click',event=>{const button=event.target.closest('[data-campus-agent]');if(button)choose(Number(button.dataset.campusAgent));});
el('play').addEventListener('click',run);
el('step').addEventListener('click',()=>{stop();if(snapshot.phase<0)api.begin();else if(snapshot.phase===6){api.showMode('crew');api.act('brief');}else api.act('next');});
el('choices').addEventListener('click',event=>{const button=event.target.closest('[data-campus-decision]');if(button){api.act(button.dataset.campusDecision);if(snapshot.phase<5){playing=true;updatePlay();schedule();}}});
el('edit').addEventListener('click',()=>{stop();api.showMode('crew');const form=app.querySelector('[data-part="brief"]');if(form.hidden)api.act('brief');});
el('board').addEventListener('click',()=>{api.showMode('crew');api.act('close-agent');app.querySelector('[data-view-switch="board"]').click();app.querySelector('[data-part="workspace"]').scrollIntoView({behavior:'smooth',block:'start'});});
el('inspect-output').addEventListener('click',()=>{api.artifact(['scenario','scenario','operations','email','review'][selected]);api.showMode('crew');api.act('close-agent');app.querySelector('.inspector').scrollIntoView({behavior:'smooth',block:'start'});});
el('customize').addEventListener('click',()=>{stop();api.showMode('playground');document.getElementById('pg-name').focus();});
root.querySelectorAll('[data-campus-skill]').forEach(button=>button.addEventListener('click',()=>{api.showMode('playground');app.dispatchEvent(new CustomEvent('bac:open-skill',{detail:button.dataset.campusSkill}));}));
app.addEventListener('bac:skill-result',event=>{log(event.detail.name+' used '+event.detail.skill,event.detail.evidence);});
app.addEventListener('bac:mode',event=>{if(event.detail!=='campus')stop();sceneView?.resize();});
log('Your crew is ready to meet you.','Select a robot to explore its persona, skills and access.');
log('The same brief connects all five roles.','Run the crew to see handoffs, resource checks and a delivery decision.');

function createScene() {
  const viewport=el('viewport');
  const scene=new THREE.Scene();
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));
  renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
  viewport.prepend(renderer.domElement); renderer.domElement.setAttribute('aria-hidden','true');
  const camera=new THREE.OrthographicCamera(-11,11,7,-7,.1,100);
  const focus=new THREE.Vector3(0,.15,0);
  let azimuth=.43,elevation=.76,zoom=1,drag=null,moved=false;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let motion=!reduced.matches,visible=true,lastFrame=0,clock=0,phase=-2,state=snapshot,activeSelection=selected;
  let lost=false;
  scene.add(new THREE.HemisphereLight(0xf3f5ef,0x42513a,2.6));
  const sun=new THREE.DirectionalLight(0xfff9eb,3.0);sun.position.set(-5,15,8);sun.castShadow=true;
  sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-12;sun.shadow.camera.right=12;sun.shadow.camera.top=10;sun.shadow.camera.bottom=-10;sun.shadow.normalBias=.035;scene.add(sun);
  const fill=new THREE.DirectionalLight(0xd8edc5,1.2);fill.position.set(8,6,-9);scene.add(fill);
  const materials=new Map();
  function mat(color,glow=false){const key=color+':'+glow;if(!materials.has(key))materials.set(key,new THREE.MeshStandardMaterial({color,roughness:.68,metalness:.12,...(glow?{emissive:color,emissiveIntensity:.6}:{})}));return materials.get(key);}
  const boxGeometry=new THREE.BoxGeometry(1,1,1);
  function box(parent,x,y,z,w,h,d,color,glow=false){const object=new THREE.Mesh(boxGeometry,mat(color,glow));object.position.set(x,y,z);object.scale.set(w,h,d);object.castShadow=true;object.receiveShadow=true;parent.add(object);return object;}
  function cylinder(parent,x,y,z,r,h,color,segments=24){const object=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,segments),mat(color));object.position.set(x,y,z);object.castShadow=true;object.receiveShadow=true;parent.add(object);return object;}
  function ring(parent,x,y,z,r,color){const mesh=new THREE.Mesh(new THREE.TorusGeometry(r,.022,6,64),mat(color,true));mesh.rotation.x=-Math.PI/2;mesh.position.set(x,y,z);parent.add(mesh);return mesh;}
  function label(text,width=512,height=100,color='#d9e9c0',bg=null){const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const context=canvas.getContext('2d');if(bg){context.fillStyle=bg;context.fillRect(0,0,width,height);}context.fillStyle=color;context.font='600 '+Math.floor(height*.43)+'px Arial';context.textAlign='center';context.textBaseline='middle';context.fillText(text,width/2,height/2,width*.94);const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return new THREE.MeshBasicMaterial({map:texture,transparent:!bg,depthWrite:false});}
  function sign(parent,text,x,y,z,w,h,color,bg){const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),label(text,512,100,color,bg));mesh.position.set(x,y,z);parent.add(mesh);return mesh;}
  // A compact exhibition floor, built entirely from geometry; no downloaded assets.
  box(scene,0,-.42,0,18,.75,12.6,0x30382c);
  box(scene,0,-.025,0,17.85,.07,12.45,0x48503f);
  box(scene,0,-.3,6.31,17.3,.075,.025,0x91c940,true);
  for(let x=-8;x<=8;x+=1)box(scene,x,.02,0,.014,.008,12,0x58634b);
  for(let z=-6;z<=6;z+=1)box(scene,0,.02,z,17.8,.008,.014,0x58634b);
  box(scene,0,.65,-6.05,18,1.35,.18,0x3c4634);
  box(scene,-8.85,.65,0,.15,1.35,12,0x3c4634);
  box(scene,0,1.36,-6.05,18,.055,.24,0x9cb579);
  box(scene,-8.85,1.36,0,.22,.055,12,0x9cb579);
  // Back wall feature, screen, and common model server.
  box(scene,-.6,1.65,-5.97,6.6,2.3,.14,0x172016);
  sign(scene,'BUILD A CLAW',-.6,2.02,-5.86,5.6,.63,'#b7e878');
  sign(scene,'AGENT CAMPUS / ZURICH',-.6,1.43,-5.85,5.4,.38,'#879b73');
  for(let i=0;i<9;i++)box(scene,-3.1+i*.62,.92,-5.82,.4,.075,.02,0x6b9738,true);
  const positions=[[-5,-3.3],[0,-3.3],[5,-3.3],[-4.8,3.0],[3.8,3.0]];
  const homes=positions.map(([x,z])=>new THREE.Vector3(x,.05,z+1));
  const titles=['EVENT HQ','DEMO STUDIO','OPERATIONS','MARKETING','REVIEW'];
  const deskLights=[];
  positions.forEach(([x,z],i)=>{
    box(scene,x,.035,z,3.35,.04,2.65,0x535f46);
    box(scene,x,.064,z+1.25,3.3,.04,.045,colors[i],true);
    box(scene,x,.82,z,2.1,.14,.85,0xb2b9a0);
    box(scene,x-.75,.42,z,.14,.8,.55,0x414d37);box(scene,x+.75,.42,z,.14,.8,.55,0x414d37);
    box(scene,x,1.36,z-.22,1.45,.76,.1,0x26331e);
    box(scene,x,1.36,z-.159,1.29,.61,.016,0x14200e);
    for(let row=0;row<3;row++){box(scene,x-.32,1.53-row*.16,z-.145,.39+.13*row,.033,.01,colors[i],true);box(scene,x+.43,1.41-row*.09,z-.145,.17,.026,.01,0x536c3a);}
    box(scene,x,.92,z+.22,.74,.018,.24,0x6b775b);
    sign(scene,titles[i],x,.15,z+1.35,2.7,.32,'#e3edce','#3b4830');
    cylinder(scene,x+.85,.98,z+.12,.1,.21,colors[i],12);
    deskLights.push(ring(scene,x,.085,z,.38,colors[i]));
  });
  // Shared state hub: all agents use this same versioned brief.
  cylinder(scene,0,.23,.4,1.14,.44,0x25351d,48);cylinder(scene,0,.48,.4,1.02,.07,0x91ae6c,48);
  ring(scene,0,.525,.4,.93,0x9bdc48);
  const core=box(scene,0,.97,.4,.67,.8,.67,0x84b94a);core.rotation.y=Math.PI/4;
  const coreRing=ring(scene,0,1.24,.4,.72,0xc8f188);
  sign(scene,'SHARED BRIEF',0,.7,1.34,1.7,.25,'#d2ecb2','#2b3c20');
  // The access gate sits at the edge of the workspace.
  box(scene,7.2,.13,2.15,1.45,.26,1.8,0x38402d);
  box(scene,6.55,1.03,2.15,.12,1.8,.16,0x728753);box(scene,7.85,1.03,2.15,.12,1.8,.16,0x728753);
  const gate=box(scene,7.2,1.36,2.15,1.42,.09,.09,0xb4cf8a,true);
  sign(scene,'ACCESS',7.2,1.93,2.17,1.5,.3,'#d7e8bf','#27351d');
  // Small Spark-like appliance and planters, for scale and life.
  box(scene,7.35,.54,-5.03,1.1,1.05,.74,0x26331f);
  for(let y=.2;y<.9;y+=.11)box(scene,7.35,y,-4.65,.8,.035,.015,0x68834b);
  box(scene,7.67,.92,-4.64,.065,.065,.02,0xa4df5e,true);
  sign(scene,'SHARED MODEL',7.2,1.24,-4.63,1.7,.23,'#d8e9c1');
  function plant(x,z){cylinder(scene,x,.25,z,.24,.5,0x333d2a,8);for(let i=0;i<5;i++){const leaf=new THREE.Mesh(new THREE.ConeGeometry(.18,.62,5),mat(i%2?0x87a660:0x507637));leaf.position.set(x+Math.sin(i*2)*.18,.65+Math.cos(i)*.12,z+Math.cos(i*2)*.18);leaf.rotation.z=Math.sin(i)*.28;scene.add(leaf);}}
  plant(-8,-5.15);plant(-8,4.9);plant(8,5.15);plant(3.4,-5.2);
  // Narrow lit walkways visually tie all workstations to the shared state.
  positions.forEach(([x,z])=>{
    const points=[new THREE.Vector3(x,.073,z+1.05),new THREE.Vector3(x,.073,.4),new THREE.Vector3(0,.073,.4)];
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0xa0ba78,transparent:true,opacity:.65})));
  });
  const brand=sign(scene,'NVIDIA',0,.075,5.5,3.25,.72,'#bac6a8');brand.rotation.x=-Math.PI/2;
  const robots=[];const hitTargets=[];const labels=[];
  const headShape=new THREE.Shape();headShape.moveTo(-.29,-.2);headShape.lineTo(.29,-.2);headShape.lineTo(.29,.2);headShape.lineTo(-.29,.2);headShape.closePath();
  const headGeometry=new THREE.ExtrudeGeometry(headShape,{depth:.38,bevelEnabled:true,bevelThickness:.07,bevelSize:.065,bevelSegments:2,steps:1});headGeometry.translate(0,0,-.19);
  positions.forEach((_,i)=>{
    const robot=new THREE.Group();robot.position.copy(homes[i]);scene.add(robot);
    const body=new THREE.Group();robot.add(body);
    const torso=box(body,0,.55,0,.4,.38,.27,0xc1c8b2);
    const head=new THREE.Mesh(headGeometry,mat(0xc8cfb9));head.position.y=.98;head.castShadow=true;body.add(head);
    box(body,0,.99,.26,.49,.25,.025,0x24331e);
    box(body,-.125,1.005,.28,.062,.075,.024,colors[i],true);box(body,.125,1.005,.28,.062,.075,.024,colors[i],true);
    box(body,0,.53,.153,.23,.095,.021,colors[i],true);
    cylinder(body,0,1.29,0,.028,.16,0x617647,8);cylinder(body,0,1.4,0,.063,.06,colors[i],10);
    const arms=[],legs=[];
    for(const side of [-1,1]){const arm=new THREE.Group();arm.position.set(side*.29,.7,0);box(arm,0,-.15,0,.12,.3,.14,0xa0ad8f);body.add(arm);arms.push(arm);const leg=new THREE.Group();leg.position.set(side*.12,.34,0);box(leg,0,-.12,0,.14,.24,.15,0x80916c);box(leg,0,-.25,.045,.18,.08,.24,0x394d29);body.add(leg);legs.push(leg);}
    const halo=ring(scene,homes[i].x,.086,homes[i].z,.48,colors[i]);
    const packet=box(body,.39,.7,.2,.21,.27,.045,colors[i],true);packet.visible=false;
    robot.traverse(object=>{if(object.isMesh){object.userData.agent=i;hitTargets.push(object);}});
    const badge=document.createElement('div');badge.className='campus-agent-label';el('labels').append(badge);labels.push(badge);
    robots.push({robot,body,arms,legs,halo,packet,home:homes[i],path:[],idle:i*.9,destination:homes[i].clone()});
  });
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
  function cam(){const distance=22;camera.position.set(Math.sin(azimuth)*Math.cos(elevation)*distance,Math.sin(elevation)*distance,Math.cos(azimuth)*Math.cos(elevation)*distance);camera.lookAt(focus);camera.zoom=zoom;camera.updateProjectionMatrix();}
  function resize(){const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;const aspect=w/h;const vertical=aspect<1.15?10.5:7.8;camera.left=-vertical*aspect;camera.right=vertical*aspect;camera.top=vertical;camera.bottom=-vertical;renderer.setSize(w,h);cam();}
  function movement(){
    robots.forEach(r=>{r.path=[r.home.clone()];r.packet.visible=false;});
    const moving={0:[0,homes[1]],1:[1,homes[2]],2:[2,new THREE.Vector3(0,.05,1.8)],3:[3,homes[4]],4:[4,new THREE.Vector3(0,.05,1.8)],5:[3,new THREE.Vector3(7.2,.05,3.3)]}[state.phase];
    if(moving){const [i,target]=moving,r=robots[i];r.packet.visible=true;r.path=[new THREE.Vector3(r.robot.position.x,.05,.5),new THREE.Vector3(target.x,.05,.5),target.clone()];}
    gate.material=mat(state.phase===5?0xe4ad4f:state.phase===6?0xa5e85c:0xb4cf8a,true);
    el('motion-status').textContent=state.phase<0?'Crew ready · explore the campus':state.phase===5?'Waiting at the access boundary':state.phase===2&&state.gap?'Capacity gap · your decision needed':state.phase===6?'Planning package ready':'Handoff in progress · brief v'+state.revision;
    if(!motion){robots.forEach(r=>{if(r.path.length)r.robot.position.copy(r.path[r.path.length-1]);r.path=[];});}
  }
  function update(next,index){state=next;activeSelection=index;if(state.phase!==phase){phase=state.phase;movement();}labels.forEach((badge,i)=>{badge.innerHTML=escape(state.agents[i].name)+'<small>'+escape(state.agents[i].role)+'</small>';badge.classList.toggle('selected',i===index);badge.classList.toggle('waiting',state.agents[i].lane===2);});}
  function syncMotionButton(){el('motion').textContent=motion?'Ⅱ':'▶';el('motion').setAttribute('aria-label',motion?'Pause scene motion':'Resume scene motion');}
  el('motion').addEventListener('click',()=>{motion=!motion;syncMotionButton();});
  reduced.addEventListener('change',()=>{motion=!reduced.matches;syncMotionButton();});
  el('camera').addEventListener('click',()=>{azimuth=.43;elevation=.76;zoom=1;cam();});
  renderer.domElement.addEventListener('pointerdown',event=>{drag={x:event.clientX,y:event.clientY};moved=false;renderer.domElement.setPointerCapture(event.pointerId);});
  renderer.domElement.addEventListener('pointermove',event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)moved=true;azimuth-=dx*.006;elevation=Math.max(.45,Math.min(1.3,elevation+dy*.004));drag={x:event.clientX,y:event.clientY};cam();});
  renderer.domElement.addEventListener('pointerup',event=>{if(!moved){const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(hitTargets);if(hits.length)choose(hits[0].object.userData.agent);}drag=null;});
  renderer.domElement.addEventListener('pointercancel',()=>{drag=null;});
  renderer.domElement.addEventListener('wheel',event=>{event.preventDefault();zoom=Math.max(.75,Math.min(1.65,zoom-event.deltaY*.0008));cam();},{passive:false});
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;el('fallback').hidden=false;root.dataset.renderer='lost';});
  renderer.domElement.addEventListener('webglcontextrestored',()=>{lost=false;el('fallback').hidden=true;root.dataset.renderer='webgl';});
  new ResizeObserver(resize).observe(viewport);
  new IntersectionObserver(items=>{visible=items[0].isIntersecting;},{threshold:0}).observe(viewport);
  function animate(now){
    requestAnimationFrame(animate);
    if(document.hidden||root.hidden||!visible||lost){lastFrame=now;return;}
    if(now-lastFrame<32)return;
    const dt=Math.min((now-lastFrame)/1000,.07);lastFrame=now;
    if(motion)clock+=dt;
    robots.forEach((r,i)=>{
      let walking=false;
      if(motion){
        if(r.path.length){const target=r.path[0],delta=target.clone().sub(r.robot.position),distance=delta.length();if(distance<.08){r.path.shift();}else{walking=true;r.robot.position.addScaledVector(delta.normalize(),Math.min(distance,dt*2.1));r.robot.rotation.y=Math.atan2(delta.x,delta.z);}}
        else if(state.phase<0){const target=r.home.clone().add(new THREE.Vector3(Math.sin(clock*.55+i)*.52,0,Math.cos(clock*.55+i)*.22));const delta=target.clone().sub(r.robot.position);walking=true;r.robot.position.lerp(target,.05);r.robot.rotation.y=Math.atan2(delta.x,delta.z);}
        else r.robot.rotation.y=THREE.MathUtils.lerp(r.robot.rotation.y,.2,.04);
        r.body.position.y=walking?Math.abs(Math.sin(clock*9+i))*.047:Math.sin(clock*2+i)*.012;
        r.arms.forEach((arm,j)=>arm.rotation.x=walking?Math.sin(clock*9+i+j*Math.PI)*.5:Math.sin(clock*2+i)*.08);
        r.legs.forEach((leg,j)=>leg.rotation.x=walking?Math.sin(clock*9+i+j*Math.PI)*.42:0);
      }
      r.halo.position.x=r.robot.position.x;r.halo.position.z=r.robot.position.z;r.halo.visible=i===activeSelection||state.agents[i].lane===1;
      const projected=r.robot.position.clone().add(new THREE.Vector3(0,1.65,0)).project(camera);
      labels[i].style.left=(projected.x*.5+.5)*viewport.clientWidth+'px';labels[i].style.top=(-projected.y*.5+.5)*viewport.clientHeight+'px';
      labels[i].style.display=projected.z>1?'none':'block';
      deskLights[i].visible=state.agents[i].lane===1;
    });
    if(motion){core.rotation.y=clock*.35;coreRing.position.y=1.22+Math.sin(clock*1.6)*.04;}
    renderer.render(scene,camera);
  }
  syncMotionButton();resize();update(snapshot,selected);requestAnimationFrame(animate);
  root.dataset.renderer='webgl';
  return {resize,update,inspect:()=>({robots:robots.map(r=>r.robot.position.toArray()),phase,motion,camera:[azimuth,elevation,zoom]})};
}
try {sceneView=createScene();}catch(error){el('fallback').hidden=false;root.dataset.renderer='fallback';console.warn('3D unavailable; accessible workflow controls remain available.',error.message);}
window.BacCampus={inspect:()=>sceneView?.inspect()||{fallback:true}};
render();
