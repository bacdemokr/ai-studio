// All rooms share one renderer and the same camera/fullscreen lifecycle.
const loungeRoom=new THREE.Group(),workshopRoom=new THREE.Group();scene.add(loungeRoom,workshopRoom);
// All three rooms stay in one connected scene.
const residentLayer=document.createElement('div');residentLayer.className='world-residents';viewport.append(residentLayer);residentLayer.hidden=true;
const residents=[],residentMeshes=[];let residentKey='',collection=[],selectedResident='',draftProfile={name:'Jinny',persona:'guide',avatar:avatarDefaults[0]},draftRig=null,draftKey='';
const roomCameras={mission:[.43,.76,1],lounge:[.43,.76,1],workshop:[.34,.64,1]};
function floor(parent,width,depth){box(parent,0,-.3,0,width,.55,depth,0x151b23);box(parent,0,-.012,0,width-.12,.05,depth-.12,0x26323f);box(parent,0,-.13,depth/2+.01,width-.45,.035,.02,0x76b900,true);for(let x=-width/2+1;x<width/2;x++)box(parent,x,.019,0,.012,.006,depth-.3,0x374654);for(let z=-depth/2+1;z<depth/2;z++)box(parent,0,.019,z,width-.3,.006,.012,0x374654);}
floor(loungeRoom,18,12.6);
box(loungeRoom,0,.65,-6.05,18,1.35,.18,0x1e2732);
for(const [z,length] of [[-2.1,7.8],[5.1,1.8]])box(loungeRoom,-8.85,.65,z,.15,1.35,length,0x1e2732);
box(loungeRoom,0,1.36,-6.05,18,.055,.24,0x63778b);
for(const [z,length] of [[-2.1,7.8],[5.1,1.8]])box(loungeRoom,-8.85,1.36,z,.22,.055,length,0x63778b);
box(loungeRoom,0,2.0,-5.97,7.0,2.0,.14,0x0c121b);sign(loungeRoom,'YOUR AGENT LOUNGE',0,2.42,-5.86,6.2,.5,'#f2f6fb');sign(loungeRoom,'INDIVIDUAL MINDS. SHARED ENGINE.',0,1.74,-5.85,6.0,.27,'#9eafc1');
for(const x of [-6.4,6.4]){box(loungeRoom,x,.45,-4.65,3.1,.7,.94,0x334453);box(loungeRoom,x,.9,-5.07,3.1,.7,.17,0x45596c);box(loungeRoom,x-1.5,.7,-4.65,.15,.7,.95,0x45596c);box(loungeRoom,x+1.5,.7,-4.65,.15,.7,.95,0x45596c);}
const loungeBrand=sign(loungeRoom,'BUILD A CLAW',0,.04,5.65,3.2,.38,'#8fabc2');loungeBrand.rotation.x=-Math.PI/2;
const residentPods=new THREE.Group();loungeRoom.add(residentPods);
function clearGeometry(parent){const shared=new Set([boxGeometry,robotHeadGeometry,robotSphereGeometry,robotLensGeometry]),geometries=new Set();parent.traverse(o=>{if(o.geometry&&!shared.has(o.geometry))geometries.add(o.geometry);});geometries.forEach(g=>g.dispose());parent.clear();}
function setCollection(agents,key){
  collection=agents||[];selectedResident=key;residentLayer.dataset.dense=collection.length>6;
  const next=JSON.stringify(collection.map(a=>[a.key,a.name,a.avatar]));
  if(next!==residentKey){
    residentKey=next;clearGeometry(residentPods);residents.length=0;residentMeshes.length=0;residentLayer.replaceChildren();
    const cols=collection.length>9?4:3,rows=Math.ceil(collection.length/cols);
    collection.forEach((a,i)=>{
      const row=Math.floor(i/cols),inRow=Math.min(cols,collection.length-row*cols),x=(i%cols-(inRow-1)/2)*(cols===4?3.8:4.4),z=rows<=1?1.4:rows===2?-1.25+row*4.0:-2.1+row*2.9;
      const avatar=a.avatar||avatarDefaults[i%5],rig=createCharacter(avatar);rig.group.scale.setScalar(1.3);rig.group.position.set(x,.19,z);residentPods.add(rig.group);
      cylinder(residentPods,x,.08,z,.88,.15,0x364658,32);const halo=ring(residentPods,x,.17,z,.84,rig.color);
      box(residentPods,x,.022,z+1.08,1.8,.012,.16,rig.color);
      const node=document.createElement('button');node.type='button';node.className='world-resident';node.dataset.resident=a.key;node.setAttribute('aria-label','Open '+a.name+'’s workspace');node.style.setProperty('--resident-color','#'+rig.color.toString(16).padStart(6,'0'));node.innerHTML='<b>'+escape(a.name)+'</b><small></small>';node.onclick=()=>root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:a.key}));residentLayer.append(node);
      rig.group.traverse(o=>{if(o.isMesh){o.userData.resident=a.key;residentMeshes.push(o);}});
      residents.push({...rig,key:a.key,node,halo,x,z,index:i});
    });
  }
  residents.forEach(r=>{const a=collection.find(a=>a.key===r.key);r.node.setAttribute('aria-pressed',r.key===key);r.node.querySelector('small').textContent=a.pending?'Mission assigned':({guide:'Guide',maker:'Maker',analyst:'Analyst'}[a.persona]+' · '+a.skills.length+' skills');r.halo.visible=r.key===key||!!a.pending;});
}
floor(workshopRoom,12,8.5);
box(workshopRoom,0,.725,-4.16,12,1.45,.17,0x17222e);box(workshopRoom,0,1.46,-4.16,12,.035,.20,0x63778b);
cylinder(workshopRoom,0,.14,.5,1.85,.25,0x182432,64);cylinder(workshopRoom,0,.29,.5,1.65,.08,0x5e7184,64);
const draftRing=ring(workshopRoom,0,.345,.5,1.57,0x76b900);
for(const x of [-4.5,4.5]){box(workshopRoom,x,.75,-2.2,1.25,1.5,.85,0x314356);for(let y=.25;y<1.4;y+=.22)box(workshopRoom,x,y,-1.765,1.0,.065,.02,0x768d9f);box(workshopRoom,x+.42,1.32,-1.74,.08,.08,.02,0x76b900,true);}
const workBrand=sign(workshopRoom,'BUILD A CLAW',0,.025,3.25,3.0,.43,'#8faac1');workBrand.rotation.x=-Math.PI/2;
function setDraft(profile){
  draftProfile=profile;const avatar=profile.avatar||avatarDefaults[0],key=JSON.stringify(avatar);if(key===draftKey)return;draftKey=key;
  if(draftRig){workshopRoom.remove(draftRig.group);clearGeometry(draftRig.group);}
  draftRig=createCharacter(avatar);draftRig.group.scale.setScalar(2.05);draftRig.group.position.set(0,.35,.5);workshopRoom.add(draftRig.group);draftRing.material=mat(draftRig.color,true);
}
function animateRooms(){
  if((room==='workshop'||overview||journey)&&draftRig){if(motion){draftRig.group.rotation.y=Math.sin(clock*.35)*.24;draftRig.body.position.y=Math.sin(clock*1.8)*.025;draftRig.arms[0].rotation.x=Math.sin(clock*1.5)*.12;}}
  if(room==='lounge'||overview||journey)residents.forEach(r=>{if(motion){r.body.position.y=Math.sin(clock*1.6+r.index)*.035;r.group.rotation.y=Math.sin(clock*.35+r.index)*.2;r.arms.forEach((a,i)=>a.rotation.x=Math.sin(clock*1.4+r.index+i)*.09);}positionLabel(r.node,loungeRoom.localToWorld(new THREE.Vector3(r.x,2.4,r.z)));});
}
function roomHitTargets(){return room==='lounge'?residentMeshes:[];}
function selectRoomObject(object){if(object.userData.resident)root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:object.userData.resident}));}
function residentInfo(){return residents.map(r=>({key:r.key,avatar:r.appearance,position:r.group.position.toArray()}));}
setDraft(draftProfile);
