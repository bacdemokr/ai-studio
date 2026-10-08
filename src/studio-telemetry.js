  const meter=document.createElement('details');meter.id='studio-telemetry';meter.innerHTML='<summary aria-label="Runtime usage">CPU — <span>RAM —</span><span>Context —</span></summary><div class="usage-panel"></div>';
  root.querySelector('.campus-scene-bottom .row').prepend(meter);
  const count=n=>typeof n==='number'?Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(n):'—';
  const percent=n=>typeof n==='number'?n.toFixed(1)+'%':'—';
  const speed=n=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(1)+' tok/s':'—';
  let telemetryBusy=false, telemetrySnapshot=null;
  function missionTelemetryRecords(snapshot){
    const job=typeof selectedScenario!=='undefined'&&selectedScenario==='plan'?currentCollaboration():crewMission();
    if(!job)return [];
    const latest=new Map();
    for(const record of Object.values(job.payload?.metrics||{})){
      const previous=latest.get(record.agent);
      if(!previous||typeof record.measuredAt!=='number'||typeof previous.measuredAt!=='number'||record.measuredAt>=previous.measuredAt)latest.set(record.agent,record);
    }
    const roster=job.payload?.roster;
    const members=roster?roster.filter((_,role)=>(job.payload.enabledRoles||roster.map((_,i)=>i)).includes(role)):[...latest.values()].map(r=>({id:r.agent,name:r.name}));
    return members.map(member=>{
      const cumulative=snapshot.agents.find(a=>a.agent===member.id)||{},record=latest.get(member.id);
      return {...(record||{}),agent:member.id,name:member.name,total:cumulative.total,calls:cumulative.calls,
        status:record?'':(job.payload.activeStages||[]).includes(roster?.indexOf(member))?'Working':'Waiting'};
    });
  }
  function renderTelemetry(snapshot){
    const records=room==='mission'?missionTelemetryRecords(snapshot):snapshot.agents.filter(a=>!a.crew);
      const knownRecords=records.filter(a=>typeof a.context==='number'&&typeof a.limit==='number'&&a.limit>0);
      const highest=knownRecords.reduce((best,a)=>!best||a.context/a.limit>best.context/best.limit?a:best,null);
      const summary=meter.querySelector('summary');
      summary.innerHTML=`CPU ${percent(snapshot.host.cpu)} <span>RAM ${percent(snapshot.host.memory)}</span><span>Context ${highest?percent(highest.context/highest.limit*100):'—'}</span>`;
      summary.title=highest?`${highest.name}: ${count(highest.context)} / ${count(highest.limit)} tokens · last reported · highest agent utilization`:'Context usage has not been reported yet.';
      meter.querySelector('.usage-panel').innerHTML=`<div class="spread"><strong>Context per agent</strong><span>Last reported · tokens</span></div>${records.length?records.map(a=>{
        const known=typeof a.context==='number'&&typeof a.limit==='number'&&a.limit>0;
        const p=known?a.context/a.limit*100:null;
        return `<div class="usage-agent" title="${escape([a.model,a.measuredAt?new Date(a.measuredAt*1000).toLocaleString():null].filter(Boolean).join(' · '))}"><div class="spread"><strong>${escape(a.name)}</strong><span>${a.status?escape(a.status)+' · ':''}${percent(p)}</span></div><div class="usage-track"><i style="width:${known?Math.min(100,p):0}%"></i></div><div class="spread"><span>${count(a.context)} / ${count(a.limit)} configured limit</span><span>${a.calls?count(a.total):'—'} cumulative</span></div><div class="spread" title="Last recorded run: output tokens divided by elapsed response time, including queueing, prompt processing and tools. Not model-only generation speed."><span>Avg output speed</span><span>${speed(a.outputTokensPerSecond)}</span></div></div>`;
      }).join(''):'<p>Run an agent to see reported usage.</p>'}<div class="usage-total spread"><strong>Cumulative usage</strong><strong>${count(snapshot.total)}</strong></div><small>Input + output across all your agents’ recorded runs. ${room==='mission'?'Context and speed belong only to the selected mission. Waiting agents have no reported context yet. Cumulative usage includes earlier missions.':'This list includes completed runs; it is not a list of currently running agents.'} Each agent has a separate context. ${snapshot.unreportedCalls?'Some runs did not report usage. ':''}Context shows the last reported prompt against its configured budget. Avg output speed includes waiting and tools; it is not model-only generation speed. Speed is recorded on new runs.</small><hr><div class="spread"><strong>App host</strong><span>CPU ${percent(snapshot.host.cpu)} · RAM ${percent(snapshot.host.memory)}</span></div><small>Host-wide utilization, not the remote inference server.</small>`;
  }
  async function updateTelemetry(){
    if(!connected||document.hidden||telemetryBusy)return;
    telemetryBusy=true;
    const requestedAgent=agentId;
    try{
      const snapshot=await api('telemetry');
      if(!connected||document.hidden||requestedAgent!==agentId)return;
      telemetrySnapshot={agentId,snapshot};
      renderTelemetry(snapshot);
    }catch{meter.querySelector('summary').removeAttribute('title');meter.querySelector('summary').textContent='Usage unavailable';meter.querySelector('.usage-panel').textContent='Usage is unavailable. It will reconnect automatically.';}
    finally{telemetryBusy=false;}
  }
  meter.addEventListener('toggle',()=>{if(meter.open)updateTelemetry();});
  function repaintTelemetry(){
    if(telemetrySnapshot?.agentId===agentId)renderTelemetry(telemetrySnapshot.snapshot);
    else renderTelemetry({agents:[],host:{},total:null});
  }
  root.addEventListener('bac:state-rendered',repaintTelemetry);
  root.addEventListener('bac:world-room',()=>{repaintTelemetry();updateTelemetry();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateTelemetry();});
  setInterval(updateTelemetry,5000);
