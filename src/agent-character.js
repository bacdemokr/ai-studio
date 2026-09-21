// Shared rigs keep a saved agent recognizable in the workshop, lounge and crew.
const avatarColors={green:0x76b900,cyan:0x55bfff,amber:0xf4b34f,coral:0xff8873,violet:0xb49aff,ice:0xcbddea};
const avatarDefaults=[{body:'classic',color:'green',accessory:'antenna'},{body:'round',color:'cyan',accessory:'headset'},{body:'rover',color:'amber',accessory:'cap'},{body:'round',color:'coral',accessory:'antenna'},{body:'classic',color:'violet',accessory:'glasses'},{body:'claw',color:'ice',accessory:'headset'}];
const robotShape=new THREE.Shape();robotShape.moveTo(-.29,-.2);robotShape.lineTo(.29,-.2);robotShape.lineTo(.29,.2);robotShape.lineTo(-.29,.2);robotShape.closePath();
const robotHeadGeometry=new THREE.ExtrudeGeometry(robotShape,{depth:.38,bevelEnabled:true,bevelThickness:.07,bevelSize:.065,bevelSegments:2,steps:1});robotHeadGeometry.translate(0,0,-.19);
const robotSphereGeometry=new THREE.SphereGeometry(1,24,16),robotLensGeometry=new THREE.TorusGeometry(.1,.019,6,20);
function createCharacter(avatar=avatarDefaults[0]){
  const appearance={...avatarDefaults[0],...avatar},color=avatarColors[appearance.color]||avatarColors.green;
  const group=new THREE.Group(),body=new THREE.Group();group.add(body);
  if(appearance.body==='fox')appearance.body='claw';
  if(appearance.body==='claw')return createClaw(appearance,color,group,body);
  if(['cat','crab'].includes(appearance.body))return createCompanion(appearance,color,group,body);
  const arms=[],legs=[];
  box(body,0,.55,0,appearance.body==='rover'?.55:.4,.38,.3,0xcad4df);
  let head;
  if(appearance.body==='round'){
    head=new THREE.Mesh(robotSphereGeometry,mat(0xe6edf5));head.scale.set(.41,.34,.32);
  }else{head=new THREE.Mesh(robotHeadGeometry,mat(0xe6edf5));if(appearance.body==='rover')head.scale.set(1.18,.78,1.02);}
  head.position.y=.99;head.castShadow=true;body.add(head);
  const face=box(body,0,.99,appearance.body==='round'?.296:.26,appearance.body==='rover'?.61:.49,.25,.03,0x111c29);
  for(const side of [-1,1]){
    box(body,side*.125,1.005,face.position.z+.026,.062,.075,.023,color,true);
    const arm=new THREE.Group();arm.position.set(side*(appearance.body==='rover'?.38:.29),.7,0);box(arm,0,-.15,0,.12,.3,.14,0xabbccc);body.add(arm);arms.push(arm);
    const leg=new THREE.Group();leg.position.set(side*.12,.34,0);body.add(leg);legs.push(leg);
    if(appearance.body!=='rover'){box(leg,0,-.12,0,.14,.24,.15,0x788c9f);box(leg,0,-.25,.045,.18,.08,.24,0x283b50);}
    else{box(body,side*.28,.17,0,.2,.22,.57,0x172330);for(const z of [-.18,.18]){const wheel=cylinder(body,side*.39,.17,z,.12,.05,0x526777,12);wheel.rotation.z=Math.PI/2;}box(body,side*.4,.28,0,.02,.04,.4,color);}
  }
  box(body,0,.54,.171,.23,.095,.025,color,true);
  equipCharacter(body,face,appearance,color);
  return {group,body,arms,legs,appearance,color};
}

