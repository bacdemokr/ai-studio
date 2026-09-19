// A miniature agent workshop: role workbenches around one shared brief.
function createScene() {
  const viewport=el('viewport');
  const scene=new THREE.Scene();
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));
  renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.0;
  viewport.prepend(renderer.domElement); renderer.domElement.setAttribute('aria-hidden','true');
  const camera=new THREE.OrthographicCamera(-11,11,7,-7,.1,180);
  const focus=new THREE.Vector3(0,.15,0);
  let azimuth=.43,elevation=.76,zoom=1,drag=null,moved=false;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let motion=!reduced.matches,visible=true,lastFrame=0,clock=0,phase=-2,state=snapshot,activeSelection=selected;
  let lost=false,lastKey='',lastActive=-1,lastJob=null;
  scene.add(new THREE.HemisphereLight(0xf4f7ff,0x161c26,1.65));
  const sun=new THREE.DirectionalLight(0xffffff,3.0);sun.position.set(-5,15,8);sun.castShadow=true;
  sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-12;sun.shadow.camera.right=12;sun.shadow.camera.top=10;sun.shadow.camera.bottom=-10;sun.shadow.normalBias=.035;scene.add(sun);scene.add(sun.target);
  const fill=new THREE.DirectionalLight(0xc7ddff,.75);fill.position.set(8,6,-9);scene.add(fill);
  const materials=new Map();
  function mat(color,glow=false){const key=color+':'+glow;if(!materials.has(key))materials.set(key,new THREE.MeshStandardMaterial({color,roughness:.48,metalness:.16,...(glow?{emissive:color,emissiveIntensity:.35}:{})}));return materials.get(key);}
  const boxGeometry=new THREE.BoxGeometry(1,1,1);
  function box(parent,x,y,z,w,h,d,color,glow=false){const object=new THREE.Mesh(boxGeometry,mat(color,glow));object.position.set(x,y,z);object.scale.set(w,h,d);object.castShadow=true;object.receiveShadow=true;parent.add(object);return object;}
  function cylinder(parent,x,y,z,r,h,color,segments=24){const object=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,segments),mat(color));object.position.set(x,y,z);object.castShadow=true;object.receiveShadow=true;parent.add(object);return object;}
  function ring(parent,x,y,z,r,color){const mesh=new THREE.Mesh(new THREE.TorusGeometry(r,.022,6,64),mat(color,true));mesh.rotation.x=-Math.PI/2;mesh.position.set(x,y,z);parent.add(mesh);return mesh;}
  function label(text,width=512,height=100,color='#e8eef5',bg=null){const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const context=canvas.getContext('2d');if(bg){context.fillStyle=bg;context.fillRect(0,0,width,height);}context.fillStyle=color;context.font='600 '+Math.floor(height*.48)+'px Arial';context.textAlign='center';context.textBaseline='middle';context.fillText(text,width/2,height/2,width*.94);const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return new THREE.MeshBasicMaterial({map:texture,transparent:!bg,depthWrite:false,toneMapped:false});}
  function sign(parent,text,x,y,z,w,h,color,bg){const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),label(text,512,100,color,bg));mesh.position.set(x,y,z);parent.add(mesh);return mesh;}
  /* AGENT_CHARACTER */
  const missionRoom=new THREE.Group();scene.add(missionRoom);
  // A compact exhibition floor; the workshop artwork is bundled for offline use.
  box(missionRoom,0,-.42,0,18,.75,12.6,0x151b23);
  box(missionRoom,0,-.025,0,17.85,.07,12.45,0x2a333e);
  box(missionRoom,0,-.3,6.31,17.3,.075,.025,0x76b900,true);
  for(let x=-8;x<=8;x+=1)box(missionRoom,x,.02,0,.014,.008,12,0x3a4653);
  for(let z=-6;z<=6;z+=1)box(missionRoom,0,.02,z,17.8,.008,.014,0x3a4653);
  box(missionRoom,0,.65,-6.05,18,1.35,.18,0x1e2732);
  for(const [z,length] of [[-2.1,7.8],[5.1,1.8]])box(missionRoom,-8.85,.65,z,.15,1.35,length,0x1e2732);
  box(missionRoom,0,1.36,-6.05,18,.055,.24,0x63778b);
  for(const [z,length] of [[-2.1,7.8],[5.1,1.8]])box(missionRoom,-8.85,1.36,z,.22,.055,length,0x63778b);
  // A framed workshop display keeps the supplied illustration inside the 3D space.
  box(missionRoom,-.6,2.4,-5.97,5.8,3.8,.14,0x0c121b);
  sign(missionRoom,'BUILD A CLAW',-.6,4.0,-5.86,4.9,.38,'#f2f6fb');
  const artworkWidth=5.22,artworkHeight=artworkWidth*508/904;
  box(missionRoom,-.6,2.175,-5.875,artworkWidth+.14,artworkHeight+.14,.025,0x343f4c);
  const artworkTexture=new THREE.TextureLoader().load('__WORKSHOP_ART_DATA_URL__');
  artworkTexture.colorSpace=THREE.SRGBColorSpace;
  artworkTexture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
  const artwork=new THREE.Mesh(new THREE.PlaneGeometry(artworkWidth,artworkHeight),new THREE.MeshBasicMaterial({map:artworkTexture,toneMapped:false}));
  artwork.position.set(-.6,2.175,-5.849);missionRoom.add(artwork);
  box(missionRoom,-.6,.60,-5.86,5.22,.026,.02,0x76b900,true);
  const positions=[[-5,-3.3],[0,-3.3],[5,-3.3],[-4.8,3.0],[3.8,3.0]];
  const homes=positions.map(([x,z])=>new THREE.Vector3(x,.05,z+1));
  const titles=['EVENT HQ','DEMO STUDIO','OPERATIONS','MARKETING','REVIEW'];
  const deskLights=[],deskScreens=[],routes=[];
  positions.forEach(([x,z],i)=>{
    box(missionRoom,x,.035,z,3.35,.04,2.65,0x343f4c);
    box(missionRoom,x,.064,z+1.25,3.3,.04,.045,colors[i],true);
    box(missionRoom,x,.82,z,2.1,.14,.85,0xb6c3d1);
    box(missionRoom,x-.75,.42,z,.14,.8,.55,0x283544);box(missionRoom,x+.75,.42,z,.14,.8,.55,0x283544);
    box(missionRoom,x,1.36,z-.22,1.45,.76,.1,0x172432);
    const monitor=box(missionRoom,x,1.36,z-.159,1.29,.61,.016,0x070e17);monitor.material=mat(0x070e17).clone();deskScreens.push(monitor);
    for(let row=0;row<3;row++){box(missionRoom,x-.32,1.53-row*.16,z-.145,.39+.13*row,.033,.01,colors[i],true);box(missionRoom,x+.43,1.41-row*.09,z-.145,.17,.026,.01,0x41627d);}
    box(missionRoom,x,.92,z+.22,.74,.018,.24,0x5e7186);
    sign(missionRoom,titles[i],x,.15,z+1.35,2.7,.32,'#e8f0f8','#1c2835');
    cylinder(missionRoom,x+.85,.98,z+.12,.1,.21,colors[i],12);
    deskLights.push(ring(missionRoom,x,.085,z,.38,colors[i]));
  });
  // Shared state hub: all agents use this same versioned brief.
  cylinder(missionRoom,0,.23,.4,1.14,.44,0x152333,48);cylinder(missionRoom,0,.48,.4,1.02,.07,0x536d87,48);
  ring(missionRoom,0,.525,.4,.93,0x76b900);
  const core=box(missionRoom,0,1.5,.4,.35,.38,.35,0x76b900);core.rotation.y=Math.PI/4;
  const coreRing=ring(missionRoom,0,1.24,.4,.72,0x96d52b);
  sign(missionRoom,'SHARED BRIEF',0,.7,1.34,1.7,.25,'#d8edfb','#132536');
  // Layered data cards make shared state the physical center of the workspace.
  for(let i=0;i<3;i++){const card=box(missionRoom,0,.72+i*.23,.4,.92,.055,.7,0xb5d0e6);card.rotation.y=.12+i*.15;}

  // The access gate sits at the edge of the workspace.
  box(missionRoom,7.2,.13,2.15,1.45,.26,1.8,0x24303d);
  box(missionRoom,6.55,1.03,2.15,.12,1.8,.16,0x758a9e);box(missionRoom,7.85,1.03,2.15,.12,1.8,.16,0x758a9e);
  const gate=box(missionRoom,7.2,1.36,2.15,1.42,.09,.09,0x9bbacf,true);
  sign(missionRoom,'ACCESS',7.2,1.93,2.17,1.5,.3,'#e1eef8','#1d2e3e');
  // Small Spark-like appliance and planters, for scale and life.
  box(missionRoom,7.35,.54,-5.03,1.1,1.05,.74,0x1b2633);
  for(let y=.2;y<.9;y+=.11)box(missionRoom,7.35,y,-4.65,.8,.035,.015,0x4b637a);
  box(missionRoom,7.67,.92,-4.64,.065,.065,.02,0x76b900,true);
  sign(missionRoom,'SHARED MODEL',7.2,1.24,-4.63,1.7,.23,'#c4d5e8');
  function plant(x,z){cylinder(missionRoom,x,.25,z,.24,.5,0x35495c,8);for(let i=0;i<5;i++){const leaf=new THREE.Mesh(new THREE.ConeGeometry(.18,.62,5),mat(i%2?0x5d985b:0x295c40));leaf.position.set(x+Math.sin(i*2)*.18,.65+Math.cos(i)*.12,z+Math.cos(i*2)*.18);leaf.rotation.z=Math.sin(i)*.28;missionRoom.add(leaf);}}
  plant(-8,-5.15);plant(-8,4.9);plant(3.4,-5.2);
  // Narrow lit walkways visually tie all workstations to the shared state.
  positions.forEach(([x,z])=>{
    const points=[new THREE.Vector3(x,.073,z+1.05),new THREE.Vector3(x,.073,.4),new THREE.Vector3(0,.073,.4)];
    const route=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:colors[routes.length],transparent:true,opacity:.2}));missionRoom.add(route);routes.push(route);
  });
  const brand=sign(missionRoom,'NVIDIA',-3.5,.075,5.5,2.8,.62,'#aebdce');brand.rotation.x=-Math.PI/2;
  const robots=[];const hitTargets=[];const labels=[];
  positions.forEach((_,i)=>{
    const rig=createCharacter(avatarDefaults[i]),robot=rig.group;robot.position.copy(homes[i]);missionRoom.add(robot);
    const halo=ring(missionRoom,homes[i].x,.086,homes[i].z,.48,rig.color);
    const packet=box(rig.body,.39,.7,.2,.21,.27,.045,rig.color,true);packet.visible=false;
    robot.traverse(object=>{if(object.isMesh){object.userData.agent=i;hitTargets.push(object);}});
    const badge=document.createElement('div');badge.className='campus-agent-label';badge.style.setProperty('--agent-color',hex(i));el('labels').append(badge);labels.push(badge);
    robots.push({...rig,robot,halo,packet,home:homes[i],path:[],idle:i*.9,destination:homes[i].clone(),avatarKey:JSON.stringify(avatarDefaults[i])});
  });
  function dressCrew(){
    robots.forEach((r,i)=>{
      const avatar=state.agents[i].avatar||avatarDefaults[i],key=JSON.stringify(avatar);if(key===r.avatarKey)return;
      const rig=createCharacter(avatar);r.robot.remove(r.body);clearGeometry(r.body);r.robot.add(rig.body);
      r.body=rig.body;r.arms=rig.arms;r.legs=rig.legs;r.appearance=rig.appearance;r.avatarKey=key;
      r.packet=box(r.body,.39,.7,.2,.21,.27,.045,rig.color,true);r.packet.visible=false;
      r.halo.material=mat(rig.color,true);labels[i].style.setProperty('--agent-color','#'+rig.color.toString(16).padStart(6,'0'));
    });
    hitTargets.length=0;robots.forEach((r,i)=>r.robot.traverse(o=>{if(o.isMesh){o.userData.agent=i;hitTargets.push(o);}}));
  }
  const hotspotLayer=document.createElement('div');hotspotLayer.className='world-hotspots';viewport.append(hotspotLayer);
  const hotspots=[];
  function hotspot(id,title,subtitle,icon,x,y,z){const button=document.createElement('button');button.className='world-hotspot';button.dataset.worldSkill=id;button.setAttribute('aria-label',title+' — '+subtitle);button.innerHTML='<span aria-hidden="true">'+icon+'</span><b>'+escape(title)+'</b><small>'+escape(subtitle)+'</small>';button.onclick=()=>root.dispatchEvent(new CustomEvent('bac:world-skill',{detail:id}));hotspotLayer.append(button);hotspots.push({id,button,position:new THREE.Vector3(x,y,z)});}
  // The knowledge cabinet is shared by document and memory skills.
  box(missionRoom,-7.65,.88,-1.3,1.0,1.65,.48,0x293849);
  for(let shelf=0;shelf<3;shelf++){box(missionRoom,-7.65,.28+shelf*.5,-1.02,1.08,.07,.56,0x70889e);for(let j=0;j<4;j++)box(missionRoom,-7.99+j*.23,.5+shelf*.5,-1.05,.13,.35,.34,[0x76b900,0x479cda,0xe3b15d,0x9e85db][(j+shelf)%4]);}
  hotspot('documents','Knowledge library','Documents & saved memory','▤',-7.65,2.15,-1.3);
  // Public-source research console.
  box(missionRoom,-7.65,.6,1.25,1.05,1.1,.62,0x293849);box(missionRoom,-7.65,1.23,1.25,.85,.6,.1,0x355e79);sign(missionRoom,'WEB',-7.65,1.24,1.31,.72,.38,'#b6deff','#162a3c');
  hotspot('web','Web explorer','Read sources & gather evidence','⌕',-7.65,1.99,1.25);
  // Compact weather instrument instead of a landscape observatory.
  box(missionRoom,7.3,.55,-1.8,.94,1,.65,0x2e4053);cylinder(missionRoom,7.3,1.45,-1.8,.027,1.0,0xa4bfd3,8);const weatherRotor=new THREE.Group();weatherRotor.position.set(7.3,1.92,-1.8);missionRoom.add(weatherRotor);for(let i=0;i<3;i++){const blade=box(weatherRotor,0,0,0,.8,.028,.055,0x8caec8);blade.rotation.y=i*Math.PI/3;}sign(missionRoom,'WEATHER',7.3,.71,-1.462,.69,.24,'#b6deff','#182c3e');
  hotspot('weather','Weather lookout','Live conditions → a plan','☀',7.3,2.4,-1.8);
  // A paired-channel terminal at the front edge.
  box(missionRoom,7.2,.48,4.75,.9,.92,.75,0x24384b);box(missionRoom,7.2,1.19,4.7,.46,.75,.10,0x102032);sign(missionRoom,'↗',7.2,1.2,4.758,.37,.56,'#b7dbe8','#304850');
  hotspot('telegram','Telegram terminal','Continue with the same agent','↗',7.2,1.95,4.75);
  hotspot('builder','Maker workshop','Build a playable mini app','⌘',-1.65,1.84,-3.3);
  hotspot('writer','Campaign studio','Turn the brief into an invitation','✎',-6.35,1.8,3);
  hotspot('crew','Shared brief','Give your specialists a mission','◇',0,2.12,.4);
  hotspot('runtime','Shared model','One model for the whole crew','▥',7.35,1.85,-5.03);
  hotspot('security','Access gate','Try the boundary · inspect evidence','⊡',7.2,2.5,2.15);
  const packets=[];for(let i=0;i<4;i++){const packet=box(missionRoom,0,.6,0,.12,.17,.035,0xa5dbef,true);packet.visible=false;packets.push(packet);}
  let packetStart=new THREE.Vector3(),packetEnd=new THREE.Vector3(),packetTime=-20;
  let room='mission';
  /* WORLD_ROOMS */
  /* WORLD_NAVIGATION */
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
  function cam(){
    camera.position.set(Math.sin(azimuth)*Math.cos(elevation)*50,Math.sin(elevation)*50,Math.cos(azimuth)*Math.cos(elevation)*50).add(focus);
    camera.lookAt(focus);camera.zoom=zoom;camera.updateProjectionMatrix();camera.updateMatrixWorld();
    sun.position.copy(focus).add(new THREE.Vector3(-5,15,8));sun.target.position.copy(focus);sun.target.updateMatrixWorld();
  }
  function frame(){
    const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;
    const aspect=w/h,vertical=viewHalfHeight||roomHeight(room);
    camera.left=-vertical*aspect;camera.right=vertical*aspect;camera.top=vertical;camera.bottom=-vertical;cam();
  }
  // CSS owns layout; resize only the drawing buffer, never the canvas's CSS size.
  function resize(){
    const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;
    renderer.setSize(w,h,false);resizeNavigation();frame();renderer.render(scene,camera);
  }
  function movement(){
    robots.forEach(r=>{r.path=r.robot.position.distanceTo(r.home)>.06?[r.home.clone()]:[];r.packet.visible=false;});
    const active=state.agents.findIndex(a=>a.lane===1||a.lane===2);
    if(active>=0){
      const r=robots[active],station={builder:[0,-2.3],documents:[-6.55,-.45],memory:[-6.55,-.45],weather:[6.3,-1],web:[-6.5,1.6],writer:[-4.8,4]}[state.missionSkill];
      const target=station?new THREE.Vector3(station[0],.05,station[1]):r.home.clone();
      r.path=[new THREE.Vector3(r.robot.position.x,.05,.5),new THREE.Vector3(0,.05,.5),new THREE.Vector3(target.x,.05,.5),target];r.packet.visible=true;
      packetStart=lastJob===state.jobId&&lastActive>=0&&lastActive!==active?robots[lastActive].home.clone():new THREE.Vector3(0,.6,.4);packetEnd=target.clone();packetTime=clock;
    }
    lastActive=active;lastJob=state.jobId;
    routes.forEach((route,i)=>{route.material.opacity=i===active ? .85 : .18;});
    // Equipment decisions are app approvals; never color OpenShell as enforced from them.
    if(!motion)robots.forEach(r=>{if(r.path.length)r.robot.position.copy(r.path.at(-1));r.path=[];});
  }
  function update(next,index){state=next;activeSelection=index;phase=state.phase;dressCrew();const key=[state.jobId,state.phase,state.missionSkill,state.agents.map(a=>a.lane).join('')].join(':');if(key!==lastKey){lastKey=key;movement();}labels.forEach((b,i)=>{b.innerHTML=escape(state.agents[i].name)+'<small>'+escape(state.agents[i].lane===1?'Working · '+state.agents[i].role:state.agents[i].lane===2?'Waiting for you':state.agents[i].role)+'</small>';b.classList.toggle('selected',index===i);b.classList.toggle('waiting',state.agents[i].lane===2);});}
  function motionButton(){el('motion').textContent=motion?'Ⅱ':'▶';el('motion').setAttribute('aria-label',motion?'Pause scene motion':'Resume scene motion');}
  el('motion').onclick=()=>{motion=!motion;if(!motion)studioSound.stop();motionButton();};reduced.addEventListener('change',()=>{motion=!reduced.matches;if(!motion)studioSound.stop();motionButton();});
  el('camera').onclick=resetNavigation;
  renderer.domElement.addEventListener('pointerdown',e=>{if(journey)return;drag={x:e.clientX,y:e.clientY};moved=false;renderer.domElement.setPointerCapture(e.pointerId);});
  renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)moved=true;azimuth-=dx*.005;elevation=Math.max(room==='workshop'?.2:.5,Math.min(1.35,elevation+dy*.003));drag={x:e.clientX,y:e.clientY};cam();});
  renderer.domElement.addEventListener('pointerup',e=>{if(!drag)return;if(!moved){const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);if(!journey){const hits=raycaster.intersectObjects(navigationTargets(),true);if(hits.length){const object=hits[0].object;if(!selectNavigationObject(object)){if(room==='mission')choose(object.userData.agent);else selectRoomObject(object);}}}}drag=null;});
  renderer.domElement.addEventListener('pointercancel',()=>drag=null);
  renderer.domElement.addEventListener('wheel',e=>{e.preventDefault();if(journey)return;zoom=Math.max(.75,Math.min(1.9,zoom-e.deltaY*.0007));cam();},{passive:false});
  renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;el('fallback').hidden=false;root.dataset.renderer='lost';});renderer.domElement.addEventListener('webglcontextrestored',()=>{lost=false;el('fallback').hidden=true;root.dataset.renderer='webgl';});
  new ResizeObserver(resize).observe(viewport);new IntersectionObserver(items=>visible=items[0].isIntersecting).observe(viewport);
  function positionLabel(node,point){const p=point.clone().project(camera);node.style.left=(p.x*.5+.5)*viewport.clientWidth+'px';node.style.top=(-p.y*.5+.5)*viewport.clientHeight+'px';node.style.display=p.z>1?'none':'';}
  function animate(now){requestAnimationFrame(animate);if(document.hidden||root.hidden||!viewport.clientWidth||lost){lastFrame=now;return;}if(now-lastFrame<32)return;const dt=Math.min((now-lastFrame)/1000,.06);lastFrame=now;if(motion)clock+=dt;
    animateNavigation(now);animateRooms(dt);
    robots.forEach((r,i)=>{let walking=false;if(motion){if(r.path.length){const delta=r.path[0].clone().sub(r.robot.position),dist=delta.length();if(dist<.1)r.path.shift();else{walking=true;r.robot.position.addScaledVector(delta.normalize(),Math.min(dist,dt*1.65));r.robot.rotation.y=Math.atan2(delta.x,delta.z);}}else if(state.agents[i].lane===0){const target=r.home.clone().add(new THREE.Vector3(Math.sin(clock*.45+i)*.32,0,Math.cos(clock*.45+i)*.18));const delta=target.clone().sub(r.robot.position);walking=delta.length()>.05;r.robot.position.lerp(target,.025);r.robot.rotation.y=THREE.MathUtils.lerp(r.robot.rotation.y,Math.atan2(delta.x,delta.z),.04);}else r.robot.rotation.y=THREE.MathUtils.lerp(r.robot.rotation.y,0,.04);r.body.position.y=walking?Math.abs(Math.sin(clock*8+i))*.04:Math.sin(clock*2+i)*.02;r.legs.forEach((l,j)=>l.rotation.x=walking?Math.sin(clock*9+i+j*Math.PI)*.4:0);r.arms.forEach((a,j)=>a.rotation.x=Math.sin(clock*(walking?8:1.6)+j*Math.PI+i)*(walking ? .38 : .08));}
      r.halo.position.set(r.robot.position.x,.086,r.robot.position.z);r.halo.visible=i===activeSelection||state.agents[i].lane!==0;deskLights[i].visible=state.agents[i].lane===1;positionLabel(labels[i],missionRoom.localToWorld(r.robot.position.clone().add(new THREE.Vector3(0,1.65,0))));});
    if(room==='mission')hotspots.forEach(h=>positionLabel(h.button,missionRoom.localToWorld(h.position.clone())));
    if(motion){core.rotation.y=clock*.25;coreRing.position.y=1.35+Math.sin(clock*1.5)*.045;weatherRotor.rotation.y=clock*.28;}
    deskScreens.forEach((screen,i)=>{const busy=state.agents[i].lane===1;screen.material.emissive.setHex(busy?colors[i]:0);screen.material.emissiveIntensity=busy ? .12 : 0;});
    packets.forEach((p,i)=>{const t=(clock-packetTime-i*.13)/2.8;p.visible=t>=0&&t<=1&&state.phase>=0;if(p.visible){p.position.lerpVectors(packetStart,packetEnd,t);p.position.y=.65+Math.sin(t*Math.PI)*1.15;}});
    renderer.render(scene,camera);
  }
  motionButton();resize();update(snapshot,0);requestAnimationFrame(animate);root.dataset.renderer='webgl';
  return {resize,update,setRoom,setCollection,setDraft,overview:showOverview,inspect:()=>({sceneStyle:'connected-studio',room,navigation:navigationInfo(),residents:residentInfo(),draft:draftProfile,crewAvatars:robots.map(r=>r.appearance),activeRole:lastActive,robots:robots.map(r=>r.robot.position.toArray()),phase,motion,visible,lost,lastFrame,clock,rootHidden:root.hidden,documentHidden:document.hidden,camera:[azimuth,elevation,zoom],hotspots:hotspots.map(h=>h.id)})};
}
