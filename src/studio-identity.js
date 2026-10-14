// Inspect saved OpenClaw files. Opening this panel never prepares or edits an agent.
let identityRequest=0;
async function openAgentDocuments(role=null,codeView=false){
 const target=agentId,request=++identityRequest;
 const name=role===null?data.profile?.name:defaultNames[role];
 if(!name||!target)return;
 dialog(codeView?'INSTRUCTIONS':'AGENT FILES','<section id="studio-identity-viewer"><h3>'+escape(name)+'</h3><p role="status">Loading agent files…</p></section>');
 el('dialog').classList.add('studio-agent-documents');
 el('dialog').classList.toggle('studio-agent-code',codeView);
 const host=el('identity-viewer');
 const current=()=>request===identityRequest&&el('dialog').open&&el('identity-viewer')===host&&agentId===target;
 try{
  const result=await api('agent-documents'+(role===null?'':'?role='+role),undefined,target);
  if(!current())return;
  const documents=result.documents||[];
  if(codeView){
   const definitions=[
    {filename:'AGENTS.md',label:'Working instructions'},
    {filename:'IDENTITY.md',label:'Identity'},
    {filename:'SOUL.md',label:'Character and boundaries'}
   ];
   const core=definitions.map(definition=>({...definition,...(documents.find(doc=>doc.group==='agent'&&doc.filename===definition.filename)||{status:'missing'})}));
   host.innerHTML='<div class="studio-identity-heading"><div><h3>'+escape(result.name)+'</h3><p>'+escape(result.description)+'</p></div><span>Read only</span></div><div class="studio-code-layout">'+core.map((doc,index)=>'<article class="studio-code-panel" data-status="'+escape(doc.status)+'"><header><div><small>'+escape(doc.label)+'</small><h4>'+escape(doc.filename)+'</h4></div><button type="button" class="studio-secondary" data-code-copy="'+index+'" '+(doc.status==='ready'?'':'disabled')+'>Copy</button></header>'+(doc.status==='ready'?'<pre tabindex="0"><code>'+escape(doc.content||'')+'</code></pre>':'<p role="status">'+(doc.status==='missing'?'File not created yet.':'Could not open this file.')+'</p>')+'</article>').join('')+'</div>';
   host.querySelector('.studio-code-layout').onclick=async event=>{
    const button=event.target.closest('[data-code-copy]');if(!button)return;
    const doc=core[Number(button.dataset.codeCopy)];if(doc?.status!=='ready')return;
    try{await copyText(doc.content);if(current())button.textContent='Copied';}
    catch{if(current())button.textContent='Select text to copy';}
   };
   return;
  }
  host.innerHTML='<div class="studio-identity-heading"><div><h3>'+escape(result.name)+'</h3><p>'+escape(result.description)+'</p></div><span>Read only</span></div><div class="studio-identity-layout"><nav aria-label="Agent documents" class="studio-identity-files">'+['agent','skill'].map(group=>{
   const items=documents.map((doc,index)=>({doc,index})).filter(({doc})=>doc.group===group);
   return items.length?'<section><h4>'+(group==='agent'?'OpenClaw files':'Custom skills')+'</h4>'+items.map(({doc,index})=>'<button type="button" data-identity-document="'+index+'" aria-pressed="false" data-status="'+escape(doc.status)+'"><strong>'+escape(group==='skill'?doc.title:doc.filename)+'</strong><small>'+escape(group==='skill'?'SKILL.md':doc.title)+'</small></button>').join('')+'</section>':'';
  }).join('')+'</nav><section class="studio-identity-document" aria-label="Document contents"><header><div><h4 id="studio-identity-filename"></h4><small id="studio-identity-file-note"></small></div><button type="button" class="studio-secondary" id="studio-identity-copy">Copy</button></header><p id="studio-identity-unavailable" role="status" hidden></p><pre id="studio-identity-source" tabindex="0"><code></code></pre></section></div>';
  let selected=null;
  const show=index=>{
   const doc=documents[index];if(!doc)return;
   selected=doc;
   for(const button of host.querySelectorAll('[data-identity-document]'))button.setAttribute('aria-pressed',String(Number(button.dataset.identityDocument)===index));
   el('identity-filename').textContent=doc.filename;
   el('identity-file-note').textContent=doc.status==='ready'?'Saved file · '+new Date(doc.updated*1000).toLocaleString():doc.title;
   el('identity-copy').disabled=doc.status!=='ready';el('identity-copy').textContent='Copy';
   el('identity-source').hidden=doc.status!=='ready';
   el('identity-source').querySelector('code').textContent=doc.content||'';
   el('identity-source').scrollTop=0;
   el('identity-unavailable').hidden=doc.status==='ready';
   el('identity-unavailable').textContent=doc.status==='missing'?'File not created yet.':'Could not open this file.';
  };
  host.querySelector('nav').onclick=event=>{const button=event.target.closest('[data-identity-document]');if(button)show(Number(button.dataset.identityDocument));};
  el('identity-copy').onclick=async()=>{
   const doc=selected,button=el('identity-copy');
   if(doc?.status!=='ready')return;
   try{await copyText(doc.content);if(current()&&selected===doc)button.textContent='Copied';}
   catch{if(current()&&selected===doc)button.textContent='Select text to copy';}
  };
  show(0);
 }catch(error){if(current())host.innerHTML='<h3>'+escape(name)+'</h3><p role="alert">'+escape(error.message)+'</p>';}
}
for(const id of ['portrait','agent-name'])el(id).onclick=()=>openAgentDocuments();
el('agent-code').onclick=()=>openAgentDocuments(null,true);
for(const id of ['crew-portrait','crew-name'])el(id).onclick=async()=>{const visitor=selectedCrewVisitor();if(visitor){await switchAgent(visitor.key);if(agentId===visitor.key)openAgentDocuments();}else openAgentDocuments(selectedCrewRole);};
el('dialog').addEventListener('close',()=>{if(!el('dialog').open)identityRequest++;});

