// Inspect generated files; explicit persona edits share the Edit agent save path.
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
  const editControl=role===null&&data.profile&&!(room==='mission'&&crewAgentEditLock(target))?'<button type="button" class="studio-secondary" data-identity-edit>Edit</button>':'<span>Read only</span>';
  const bindEdit=()=>{
   const button=host.querySelector('[data-identity-edit]');
   if(button)button.onclick=()=>editAgentPersona(host,current,()=>openAgentDocuments(role,codeView),target);
  };
  if(codeView){
   const definitions=[
    {filename:'AGENTS.md',label:'Working instructions'},
    {filename:'IDENTITY.md',label:'Identity'},
    {filename:'SOUL.md',label:'Character and boundaries'}
   ];
   const core=definitions.map(definition=>({...definition,...(documents.find(doc=>doc.group==='agent'&&doc.filename===definition.filename)||{status:'missing'})}));
   host.innerHTML='<div class="studio-identity-heading"><div><h3>'+escape(result.name)+'</h3><p>'+escape(result.description)+'</p></div>'+editControl+'</div><div class="studio-code-layout">'+core.map((doc,index)=>'<article class="studio-code-panel" data-status="'+escape(doc.status)+'"><header><div><small>'+escape(doc.label)+'</small><h4>'+escape(doc.filename)+'</h4></div><button type="button" class="studio-secondary" data-code-copy="'+index+'" '+(doc.status==='ready'?'':'disabled')+'>Copy</button></header>'+(doc.status==='ready'?'<pre tabindex="0"><code>'+escape(doc.content||'')+'</code></pre>':'<p role="status">'+(doc.status==='missing'?'File not created yet.':'Could not open this file.')+'</p>')+'</article>').join('')+'</div>';
   host.querySelector('.studio-code-layout').onclick=async event=>{
    const button=event.target.closest('[data-code-copy]');if(!button)return;
    const doc=core[Number(button.dataset.codeCopy)];if(doc?.status!=='ready')return;
    try{await copyText(doc.content);if(current())button.textContent='Copied';}
    catch{if(current())button.textContent='Select text to copy';}
   };
   bindEdit();
   return;
  }
  host.innerHTML='<div class="studio-identity-heading"><div><h3>'+escape(result.name)+'</h3><p>'+escape(result.description)+'</p></div>'+editControl+'</div><div class="studio-identity-layout"><nav aria-label="Agent documents" class="studio-identity-files">'+['agent','skill'].map(group=>{
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
  bindEdit();
 }catch(error){if(current())host.innerHTML='<h3>'+escape(name)+'</h3><p role="alert">'+escape(error.message)+'</p>';}
}
// Save profile fields, never independent overrides of generated runtime files.
function editAgentPersona(host,current,reopen,target){
 const original={...data.profile};
 const existing=[...host.children];existing.forEach(node=>node.hidden=true);
 const form=document.createElement('form');form.className='studio-persona-editor';
 form.innerHTML='<header><h3>Edit persona</h3><p>Changes apply to your next conversation and stay in sync with Edit agent.</p></header>'+
  '<label>Name<input name="name" required maxlength="32"></label>'+
  '<label>Tone<textarea name="tonePrompt" rows="2" maxlength="800"></textarea></label>'+
  '<label>Role<textarea name="purpose" rows="4" maxlength="240"></textarea></label>'+
  '<p class="studio-persona-error" role="alert" hidden></p><footer><button type="button" class="studio-secondary" data-persona-cancel>Cancel</button><button type="submit" class="studio-primary">Save changes</button></footer>';
 host.append(form);
 form.elements.name.value=original.name;
 form.elements.tonePrompt.value=savedTonePrompt(original);
 form.elements.purpose.value=original.purpose||personas[original.persona]||'';
 form.querySelector('[data-persona-cancel]').onclick=()=>{form.remove();existing.forEach(node=>node.hidden=false);host.querySelector('[data-identity-edit]').focus();};
 form.onsubmit=async event=>{
  event.preventDefault();if(!current())return;
  const fields={name:form.elements.name.value.trim(),tonePrompt:form.elements.tonePrompt.value.trim(),purpose:form.elements.purpose.value.trim()};
  const errorBox=form.querySelector('[role=alert]');errorBox.hidden=true;
  const controls=[...form.elements];controls.forEach(control=>control.disabled=true);
  try{
   const state=await api('state',undefined,target);
   if(!current())return;
   if(!state.profile||['name','tonePrompt','tone','purpose','persona'].some(key=>state.profile[key]!==original[key]))throw new Error('This persona changed elsewhere. Reopen Edit to load the latest version.');
   const tone=Object.keys(tones).find(key=>matchesTonePrompt(key,fields.tonePrompt))||'kind';
   await api('profile',{...state.profile,...fields,tone},target);
   if(!current())return;
   await refresh();
   if(current())await reopen();
  }catch(error){if(current()){errorBox.textContent=error.message;errorBox.hidden=false;}}
  finally{controls.forEach(control=>control.disabled=false);}
 };
 form.elements.name.focus();
}
for(const id of ['portrait','agent-name'])el(id).onclick=()=>openAgentDocuments();
el('agent-code').onclick=()=>openAgentDocuments(null,true);
el('crew-instructions').onclick=async()=>{const key=selectedCrewVisitor()?.key;if(!key)return;await switchAgent(key);if(room==='mission'&&selectedCrewVisitor()?.key===key&&agentId===key)openAgentDocuments(null,true);};
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

