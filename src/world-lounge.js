// Idle personality vignettes and brief excerpts of actual completed replies.
// All timing runs on the scene clock: no requests, timers or background jobs.
const loungePersonalities={
  guide:{title:'도우미',speed:.70,rest:[2.8,5.2],intro:name=>`안녕하세요, ${name}입니다. 함께해요!`,lines:[
    '하나씩 해보죠. 같이 풀어봐요.',
    '복잡한 걸 쉽게 풀어내는 게 좋아요.',
    '처음 오셨나요? 잘 오셨어요.',
    '편하게 물어보세요. 사소한 질문도 좋아요.',
    '작은 응원 한마디가 꽤 힘이 되죠.'
  ]},
  maker:{title:'제작자',speed:1.02,rest:[1.2,3.0],intro:name=>`저는 ${name}입니다. 뭘 만들어볼까요?`,lines:[
    '직접 만들어보면 제일 잘 배우게 돼요.',
    '조금 다르게 해보면 어떨까요?',
    '아이디어만 주세요. 호기심은 제가 챙길게요.',
    '제가 좋아하는 질문은 “이렇게 해보면?”이에요.',
    '작은 실험에도 가능성은 많아요.'
  ]},
  analyst:{title:'연구원',speed:.57,rest:[3.8,6.5],intro:name=>`저는 ${name}입니다. 조금 더 살펴볼까요?`,lines:[
    '좋은 질문과 확실한 근거가 좋아요.',
    '작은 차이를 찾는 게 제 취향이에요.',
    '먼저 이해하고, 그다음 결정하죠.',
    '다르게 보면 새로운 게 보이기도 해요.',
    '꼼꼼히 살피고, “왜?”를 묻는 편이에요.'
  ]}
};
// Short, authored greetings reflect voice; answer length governs actual task replies.
const loungeVoices={
  direct:{guide:['목표는 명확하게, 다음 행동은 구체적으로.','바로 실행할 수 있는 계획을 세우죠.'],maker:['말은 줄이고, 첫 버전부터 만들어보죠.','작게 시작해서, 해보고, 고치죠.'],analyst:['근거부터 보여주세요.','사실부터 확인하고 결론을 내리죠.']},
  playful:{guide:['복잡한 아이디어의 내비게이션이라고 생각해주세요.','한 걸음 나아가면 제 체크리스트도 신나요.'],maker:['아이디어를 넣으면 작은 발명품이 나옵니다.','제 취미요? “만약에”를 시제품으로 바꾸기요.'],analyst:['제 수집품은 소문보다 출처예요.','수수께끼인가요? 마음의 돋보기를 꺼내볼게요.']},
  cynical:{guide:['또 회의요? 끝나고 할 일이 생긴다면 좋죠.','“어떻게든 되겠지”에도 체크리스트는 필요하죠.'],maker:['거창한 아이디어군요. 작은 버전부터 돌려보죠.','발표 자료요? 일단 만들어보는 게 낫겠어요.'],analyst:['자신 있는 주장이네요. 출처는요?','그냥 추측하라고요? 근거부터 주세요.']}
};
// Idle dialogue is authored flavor, never a claim that research or tool work occurred.
// Use the purpose only to pick a topic; never recite the user's instructions.
function purposeDialogue(r){
  const text=r.purpose.trim().toLowerCase();
  const domains=[
    [/weather|forecast|날씨|기상/,['날씨','도시를 알려주시면 날씨부터 살펴볼게요.','날씨부터 확인하고 외출 계획을 세우죠.','날씨도 변덕이 있죠. 우산은 그걸 잘 알아요.','소풍이요? 일단 일기예보부터 보죠.']],
    [/document|pdf|slide|deck|summar|문서|요약|슬라이드/,['문서 정리','핵심부터 같이 찾아봐요.','세 가지로, 핵심만 정리하죠.','두꺼운 자료도 요약하면 가벼워져요.','슬라이드는 많은데, 요점은 어디 있을까요?']],
    [/travel|trip|food|여행|맛집/,['여행 계획','좋아하는 것부터 여행에 담아봐요.','목적지, 날짜, 예산부터 정하죠.','제 여행 계획에는 간식 시간이 꼭 있어요.','빈틈없는 일정이군요. 여행이 아니라 출근 같아요.']],
    [/research|compare|조사|연구/,['자료 조사','궁금한 점을 조금 더 살펴봐요.','질문과 살펴볼 자료를 알려주세요.','믿을 만한 출처는 보물 같아요.','그럴듯하네요. 사실인지는 따로 봐야겠지만요.']],
    [/app|game|code|build|앱|게임|코딩|개발/,['만들기','아이디어를 작은 버전부터 만들어봐요.','기능 하나를 골라서 제대로 만들어보죠.','시제품은 작게, 호기심은 크게!','큰 아이디어군요. 쓸 만한 최소 버전부터 볼까요?']],
    [/writ|content|invitation|campaign|글|작성|마케팅/,['글쓰기','읽는 사람에게 잘 전해질 표현을 찾아봐요.','독자, 메시지, 형식부터 정하죠.','빈 문서보다 심심한 제목이 더 무서워요.','“혁신적”이라고요? 일단 믿을 만하게 써보죠.']]
  ];
  const match=domains.find(([pattern])=>pattern.test(text));
  const tone=['kind','direct','playful','cynical'].includes(r.tone)?r.tone:'kind';
  const voiceIndex={kind:1,direct:2,playful:3,cynical:4}[tone];
  const lines=match?[match[1][voiceIndex],{
    kind:`${match[1][0]}, 함께하면 더 수월할 거예요.`,
    direct:`${match[1][0]}부터 집중해보죠.`,
    playful:`${match[1][0]}에 호기심 한 스푼!`,
    cynical:`${match[1][0]}, 불필요한 일은 빼고 해보죠.`
  }[tone]]:(loungeVoices[tone]?.[r.persona]||loungePersonalities[r.persona].lines);
  return lines[r.line++%lines.length];
}
function compactLoungeLine(text,r){
  const line=String(text||'').replace(/\s+/g,' ').trim();
  if(line&&Array.from(line).length<=80)return line;
  return {kind:'준비되면 말씀해주세요.',direct:'다음은 뭘 할까요?',playful:'오늘은 뭘 해볼까요?',cynical:'준비됐어요. 보람 있는 일을 해보죠.'}[r.tone]||'준비되면 말씀해주세요.';
}
function loungeLine(r){
  if(r.purpose)return purposeDialogue(r);
  const mood=loungePersonalities[r.persona],voice=loungeVoices[r.tone];
  if(!voice)return r.saidIntro?mood.lines[r.line++%mood.lines.length]:mood.intro(r.name);
  const lines=voice[r.persona],line=lines[r.line++%lines.length];
  return (r.saidIntro?'':`${r.name}입니다. `)+line;
}
// An excerpt, not another model call: preserve the reply's wording and persona.
function loungeReplyExcerpt(answer){
 const text=String(answer||'').replace(/```[^\n]*\n/g,'').replace(/```/g,'')
  .replace(/!\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1')
  .replace(/<[^>]*>/g,'').replace(/^[ \t]*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)/gm,'')
  .replace(/[*_`~]/g,'').replace(/\s+/g,' ').trim();
 if(text.length<=240)return text;
 const excerpt=text.slice(0,237),sentences=[...excerpt.matchAll(/[.!?。！？](?=\s|$)/g)];
 const end=sentences.at(-1)?.index;
 return (end>=60?excerpt.slice(0,end+1):excerpt.replace(/\s+\S*$/,'')).trim()+'…';
}
const loungeBounds={left:-7.1,right:7.1,back:-2.7,front:4.4};
const loungeLayoutKey='bac-lounge-layout-v1';
let loungeLayout={};try{const saved=JSON.parse(localStorage.getItem(loungeLayoutKey)||'{}');if(saved&&typeof saved==='object')loungeLayout=saved;}catch{}
function savedLoungePosition(key){const p=loungeLayout[key];return Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)?[THREE.MathUtils.clamp(p[0],loungeBounds.left,loungeBounds.right),THREE.MathUtils.clamp(p[1],loungeBounds.back,loungeBounds.front)]:null;}
function loungePointerPoint(e){
 const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
 const hit=raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),-.015),new THREE.Vector3());return hit?loungeRoom.worldToLocal(hit):null;
}
function beginResidentDrag(e,key){
 if(e.button!==0||room!=='lounge'||overview||journey||arrival||drag)return false;
 const r=residents.find(r=>r.key===key),point=loungePointerPoint(e);if(!r||!point||r.atOpenTask||r.atRoundtable)return false;
 endLoungeSpeech();r.target=null;
 drag={resident:r,x:e.clientX,y:e.clientY,start:r.group.position.clone(),offset:r.group.position.clone().sub(point),pointerId:e.pointerId};moved=false;
 r.dragging=true;e.currentTarget.setPointerCapture(e.pointerId);e.preventDefault();return true;
}
function moveResidentDrag(e){
 if(!drag?.resident||drag.pointerId!==e.pointerId)return false;
 if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>5)moved=true;
 if(!moved)return true;
 const p=loungePointerPoint(e);if(!p)return true;p.add(drag.offset);p.x=THREE.MathUtils.clamp(p.x,loungeBounds.left,loungeBounds.right);p.z=THREE.MathUtils.clamp(p.z,loungeBounds.back,loungeBounds.front);
 if(!residents.some(r=>r!==drag.resident&&Math.hypot(r.group.position.x-p.x,r.group.position.z-p.z)<1.4))drag.resident.group.position.set(p.x,.015,p.z);
 return true;
}
function endResidentDrag(cancel=false){
 if(!drag?.resident)return false;
 const r=drag.resident;r.dragging=false;
 if(cancel)r.group.position.copy(drag.start);
 else if(moved){r.placed=true;loungeLayout[r.key]=[r.group.position.x,r.group.position.z];try{localStorage.setItem(loungeLayoutKey,JSON.stringify(loungeLayout));}catch{}r.suppressClickUntil=performance.now()+400;}
 // Selecting and placing a resident are compatible. Small pointer movement
 // during a name-tag click must not silently discard the workspace selection.
 drag=null;
 if(!cancel)root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:r.key}));
 return true;
}
const loungeIdleInterval=30;
let loungeTime=0,loungeSpeaker=null,lastLoungeSpeaker='',nextLoungeSpeech=.9,nextLoungeIdle=loungeIdleInterval;
const welcomeSpeakers=[];
function queueWelcome(key){
  endLoungeSpeech();
  if(!welcomeSpeakers.includes(key))welcomeSpeakers.push(key);
  nextLoungeSpeech=loungeTime;
}
function welcomeLine(r){
  return `안녕하세요, ${r.name}입니다.`;
}
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
  r.completionSpeech=false;r.node.removeAttribute('aria-describedby');r.node.removeAttribute('title');r.activity=r.pending?'assigned':'resting';r.waitUntil=loungeTime+1.1+residentRandom(r);loungeSpeaker=null;nextLoungeSpeech=loungeTime+2.7;
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
    const avatar={...avatarDefaults[index%5],...a.avatar,protection:a.protection||'standard'};let r=residents.find(r=>r.key===a.key);
    if(!r){
      const [x,z]=savedLoungePosition(a.key)||loungeSpawn(),rig=createCharacter(avatar),mount=new THREE.Group();rig.group.scale.setScalar(1.3);rig.group.position.set(x,.015,z);mount.add(rig.group);residentPods.add(mount);
      const halo=ring(mount,x,.045,z,.65,rig.color);
      const node=document.createElement('button');node.type='button';node.className='world-resident';node.dataset.resident=a.key;node.dataset.speaking='false';node.innerHTML='<b></b><small></small><span class="world-resident-speech" hidden></span>';residentLayer.append(node);
      const speech=node.querySelector('.world-resident-speech');speech.id='lounge-speech-'+a.key;
      r={...rig,placed:!!savedLoungePosition(a.key),key:a.key,mount,node,halo,seed:residentSeed(a.key),target:null,waitUntil:loungeTime+.25+index*.4,activity:'resting',hovered:false,focused:false,saidIntro:false,line:0,speechText:'',blockedFor:0};residents.push(r);
      node.onclick=e=>{if(e.detail>0&&performance.now()<(r.suppressClickUntil||0)){e.preventDefault();return;}root.dispatchEvent(new CustomEvent('bac:collection-select',{detail:r.key}));};
      node.style.touchAction='none';node.style.cursor='grab';
      node.onpointerdown=e=>beginResidentDrag(e,r.key);node.onpointermove=moveResidentDrag;
      node.onpointerup=()=>{if(drag?.resident===r){endResidentDrag();r.suppressClickUntil=performance.now()+400;}};node.onpointercancel=()=>endResidentDrag(true);
      node.onpointerenter=()=>r.hovered=true;node.onpointerleave=()=>r.hovered=false;
      node.onfocus=()=>r.focused=true;node.onblur=()=>r.focused=false;
    }else if(['body','color','accessory','protection'].some(field=>r.appearance[field]!==avatar[field])){
      const old=r.group,rig=createCharacter(avatar);rig.group.scale.setScalar(1.3);rig.group.position.copy(old.position);rig.group.rotation.copy(old.rotation);
      r.mount.remove(old);clearGeometry(old);r.mount.add(rig.group);Object.assign(r,rig);r.halo.material=mat(rig.color,true);
    }
    const tone=loungeVoices[a.tone]?a.tone:'kind';
    if(r.persona!==a.persona||r.name!==a.name||r.tone!==tone||r.purpose!==(a.purpose||'')){if(loungeSpeaker===r)endLoungeSpeech();r.saidIntro=false;r.line=0;}
    r.deleting=!!a.deleting;r.heartbeat=!!a.techRadar||(a.skills||[]).includes('radar');
    if(r.deleting){
      if(loungeSpeaker===r)endLoungeSpeech();
      r.completionCue=false;r.target=null;
    }
    const latest=a.latestMission,signature=latest?latest.id+':'+latest.status:'',replyHeld=!!protectionReplyDelay(a.key,null);
    r.replyExcerpt=!r.deleting&&!replyHeld&&latest?.status==='done'?loungeReplyExcerpt(latest.answerPreview):'';
    if(r.missionSignature!==undefined&&signature!==r.missionSignature&&r.replyExcerpt){
      // A fresh answer takes precedence over an unrelated idle vignette.
      if(loungeSpeaker&&!loungeSpeaker.completionSpeech)endLoungeSpeech();
      else if(loungeSpeaker===r)endLoungeSpeech();
      r.completionCue=true;nextLoungeSpeech=loungeTime;
    }
    if(!replyHeld)r.missionSignature=signature;
    // Shared-event reservations protect identity; only unfinished activity makes the resident busy.
    const occupied='activity' in a?!!a.activity:['queued','running','waiting','stopping'].includes(latest?.status);
    if(occupied)r.completionCue=false;
    r.name=a.name;r.purpose=a.purpose||'';r.persona=loungePersonalities[a.persona]?a.persona:'guide';r.tone=tone;r.verbosity=a.verbosity||'balanced';r.pending=occupied;
    if(loungeSpeaker===r&&r.pending)endLoungeSpeech();
    if(r.deleting)r.activity='deleting';
    else if(r.pending)r.activity='assigned';
    else if(r.activity==='assigned')r.activity='resting';
    r.node.setAttribute('aria-label','Open '+a.name+'’s workspace');r.node.setAttribute('aria-pressed',r.key===key);r.node.style.setProperty('--resident-color','#'+r.color.toString(16).padStart(6,'0'));r.node.querySelector('b').textContent=a.name;
    r.node.querySelector('small').textContent=r.deleting?(a.deletionWaiting?'Deleting…':'Cleanup paused'):r.pending?'Busy':'Ready';
    r.halo.visible=r.key===key||r.pending||loungeSpeaker===r;
  });
  residentMeshes.length=0;residents.forEach(r=>r.group.traverse(o=>{if(o.isMesh){o.userData.resident=r.key;residentMeshes.push(o);}}));
  if(!residents.length){lastLoungeSpeaker='';nextLoungeSpeech=loungeTime+.9;nextLoungeIdle=loungeTime+loungeIdleInterval;}
  syncVisitorCollection();
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
  if(r.deleting){r.activity='deleting';return false;}
  r.activity=r.pending?'assigned':loungeSpeaker===r?'speaking':'resting';
  if(r.placed||r.dragging||r.pending||r.hovered||r.focused||loungeSpeaker===r)return false;
  if(!r.target&&loungeTime>=r.waitUntil)chooseLoungeTarget(r);
  if(!r.target)return false;
  const delta=r.target.clone().sub(p),distance=delta.length();
  if(distance<.18){r.target=null;r.waitUntil=loungeTime+mood.rest[0]+residentRandom(r)*(mood.rest[1]-mood.rest[0]);return false;}
  const steering=delta.normalize();
  // Yield before bodies overlap. Repulsion opposing the goal used to flip the
  // normalized heading each frame when two residents met.
  const next=p.clone().addScaledVector(steering,Math.min(distance,dt*mood.speed));
  next.x=THREE.MathUtils.clamp(next.x,loungeBounds.left,loungeBounds.right);next.z=THREE.MathUtils.clamp(next.z,loungeBounds.back,loungeBounds.front);
  const approachingNeighbor=residents.some(o=>{
    if(o===r)return false;
    const gap=p.distanceTo(o.group.position),nextGap=next.distanceTo(o.group.position);
    return nextGap<1.85&&nextGap<gap-.00001;
  });
  if(approachingNeighbor||next.distanceTo(p)<.001){
    r.blockedFor+=dt;r.holdHeadingUntil=loungeTime+1.5;
    if(r.blockedFor>.75){r.target=null;r.waitUntil=loungeTime+1+residentRandom(r)*1.2;}
    return false;
  }
  r.blockedFor=0;p.copy(next);turnResident(r,Math.atan2(steering.x,steering.z),dt);r.activity='walking';return true;
}
function startLoungeSpeech(){
  if(loungeSpeaker||loungeTime<nextLoungeSpeech||overview||journey||arrival||room!=='lounge'||drag)return;
  while(welcomeSpeakers.length&&!residents.some(r=>r.key===welcomeSpeakers[0]&&!r.pending&&!r.deleting&&!r.atOpenTask&&!r.atRoundtable))welcomeSpeakers.shift();
  const newcomer=residents.find(r=>r.key===welcomeSpeakers[0]);
  if(!motion&&!newcomer&&!residents.some(r=>r.completionCue))return;
  const eligible=residents.filter(r=>!r.deleting&&!r.atRoundtable&&!r.atOpenTask&&!r.pending&&(r.completionCue||(!r.hovered&&!r.focused)));if(!eligible.length&&!newcomer)return;
  const start=(residents.findIndex(r=>r.key===lastLoungeSpeaker)+1)%Math.max(1,residents.length);
  const ordered=[...residents.slice(start),...residents.slice(0,start)].filter(r=>eligible.includes(r));
  // Greetings and actual replies are immediate. Ambient chatter has one shared
  // 30-second cadence, regardless of roster size or previous conversations.
  let r=newcomer||ordered.find(r=>r.completionCue);
  if(!r){
    if(!motion||loungeTime<nextLoungeIdle)return;
    // Paused heartbeat agents also stay out of ambient chatter.
    const idle=eligible.filter(r=>!r.heartbeat);if(!idle.length)return;
    const others=idle.filter(r=>r.key!==lastLoungeSpeaker),candidates=others.length?others:idle;
    r=candidates[Math.floor(Math.random()*candidates.length)];
  }
  if(newcomer)welcomeSpeakers.shift();
  r.completionSpeech=!newcomer&&!!r.completionCue;if(!newcomer)r.completionCue=false;
  r.speechText=r.completionSpeech?r.replyExcerpt:compactLoungeLine(newcomer?welcomeLine(r):loungeLine(r),r);r.saidIntro=true;
  r.node.dataset.speechKind=r.completionSpeech?'reply':'idle';
  const speech=r.node.querySelector('.world-resident-speech');speech.textContent=r.speechText;speech.hidden=false;r.node.dataset.speaking='true';r.node.setAttribute('aria-describedby',speech.id);
  r.node.title=r.completionSpeech?'최근 답변의 일부입니다 · 전체 대화 보기':'말투에 맞춘 짧은 잡담입니다 · 선택하면 대화를 열어요';r.speechUntil=loungeTime+(r.completionSpeech?Math.min(14,Math.max(6,r.speechText.length/20)):5.8);r.target=null;
  loungeSpeaker=r;lastLoungeSpeaker=r.key;
  nextLoungeIdle=loungeTime+loungeIdleInterval;
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
    const compact=innerWidth<=560;
    const top=Math.min(h-(compact?80:104),Math.max((compact?154:114)+r.node.offsetHeight,y));r.node.style.top=top+'px';
    r.node.style.setProperty('--speech-tail',THREE.MathUtils.clamp(x-parseFloat(r.node.style.left)+half,18,r.node.offsetWidth-18)+'px');
  }
}
function animateLounge(dt){
  {
    loungeTime+=dt;
    if(loungeSpeaker&&loungeTime>=loungeSpeaker.speechUntil&&!loungeSpeaker.hovered&&!loungeSpeaker.focused)endLoungeSpeech();
    startLoungeSpeech();
  }
  residents.forEach((r,index)=>{
    if(r.atRoundtable||r.atOpenTask){r.mount.visible=false;r.node.hidden=true;return;}
    if(arrival?.key===r.key){r.mount.visible=false;r.node.hidden=true;return;}
    if(motion){
      const walking=moveResident(r,dt),speaking=loungeSpeaker===r,beat=loungeTime*(walking?8:1.7)+index;
      if(speaking)turnResident(r,azimuth,dt);
      else if(!walking&&!r.target&&loungeTime>=(r.holdHeadingUntil||0)&&!r.hovered&&!r.focused)turnResident(r,Math.sin(loungeTime*.4+index)*.35,dt);
      r.body.position.y=walking?Math.abs(Math.sin(beat))*.035:Math.sin(beat)*.018;
      r.legs.forEach((leg,j)=>leg.rotation.x=walking?Math.sin(beat+j*Math.PI)*.32:0);
      r.arms.forEach((arm,j)=>{arm.rotation.x=Math.sin(beat+j*Math.PI)*(walking?.27:.065);arm.rotation.z=speaking&&j===0?(r.persona==='guide'?-1.9+Math.sin(loungeTime*5)*.16:r.persona==='maker'?-1.15+Math.sin(loungeTime*4)*.2:-.48):0;});
    }
    r.halo.position.set(r.group.position.x,.045,r.group.position.z);r.halo.visible=r.key===selectedResident||r.pending||loungeSpeaker===r;
    placeResident(r);
  });
}