// Browser-based folder access works on both local and remote installations.
function syncFileButtons(){
 personalFilesButton.hidden=!data.hasFiles;
 const visitor=selectedCrewVisitor();
 scenarioFilesButton.hidden=visitor?!visitorAvailable(visitor):!(data.fileWorkspaces||[]).includes(String(selectedCrewRole));
}
async function openWorkspaceFiles(team=false,allowEmpty=false){
 const visitor=team?selectedCrewVisitor():null;if(visitor){await switchAgent(visitor.key);if(agentId===visitor.key)return openWorkspaceFiles(false,true);return;}
 const target=agentId,scenario=selectedScenario,role=selectedCrewRole,workspace=team?String(role):'personal';
 if(!allowEmpty&&(team?!(data.fileWorkspaces||[]).includes(workspace):!data.hasFiles))return;
 const name=team?defaultNames[role]:data.profile?.name;
 dialog('FILES','<section id="studio-workspace-browser"><header><h3>'+escape(name?name+' files':'Agent files')+'</h3></header><p id="studio-file-status" role="status">Loading files…</p><div id="studio-file-folders"></div></section>');
 const host=el('workspace-browser');
 const current=()=>host.isConnected&&el('dialog').open&&target===agentId&&scenario===selectedScenario&&(!team||role===selectedCrewRole);
 try{
  const result=await api('workspace-files?workspace='+encodeURIComponent(workspace),undefined,target);
  if(!current())return;
  const files=result.files||[];
  el('file-status').textContent=files.length?'':'No files yet.';
  el('file-folders').innerHTML=[['inbox','Uploaded files'],['artifacts','Results']].map(([folder,label])=>{
   const items=files.filter(f=>f.kind===folder);
   return items.length?'<section class="studio-file-folder"><h4>'+label+'</h4>'+items.map(f=>'<button type="button" class="studio-secondary" data-browse-file="'+escape(f.path)+'"><span>'+escape(f.path.slice(folder.length+1))+'</span><small>'+Math.ceil(f.size/1024)+' KB ↗</small></button>').join('')+'</section>':'';
  }).join('');
  el('file-folders').onclick=event=>{const button=event.target.closest('[data-browse-file]');if(button&&current())openFile(button.dataset.browseFile,'',workspace);};
 }catch(error){if(current())el('file-status').textContent=error.message;}
}
const personalFilesButton=document.createElement('button');personalFilesButton.type='button';personalFilesButton.hidden=true;personalFilesButton.id='studio-personal-files';personalFilesButton.className='studio-secondary';personalFilesButton.textContent='Files';personalFilesButton.onclick=()=>openWorkspaceFiles(false);el('agent-code').after(personalFilesButton);
const scenarioFilesButton=document.createElement('button');scenarioFilesButton.type='button';scenarioFilesButton.hidden=true;scenarioFilesButton.className='studio-team-utility';scenarioFilesButton.textContent='Files';scenarioFilesButton.onclick=()=>openWorkspaceFiles(true);teamConnectionBar.querySelector('.studio-team-utilities').prepend(scenarioFilesButton);
