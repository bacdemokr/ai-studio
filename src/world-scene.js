// A geometry-only, interactive island. Hotspots open the actual skill missions.
function createScene() {
  const viewport=el('viewport'), scene=new THREE.Scene();
  scene.background=new THREE.Color(0x8fb4a3);scene.fog=new THREE.Fog(0x8fb4a3,42,88);
  const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.6));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.04;
  viewport.prepend(renderer.domElement);renderer.domElement.setAttribute('aria-hidden','true');
  const camera=new THREE.OrthographicCamera(-15,15,9,-9,.1,120),focus=new THREE.Vector3(0,0,0);
  let azimuth=.18,elevation=.85,zoom=1,drag=null,moved=false,motion=!matchMedia('(prefers-reduced-motion: reduce)').matches;
  let state=snapshot,activeSelection=0,phase=-2,lastKey='',clock=0,lastFrame=0,visible=true,lost=false;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  scene.add(new THREE.HemisphereLight(0xf8fff1,0x799f8a,1.8));
  const sun=new THREE.DirectionalLight(0xfff0cd,2.6);sun.position.set(-7,20,10);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-18,right:18,top:16,bottom:-16});sun.shadow.normalBias=.04;scene.add(sun);
  const materials=new Map();
  function mat(color,glow=false){const k=color+':'+glow;if(!materials.has(k))materials.set(k,new THREE.MeshStandardMaterial({color,roughness:.65,metalness:.08,...(glow?{emissive:color,emissiveIntensity:.35}:{})}));return materials.get(k);}
  function mesh(parent,geo,x,y,z,color,scale=[1,1,1]){const o=new THREE.Mesh(geo,mat(color));o.position.set(x,y,z);o.scale.set(...scale);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
  const cube=new THREE.BoxGeometry(1,1,1),sphere=new THREE.SphereGeometry(1,16,12);
  const box=(p,x,y,z,w,h,d,c)=>mesh(p,cube,x,y,z,c,[w,h,d]);
  const ball=(p,x,y,z,rx,ry,rz,c)=>mesh(p,sphere,x,y,z,c,[rx,ry,rz]);
  const cyl=(p,x,y,z,r,h,c,n=40)=>mesh(p,new THREE.CylinderGeometry(r,r,h,n),x,y,z,c);
  function ring(p,x,y,z,r,color,width=.035){const o=mesh(p,new THREE.TorusGeometry(r,width,8,64),x,y,z,color);o.rotation.x=-Math.PI/2;return o;}
  function sign(p,text,x,y,z,w,h,color='#e4f0d9',background='#203527'){
    const c=document.createElement('canvas');c.width=768;c.height=128;const ctx=c.getContext('2d');if(background){ctx.fillStyle=background;ctx.fillRect(0,0,768,128);}ctx.fillStyle=color;ctx.font='600 52px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,384,64,720);const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;const o=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture,transparent:!background}));o.position.set(x,y,z);p.add(o);return o;
  }
  // Quiet water and a gently irregular, raised island with a luminous shoreline.
  const water=mesh(scene,new THREE.PlaneGeometry(200,200),0,-.58,0,0x6d9d90);water.rotation.x=-Math.PI/2;water.receiveShadow=true;
  const shore=new THREE.Shape();const outline=[];
  for(let i=0;i<=96;i++){const a=i/96*Math.PI*2,r=1+.032*Math.sin(a*5)+.018*Math.cos(a*9);const x=Math.cos(a)*12*r,z=Math.sin(a)*8.2*r;outline.push([x,z]);if(i===0)shore.moveTo(x,z);else shore.lineTo(x,z);}
  const island=mesh(scene,new THREE.ExtrudeGeometry(shore,{depth:.58,bevelEnabled:true,bevelSize:.24,bevelThickness:.25,bevelSegments:3,steps:1}),0,-.42,0,0xe3e3ca);island.rotation.x=-Math.PI/2;
  const shoreLine=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(outline.map(([x,z])=>new THREE.Vector3(x*1.022,-.29,-z*1.024))),new THREE.LineBasicMaterial({color:0xe7fff2,transparent:true,opacity:.85}));scene.add(shoreLine);
  const waveRings=[];for(let i=0;i<3;i++){const o=ring(scene,0,-.43-i*.025,0,12.7+i*.85,0xc5eee0,.018);o.scale.z=.72;o.material=new THREE.MeshBasicMaterial({color:0xd7f7e9,transparent:true,opacity:.35-i*.07});waveRings.push(o);}
  function plant(x,z,height=1){const g=new THREE.Group();g.position.set(x,0,z);scene.add(g);cyl(g,0,height*.42,0,.055,height*.9,0x947f50,8);for(let i=0;i<5;i++){const a=i/5*Math.PI*2;const leaf=ball(g,Math.sin(a)*.32,height*.88,Math.cos(a)*.32,.15,.055,.55,i%2?0x608f58:0x85aa6a);leaf.rotation.y=a;leaf.rotation.z=Math.sin(a)*.15;}return g;}
  function grass(x,z,c=0x81b6a0){for(let i=0;i<4;i++){const o=mesh(scene,new THREE.ConeGeometry(.05,.52+(.1*i),4),x+i*.11,.2,z+Math.sin(i)*.1,c);o.rotation.z=(i-1.5)*.12;}}
  [[-10,-2,1.9],[-8,-5,1.5],[8,-5,2.1],[10,1,1.7],[-8,4.8,1.6],[6,6,1.9]].forEach(x=>plant(...x));
  [[-10,1],[-6,-6],[3,-6.7],[10,3],[3,7],[-5,6.5],[-11,-1],[8,5]].forEach(([x,z],i)=>grass(x,z,i%2?0x91b779:0x85b5a2));
  for(let i=0;i<12;i++){const a=i*2.4;ball(scene,Math.cos(a)*11.3,.1,Math.sin(a)*7.6,.18+(i%3)*.1,.12,.17,0xb9cbb3);}
  const hotspotLayer=document.createElement('div');hotspotLayer.className='world-hotspots';viewport.append(hotspotLayer);
  const hotspots=[],hitTargets=[],labels=[],robots=[],deskLights=[],positions=[[-1,-1.1],[-5,-.2],[5,-.7],[-3.7,3.7],[3.6,3.9]];
  const homes=positions.map(([x,z])=>new THREE.Vector3(x,.28,z));
  function hotspot(id,title,subtitle,x,y,z){const b=document.createElement('button');b.className='world-hotspot';b.dataset.worldSkill=id;b.innerHTML='<b>'+escape(title)+'</b><small>'+escape(subtitle)+'</small>';b.onclick=()=>root.dispatchEvent(new CustomEvent('bac:world-skill',{detail:id}));hotspotLayer.append(b);hotspots.push({id,button:b,position:new THREE.Vector3(x,y,z)});}
  function platform(x,z,r,color=0xcad5bc){cyl(scene,x,.2,z,r,.16,color);ring(scene,x,.29,z,r*.96,0x9db588,.026);}
  // A small stage hosts the crew: the shared brief glows at its center.
  platform(0,-4.4,2.4,0xc5d0b6);box(scene,0,.62,-5.5,4.1,.76,.5,0x344839);box(scene,0,1.05,-5.54,4.5,.12,.74,0x6c9157);
  box(scene,-2.05,1.9,-5.45,.1,2.5,.1,0x526c4a);box(scene,2.05,1.9,-5.45,.1,2.5,.1,0x526c4a);box(scene,0,3.13,-5.45,4.4,.1,.15,0x536e4b);
  sign(scene,'BUILD A CLAW',0,2.68,-5.36,4.2,.65,'#c6ed91','#172b20');sign(scene,'CREATE  /  COLLABORATE  /  EXPLORE',0,2.2,-5.34,4.1,.27,'#d8e8c2','#24382b');
  hotspot('crew','CREW STAGE','Plan an event together',0,3.5,-5.4);
  // Document library / persistent memory: readable books, a lamp, and a small tree.
  const library=new THREE.Group();library.position.set(-7,0,-2.8);scene.add(library);platform(-7,-2.8,1.45);
  box(library,0,1.14,0,1.8,2.0,.5,0x8d7854);for(let y=.45;y<2.0;y+=.55){box(library,0,y,.09,1.9,.09,.6,0xc6b98e);for(let j=0;j<7;j++)box(library,-.73+j*.24,y+.23,.12,.15,.34+(j%3)*.045,.35,[0x82b395,0xd2a272,0x9ab7ce,0xc2b286][j%4]);}
  hotspot('documents','KNOWLEDGE LIBRARY','Documents & memory',-7,2.7,-2.8);
  // Maker workshop: a screen, a tiny arcade cabinet, and game blocks.
  const maker=new THREE.Group();maker.position.set(-7,0,2.5);scene.add(maker);platform(-7,2.5,1.5,0xd5d8bd);
  box(maker,0,.95,0,2.15,.12,1.05,0x9c8a61);for(const x of [-.84,.84])box(maker,x,.53,0,.13,.8,.8,0x6d7553);
  box(maker,-.36,1.51,-.1,1.1,.85,.12,0x233c36);sign(maker,'<  PLAY  >',-.36,1.52,-.03,1.02,.59,'#b7ef69','#243b32');box(maker,-.36,1.04,.25,.77,.035,.22,0x506f5b);
  box(maker,.8,1.25,0,.48,.55,.55,0x85b0c6);box(maker,.8,1.56,.03,.43,.14,.5,0xaccfdd);ball(maker,.8,1.67,.1,.05,.05,.05,0x24443e);
  hotspot('builder','MAKER WORKSHOP','Build a playable mini app',-7,2.3,2.5);
  // Weather observatory with a sun/cloud mobile and telescope.
  platform(7.1,-3.2,1.45,0xd9dbc0);const weather=new THREE.Group();weather.position.set(7.1,0,-3.2);scene.add(weather);
  for(const a of [0,2.1,4.2]){const leg=cyl(weather,Math.sin(a)*.36,.73,Math.cos(a)*.36,.045,1.05,0x746b4c,8);leg.rotation.z=Math.sin(a)*.35;}
  const telescope=cyl(weather,0,1.42,0,.22,1.4,0x4d8290,16);telescope.rotation.z=1.05;const lens=cyl(weather,-.58,1.75,0,.26,.08,0xaad9d1,16);lens.rotation.z=1.05;
  const sunBall=ball(weather,.9,2.35,-.2,.33,.33,.14,0xe5c75b);for(let i=0;i<4;i++)ball(weather,.45+i*.22,2.0,.06,.27,.18,.16,0xf1f2dc);
  hotspot('weather','WEATHER LOOKOUT','Live conditions → a plan',7.1,3,-3.2);
  // Operations rack and a separate OpenShell gate remain clearly distinct.
  platform(8,1.5,1.45,0xc2d3c2);box(scene,8,1.04,1.5,1.28,1.6,.8,0x31453b);for(let i=0;i<5;i++){box(scene,8,.51+i*.27,1.94,1.05,.16,.03,0x78917a);ball(scene,8.39,.51+i*.27,1.97,.025,.025,.02,0xa8db69);}hotspot('runtime','SPARK ENGINE ROOM','One model for the whole crew',8,2.45,1.5);
  const gateGroup=new THREE.Group();gateGroup.position.set(7.2,0,4.8);scene.add(gateGroup);box(gateGroup,-.7,1.05,0,.12,1.65,.17,0x658965);box(gateGroup,.7,1.05,0,.12,1.65,.17,0x658965);const gate=box(gateGroup,0,1.85,0,1.55,.14,.18,0xa6d768);sign(gateGroup,'OPENSHELL',0,1.45,.1,1.23,.3,'#1e492b','#b4d79c');hotspot('security','ACCESS GATE','Try the boundary · inspect actual evidence',7.2,2.3,4.8);
  // Marketing atelier: a poster easel and a stack of deliverables.
  platform(-2,5.6,1.3,0xdedac0);for(const x of [-2.48,-1.52]){const leg=box(scene,x,.86,5.6,.065,1.45,.08,0x998465);leg.rotation.z=x<-2?.1:-.1;}box(scene,-2,1.51,5.54,1.35,1.15,.09,0xe8e6c8);sign(scene,'BUILD A CLAW',-2,1.69,5.6,1.2,.24,'#1e4230','#e8e6c8');box(scene,-2,1.42,5.61,.97,.15,.01,0x7bad48);sign(scene,'ZURICH  /  MAKE IT YOURS',-2,1.17,5.62,1.1,.16,'#47623b','#e8e6c8');hotspot('writer','CAMPAIGN ATELIER','Turn the brief into an invitation',-2,2.5,5.6);
  // A floating globe for browsing, and a phone pier for the companion channel.
  platform(-8,-.2,.65);const globe=ball(scene,-8,1.3,-.2,.48,.48,.48,0x73ada3);const meridian=ring(scene,-8,1.3,-.2,.56,0xd5e7b9,.03);meridian.rotation.z=.7;meridian.rotation.x=.3;cyl(scene,-8,.63,-.2,.05,.7,0x6a8e6c,10);hotspot('web','WEB EXPLORER','Read sources. Follow your curiosity.',-9.2,1.7,.1);
  for(let j=0;j<5;j++)box(scene,3.4,.1,6.4+j*.38,2,.12,.33,0xa38d61);box(scene,3.4,.65,6.8,.62,1.04,.07,0x294b42);sign(scene,'↗',3.4,.68,6.85,.5,.78,'#d4f0da','#4d978a');hotspot('telegram','TELEGRAM PIER','The same agent, on your phone',3.4,1.75,7.2);
  // Central model/brief monument with restrained NVIDIA lettering.
  cyl(scene,0,.3,.5,1.26,.34,0x324d3b);cyl(scene,0,.5,.5,1.13,.09,0xc9d9af);ring(scene,0,.56,.5,1.05,0x93c756,.055);
  const brand=sign(scene,'NVIDIA',0,.562,.67,1.5,.38,'#1c3a29',null);brand.rotation.x=-Math.PI/2;
  const core=box(scene,0,1.05,.2,.62,.65,.62,0x8cae68);core.rotation.y=.4;const coreRing=ring(scene,0,1.29,.2,.53,0xc7e2a0);
  const briefLabel=sign(scene,'SHARED BRIEF',0,.74,1.33,1.8,.26,'#dcebd0','#29422f');
  // Five expressive claw companions, each with its own colors and role accessory.
  const shells=[0x97c85b,0x77b5d0,0xe0b659,0xd58f83,0xb0a0d4];
  homes.forEach((home,i)=>{
    const robot=new THREE.Group();robot.position.copy(home);scene.add(robot);const body=new THREE.Group();robot.add(body);
    ball(body,0,.54,0,.46,.27,.33,shells[i]);ball(body,0,.47,.21,.31,.12,.16,0xf1e6c9);
    const eyes=[];for(const side of [-1,1]){const stalk=cyl(body,side*.22,.93,.1,.036,.49,shells[i],8);stalk.rotation.z=-side*.14;const eye=ball(body,side*.25,1.17,.1,.115,.12,.1,0xf3f0d9);ball(body,side*.25,1.175,.19,.047,.052,.035,0x243b2f);eyes.push(eye);}
    const smile=mesh(body,new THREE.TorusGeometry(.1,.012,5,18,Math.PI),0,.48,.344,0x567348);smile.rotation.z=Math.PI;
    const arms=[],legs=[];
    for(const side of [-1,1]){
      const arm=new THREE.Group();arm.position.set(side*.43,.59,.08);body.add(arm);const segment=ball(arm,side*.23,.04,.06,.28,.075,.08,shells[i]);segment.rotation.z=side*.2;
      const claw=new THREE.Group();claw.position.set(side*.46,.15,.11);arm.add(claw);ball(claw,0,0,0,.17,.18,.14,shells[i]);const finger=ball(claw,side*.075,.15,.03,.075,.18,.09,shells[i]);finger.rotation.z=-side*.33;const other=ball(claw,-side*.075,.1,.055,.06,.12,.08,shells[i]);other.rotation.z=side*.42;arms.push(arm);
      for(let j=0;j<3;j++){const leg=new THREE.Group();leg.position.set(side*.3,.39,-.18+j*.18);const upper=ball(leg,side*.2,-.055,.03,.24,.052,.06,shells[i]);upper.rotation.z=-side*.3;const lower=ball(leg,side*.38,-.16,.06,.045,.14,.055,shells[i]);lower.rotation.z=side*.22;body.add(leg);legs.push(leg);}
    }
    // Role badges are visible on the shell; color travels with a handoff packet.
    const badge=box(body,0,.57,.336,.19,.13,.015,0x34543b);sign(body,['★','⌘','▥','✎','✓'][i],0,.576,.35,.16,.11,'#eff6dc',null);
    if(i===1){box(body,0,.86,-.03,.48,.08,.32,0x547f8a);ball(body,0,.91,-.03,.22,.12,.16,0x547f8a);}
    if(i===2){const helmet=ball(body,0,.82,-.04,.32,.16,.23,0xf1c661);box(body,0,.77,.05,.75,.055,.35,0xf1c661);}
    const halo=ring(scene,home.x,.27,home.z,.81,shells[i],.028);const packet=box(body,.82,.62,.12,.22,.3,.045,0xe9ecd5);packet.visible=false;
    robot.traverse(o=>{if(o.isMesh){o.userData.agent=i;hitTargets.push(o);}});
    const label=document.createElement('div');label.className='campus-agent-label';el('labels').append(label);labels.push(label);
    robots.push({robot,body,arms,legs,halo,packet,home,path:[],idle:i*.85,eyes});deskLights.push(ring(scene,home.x,.26,home.z,1.02,0xbee684,.025));
  });
  const packets=[];for(let i=0;i<6;i++){const dot=ball(scene,0,.6,0,.05,.05,.05,0xd7eeb4);dot.visible=false;packets.push(dot);}
  let packetStart=new THREE.Vector3(),packetEnd=new THREE.Vector3(),packetTime=-20;
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
  function cam(){camera.position.set(Math.sin(azimuth)*Math.cos(elevation)*30,Math.sin(elevation)*30,Math.cos(azimuth)*Math.cos(elevation)*30);camera.lookAt(focus);camera.zoom=zoom;camera.updateProjectionMatrix();}
  function resize(){const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;const aspect=w/h,vertical=aspect<1?13:aspect<1.5?11:9.4;camera.left=-vertical*aspect;camera.right=vertical*aspect;camera.top=vertical;camera.bottom=-vertical;renderer.setSize(w,h);cam();renderer.render(scene,camera);}
  function movement(){
    robots.forEach(r=>{r.path=[r.home.clone()];r.packet.visible=false;});
    const active=state.agents.findIndex(a=>a.lane===1||a.lane===2);
    if(active>=0){
      const r=robots[active],station={builder:[-5.5,2.4],documents:[-5.7,-2.5],memory:[-5.7,-2.5],weather:[5.8,-3],web:[-6.5,.1],writer:[-1.7,4.5]}[state.missionSkill];
      const target=station?new THREE.Vector3(station[0],.28,station[1]):new THREE.Vector3([0,-4,4,-2,2][active],.28,[-2.6,-.8,-1,3,2][active]);
      r.path=[new THREE.Vector3(r.robot.position.x,.28,1.7),new THREE.Vector3(target.x,.28,1.7),target];r.packet.visible=true;
      packetStart=robots[Math.max(0,active-1)].robot.position.clone();packetEnd=target.clone();packetTime=clock;
    }
    if(!motion)robots.forEach(r=>{if(r.path.length)r.robot.position.copy(r.path.at(-1));r.path=[];});
  }
  function update(next,index){state=next;activeSelection=index;phase=state.phase;const key=[state.jobId,state.phase,state.missionSkill,state.agents.map(a=>a.lane).join('')].join(':');if(key!==lastKey){lastKey=key;movement();}labels.forEach((b,i)=>{b.innerHTML=escape(state.agents[i].name)+'<small>'+escape(state.agents[i].lane===1?'Working · '+state.agents[i].role:state.agents[i].lane===2?'Waiting for you':state.agents[i].role)+'</small>';b.classList.toggle('selected',index===i);b.classList.toggle('waiting',state.agents[i].lane===2);});}
  function motionButton(){el('motion').textContent=motion?'Ⅱ':'▶';el('motion').setAttribute('aria-label',motion?'Pause scene motion':'Resume scene motion');}
  el('motion').onclick=()=>{motion=!motion;motionButton();};reduced.addEventListener('change',()=>{motion=!reduced.matches;motionButton();});
  el('camera').onclick=()=>{azimuth=.18;elevation=.85;zoom=1;cam();};
  renderer.domElement.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};moved=false;renderer.domElement.setPointerCapture(e.pointerId);});
  renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)moved=true;azimuth-=dx*.005;elevation=Math.max(.5,Math.min(1.35,elevation+dy*.003));drag={x:e.clientX,y:e.clientY};cam();});
  renderer.domElement.addEventListener('pointerup',e=>{if(!moved){const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(hitTargets);if(hits.length)choose(hits[0].object.userData.agent);}drag=null;});
  renderer.domElement.addEventListener('pointercancel',()=>drag=null);
  renderer.domElement.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.75,Math.min(1.9,zoom-e.deltaY*.0007));cam();},{passive:false});
  renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;el('fallback').hidden=false;root.dataset.renderer='lost';});renderer.domElement.addEventListener('webglcontextrestored',()=>{lost=false;el('fallback').hidden=true;root.dataset.renderer='webgl';});
  new ResizeObserver(resize).observe(viewport);new IntersectionObserver(items=>visible=items[0].isIntersecting).observe(viewport);
  function positionLabel(node,point){const p=point.clone().project(camera);node.style.left=(p.x*.5+.5)*viewport.clientWidth+'px';node.style.top=(-p.y*.5+.5)*viewport.clientHeight+'px';node.style.display=p.z>1?'none':'';}
  function animate(now){requestAnimationFrame(animate);if(document.hidden||root.hidden||!viewport.clientWidth||lost){lastFrame=now;return;}if(now-lastFrame<32)return;const dt=Math.min((now-lastFrame)/1000,.06);lastFrame=now;if(motion)clock+=dt;
    robots.forEach((r,i)=>{let walking=false;if(motion){if(r.path.length){const delta=r.path[0].clone().sub(r.robot.position),dist=delta.length();if(dist<.1)r.path.shift();else{walking=true;r.robot.position.addScaledVector(delta.normalize(),Math.min(dist,dt*1.65));r.robot.rotation.y=Math.atan2(delta.x,delta.z);}}else if(state.agents[i].lane===0){const target=r.home.clone().add(new THREE.Vector3(Math.sin(clock*.28+i)*1.2,0,Math.cos(clock*.28+i)*.75));const delta=target.clone().sub(r.robot.position);walking=delta.length()>.05;r.robot.position.lerp(target,.025);r.robot.rotation.y=THREE.MathUtils.lerp(r.robot.rotation.y,Math.atan2(delta.x,delta.z),.04);}else r.robot.rotation.y=THREE.MathUtils.lerp(r.robot.rotation.y,0,.04);r.body.position.y=walking?Math.abs(Math.sin(clock*8+i))*.04:Math.sin(clock*2+i)*.02;r.legs.forEach((l,j)=>l.rotation.x=walking?Math.sin(clock*9+i+j)*.4:0);r.arms.forEach((a,j)=>a.rotation.z=Math.sin(clock*(walking?5:1.6)+j+i)*.16);}
      r.halo.position.set(r.robot.position.x,.29,r.robot.position.z);r.halo.visible=i===activeSelection||state.agents[i].lane!==0;deskLights[i].visible=state.agents[i].lane===1;positionLabel(labels[i],r.robot.position.clone().add(new THREE.Vector3(0,1.57,0)));});
    hotspots.forEach(h=>positionLabel(h.button,h.position));
    if(motion){core.rotation.y=clock*.25;coreRing.position.y=1.25+Math.sin(clock*1.5)*.06;globe.rotation.y=clock*.12;sunBall.position.y=2.35+Math.sin(clock)*.055;waveRings.forEach((r,i)=>{r.scale.setScalar(1+Math.sin(clock*.45+i)*.016);r.scale.z*=.72;});}
    packets.forEach((p,i)=>{const t=(clock-packetTime-i*.13)/2.8;p.visible=t>=0&&t<=1&&state.phase>=0;if(p.visible){p.position.lerpVectors(packetStart,packetEnd,t);p.position.y=.65+Math.sin(t*Math.PI)*1.15;}});
    renderer.render(scene,camera);
  }
  motionButton();resize();update(snapshot,0);requestAnimationFrame(animate);root.dataset.renderer='webgl';
  return {resize,update,inspect:()=>({robots:robots.map(r=>r.robot.position.toArray()),phase,motion,visible,lost,lastFrame,clock,rootHidden:root.hidden,documentHidden:document.hidden,camera:[azimuth,elevation,zoom],hotspots:hotspots.map(h=>h.id)})};
}
