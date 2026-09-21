// Inspect saved OpenClaw files. Opening this panel never prepares or edits an agent.
let identityRequest=0;
async function openAgentDocuments(role=null){
 const target=agentId,request=++identityRequest;
 const name=role===null?data.profile?.name:defaultNames[role];
 if(!name||!target)return;
 dialog('AGENT FILES','<section id="studio-identity-viewer"><h3>'+escape(name)+'</h3><p role="status">Loading agent files…</p></section>');
 el('dialog').classList.add('studio-agent-documents');
 const host=el('identity-viewer');
 const current=()=>request===identityRequest&&el('dialog').open&&el('identity-viewer')===host&&agentId===target;
 try{
  const result=await api('agent-documents'+(role===null?'':'?role='+role),undefined,target);
  if(!current())return;
  const documents=result.documents||[];
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
   el('identity-unavailable').textContent=doc.status==='missing'?'This file has not been created yet. It will appear when this agent’s runtime is prepared.':'This saved file could not be opened.';
  };
  host.querySelector('nav').onclick=event=>{const button=event.target.closest('[data-identity-document]');if(button)show(Number(button.dataset.identityDocument));};
  el('identity-copy').onclick=async()=>{
   const doc=selected,button=el('identity-copy');
   if(doc?.status!=='ready')return;
   try{await navigator.clipboard.writeText(doc.content);if(current()&&selected===doc)button.textContent='Copied';}
   catch{if(current()&&selected===doc)button.textContent='Select text to copy';}
  };
  show(0);
 }catch(error){if(current())host.innerHTML='<h3>'+escape(name)+'</h3><p role="alert">'+escape(error.message)+'</p>';}
}
for(const id of ['portrait','agent-name'])el(id).onclick=()=>openAgentDocuments();
for(const id of ['crew-portrait','crew-name'])el(id).onclick=()=>openAgentDocuments(selectedCrewRole);
el('dialog').addEventListener('close',()=>{if(!el('dialog').open)identityRequest++;});
