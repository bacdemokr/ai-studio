// All rooms share one renderer and the same camera/fullscreen lifecycle.
const loungeRoom=new THREE.Group(),workshopRoom=new THREE.Group();scene.add(loungeRoom,workshopRoom);
// All three rooms stay in one connected scene.
const residentLayer=document.createElement('div');residentLayer.className='world-residents';viewport.append(residentLayer);residentLayer.hidden=true;
const residents=[],residentMeshes=[];let collection=[],selectedResident='',draftProfile={name:'Jinny',persona:'guide',avatar:avatarDefaults[0]},draftRig=null,draftKey='';
const roomCameras={mission:[.43,.76,1],lounge:[.43,.76,1],workshop:[.34,.64,1]};
function floor(parent,width,depth){box(parent,0,-.3,0,width,.55,depth,0x151b23);box(parent,0,-.012,0,width-.12,.05,depth-.12,0x26323f);box(parent,0,-.13,depth/2+.01,width-.45,.035,.02,0x76b900,true);for(let x=-width/2+1;x<width/2;x++)box(parent,x,.019,0,.012,.006,depth-.3,0x374654);for(let z=-depth/2+1;z<depth/2;z++)box(parent,0,.019,z,width-.3,.006,.012,0x374654);}
floor(loungeRoom,18,12.6);
box(loungeRoom,0,.65,-6.05,18,1.35,.18,0x1e2732);
box(loungeRoom,-8.85,.65,0,.15,1.35,12,0x1e2732);
box(loungeRoom,0,1.36,-6.05,18,.055,.24,0x63778b);
box(loungeRoom,-8.85,1.36,0,.22,.055,12,0x63778b);
box(loungeRoom,0,2.0,-5.97,7.0,2.0,.14,0x0c121b);sign(loungeRoom,'YOUR AGENT LOUNGE',0,2.42,-5.86,6.2,.5,'#f2f6fb');sign(loungeRoom,'INDIVIDUAL MINDS. SHARED ENGINE.',0,1.74,-5.85,6.0,.27,'#9eafc1');
for(const x of [-6.4,6.4]){box(loungeRoom,x,.45,-4.65,3.1,.7,.94,0x334453);box(loungeRoom,x,.9,-5.07,3.1,.7,.17,0x45596c);box(loungeRoom,x-1.5,.7,-4.65,.15,.7,.95,0x45596c);box(loungeRoom,x+1.5,.7,-4.65,.15,.7,.95,0x45596c);}
const loungeBrand=sign(loungeRoom,'BUILD A CLAW',-4,.04,5.65,3.2,.38,'#8fabc2');loungeBrand.rotation.x=-Math.PI/2;
const residentPods=new THREE.Group();loungeRoom.add(residentPods);
function clearGeometry(parent){const shared=new Set([boxGeometry,robotHeadGeometry,robotSphereGeometry,robotLensGeometry]),geometries=new Set();parent.traverse(o=>{if(o.geometry&&!shared.has(o.geometry))geometries.add(o.geometry);});geometries.forEach(g=>g.dispose());parent.clear();}
/* LOUNGE_LIFE */
floor(workshopRoom,12,8.5);
for(const x of [-3.6,3.6]){box(workshopRoom,x,.725,-4.16,4.8,1.45,.17,0x17222e);box(workshopRoom,x,1.46,-4.16,4.8,.035,.20,0x63778b);}
cylinder(workshopRoom,0,.14,.5,1.85,.25,0x182432,64);cylinder(workshopRoom,0,.29,.5,1.65,.08,0x5e7184,64);
const draftRing=ring(workshopRoom,0,.345,.5,1.57,0x76b900);
for(const x of [-4.5,4.5]){box(workshopRoom,x,.75,-2.2,1.25,1.5,.85,0x314356);for(let y=.25;y<1.4;y+=.22)box(workshopRoom,x,y,-1.765,1.0,.065,.02,0x768d9f);box(workshopRoom,x+.42,1.32,-1.74,.08,.08,.02,0x76b900,true);}
const workBrand=sign(workshopRoom,'BUILD A CLAW',0,.025,3.25,3.0,.43,'#8faac1');workBrand.rotation.x=-Math.PI/2;
function setDraft(profile){
  draftProfile=profile;const avatar=profile.avatar||avatarDefaults[0],key=JSON.stringify(avatar);if(key===draftKey)return;draftKey=key;
  if(draftRig){workshopRoom.remove(draftRig.group);clearGeometry(draftRig.group);}
  draftRig=createCharacter(avatar);draftRig.group.scale.setScalar(2.05);draftRig.group.position.set(0,.35,.5);workshopRoom.add(draftRig.group);draftRing.material=mat(draftRig.color,true);
}
function animateRooms(dt){
  if((room==='workshop'||overview||journey)&&draftRig){if(motion){draftRig.group.rotation.y=Math.sin(clock*.35)*.24;draftRig.body.position.y=Math.sin(clock*1.8)*.025;draftRig.arms[0].rotation.x=Math.sin(clock*1.5)*.12;}}
  if(room==='lounge'||overview||journey)animateLounge(dt);
}
function roomHitTargets(){return room==='lounge'?residentMeshes:[];}
function selectRoomObject(object){if(object.userData.resident)root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:object.userData.resident}));}
function residentInfo(){return residents.map(r=>({key:r.key,avatar:r.appearance,persona:r.persona,position:r.group.position.toArray(),activity:r.activity,speech:r.speechText||null}));}
setDraft(draftProfile);