function equipCharacter(body,face,appearance,color){
  if(appearance.protection==='openshell'){
    const shield=new THREE.Group();shield.name='openshell-shield';shield.position.set(.12,.57,.48);shield.rotation.y=-.12;body.add(shield);
    const shape=new THREE.Shape();shape.moveTo(0,.40);shape.lineTo(.32,.25);shape.lineTo(.27,-.15);shape.quadraticCurveTo(.18,-.32,0,-.41);shape.quadraticCurveTo(-.18,-.32,-.27,-.15);shape.lineTo(-.32,.25);shape.closePath();
    const plate=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.045,bevelEnabled:true,bevelThickness:.012,bevelSize:.018,bevelSegments:1,steps:1}),mat(0x76b900));plate.castShadow=true;shield.add(plate);
    const rim=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(shape.getPoints(24).map(p=>new THREE.Vector3(p.x,p.y,.065))),new THREE.LineBasicMaterial({color:0xc5ef91}));shield.add(rim);
    const shackle=new THREE.Mesh(new THREE.TorusGeometry(.085,.015,6,20,Math.PI),mat(0xf3ffe6));shackle.position.set(0,.09,.085);shield.add(shackle);
    for(const x of [-.085,.085])box(shield,x,.052,.085,.03,.075,.025,0xf3ffe6);
    box(shield,0,-.035,.085,.23,.17,.035,0xf3ffe6);box(shield,0,-.03,.109,.025,.06,.012,0x416b0b);
  }

  if(appearance.accessory==='headset'){
    box(body,0,1.27,0,.78,.055,.29,0x344a61);for(const side of [-1,1])box(body,side*.4,1.02,0,.12,.24,.26,color);
    box(body,.39,.89,.22,.045,.045,.30,0x526777);
  }else if(appearance.accessory==='glasses'){
    const eyeY=appearance.body==='claw'?1.28:1.005;
    for(const side of [-1,1]){const lens=new THREE.Mesh(robotLensGeometry,mat(color));lens.position.set(side*.125,eyeY,face.position.z+.049);body.add(lens);}box(body,0,eyeY,face.position.z+.049,.065,.018,.018,color);
    cylinder(body,.28,1.33,0,.022,.14,0x72859a,8);
  }else if(appearance.accessory==='cap'){
    const cap=new THREE.Mesh(robotSphereGeometry,mat(color));cap.scale.set(.39,.14,.32);cap.position.set(0,1.29,0);body.add(cap);box(body,0,1.24,.13,.79,.045,.55,color);
  }else{cylinder(body,0,1.36,0,.024,.22,0x72859a,8);cylinder(body,0,1.49,0,.065,.07,color,12);}
}

function createCompanion(appearance,color,group,body){
  const arms=[],legs=[],crab=appearance.body==='crab';
  function oval(parent,x,y,z,sx,sy,sz,tint){const mesh=new THREE.Mesh(robotSphereGeometry,mat(tint));mesh.position.set(x,y,z);mesh.scale.set(sx,sy,sz);mesh.castShadow=true;parent.add(mesh);return mesh;}
  oval(body,0,crab?.61:.57,0,crab?.49:.27,crab?.27:.36,.26,color);
  if(!crab){
    oval(body,0,1.02,.01,.37,.31,.3,color);
    oval(body,0,.56,.225,.16,.23,.055,0xe6edf5);
    for(const side of [-1,1]){
      const ear=new THREE.Mesh(new THREE.ConeGeometry(.14,.32,4),mat(color));ear.position.set(side*.245,1.34,0);ear.rotation.z=-side*.17;body.add(ear);
      const inner=new THREE.Mesh(new THREE.ConeGeometry(.082,.22,4),mat(0xffabb9));inner.position.set(side*.245,1.36,.07);body.add(inner);
      oval(body,side*.105,.94,.286,.13,.085,.085,0xe6edf5);
    }
    oval(body,0,.98,.36,.042,.033,.035,0x172330);
    const tail=new THREE.Group();tail.position.set(0,.42,-.19);body.add(tail);
    const plume=oval(tail,.18,.2,-.26,.07,.32,.11,color);plume.rotation.z=-.5;
    oval(tail,.32,.46,-.26,.065,.12,.085,0xe6edf5);
  }
  const face={position:{z:.30}};
  for(const side of [-1,1]){
    if(crab){cylinder(body,side*.16,.96,.15,.035,.3,color,10);oval(body,side*.16,1.1,.15,.09,.1,.08,0xe6edf5);}
    oval(body,side*(crab?.16:.135),crab?1.11:1.07,crab?.224:.296,.036,.052,.025,0x101b29);
    const arm=new THREE.Group();arm.position.set(side*(crab?.43:.25),crab?.72:.72,0);body.add(arm);arms.push(arm);
    if(crab){
      oval(arm,side*.14,.07,.05,.2,.075,.08,color);
      for(const tip of [-1,1]){const claw=oval(arm,side*.30,.18,.06+tip*.09,.12,.18,.06,color);claw.rotation.z=-side*.4;}
      for(let i=0;i<3;i++){const limb=new THREE.Group();limb.position.set(side*.35,.47,(i-1)*.18);body.add(limb);legs.push(limb);const foot=box(limb,side*.16,-.15,0,.32,.085,.08,color);foot.rotation.z=side*.55;}
    }else{
      oval(arm,side*.02,-.13,.01,.085,.20,.09,color);oval(arm,side*.02,-.29,.045,.09,.07,.10,0xe6edf5);
      const leg=new THREE.Group();leg.position.set(side*.14,.28,0);body.add(leg);legs.push(leg);oval(leg,0,-.12,.065,.115,.14,.16,color);
    }
  }
  equipCharacter(body,face,appearance,color);
  return {group,body,arms,legs,appearance,color};
}

