// Shared rigs keep a saved agent recognizable in the workshop, lounge and crew.
const avatarColors={green:0x76b900,cyan:0x55bfff,amber:0xf4b34f,coral:0xff8873,violet:0xb49aff,ice:0xcbddea};
const avatarDefaults=[{body:'classic',color:'green',accessory:'antenna'},{body:'round',color:'cyan',accessory:'headset'},{body:'rover',color:'amber',accessory:'cap'},{body:'round',color:'coral',accessory:'antenna'},{body:'classic',color:'violet',accessory:'glasses'}];
const robotShape=new THREE.Shape();robotShape.moveTo(-.29,-.2);robotShape.lineTo(.29,-.2);robotShape.lineTo(.29,.2);robotShape.lineTo(-.29,.2);robotShape.closePath();
const robotHeadGeometry=new THREE.ExtrudeGeometry(robotShape,{depth:.38,bevelEnabled:true,bevelThickness:.07,bevelSize:.065,bevelSegments:2,steps:1});robotHeadGeometry.translate(0,0,-.19);
const robotSphereGeometry=new THREE.SphereGeometry(1,24,16),robotLensGeometry=new THREE.TorusGeometry(.1,.019,6,20);
function createCharacter(avatar=avatarDefaults[0]){
  const appearance={...avatarDefaults[0],...avatar},color=avatarColors[appearance.color]||avatarColors.green;
  const group=new THREE.Group(),body=new THREE.Group();group.add(body);
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
  if(appearance.accessory==='headset'){
    box(body,0,1.27,0,.78,.055,.29,0x344a61);for(const side of [-1,1])box(body,side*.4,1.02,0,.12,.24,.26,color);
    box(body,.39,.89,.22,.045,.045,.30,0x526777);
  }else if(appearance.accessory==='glasses'){
    for(const side of [-1,1]){const lens=new THREE.Mesh(robotLensGeometry,mat(color));lens.position.set(side*.125,1.005,face.position.z+.049);body.add(lens);}box(body,0,1.005,face.position.z+.049,.065,.018,.018,color);
    cylinder(body,.28,1.33,0,.022,.14,0x72859a,8);
  }else if(appearance.accessory==='cap'){
    const cap=new THREE.Mesh(robotSphereGeometry,mat(color));cap.scale.set(.39,.14,.32);cap.position.set(0,1.29,0);body.add(cap);box(body,0,1.24,.13,.79,.045,.55,color);
  }else{cylinder(body,0,1.36,0,.024,.22,0x72859a,8);cylinder(body,0,1.49,0,.065,.07,color,12);}
  return {group,body,arms,legs,appearance,color};
}
