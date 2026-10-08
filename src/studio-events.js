// Event briefs, deterministic planning, and the deliverables handed over by the crew.
let eventCatalog=null,eventPreviewVersion=0,eventPreviewValid=false,eventSubmitting=false,eventPackageKey='',eventPackageTab='plan',eventContribution='all',eventContributionJob='',eventPreviewUrl='',audienceReport=null,audienceJob='';
const eventPackage=document.createElement('section');eventPackage.id='studio-event-package';eventPackage.className='studio-event-package';eventPackage.hidden=true;el('workspace').before(eventPackage);
// Role links lead to each saved contribution, not a section of Morgan's page.
function hasCrewDeliverable(job,role){
 const p=job?.payload;if(!p||p.brief?.schema!==2||!p.outputs?.[role]||role===0)return false;
 if(p.workflow==='showcase')return role===1?!!p.capacity?.topics?.length:role===2?!!p.capacity?.schedule?.length:role===3?!!(p.campaign||p.website?.path):false;
 return role===1||role===2?!!p.capacity:role===3?!!p.campaign:role===4?!!p.survey:role===5?!!p.website:false;
}
function selectEventContribution(role='all'){
 eventContribution=String(role);eventContributionJob=crewMission()?.id||'';
 if(role!=='all')eventPackageTab=({1:'plan',2:'plan',3:'invitations',4:'audience',5:'website'})[role]||'plan';
}
function eventPageDocument(html){
 const doc=new DOMParser().parseFromString(html,'text/html');
 // Older saved packages contain a redundant booth-only summary.
 doc.querySelectorAll('.floor-grid').forEach(grid=>{
  const section=grid.closest('section');
  if(section?.querySelector('h2')?.textContent.trim()==='One theme. One booth.')section.remove();
 });
 return doc;
}
function showcaseDocument(html,authored=false){
 const doc=authored?new DOMParser().parseFromString(html,'text/html'):eventPageDocument(html);
 // Read-only preview. Same-origin lets the parent measure its height; scripts
 // remain forbidden by both the iframe sandbox and this restrictive CSP.
 doc.querySelectorAll('script,iframe,object,embed,base,form,input,button,textarea,select,link,meta[http-equiv],svg,math').forEach(node=>node.remove());
 doc.querySelectorAll('style').forEach(node=>{if(/@import|url\s*\(/i.test(node.textContent))node.remove();});
 for(const node of doc.querySelectorAll('*')){
  for(const attr of [...node.attributes])if(/^on/i.test(attr.name)||['srcdoc','src','srcset','action','formaction','autofocus','contenteditable'].includes(attr.name))node.removeAttribute(attr.name);
  if(/@import|url\s*\(/i.test(node.getAttribute('style')||''))node.removeAttribute('style');
  if(node.hasAttribute('href')){
   const href=node.getAttribute('href');
   if(!href.startsWith('#')&&!/^https?:\/\//i.test(href))node.removeAttribute('href');
   else if(!href.startsWith('#')){node.setAttribute('target','_blank');node.setAttribute('rel','noopener noreferrer');}
  }
 }
 const csp=doc.createElement('meta');csp.httpEquiv='Content-Security-Policy';csp.content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'";doc.head.prepend(csp);
 const style=doc.createElement('style');style.textContent='html,body{height:auto!important;min-height:0!important;overflow:visible!important;scroll-behavior:auto!important}body{display:flow-root}html{overflow:hidden!important}.scroll{max-height:none!important}';doc.head.append(style);
 return '<!doctype html>'+doc.documentElement.outerHTML;
}
function scrollResultTo(target,behavior='smooth'){
 if(activeSurface!=='deliverables'||!target)return;
 const body=el('surface-body'),nav=eventPackage.querySelector('.event-package-tabs');
 const top=target===eventPackage?0:body.scrollTop+target.getBoundingClientRect().top-body.getBoundingClientRect().top-(nav?.getBoundingClientRect().height||0)-parseFloat(getComputedStyle(body).paddingTop)-20;
 body.scrollTo({top,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':behavior});
}
let pendingPreviewScroll='';
function navigateShowcaseContribution(behavior='smooth'){
 if(crewMission()?.payload.workflow!=='showcase')return;
 eventPackage.querySelectorAll('[data-contribution]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.contribution===eventContribution)));
 pendingPreviewScroll='';
 const frame=eventPackage.querySelector('.event-showcase-preview');
 if(eventContribution==='3'&&frame&&frame.dataset.sized!=='true'){pendingPreviewScroll='3';return;}
 scrollResultTo(eventContribution==='all'?eventPackage:eventPackage.querySelector('#bac-result-'+eventContribution),behavior);
}
let previewCleanup=()=>{};
function mountResultPreview(frame,html,authored){
 eventPreviewUrl=URL.createObjectURL(new Blob([showcaseDocument(html,authored)],{type:'text/html'}));
 frame.onload=()=>{
  const doc=frame.contentDocument;if(!frame.isConnected||!doc?.body)return;
  const resize=()=>{
   if(!frame.isConnected||!frame.offsetWidth)return;
   const height=Math.ceil(doc.body.getBoundingClientRect().height);if(height<=0)return;
   if(Math.abs(frame.clientHeight-height)>1)frame.style.height=height+'px';
   frame.dataset.sized='true';
   if(pendingPreviewScroll&&pendingPreviewScroll===eventContribution)navigateShowcaseContribution('instant');
  };
  const observer=new ResizeObserver(resize);observer.observe(doc.body);resize();
  // In-page links also scroll the outer Results panel, never a second viewport.
  const click=e=>{const link=e.target.closest('a[href^="#"]');if(!link)return;e.preventDefault();let id;try{id=decodeURIComponent(link.getAttribute('href').slice(1));}catch{return;}const target=doc.getElementById(id);if(target){const body=el('surface-body'),nav=eventPackage.querySelector('.event-package-tabs');body.scrollTo({top:body.scrollTop+frame.getBoundingClientRect().top+target.getBoundingClientRect().top-body.getBoundingClientRect().top-(nav?.getBoundingClientRect().height||0)-parseFloat(getComputedStyle(body).paddingTop)-20,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}};
  doc.addEventListener('click',click);previewCleanup=()=>{observer.disconnect();doc.removeEventListener('click',click);};
  frame.dataset.ready='true';
 };
 frame.src=eventPreviewUrl;
}
async function downloadPackageFile(path){try{const file=await api('file?path='+encodeURIComponent(path)+'&job='+encodeURIComponent(crewMission().id));if(!(data.jobs||[]).some(j=>j.payload.website?.authored&&j.payload.website.path===path)&&path.endsWith('event-page.html')&&typeof file.content==='string'&&file.encoding!=='base64')file.content='<!doctype html>'+eventPageDocument(file.content).documentElement.outerHTML;downloadBytes(file.encoding==='base64'?Uint8Array.from(atob(file.content),c=>c.charCodeAt(0)):file.content,file.mime||'text/plain',path.split('/').pop());}catch(error){alert(error.message);}}
function eventBrief(form){
 const values=new FormData(form),brief={schema:2,region:'',language:'English'};
 for(const key of ['city','startTime','teardownTime','venue','startDate','endDate'])brief[key]=values.get(key);
 for(const key of ['attendees','duration','days','groupSize','session','themeCount'])brief[key]=Number(values.get(key));
 return brief;
}
function presenterTimetable(b,c){
 const start=b.startTime.split(':').reduce((v,n)=>v*60+Number(n),0),times=[];
 for(let t=start;t+c.session<=start+b.duration;t+=c.session)times.push(String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0'));
 const visits=new Map(c.schedule.map(r=>[[r.day,r.booth,r.start].join(':'),r]));
 return Array.from({length:b.days},(_,d)=>`<h4>Day ${d+1}</h4><div class="event-table-wrap"><table class="event-rota-grid"><thead><tr><th>Booth / local time</th>${times.map(t=>'<th>'+t+'</th>').join('')}</tr></thead><tbody>${c.booths.map((booth,i)=>`<tr style="--rota-color:${['#263c20','#203747','#433b20','#402c37','#322c43','#203c37'][i%6]}"><th>${escape(booth.booth)}<small>${escape(booth.topic)}</small></th>${times.map(t=>{const r=visits.get([d+1,booth.booth,t].join(':'));return '<td'+(r?' class="is-assigned"':'')+'>'+(r?escape(r.presenter):'—')+'</td>';}).join('')}</tr>`).join('')}</tbody></table></div>`).join('')+'<p class="event-note">Presenter numbers are unassigned staffing slots. Blank slots have no scheduled visit.</p>';
}
let demoPreparationId=null,demoPreparing=false,demoPreparationError='',demoAutoPrepare=false;
const crewWarmups=new Map();
let crewStartupReady=false;
function warmCrewOnOpen(){
 if(!crewStartupReady||!connected||!agentId||changingAgent||removingAgent||!runtime.gateway||data.deleting||data.bacResetting)return;
 const key=runtime.instance+':'+(data.crewOwner||agentId),now=Date.now();
 if((crewWarmups.get(key)||0)>now)return;
 const target=agentId;crewWarmups.set(key,Infinity);
 api('prepare-demo',{background:true},target).catch(()=>{
  // A policy edit or current mission can briefly hold the preparation fence.
  // The server deduplicates attempts, including terminal preparation failures.
  crewWarmups.set(key,Date.now()+30000);
 });
}
const excludedDemoGuests=new Set();
function demoGuestChoices(){
 const skipped=new Map((matchingPreparation()?.payload.roundtable?.skipped||[]).map(m=>[m.key,m.detail]));
 return (data.agents||[]).map(a=>({key:a.key,name:a.name,reason:a.deleting?'Unavailable':a.activity?'Busy with another task.':skipped.get(a.key)||''}));
}
function selectedDemoRoles(){return [...(el('crew-form')?.querySelectorAll('[name=crewRole]:checked')||[])].map(input=>Number(input.value));}
function eventTeamWorking(kinds=['crew','crew-chat']){
 return selectedScenario==='event-brief'&&[...(data.jobs||[]),...(data.crewChats||[])].some(j=>kinds.includes(j.kind)&&['queued','running','waiting','stopping'].includes(j.status));
}
function matchingPreparation(){
 const prep=data.preparation;
 return prep?.id===demoPreparationId&&prep.valid!==false&&selectedDemoRoles().every(role=>prep.payload.enabledRoles.includes(role))?prep:null;
}
function syncDemoPreparation(){
 const box=el('demo-preparation');if(!box||!el('dialog').open)return;
 const prep=matchingPreparation(),status=prep?.status|| (demoPreparing?'queued':'idle');
 const error=demoPreparationError||prep?.result?.error||(status==='cancelled'?'Preparation stopped. Check again when ready.':'');
 const preparing=demoPreparing||['queued','running'].includes(status);
 const guests=demoGuestChoices();
 box.innerHTML='<div class="demo-ready-heading"><b>BaC crew</b><span>'+escape(error?'Needs attention':status==='done'?'Ready':status==='idle'?'Not checked':status==='queued'?'Queued':'Preparing')+'</span></div>'+(error?'<p class="event-plan-error" role="alert">'+escape(error)+'</p>':'')+(prep?.payload.checks||[]).filter(c=>c.required).map(c=>'<div class="demo-ready-row" data-status="'+escape(c.status)+'"><span>'+escape(c.name)+'</span><small>'+escape(c.detail||(c.status==='ready'?'Ready':c.status==='preparing'?'Preparing':'Needs attention'))+'</small></div>').join('')+'<button type="button" class="studio-secondary" id="studio-prepare-demo" '+(!runtime.gateway||preparing||eventTeamWorking()||data.bacResetting?'disabled':'')+'>'+(preparing?'Preparing…':status==='done'?'Check again':error?'Retry preparation':'Prepare demo')+'</button>'+(guests.length?'<div class="demo-guests"><b>Personal reactions · optional</b><div class="demo-guest-list">'+guests.map(g=>'<label class="demo-guest" data-available="'+String(!g.reason)+'"><input type="checkbox" data-demo-guest="'+escape(g.key)+'" '+(!g.reason&&!excludedDemoGuests.has(g.key)?'checked ':'')+(g.reason?'disabled ':'')+'><span>'+escape(g.name)+'</span>'+(g.reason?'<small>'+escape(g.reason)+'</small>':'')+'</label>').join('')+'</div></div>':'');
 box.querySelectorAll('[data-demo-guest]').forEach(input=>input.onchange=()=>{if(input.checked)excludedDemoGuests.delete(input.dataset.demoGuest);else excludedDemoGuests.add(input.dataset.demoGuest);});
 el('prepare-demo').onclick=prepareDemo;
 syncEventLaunch();
 if(demoAutoPrepare&&runtime.gateway&&!demoPreparing){demoAutoPrepare=false;queueMicrotask(prepareDemo);}
}
async function prepareDemo(){
 if(demoPreparing||eventTeamWorking()||!el('demo-preparation')||!el('dialog').open||!runtime.gateway||data.bacResetting)return;
 const form=el('crew-form');demoAutoPrepare=false;demoPreparing=true;demoPreparationError='';demoPreparationId=null;syncDemoPreparation();
 try{const prepared=await api('prepare-demo',{enabledRoles:selectedDemoRoles()});if(el('crew-form')!==form)return;demoPreparationId=prepared.id;await refresh();}
 catch(error){if(el('crew-form')===form)demoPreparationError=error.message;}
 finally{demoPreparing=false;if(el('crew-form')===form)syncDemoPreparation();}
}
function syncEventLaunch(){
 const form=el('crew-form'),button=el('launch-event');if(!form||!button)return;
 const preparation=matchingPreparation(),preparing=demoPreparing||['queued','running'].includes(preparation?.status);
 const prepared=preparation?.status==='done'&&!demoPreparationError;
 button.disabled=!teamReady()||eventSubmitting||eventTeamWorking()||!!data.bacResetting||!eventPreviewValid||!prepared||!form.querySelector('[name=crewRole]:checked');
 button.textContent=!runtime.gateway?gatewayLabel():!teamRuntime().teamModel?'Model not connected':eventSubmitting?'Assigning your brief…':preparing?'Preparing…':!prepared?'Prepare demo':'Start the event plan';
 const note=el('event-connection');if(note){note.hidden=!!teamReady();note.textContent=runtime.gateway?'Model not connected. Enable Local or External Endpoint in Settings.':gatewayState()==='slow'?'Waiting for the agent runtime. Checking automatically.':'Agent runtime unavailable. Use Retry connection in the status indicator.';}
}
async function updateEventPreview(){
 const form=el('crew-form');if(!form)return;const version=++eventPreviewVersion;eventPreviewValid=false;syncEventLaunch();
 try{
  const {brief:b,capacity:c}=await api('event-plan',{brief:eventBrief(form)});
  if(version!==eventPreviewVersion||el('crew-form')!==form)return;
  el('event-preview').innerHTML=`<div class="event-preview-head"><b>Your booth plan</b><span>Calculated from this brief</span></div><p class="event-note">${escape(b.startTime)}-${escape(b.endTime)} local time${b.teardownTime?` · Take down by ${escape(b.teardownTime)}`:''}</p><div class="event-metrics"><div><strong>${c.boothCount} / ${b.boothLimit}</strong><span>demo booths</span></div><div><strong>${c.session} min</strong><span>per group</span></div><div><strong>${c.presenterCount}</strong><span>presenters / day</span></div><div><strong>${c.staff}</strong><span>total staff / day</span></div></div>${c.adjusted?`<p class="event-adjustment">The crew will use ${c.session}-minute visits instead of ${b.session} minutes to stay within ${b.boothLimit} booths.</p>`:''}<div class="event-topic-summary">${c.topics.map(t=>`<span><b>${escape(t.topic)}</b>${t.attendees} attendees · ${t.groups} visits · ${t.presenters} presenter${t.presenters===1?'':'s'}</span>`).join('')}</div><small>One interest-based demo per attendee across the event. Equal topic split. Includes ${c.floorHosts} floor host${c.floorHosts===1?'':'s'} and 1 lead. Presenters are sized to the visit load. Normally 45 minutes presenting, then at least 15 minutes of rest. Unused time is marked No visit. Names are unassigned.</small>`;
  eventPreviewValid=true;syncEventLaunch();
 }catch(error){if(version===eventPreviewVersion&&el('event-preview'))el('event-preview').innerHTML='<p class="event-plan-error">'+escape(error.message)+'</p>';}
}
async function crewForm(){
 if(selectedScenario!=='event-brief')return;const scenarioAtOpen=selectedScenario;
 try{eventCatalog=eventCatalog||await api('event-catalog');}catch(error){alert(error.message);return;}
 if(selectedScenario!==scenarioAtOpen)return;
 dialog('Event Brief',`<label class="event-template-picker">Template<select id="studio-event-template">${eventCatalog.templates.map(t=>`<option value="${t.id}">${escape(t.title)} (Template)</option>`).join('')}</select></label><form id="studio-crew-form"><div class="studio-form-grid"><label>City<input name="city" maxlength="80" required></label><label>Event date · start<input type="date" name="startDate"></label><label>Event date · end<input type="date" name="endDate"></label><label>Venue<input name="venue" maxlength="120" placeholder="To be confirmed"></label><label>Total attendees<input type="number" name="attendees" min="1" max="3000" step="1" required></label><label>Event duration · minutes per day<input type="number" name="duration" min="30" max="720" step="30" required></label><label>Event days<input type="number" name="days" min="1" max="5" required></label><label>People per group<input type="number" name="groupSize" value="5" min="1" max="30" required></label><label>Preferred demo length · minutes<input type="number" name="session" value="15" min="5" max="60" step="5" required></label><label>Themes (one booth each)<select name="themeCount"><option value="2">2 themes</option><option value="3">3 themes</option><option value="4">4 themes</option><option value="5">5 themes</option><option value="6">6 themes</option></select></label><div class="event-time-field"><span id="studio-event-time-label">Daily start · local time</span><div class="event-start-time" role="group" aria-labelledby="studio-event-time-label"><select name="startHour" aria-label="Start hour (24-hour)">${Array.from({length:24},(_,i)=>`<option value="${String(i).padStart(2,'0')}">${String(i).padStart(2,'0')}</option>`).join('')}</select><span aria-hidden="true">:</span><select name="startMinute" aria-label="Start minute"><option value="00">00</option><option value="30">30</option></select></div><input type="hidden" name="startTime" value="10:00"></div><label>Take down by · local time (optional)<input type="time" name="teardownTime"></label></div><div id="studio-event-preview" class="event-plan-preview" aria-live="polite"></div>${crewAssignments()}<section id="studio-demo-preparation" class="demo-preparation" aria-live="polite"></section><p id="studio-event-connection" class="event-note" role="status" hidden></p><div class="studio-dialog-actions"><button id="studio-launch-event" type="submit" class="studio-primary" disabled>Give the brief to my crew</button></div></form>`);
 const form=el('crew-form');eventSubmitting=false;eventPreviewValid=false;syncEventLaunch();
 function syncDates(){
  const start=form.elements.startDate,end=form.elements.endDate,days=form.elements.days;
  end.min=start.value;end.setCustomValidity('');
  days.readOnly=!!start.value;
  if(start.value){
   const count=end.value?Math.round((Date.parse(end.value)-Date.parse(start.value))/86400000)+1:1;
   if(count>=1&&count<=5)days.value=count;
   else end.setCustomValidity('Choose an end date within 1 to 5 event days.');
  }else if(end.value)end.setCustomValidity('Choose a start date first.');
 }
 function applyTemplate(id){
  const template=eventCatalog.templates.find(t=>t.id===id);if(!template)return;
  el('event-template').value=id;
  for(const k of ['city','attendees','duration','days','venue','startDate','endDate','teardownTime'])form.elements[k].value=template[k]??'';
  const startTime=template.startTime||'10:00';
  for(const [key,value] of Object.entries({groupSize:template.groupSize??5,session:15,themeCount:template.topics.length,startTime,startHour:startTime.slice(0,2),startMinute:startTime.slice(3)}))form.elements[key].value=value;
  syncDates();updateEventPreview();
 }
 el('event-template').onchange=e=>applyTemplate(e.target.value);
 form.addEventListener('input',e=>{
  if(e.target.name==='crewRole'){updateCrewSelection();return;}
  if(['startDate','endDate'].includes(e.target.name))syncDates();
  if(['startHour','startMinute'].includes(e.target.name))form.elements.startTime.value=form.elements.startHour.value+':'+form.elements.startMinute.value;
  updateEventPreview();
 });
 function updateCrewSelection(){const count=form.querySelectorAll('[name=crewRole]:checked').length;el('crew-selection-note').textContent=count+' selected';demoPreparationError='';syncDemoPreparation();}
 form.onsubmit=async event=>{event.preventDefault();syncEventLaunch();if(el('launch-event').disabled)return;eventSubmitting=true;syncEventLaunch();const enabledRoles=selectedDemoRoles();try{const job=await api('jobs',{kind:'crew',workflow:'showcase',executionMode:'agent-led-v1',brief:eventBrief(form),enabledRoles,preparationId:demoPreparationId,guestKeys:demoGuestChoices().filter(g=>!g.reason&&!excludedDemoGuests.has(g.key)).map(g=>g.key),preset:true});selectedJob=job.id;selectedCrewRole=0;eventPackageTab='plan';el('dialog').close();await refresh();showBoard(false);}catch(error){demoPreparationError=error.message;syncDemoPreparation();}finally{eventSubmitting=false;syncEventLaunch();}};
 applyTemplate('zurich');
 const previous=data.preparation;
 demoPreparationId=previous?.valid&&(previous.payload.background||['queued','running','error','cancelled'].includes(previous.status))&&selectedDemoRoles().every(r=>previous.payload.enabledRoles.includes(r))?previous.id:null;
 demoPreparationError='';demoAutoPrepare=!demoPreparationId;syncDemoPreparation();
}
function renderEventPackage(force=false){
 const job=crewMission();eventPackage.hidden=room!=='mission'||job?.payload.brief?.schema!==2;if(eventPackage.hidden)return;
 if(eventContributionJob!==job.id)selectEventContribution();
 const p=job.payload,b=p.brief,c=p.capacity;
 const key=JSON.stringify(p.workflow==='showcase'?[job.id,b,c,p.outputs,p.website,p.campaign,p.packageFiles,p.pageDraft?.status,p.schedulePlan]:[job.id,job.status,job.updated,job.events.length,p.roundtable,eventPackageTab,eventContribution,audienceJob,audienceReport]);
 if(key===eventPackageKey&&!force){if(p.workflow==='showcase')updateResultReactions(job);return;}eventPackageKey=key;
 eventPackage.classList.toggle('is-showcase',p.workflow==='showcase');
 if(p.workflow==='showcase'){renderShowcasePackage(job);return;}
 const included=i=>!p.enabledRoles||p.enabledRoles.includes(i);
 const tabs=[['plan','Booth plan & rota',1],['invitations','Venue & invitations',3],['audience','Audience feedback',4],['website','Event page',5]].filter(([id,title,i])=>id==='plan'?(included(1)||included(2)):included(i));
 if(!tabs.some(t=>t[0]===eventPackageTab))eventPackageTab=tabs[0]?.[0]||'brief';
 const roleName=i=>p.roster?.[i]?.name||defaultNames[i];
 const files=p.packageFiles||[],file=suffix=>files.find(f=>f.endsWith(suffix));
 const download=(suffix,label)=>file(suffix)?`<button class="studio-secondary" data-package-download="${file(suffix)}">${label} ↓</button>`:'';
 let body=eventPackageTab==='brief'?'<div class="event-empty"><b>Event brief</b><p>'+escape(p.outputs?.['0']||'The selected crew is preparing your brief.')+'</p></div>':'';
 if(eventPackageTab==='plan')body=`<div class="event-metrics"><div><strong>${b.attendees}</strong><span>total attendees</span></div><div><strong>${c.boothCount} / ${b.boothLimit}</strong><span>booths</span></div><div><strong>${c.session} min</strong><span>per group</span></div><div><strong>${c.staff}</strong><span>staff / day</span></div></div>${c.adjusted?`<p class="event-adjustment">Visit length adjusted from ${b.session} to ${c.session} minutes to respect the booth limit.</p>`:''}<div class="event-table-wrap"><table><thead><tr><th>Booth</th><th>Topic</th><th>Demo concept</th><th>Presenter slot</th></tr></thead><tbody>${c.booths.map(r=>`<tr><td>${r.booth}</td><td>${escape(r.topic)}</td><td>${escape(r.demo)}</td><td>${escape(r.presenter)}${r.presenterExpertise?'<small class="event-expertise">'+escape(r.presenterExpertise)+'</small>':''}</td></tr>`).join('')}</tbody></table></div><div class="event-actions">${download('-presenter-rota.xlsx','Download Excel')}${!included(2)?'<span>Operations excluded · schedule preview only; no Excel export.</span>':!file('-presenter-rota.xlsx')?'<span>'+escape(roleName(2))+' will hand over the Excel booth timetable after reviewing the plan.</span>':''}</div><details><summary>View booth timetable · ${b.days} day${b.days===1?'':'s'}</summary>${presenterTimetable(b,c)}</details><p class="event-note">${escape(c.demoSource||'Catalog starting concepts; '+roleName(1)+' will refine the demos.')} ${escape(c.assumptions)}</p>`;
 if(eventPackageTab==='invitations')body=p.campaign?`<div class="event-invitation"><div><span class="studio-kicker">${escape(roleName(3))} / INVITATION DRAFT</span><h4>${escape(p.campaign.subject)}</h4><p class="event-mail-body">${escape(p.campaign.body)}</p></div><aside><span class="studio-kicker">HOTEL CANDIDATE</span><h4>${escape(p.campaign.venue.name)}</h4><p>${escape(p.campaign.venue.status)}</p>${p.campaign.venue.url?`<a href="${escape(p.campaign.venue.url)}" target="_blank" rel="noreferrer">Agent-reported source</a>`:'<p>No verified source supplied yet.</p>'}<p>Review the date, recipient, venue and registration link before using this draft.</p><div class="event-actions">${download('-invitation.eml','Save .eml draft')}${download('-invitation.html','Save readable HTML')}</div></aside></div>`:'<div class="event-empty"><b>'+escape(roleName(3))+' is your venue scout and writer.</b><p>The hotel candidate, invitation preview and downloadable email draft will appear after the marketing handoff.</p></div>';
 if(eventPackageTab==='audience'){
  const report=audienceJob===job.id?audienceReport:null;
  body=p.survey?`<div class="event-survey"><div><span class="studio-kicker">${escape(roleName(4))} / AUDIENCE &amp; REVIEW</span><p>${escape(p.survey.authorship)}. Collect interests, experience and usefulness ratings without names or emails.</p><label for="studio-survey-link">Survey link<input id="studio-survey-link" readonly value="${escape(location.origin+p.survey.path)}"></label><div class="event-actions"><a class="studio-primary" href="${escape(p.survey.path)}" target="_blank" rel="noopener">Try the survey</a><button class="studio-secondary" data-survey-action="copy">Copy link</button></div><small>For other devices, open this app through the server’s LAN address before copying the link. The server must stay running.</small></div><div><div class="event-preview-head"><b>${report?report.total+' response'+(report.total===1?'':'s'):'Audience pulse'}</b><button class="studio-secondary" data-survey-action="refresh">Refresh ↻</button></div>${report?report.topics.map(t=>`<div class="event-vote"><span>${escape(t.title)}</span><b>${t.count}</b><i style="--vote:${report.total?100*t.count/report.total:0}%"></i></div>`).join(''):'<p>Open the survey and submit feedback, then refresh the results here.</p>'}<p>${report?.rating!=null?'Usefulness: '+report.rating+' / 5. ':''}Small samples are directional. Replanning preserves the original package and uses these interests to split the same total attendance.</p><button class="studio-primary" data-survey-action="replan" ${!report?.total||job.status!=='done'?'disabled':''}>Give these interests to the crew</button></div></div>`:'<div class="event-empty"><b>'+escape(roleName(4))+' will prepare your audience survey.</b></div>';
 }
 if(eventPackageTab==='website')body=p.website?`<div class="event-invitation"><div><span class="studio-kicker">${escape(p.website.author)} / EVENT PAGE STUDIO</span><h4>${escape(p.website.headline)}</h4><div class="event-actions"><button class="studio-primary" data-studio-file="${escape(p.website.path)}">Open event page</button>${download('-event-page.html','Download HTML')}</div></div></div>`:'<div class="event-empty"><b>No event page yet.</b></div>';
 eventPackage.innerHTML=`<div class="event-package-heading"><div><span class="studio-kicker">${job.status==='done'?'EVENT PACKAGE':'RESULTS SO FAR'}</span><h3>${escape(b.city)} · Event materials</h3><p>${b.days} day${b.days===1?'':'s'} × ${b.duration} min · ${escape(b.language)}</p></div><span class="event-package-harness">Showcasing · ${b.harnesses.map(h=>h==='hermes'?'Hermes':'OpenClaw').join(' + ')}</span></div><nav class="event-package-tabs" aria-label="Event deliverables">${tabs.map(([id,label])=>`<button data-package-tab="${id}" aria-pressed="${eventPackageTab===id}">${label}</button>`).join('')}</nav><div class="event-package-body">${body}</div>`;
}
eventPackage.onclick=async e=>{
 const contribution=e.target.closest('[data-contribution]');if(contribution){selectEventContribution(contribution.dataset.contribution);if(crewMission()?.payload.workflow==='showcase')navigateShowcaseContribution();else renderEventPackage();return;}
 const tab=e.target.closest('[data-package-tab]');if(tab){eventPackageTab=tab.dataset.packageTab;renderEventPackage();return;}
 const json=e.target.closest('[data-result-json]');if(json){openResultJson(json.dataset.resultJson,json.dataset.resultTitle,crewMission().id);return;}
 const download=e.target.closest('[data-package-download]');if(download){downloadPackageFile(download.dataset.packageDownload);return;}
 const action=e.target.closest('[data-survey-action]');if(!action)return;const job=crewMission();
 try{
  if(action.dataset.surveyAction==='copy'){try{await navigator.clipboard.writeText(el('survey-link').value);alert('Survey link copied.');}catch{el('survey-link').focus();el('survey-link').select();alert('Select and copy the survey link.');}return;}
  action.disabled=true;
  if(action.dataset.surveyAction==='refresh'){audienceReport=await api('survey-report?id='+encodeURIComponent(job.id));audienceJob=job.id;renderEventPackage();}
  if(action.dataset.surveyAction==='replan'){const next=await api('survey-replan',{id:job.id});selectedJob=next.id;eventPackageTab='plan';await refresh();alert('A new crew mission is using the audience interests. Your original package is preserved.');}
 }catch(error){alert(error.message);}finally{action.disabled=false;}
};

function resultDownloads(p,items){
 return items.map(([suffix,label])=>{const path=(p.packageFiles||[]).find(f=>f.endsWith(suffix));return path?`<button class="studio-secondary" data-package-download="${escape(path)}">${label}</button>`:'';}).join('');
}
function resultJsonActions(p,items){
 return items.map(([suffix,label,title])=>{const path=(p.packageFiles||[]).find(f=>f.endsWith(suffix));return path?`<button class="studio-secondary" data-result-json="${escape(path)}" data-result-title="${escape(title)}">${escape(label)}</button>`:'';}).join('');
}
function resultSection(id,title,credit,actions,body){
 return `<section class="result-section" id="bac-result-${id}"><header class="result-section-heading"><div><h4>${escape(title)}</h4>${credit?'<p>'+escape(credit)+'</p>':''}</div><div class="result-downloads">${actions}</div></header>${body}</section>`;
}
function resultThemes(p){
 const sources=p.research?.sources||[],raw=p.agentResults?.['1']?.demos?.demos||[];
 return '<div class="result-themes">'+p.capacity.topics.map((topic,i)=>{
  const original=raw.find(t=>t.topic===topic.id),t=original?{...topic,...original,topic:original.theme,demo:original.title}:topic;
  const source=sources.find(s=>s.id===original?.sourceId),url=source?.url||t.source;
  const details=[['Why this demo',t.why],['Success check',t.proof],['Demo boundary',t.risk],['Presenter expertise',t.presenterExpertise]].filter(([,v])=>v);
  return `<article class="result-theme"><div class="result-theme-label"><span>Booth-${i+1}</span><span>${escape(t.topic)}</span></div><h5>${escape(t.demo)}</h5><dl>${[['Activity',t.action],['Outcome',t.outcome]].filter(([,v])=>v).map(([k,v])=>'<dt>'+k+'</dt><dd>'+escape(v)+'</dd>').join('')}</dl>${url&&/^https:\/\//i.test(url)?'<a class="result-source" href="'+escape(url)+'" target="_blank" rel="noopener noreferrer">'+escape((source?.id?source.id+' · ':'')+(source?.title||t.sourceTitle||'Research source'))+'</a>':''}${details.length?'<details class="result-details"><summary>Research & demo details</summary>'+details.map(([k,v])=>'<p><b>'+k+'</b>'+escape(v)+'</p>').join('')+'</details>':''}</article>`;
 }).join('')+'</div>';
}
function resultScheduleMarkup(html){
 // Schedule fragments contain only app-rendered tables and escaped agent text.
 // Use a small allowlist before inserting old or new fragments into the UI.
 const doc=new DOMParser().parseFromString(html,'text/html');
 const allowed=new Set('SECTION H2 H3 P DIV SPAN DETAILS SUMMARY TABLE THEAD TBODY TR TH TD B STRONG SMALL BR'.split(' '));
 for(const node of [...doc.body.querySelectorAll('*')]){
  if(!allowed.has(node.tagName)){node.remove();continue;}
  for(const attr of [...node.attributes])if(!['class','open','style'].includes(attr.name))node.removeAttribute(attr.name);
  const color=node.style.getPropertyValue('--person').trim();node.removeAttribute('style');if(/^#[0-9a-f]{6}$/i.test(color))node.style.setProperty('--person',color);
 }
 const section=doc.body.querySelector('section');
 if(section){section.querySelector(':scope > h2')?.remove();section.querySelector(':scope > p')?.remove();}
 return (section||doc.body).innerHTML;
}
function updateResultReactions(job){
 const target=eventPackage.querySelector('.result-reactions');if(!target)return;
 const key=JSON.stringify(job.payload.roundtable);if(target.dataset.key===key)return;
 target.dataset.key=key;target.innerHTML=roundtableMarkup(job);
}
async function renderShowcasePackage(job){
 const p=job.payload,key=eventPackageKey,view=eventContribution,name=role=>p.roster?.[role]?.name||defaultNames[role];
 const available=[1,2,3].filter(role=>hasCrewDeliverable(job,role)),postLabel=p.brief.themeCount?'LinkedIn post':'Invitation';
 const links=[[1,name(1)+' · Themes & demos'],[2,name(2)+' · Presenter timetable'],['webpage',name(3)+' · Webpage'],[3,name(3)+' · '+postLabel]].filter(([id])=>id==='webpage'?!!p.website?.path:available.includes(id));
 const scroll=el('surface-body').scrollTop,sameJob=eventPackage.dataset.job===job.id;eventPackage.dataset.job=job.id;
 previewCleanup();previewCleanup=()=>{};
 if(eventPreviewUrl){URL.revokeObjectURL(eventPreviewUrl);eventPreviewUrl='';}
 eventPackage.classList.add('is-showcase');
 let sections='';
 if(available.includes(1))sections+=resultSection('1',name(1)+' · Themes & demos','Research & demo concepts: '+name(1)+' · Layout: app',resultJsonActions(p,[['-themes.json','View proposal',name(1)+' · Proposal'],['-theme-research.json','View sources',name(1)+' · Sources']]),resultThemes(p));
 if(available.includes(2)){
  const notes=p.decisionNotes||{},criteria=p.schedulePlan?.criteria||[];
  const decisions=criteria.length||notes.summary?'<details class="result-details result-schedule-decisions"><summary>Scheduling decisions</summary>'+(criteria.length?'<ul>'+criteria.map(c=>'<li>'+escape(c)+'</li>').join('')+'</ul>':'<p>'+escape(notes.summary)+'</p>')+(notes.tradeoff?'<p><b>Tradeoff</b>'+escape(notes.tradeoff)+'</p>':'')+(notes.check?'<p><b>Before opening</b>'+escape(notes.check)+'</p>':'')+'</details>':'';
  sections+=resultSection('2',name(2)+' · Presenter timetable',p.executionMode?(p.capacity?.staffingPolicy==='tool-calculated'?'Schedule: tool · Review & export: '+name(2):'Slots & rotations: '+name(2)+' · Table & Excel: app'):'Schedule: app · Operations review: '+name(2),resultJsonActions(p,[['-schedule-plan.json','View plan',name(2)+' · Schedule plan']])+resultDownloads(p,[['-presenter-rota.xlsx','Download Excel']]),decisions+'<div class="result-schedule">'+(p.scheduleFragment?resultScheduleMarkup(p.scheduleFragment):presenterTimetable(p.brief,p.capacity))+'</div>');
 }
 if(p.website?.path)sections+=resultSection('webpage',name(3)+' · Webpage',p.website.authored?'HTML & copy: '+name(3)+' · App supplies the starter and inserts the timetable':'Page assembled by app from crew contributions',resultDownloads(p,[['-event-page.html','Download HTML']]),'<iframe class="event-showcase-preview" title="Event showcase preview" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" scrolling="no"></iframe>');
 else if(p.enabledRoles?.includes(3))sections+=resultSection('webpage',name(3)+' · Webpage','', '', '<p class="result-pending">'+(p.pageDraft?.status==='failed'?'Webpage could not be completed.':'Waiting for the webpage.')+'</p>');
 if(available.includes(3)&&p.campaign)sections+=resultSection('3',name(3)+' · '+postLabel,'',resultDownloads(p,[['-linkedin-post.txt','Download post'],['-invitation.eml','Download email']]),'<div class="result-post">'+escape(p.campaign.body||'')+'</div>');
 eventPackage.innerHTML=`<div class="event-package-heading"><h3>${escape(p.brief.city)} · Results</h3></div><nav class="event-package-tabs" aria-label="Jump to result section"><button data-contribution="all" aria-pressed="${view==='all'}">All results</button><div class="event-section-shortcuts">${links.map(([id,label])=>`<button data-contribution="${id}" aria-pressed="${view===String(id)}">${escape(label)}</button>`).join('')}</div></nav><div class="result-sections">${sections||'<p class="result-pending">Results will appear as the crew finishes.</p>'}<div class="result-reactions"></div></div>`;
 updateResultReactions(job);
 if(sameJob)el('surface-body').scrollTop=scroll;
 else navigateShowcaseContribution('instant');
 const frame=eventPackage.querySelector('iframe');if(!frame)return;
 try{
  const file=await api('file?path='+encodeURIComponent(p.website.path)+'&job='+encodeURIComponent(job.id));
  if(key!==eventPackageKey||!frame.isConnected)return;
  mountResultPreview(frame,file.content,p.website.authored);
 }catch(error){if(key===eventPackageKey&&frame.isConnected)frame.replaceWith(Object.assign(document.createElement('p'),{textContent:error.message}));}
}
