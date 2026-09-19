// A persistent inspector: selection is independent of the role currently working.
function renderCrewPassport(){
  if(room!=='mission')return;
  const i=selectedCrewRole,crew=crewMission(),member=crew?.payload.roster?.[i];
  const name=member?.name||defaultNames[i],role=roles[i][1],description=roles[i][2];
  const persona=member?.persona||['guide','maker','analyst','guide','analyst'][i];
  const avatar=member?.avatar||window.BacCampus?.inspect().crewAvatars?.[i]||{};
  const output=crew?.payload.outputs?.[i],stage=crew?.payload.stage??-1;
  const done=!!output,working=['running','stopping'].includes(crew?.status)&&stage===i;
  const waiting=crew?.status==='waiting'&&i===2,failed=crew?.status==='error'&&stage===i;
  let status='READY TO COLLABORATE',task=description;
  if(waiting){status='YOUR DECISION IS NEEDED';task='Equipment needs exceed the available devices. Review the capacity plan in Mission control.';}
  else if(done){status='DELIVERED';task=i===4?'The crew review is ready. Open the deliverable below.':'This role’s output is saved and available to the crew.';}
  else if(failed){status='NEEDS ATTENTION';task=crew.result?.error||'This step could not finish. Open Mission control to review recovery options.';}
  else if(working){status=crew.status==='stopping'?'FINISHING THE CURRENT STEP':'WORKING ON THE BRIEF';}
  else if(crew?.status==='cancelled'){status='MISSION CANCELLED';task='This role did not deliver an output before the mission was cancelled.';}
  else if(crew){status='WAITING FOR ITS TURN';task=i?'Waiting for the shared brief and earlier deliverables. '+description:'Waiting for the shared model to start the brief.';}
  el('crew-number').textContent=String(i+1).padStart(2,'0')+' / 05';
  el('crew-name').textContent=name;el('crew-role').textContent=role;
  el('crew-persona').textContent=(personas[persona]||description)+' '+voiceSummary(member||{});
  const portrait=el('crew-portrait');portrait.dataset.body=avatar.body||'classic';portrait.dataset.accessory=avatar.accessory||'antenna';
  const color=appearanceColors[avatar.color]||appearanceColors.green;
  portrait.style.setProperty('--avatar-accent',color);el('crew-passport').style.setProperty('--crew-color',color);
  const skills=(member?.skills||(i===3?['documents','writer','web']:['documents','writer'])).map(s=>titles[s]||s),markup=skills.map(s=>'<span>'+escape(s)+'</span>').join('');
  if(el('crew-skills').innerHTML!==markup)el('crew-skills').innerHTML=markup;
  el('crew-status').textContent=status;el('crew-task').textContent=task;
  el('crew-state').dataset.state=waiting||failed?'attention':done?'done':working?'working':'ready';
  const roleName=index=>crew?.payload.roster?.[index]?.name||defaultNames[index];
  el('crew-from').textContent=i?roleName(i-1)+' · '+roles[i-1][1]:'Your event brief';
  el('crew-to').textContent=i<4?roleName(i+1)+' · '+roles[i+1][1]:'Your reviewed plan';
  el('crew-access').textContent=member?.protection==='openshell'?'OpenShell on · Uses this personal agent’s policy.':'OpenShell off · Ready to collaborate.';
  el('crew-deliverable').hidden=!done;el('crew-output-empty').hidden=done;
  if(el('crew-output').textContent!==(output||''))el('crew-output').textContent=output||'';
  el('crew-output-empty').textContent=crew?'No deliverable from this role yet.':'Give the crew an event brief to see this role in action.';
  el('crew-action').textContent=crew?'Open Mission control ↗':'Launch a crew mission ↗';
}
el('crew-close').onclick=()=>{root.dataset.crewDetails='false';worldViewport.focus({preventScroll:true});};
el('crew-action').onclick=()=>crewMission()?showBoard(true):crewForm();
