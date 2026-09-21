  const meter=document.createElement('details');meter.id='studio-telemetry';meter.innerHTML='<summary aria-label="Runtime usage">CPU — <span>RAM —</span><span>Context —</span></summary><div class="usage-panel"></div>';
  root.querySelector('.campus-scene-bottom .row').prepend(meter);
  const count=n=>typeof n==='number'?Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(n):'—';
  const percent=n=>typeof n==='number'?n.toFixed(1)+'%':'—';
  let telemetryBusy=false;
  async function updateTelemetry(){
    if(!connected||document.hidden||telemetryBusy)return;
    telemetryBusy=true;
    try{
      const snapshot=await api('telemetry');
      if(!connected||document.hidden)return;
      const records=snapshot.agents.filter(a=>room==='mission'?a.crew:!a.crew);
      const knownRecords=records.filter(a=>typeof a.context==='number'&&typeof a.limit==='number'&&a.limit>0);
      const highest=knownRecords.reduce((best,a)=>!best||a.context/a.limit>best.context/best.limit?a:best,null);
      const summary=meter.querySelector('summary');
      summary.innerHTML=`CPU ${percent(snapshot.host.cpu)} <span>RAM ${percent(snapshot.host.memory)}</span><span>Context ${highest?percent(highest.context/highest.limit*100):'—'}${highest?' max':''}</span>`;
      summary.title=highest?`${highest.name}: ${count(highest.context)} / ${count(highest.limit)} tokens · last reported · highest agent utilization`:'Context usage has not been reported yet.';
      meter.querySelector('.usage-panel').innerHTML=`<div class="spread"><strong>Context per agent</strong><span>Last reported · tokens</span></div>${records.length?records.map(a=>{
        const known=typeof a.context==='number'&&typeof a.limit==='number'&&a.limit>0;
        const p=known?a.context/a.limit*100:null;
        return `<div class="usage-agent" title="${escape([a.model,a.measuredAt?new Date(a.measuredAt*1000).toLocaleString():null].filter(Boolean).join(' · '))}"><div class="spread"><strong>${escape(a.name)}</strong><span>${percent(p)}</span></div><div class="usage-track"><i style="width:${known?Math.min(100,p):0}%"></i></div><div class="spread"><span>${count(a.context)} / ${count(a.limit)} configured limit</span><span>${a.calls?count(a.total):'—'} cumulative</span></div></div>`;
      }).join(''):'<p>Run an agent to see reported usage.</p>'}<div class="usage-total spread"><strong>Cumulative usage</strong><strong>${count(snapshot.total)}</strong></div><small>Input + output across your agents’ recorded runs. Separate contexts; shared model. ${snapshot.unreportedCalls?'Some runs did not report usage. ':''}Context shows the last reported prompt against its configured budget, not live GPU capacity.</small><hr><div class="spread"><strong>App host</strong><span>CPU ${percent(snapshot.host.cpu)} · RAM ${percent(snapshot.host.memory)}</span></div><small>Host-wide utilization, not the remote inference server.</small>`;
    }catch{meter.querySelector('summary').removeAttribute('title');meter.querySelector('summary').textContent='Usage unavailable';meter.querySelector('.usage-panel').textContent='Usage is unavailable. It will reconnect automatically.';}
    finally{telemetryBusy=false;}
  }
  meter.addEventListener('toggle',()=>{if(meter.open)updateTelemetry();});
  root.addEventListener('bac:world-room',updateTelemetry);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateTelemetry();});
  setInterval(updateTelemetry,5000);
