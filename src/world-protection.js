// Shield effects require native OpenShell network denial evidence.
const protectionSeen=new Set(),protectionHits=new Map(),protectionCooldown=new Map();
const protectionReplies=new Map();
function protectionReplyDelay(owner,role=null){
  const key=owner+':'+(role===null?'personal':role),hold=protectionReplies.get(key);
  if(hold&&performance.now()<hold.until)return hold;
  return null;
}
let protectionPrimed=false;
const protectionLayer=document.createElement('div');protectionLayer.className='world-protection-layer';viewport.append(protectionLayer);
function protectionTarget(event){return event.role===null?residents.find(r=>r.key===event.owner)?.group:robots[event.role]?.robot;}
function disposeProtection(hit){
  scene.remove(hit.group);hit.label.remove();
  hit.group.traverse(o=>{o.geometry?.dispose();if(o.material)o.material.dispose();});
}
function protectionMaterial(color,opacity=1){return new THREE.MeshBasicMaterial({color,transparent:true,opacity,side:THREE.DoubleSide,depthWrite:false,toneMapped:false,blending:THREE.AdditiveBlending});}
function createProtectionShell(){
  return new THREE.Mesh(new THREE.SphereGeometry(1.8,48,24,0,Math.PI*2,0,Math.PI/2),new THREE.ShaderMaterial({
    transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,
    uniforms:{elapsed:{value:-1},fade:{value:1},impactPoint:{value:new THREE.Vector3(1.35,1/1.08,.75)}},
    vertexShader:`varying vec3 localPoint;varying vec3 viewNormal;varying vec3 viewDirection;varying vec2 surfaceUV;
      void main(){localPoint=position;surfaceUV=uv;viewNormal=normalize(normalMatrix*normal);vec4 p=modelViewMatrix*vec4(position,1.);viewDirection=-p.xyz;gl_Position=projectionMatrix*p;}`,
    fragmentShader:`uniform float elapsed;uniform float fade;uniform vec3 impactPoint;
      varying vec3 localPoint;varying vec3 viewNormal;varying vec3 viewDirection;varying vec2 surfaceUV;
      void main(){
        float edge=pow(1.-abs(dot(normalize(viewNormal),normalize(viewDirection))),2.);
        vec2 p=surfaceUV*vec2(32.,20.),r=vec2(1.,1.732);
        vec2 a=mod(p,r)-r*.5,b=mod(p-r*.5,r)-r*.5;
        vec2 cell=abs(dot(a,a)<dot(b,b)?a:b);
        float hex=max(cell.x,dot(cell,vec2(.5,.866)));
        float grid=smoothstep(.43,.485,hex);
        float distanceToHit=distance(localPoint,impactPoint);
        float hitEnabled=step(0.,elapsed),t=max(0.,elapsed);
        float wave=(1.-smoothstep(.025,.12,abs(distanceToHit-t*2.2)))*exp(-t*.95)*hitEnabled;
        float echo=(1.-smoothstep(.02,.08,abs(distanceToHit-max(0.,t-.2)*1.6)))*exp(-t*1.7)*hitEnabled;
        float flash=exp(-distanceToHit*4.)*exp(-t*5.)*hitEnabled;
        vec3 color=mix(vec3(.16,.72,1.),vec3(.65,1.,.76),edge*.7+wave*.3);
        color=mix(color,vec3(1.,.62,.22),flash*.85);
        float alpha=(.035+edge*.44+grid*(.06+wave*.34)+wave*.48+echo*.18+flash*.6)*fade;
        gl_FragColor=vec4(color,alpha);
      }`
  }));
}
function observeProtection(events=[]){
  const now=Date.now()/1000;
  for(const event of events){
    if(!event.id||event.source!=='OpenShell policy log'||event.action!=='deny'||protectionSeen.has(event.id))continue;
    protectionSeen.add(event.id);
    if(!protectionPrimed||now-event.observedAt>12||now-event.time>30||event.time>now+2)continue;
    const key=event.owner+':'+(event.role===null?'personal':event.role),target=protectionTarget(event);
    if(!target||performance.now()-(protectionCooldown.get(key)||-Infinity)<4500)continue;
    protectionCooldown.set(key,performance.now());
    if(!overview&&!journey&&room===(event.role===null?'lounge':'mission')){
      const hold={time:event.time,until:performance.now()+3000};protectionReplies.set(key,hold);
      setTimeout(()=>{if(protectionReplies.get(key)===hold){protectionReplies.delete(key);root.dispatchEvent(new Event('bac:protection-reveal'));}},3000);
    }
    if(protectionHits.size>=3){const [oldKey,old]=protectionHits.entries().next().value;disposeProtection(old);protectionHits.delete(oldKey);}
    const group=new THREE.Group();group.name='openshell-impact';group.visible=false;scene.add(group);
    const shell=createProtectionShell();shell.scale.y=1.08;group.add(shell);
    const rim=new THREE.Mesh(new THREE.TorusGeometry(1.8,.035,8,80),protectionMaterial(0x7fe9ff,.85));rim.rotation.x=-Math.PI/2;rim.position.y=.045;group.add(rim);
    const impact=new THREE.Group();impact.visible=false;impact.position.set(1.35,1,.75);impact.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3(1.35,1/(1.08*1.08),.75).normalize());group.add(impact);
    const wave=new THREE.Mesh(new THREE.RingGeometry(.23,.26,48),protectionMaterial(0xb6ffe3));impact.add(wave);
    const seal=new THREE.Group();impact.add(seal);
    // A small amber stop cross makes the collision legible even at a distance.
    for(const angle of [-Math.PI/4,Math.PI/4]){const bar=new THREE.Mesh(new THREE.BoxGeometry(.075,.48,.025),protectionMaterial(0xffb86b));bar.rotation.z=angle;seal.add(bar);}
    const points=[];
    for(let i=0;i<10;i++){
      const angle=i*Math.PI/5;let previous=new THREE.Vector3();
      for(let j=1;j<=5;j++){
        const radius=j*.16,a=angle+(j%2?.2:-.13),next=new THREE.Vector3(Math.cos(a)*radius,Math.sin(a)*radius,.025);
        points.push(previous,next);previous=next;
      }
    }
    const sparks=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0xc5faff,transparent:true,opacity:1,depthWrite:false,toneMapped:false,blending:THREE.AdditiveBlending}));impact.add(sparks);
    // The request originates INSIDE the boundary and never crosses it. On denial
    // the amber packet reverses back toward its agent, then dissolves.
    const request=new THREE.Group();request.visible=motion;group.add(request);
    const packet=new THREE.Mesh(new THREE.SphereGeometry(.1,12,8),protectionMaterial(0xffce83));request.add(packet);
    const glow=new THREE.Mesh(new THREE.SphereGeometry(.2,12,8),protectionMaterial(0xffb66b,.25));packet.add(glow);
    const trail=new THREE.Mesh(new THREE.CylinderGeometry(.018,.035,1,8),protectionMaterial(0xffb66b,.8));request.add(trail);
    const origin=new THREE.Vector3(0,.95,.05),destination=impact.position.clone();
    const label=document.createElement('div');label.className='world-protection-hit';label.setAttribute('role','status');
    const title=document.createElement('b');title.textContent='⛨ Request blocked';const host=document.createElement('small');host.textContent=String(event.host||'').slice(0,120);
    const caption=document.createElement('span');caption.textContent='OpenShell · connection stopped';label.append(title,host,caption);protectionLayer.append(label);
    protectionHits.set(key,{event,group,shell,rim,impact,wave,seal,sparks,request,packet,glow,trail,origin,destination,label,began:performance.now(),phase:'request'});
  }
  protectionPrimed=true;
  while(protectionSeen.size>256)protectionSeen.delete(protectionSeen.values().next().value);
  for(const [key,stamp] of protectionCooldown)if(performance.now()-stamp>30000)protectionCooldown.delete(key);
}
function animateProtection(now){
  for(const [key,hit] of protectionHits){
    const age=(now-hit.began)/1000,target=protectionTarget(hit.event),duration=motion?3.8:3;
    if(!target||age>duration){disposeProtection(hit);protectionHits.delete(key);continue;}
    const shown=!overview&&!journey&&room===(hit.event.role===null?'lounge':'mission');
    hit.group.visible=shown;hit.label.hidden=!shown;
    if(!shown)continue;
    target.getWorldPosition(hit.group.position);hit.group.position.y+=.025;hit.group.rotation.y=azimuth;
    const collision=.6,t=age-collision,fade=motion?Math.min(1,(duration-age)/.9):1;
    hit.phase=!motion?'blocked':t<0?'request':t<.85?'impact':'blocked';
    hit.shell.material.uniforms.elapsed.value=motion?t:10;hit.shell.material.uniforms.fade.value=fade;
    hit.rim.material.opacity=(.6+(t>=0?.35*Math.exp(-t*3):0))*fade;
    hit.impact.visible=!motion||t>=0;
    hit.wave.visible=motion;hit.sparks.visible=motion;
    hit.wave.scale.setScalar(.6+Math.max(0,t)*3.2);hit.wave.material.opacity=Math.max(0,1-t/1.05)*fade;
    // A single local impact, not repeated flashes across the screen.
    hit.sparks.scale.setScalar(.45+Math.min(1,Math.max(0,t))*1.1);
    hit.sparks.material.opacity=Math.max(0,1-t/.8)*(.72+.28*Math.sin(t*28));
    hit.sparks.rotation.z=Math.max(0,t)*.28;hit.seal.scale.setScalar(motion?.7+.3*Math.min(1,Math.max(0,t)*7):1);
    hit.seal.children.forEach(o=>o.material.opacity=fade);
    hit.request.visible=motion&&age<collision+.7;
    if(hit.request.visible){
      const progress=t<0?age/collision:Math.max(0,1-t/.66);
      hit.packet.position.lerpVectors(hit.origin,hit.destination,progress);
      const tailProgress=t<0?Math.max(0,progress-.27):Math.min(1,progress+.23);
      const tail=hit.origin.clone().lerp(hit.destination,tailProgress),delta=hit.packet.position.clone().sub(tail);
      hit.trail.position.copy(tail).add(hit.packet.position).multiplyScalar(.5);
      hit.trail.scale.y=Math.max(.001,delta.length());hit.trail.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());
      hit.packet.material.opacity=t<0?1:Math.max(0,1-t/.7);hit.glow.material.opacity=.25*hit.packet.material.opacity;hit.trail.material.opacity=.8*hit.packet.material.opacity;
    }
    hit.label.dataset.phase=hit.phase;hit.label.style.opacity=String(motion?(t<0?.5:fade):1);
    positionLabel(hit.label,hit.group.position.clone().add(new THREE.Vector3(0,2.65,0)));
  }
}