// Uploaded documents open independently of chat navigation or attachment selection.
function attachmentCsvRows(text,maxRows=1000,maxColumns=100){
 const rows=[];let row=[],cell='',quoted=false,clipped=false;
 const field=()=>{if(row.length<maxColumns)row.push(cell);else clipped=true;cell='';};
 const record=()=>{field();rows.push(row);row=[];};
 text=text.replace(/^\uFEFF/,'');
 for(let i=0;i<text.length;i++){
  const char=text[i];
  if(char==='"'){
   if(quoted&&text[i+1]==='"'){cell+='"';i++;}
   else if(quoted||cell==='')quoted=!quoted;
   else cell+=char;
  }else if(char===','&&!quoted)field();
  else if((char==='\n'||char==='\r')&&!quoted){
   if(char==='\r'&&text[i+1]==='\n')i++;
   record();
   if(rows.length>=maxRows){clipped=clipped||i<text.length-1;return {rows,clipped};}
  }else cell+=char;
 }
 if(cell!==''||row.length||quoted)record();
 return {rows,clipped};
}
function attachmentPreviewMarkup(name,text,extracted=false){
 const limit=500000,shortened=text.length>limit,preview=text.slice(0,limit);
 let content,note=extracted?'Extracted text · original formatting and images are not shown.':'';
 if(/\.csv$/i.test(name)&&!extracted){
  const {rows,clipped}=attachmentCsvRows(preview);
  content='<div class="table-scroll"><table>'+rows.map((row,index)=>'<tr>'+row.map(cell=>'<'+(index?'td':'th')+'>'+escape(cell)+'</'+(index?'td':'th')+'>').join('')+'</tr>').join('')+'</table></div>';
  if(clipped||shortened)note='Preview limited to 1,000 rows, 100 columns and 500,000 characters. Download for the full file.';
 }else{
  content='<pre>'+escape(preview)+'</pre>';
  if(shortened)note+=(note?' ':'')+'Preview shortened. Download for the full file.';
 }
 return '<h1>'+escape(name)+'</h1><p class="note">'+escape(note)+'</p>'+content;
}
async function openAttachmentTab(path,workspace){
 const target=agentId,scenario=selectedScenario,name=path.split('/').pop();
 const tab=window.open('about:blank','_blank');
 if(!tab){alert('Allow pop-ups for this site to preview attachments.','error');return;}
 tab.opener=null;
 const shell=body=>'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+escape(name)+'</title><style>html{color-scheme:dark}body{margin:0;padding:32px;background:#101a22;color:#e2eaf0;font:15px/1.65 system-ui,sans-serif}main{max-width:1200px;margin:auto}h1{font-size:22px;overflow-wrap:anywhere;margin:0 0 8px}.note{color:#9db2bf;font-size:13px}pre{font:15px/1.8 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;background:#15232d;padding:24px;border:1px solid #304653;border-radius:12px}a{display:inline-block;color:#cee7a8;margin:0 0 20px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:10px 14px;border:1px solid #304653;white-space:pre-wrap;min-width:100px;max-width:480px;overflow-wrap:anywhere}th{background:#23352a;position:sticky;top:0}tr:nth-child(even){background:#15232d}.table-scroll{overflow:auto;max-height:80vh;border-radius:8px}@media(max-width:600px){body{padding:16px}pre{padding:16px}}</style></head><body><main>'+body+'</main></body></html>';
 const show=body=>{if(tab.closed)return;tab.document.open();tab.document.write(shell(body));tab.document.close();};
 show('<h1>'+escape(name)+'</h1><p role="status">Loading file…</p>');
 const read=filePath=>api('file?path='+encodeURIComponent(filePath)+'&workspace='+encodeURIComponent(workspace),undefined,target,scenario);
 try{
  const file=await read(path);if(tab.closed)return;
  const binary=file.encoding==='base64';
  const readable=binary?await read(path+'.txt'):file;
  if(tab.closed)return;
  show(attachmentPreviewMarkup(name,readable.content||'',binary));
  const blob=new Blob([binary?Uint8Array.from(atob(file.content),c=>c.charCodeAt(0)):file.content],{type:file.mime||(/\.csv$/i.test(name)?'text/csv;charset=utf-8':'text/plain;charset=utf-8')});
  const url=URL.createObjectURL(blob),link=tab.document.createElement('a');
  link.href=url;link.download=name;link.textContent='Download original';
  tab.document.querySelector('h1').after(link);
  const cleanup=setInterval(()=>{if(tab.closed){clearInterval(cleanup);URL.revokeObjectURL(url);}},5000);
 }catch(error){show('<h1>'+escape(name)+'</h1><p role="alert">'+escape(error.message||'Could not open this file.')+'</p>');}
}
