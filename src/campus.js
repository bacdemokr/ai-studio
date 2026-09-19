// Three.js is bundled above. The scene consumes the same workflow state as the board.
const app = document.getElementById('bac-planner');
const root = document.getElementById('agent-campus');
const el = name => document.getElementById('campus-' + name);
const api = window.BacDemo;
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors = [0x76b900, 0x55bfff, 0xf4b34f, 0xff8873, 0xb49aff];
const hex = i => '#' + colors[i].toString(16);
let snapshot = api.snapshot(), selected = 0, playing = false, timer = null, lastEvent = '', lastPhase = -2;
let sceneView = null, live = false;
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
function choose(i) {selected=i;if(live){render();root.dispatchEvent(new CustomEvent('bac:live-select',{detail:i}));}else{api.select(i);render();}}
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
  if(live)return;
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

/* WORLD_SCENE */
try {sceneView=createScene();}catch(error){el('fallback').hidden=false;root.dataset.renderer='fallback';console.warn('3D unavailable; accessible workflow controls remain available.',error.message);}
window.BacCampus={setRoom:(room,options)=>sceneView?.setRoom(room,options),overview:()=>sceneView?.overview(),setCollection:(agents,key)=>sceneView?.setCollection(agents,key),setDraft:profile=>sceneView?.setDraft(profile),inspect:()=>sceneView?.inspect()||{fallback:true},setLive:next=>{live=true;stop();snapshot=next;selected=next.selected;render();}};
render();
