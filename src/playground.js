(() => {
  const root = document.getElementById('bac-playground');
  const app = document.getElementById('bac-planner');
  const el = id => root.querySelector('#pg-' + id);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const iconPaths = {
    weather:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
    telegram:'<path d="m21 3-7 18-4-7-7-4 18-7ZM10 14 21 3"/>',
    memory:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/><rect x="10" y="10" width="4" height="4"/>',
  };
  const icon = id => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+iconPaths[id]+'</svg>';
  const skills = [
    {id:'weather', title:'Weather lookout', subtitle:'Read data. Make a plan.', symbol:'☀', tone:'sand', description:'Check a practice forecast, then suggest what to bring.'},
    {id:'search', title:'Web scout', subtitle:'Search. Compare. Explain.', symbol:'⌕', tone:'blue', description:'Inspect three prepared results and compare what each one contributes.'},
    {id:'telegram', title:'Telegram buddy', subtitle:'Your agent, on your phone.', symbol:'↗', tone:'rose', description:'Pair a practice phone and preview a reply from the same agent.'},
    {id:'memory', title:'Remember me', subtitle:'Teach it a preference.', symbol:'✎', tone:'purple', description:'Save a short note and see it used in another mission.'},
  ];
  const state = {skill:'weather', equipped:new Set(['weather','search']), name:'Jinny', persona:'friendly', memory:'', paired:false, brief:null, pending:null};
  const weather = {
    Zurich:{temperature:16, condition:'light rain', suggestion:'Bring a light rain jacket and keep the hands-on demos indoors.'},
    Austin:{temperature:30, condition:'sunny', suggestion:'Bring water and plan the hands-on demos in a shaded or indoor space.'},
    Seattle:{temperature:13, condition:'cloudy', suggestion:'Bring an extra layer and keep a sheltered meeting point.'},
  };
  const examples = {
    workshop:[
      {title:'Make an agent your own', kind:'Onboarding example', excerpt:'Choose a name and persona, equip one skill, then compare the result with that skill removed.'},
      {title:'Check the evidence', kind:'Search example', excerpt:'Open the underlying result cards. Compare a summary against the original snippets before using it.'},
      {title:'Move a task to your phone', kind:'Messaging example', excerpt:'Pair a phone session, preview the destination and message, and handle a denied connection.'},
    ],
    event:[
      {title:'Prepare a fallback', kind:'Demo runbook example', excerpt:'Keep example outputs available for each session in case a live service is unavailable.'},
      {title:'Check station capacity', kind:'Operations example', excerpt:'Allocate attendees by interest, divide them into groups, then compare required stations with equipment availability.'},
      {title:'Align the invitation', kind:'Marketing example', excerpt:'Use the approved event duration, session language and venue details in attendee-facing copy.'},
    ],
  };
  function skill() { return skills.find(s => s.id === state.skill); }
  function invalidate() {
    state.pending = null;
    el('permission').hidden = true;
    el('error').hidden = true;
    el('trace').replaceChildren();
    el('result').innerHTML = '<span class="quiet">Ready for a new practice run.</span>';
  }
  function render() {
    el('loadout').innerHTML = skills.map(s => `<label><input type="checkbox" data-equip="${s.id}" ${state.equipped.has(s.id)?'checked':''}>${s.title}</label>`).join('');
    el('missions').innerHTML = skills.map(s => `<button class="pg-mission" data-mission="${s.id}" aria-pressed="${state.skill===s.id}" style="--tone:var(--${s.tone})"><span class="pg-symbol" aria-hidden="true">${icon(s.id)}</span><strong>${s.title}</strong><span class="quiet">${s.subtitle}</span></button>`).join('');
    el('mission-kicker').textContent = state.name + ' · SOLO MISSION';
    el('mission-title').textContent = skill().title;
    el('mission-description').textContent = skill().description;
    el('equipped').textContent = state.equipped.has(state.skill) ? 'Skill equipped' : 'Equip this skill to try it';
    for (const s of skills) el(s.id + '-inputs').hidden = s.id !== state.skill;
    el('block-control').hidden = !['weather','search'].includes(state.skill);
    el('run').textContent = {weather:'Check practice weather',search:'Explore sample results',telegram:'Preview phone reply',memory:'Remember this note'}[state.skill];
    el('pair-status').textContent = state.paired ? 'Practice phone · paired' : 'Practice phone · disconnected';
    el('pair').textContent = state.paired ? 'Disconnect practice phone' : 'Pair practice phone';
    el('memory-summary').textContent = state.memory || 'Nothing remembered yet.';
  }
  function trace(access, finished=false) {
    const equipped = state.equipped.has(state.skill);
    const items = [
      ['Request',state.name+' received the mission','done'],
      ['Skill',skill().title,equipped?'done':'blocked'],
      ['Access',access,access.includes('blocked')?'blocked':equipped?'done':'waiting'],
      ['Result',finished?'Ready to inspect':'Waiting',finished?'done':'waiting'],
    ];
    el('trace').innerHTML = items.map(([title,detail,status]) => `<div data-state="${status}"><strong>${title}</strong>${escape(detail)}</div>`).join('');
  }
  function error(text) { el('error').textContent = text; el('error').hidden = false; }
  function prefix() {
    return {friendly:'Let’s try this together. ',playful:'Tiny mission, useful discovery! ',precise:'Based on the supplied practice data: '}[state.persona];
  }
  function noteMarkup() {
    return state.memory && state.equipped.has('memory') ? `<p class="quiet">Your saved preference: ${escape(state.memory)}</p>` : '';
  }
  function finish(request) {
    state.pending = null;
    el('permission').hidden = true;
    if (request.skill === 'weather') {
      const data = weather[request.city];
      el('result').innerHTML = `<span class="pill">Fictional forecast · practice only</span><h3 style="margin-top:12px">${escape(request.city)} · ${data.temperature} °C · ${data.condition}</h3><p class="pg-answer">${escape(prefix()+data.suggestion)}</p>${noteMarkup()}<details><summary>Inspect the tool result</summary><p>Prepared fixture: city, temperature and condition. No weather service was contacted.</p></details>`;
    } else if (request.skill === 'search') {
      const cards = examples[request.query];
      el('result').innerHTML = `<span class="pill">Prepared search examples · not live results</span><p class="pg-answer">${escape(prefix())}${request.query==='workshop'?'Try personalization, evidence checking and phone messaging as three short missions.':'Prepare fallback outputs, check station capacity and align attendee copy.'}</p>${noteMarkup()}<div class="pg-evidence">${cards.map((card,i)=>`<article><strong>${i+1}. ${card.title}</strong><p class="quiet">${card.kind}</p><details><summary>Inspect example evidence</summary><p>${card.excerpt}</p></details></article>`).join('')}</div>`;
    } else if (request.skill === 'telegram') {
      el('result').innerHTML = `<span class="pill">Phone preview · not delivered</span><div class="pg-chat"><div class="pg-bubble incoming"><span class="quiet">Practice phone → ${escape(state.name)}</span><p>${escape(request.message)}</p></div><div class="pg-bubble"><span class="quiet">${escape(state.name)} → practice phone</span><p>${escape(request.reply)}</p></div></div><p class="quiet">No Telegram account is connected and no message was sent.</p>`;
    } else {
      state.memory = request.note;
      el('result').innerHTML = `<span class="pill">Saved in this session</span><p class="pg-answer">${escape(state.memory)}</p><p>Try Weather lookout or ask your practice phone what I remember.</p>`;
      render();
    }
    trace(request.skill==='memory'?'Browser session only':'Allowed in simulation',true);
  }
  function makeRequest() {
    const request = {skill:state.skill, city:el('city').value, query:el('query').value, note:el('note').value.trim()};
    if (state.skill === 'telegram') {
      const selected = el('message').value;
      request.message = el('message').selectedOptions[0].text;
      let reply;
      if (selected === 'intro') reply = `I’m ${state.name}. My equipped skills are: ${skills.filter(s=>state.equipped.has(s.id)).map(s=>s.title).join(', ')}.`;
      else if (selected === 'plan') reply = state.brief ? `The shared brief is for BaC ${state.brief.location}, ${state.brief.region}: ${state.brief.attendees} attendees, ${state.brief.duration} minutes, in ${state.brief.language}. Each group has up to ${state.brief.groupSize} people for a ${state.brief.session}-minute session. The crew view shows the current planning stage.` : 'There is no BaC brief yet. Open Plan a BaC to start one; I can use it here afterwards.';
      else reply = !state.equipped.has('memory') ? 'Equip Remember me to access session notes.' : state.memory ? `You told me: ${state.memory}` : 'I do not have a note yet. Try Remember me first.';
      request.reply = prefix() + reply;
    }
    return request;
  }
  function run() {
    invalidate();
    if (!state.name.trim()) { error('Give your agent a name first.'); return; }
    if (!state.equipped.has(state.skill)) {
      trace('Not checked');
      error('Equip ' + skill().title + ' in your agent passport, then try again.');
      return;
    }
    if (state.skill === 'telegram' && !state.paired) { trace('Pairing required'); error('Pair the practice phone before previewing a reply.'); return; }
    const request = makeRequest();
    if (state.skill === 'memory' && !request.note) { error('Write a short preference to remember.'); return; }
    if (state.skill === 'telegram' || (['weather','search'].includes(state.skill) && el('block').checked)) {
      state.pending = request;
      trace('Connection blocked');
      el('permission-text').textContent = state.skill === 'telegram' ? 'The reply is prepared. Previewing delivery to the practice phone needs a simulated access decision.' : 'The skill is equipped, but this practice connection is blocked. Allow one attempt or keep it blocked.';
      el('permission').hidden = false;
      el('result').innerHTML = state.skill === 'telegram' ? `<strong>Prepared reply</strong><p class="pg-answer">${escape(request.reply)}</p><p class="quiet">Destination: practice phone · no real delivery</p>` : '<p>The request stopped before a tool result was available.</p>';
      return;
    }
    finish(request);
  }
  root.addEventListener('click', event => {
    const mission = event.target.closest('[data-mission]');
    if (mission) { state.skill=mission.dataset.mission; invalidate(); render(); }
  });
  el('loadout').addEventListener('change', event => {
    const id = event.target.dataset.equip;
    if (!id) return;
    if (event.target.checked) state.equipped.add(id); else state.equipped.delete(id);
    invalidate(); render();
  });
  for (const id of ['city','query','message','block','note']) el(id).addEventListener('input', invalidate);
  el('name').addEventListener('input', () => { state.name=el('name').value.trim(); invalidate(); render(); });
  el('persona').addEventListener('change', () => { state.persona=el('persona').value; invalidate(); render(); });
  el('pair').addEventListener('click', () => { state.paired=!state.paired; invalidate(); render(); });
  el('run').addEventListener('click', run);
  el('allow').addEventListener('click', () => { if (state.pending) finish(state.pending); });
  el('deny').addEventListener('click', () => {
    if (!state.pending) return;
    state.pending=null; el('permission').hidden=true; trace('Connection blocked');
    el('result').innerHTML='<strong>Kept blocked</strong><p>The skill stays equipped. No tool ran and nothing was delivered. Change the access choice and try again.</p>';
  });
  el('forget').addEventListener('click', () => { state.memory=''; invalidate(); render(); el('result').textContent='Session note cleared.'; });
  el('join').addEventListener('click', () => {
    if (!state.name.trim()) { error('Give your agent a name before joining the crew.'); return; }
    app.dispatchEvent(new CustomEvent('bac:join-request',{detail:{name:state.name,persona:state.persona,extraSkills:skills.filter(s=>state.equipped.has(s.id)).map(s=>s.title)}}));
  });
  app.addEventListener('bac:brief-changed', event => { state.brief={...event.detail}; invalidate(); });
  app.addEventListener('bac:agent-changed', event => {
    state.name=event.detail.name; state.persona=event.detail.persona;
    el('name').value=state.name; el('persona').value=state.persona;
    invalidate(); render();
  });
  render();
})();