// Upright lobster silhouette: oversized open pincers, segmented tail, no feline ears.
function createClaw(appearance,color,group,body){
  const arms=[],legs=[];
  function oval(parent,x,y,z,sx,sy,sz,tint=color){const mesh=new THREE.Mesh(robotSphereGeometry,mat(tint));mesh.position.set(x,y,z);mesh.scale.set(sx,sy,sz);mesh.castShadow=true;parent.add(mesh);return mesh;}
  oval(body,0,.66,0,.28,.39,.25);
  oval(body,0,1.01,.025,.33,.28,.27);
  for(let i=0;i<4;i++){
    oval(body,0,.47-i*.07,-.18-i*.09,.23-i*.025,.095,.15);
    box(body,0,.48-i*.07,.215,.35-i*.04,.025,.02,0xe6edf5);
  }
  for(const side of [-1,1]){
    const fan=oval(body,side*.11,.18,-.57,.16,.055,.17);fan.rotation.y=side*.45;
    cylinder(body,side*.13,1.20,.17,.029,.15,color,8);
    oval(body,side*.13,1.28,.20,.074,.085,.065,0xe6edf5);
    oval(body,side*.13,1.28,.258,.032,.043,.02,0x111c29);
    const arm=new THREE.Group();arm.position.set(side*.29,.67,0);body.add(arm);arms.push(arm);
    const forearm=oval(arm,side*.14,.015,.10,.19,.08,.09);forearm.rotation.z=side*.35;
    const outline=new THREE.Shape();outline.moveTo(-.10,0);outline.quadraticCurveTo(-.31,.23,-.18,.48);outline.lineTo(-.05,.31);outline.lineTo(0,.20);outline.lineTo(.055,.32);outline.lineTo(.18,.48);outline.quadraticCurveTo(.31,.23,.10,0);outline.closePath();
    const pincer=new THREE.Mesh(new THREE.ExtrudeGeometry(outline,{depth:.14,bevelEnabled:true,bevelThickness:.025,bevelSize:.025,bevelSegments:2,steps:1}),mat(color));
    pincer.position.set(side*.26,.04,.12);pincer.rotation.z=-side*.22;pincer.castShadow=true;arm.add(pincer);
    for(let i=0;i<2;i++){const leg=new THREE.Group();leg.position.set(side*.19,.34,-i*.15);body.add(leg);legs.push(leg);const foot=box(leg,side*.09,-.15,.06,.12,.26,.12,0x526777);foot.rotation.z=side*.22;}
  }
  box(body,0,.91,.285,.12,.025,.025,0x111c29);
  equipCharacter(body,{position:{z:.28}},appearance,color);
  return {group,body,arms,legs,appearance,color};
}
