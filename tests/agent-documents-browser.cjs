// Real HTTP/SQLite and browser editing; isolated agents and simulated inference.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18296),origin='http://127.0.0.1:'+port;
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1000},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedDefinition=text;}}}));
  let writeHeaders,readHeaders;
  page.on('request',r=>{if(r.url()===origin+'/api/agent-documents'){if(r.method()==='POST')writeHeaders=r.headers();else readHeaders=r.headers();}});
  await page.goto(origin);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-room=workshop]').click();
  await page.getByRole('button',{name:'프로그래머',exact:true}).click();
  await page.locator('#studio-skill-picker input[value="web"]').check();
  await page.locator('#studio-name').fill('Jinny');await page.locator('input[name=protection][value=standard]').check();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&BacStudio.inspect().profile?.name==='Jinny'&&!BacStudio.inspect().jobs.some(j=>['queued','running'].includes(j.status)));
  await page.locator('#studio-agent-name').click();
  const source=page.locator('#studio-identity-source'),modal=page.locator('#studio-dialog'),save=page.locator('[data-identity-save]');
  await source.waitFor();assert.equal(await source.getAttribute('aria-label'),'SOUL.md');
  assert(await save.isDisabled());assert.equal(await modal.getByRole('button',{name:'Edit',exact:true}).count(),0);
  const apiRead=async()=>{const response=await page.request.get(origin+'/api/agent-documents',{headers:{'X-BaC-Agent':await page.evaluate(()=>BacStudio.inspect().agentId)}});assert(response.ok());return response.json();};
  const original=await apiRead(),expected=new Map();
  for(let index=0;index<original.documents.length;index++){
   const doc=original.documents[index];
   await page.locator('[data-identity-document="'+index+'"]').click();
   assert.equal(await source.inputValue(),doc.content||'');
   const content=(doc.content||'')+'\n\n## My notes\n한글 - '+doc.path+'\n<script>window.identityInjected=true</script>\n';
   expected.set(doc.path,content);await source.fill(content);
  }
  await page.locator('[data-identity-document="0"]').click();assert.equal(await source.inputValue(),expected.get('SOUL.md'));
  await page.locator('#studio-identity-copy').click();assert.equal(await page.evaluate(()=>window.copiedDefinition),expected.get('SOUL.md'));
  assert.equal(await page.evaluate(()=>window.identityInjected),undefined);
  await page.keyboard.press('Escape');await page.locator('#studio-agent-code').click();
  const panels=page.locator('.studio-code-panel'),instructionSource=page.locator('[data-code-source="0"]');
  await instructionSource.waitFor();assert.equal(await panels.count(),3);
  assert.equal(await modal.locator('nav').count(),0);
  const panelBoxes=await Promise.all((await panels.all()).map(panel=>panel.boundingBox()));
  assert(panelBoxes.every(box=>Math.abs(box.y-panelBoxes[0].y)<1));
  assert(panelBoxes[0].x<panelBoxes[1].x&&panelBoxes[1].x<panelBoxes[2].x);
  for(const [index,filename] of ['AGENTS.md','IDENTITY.md','SOUL.md'].entries()){
   const editor=page.locator('[data-code-source="'+index+'"]');
   assert.equal(await editor.inputValue(),expected.get(filename));
   const value=expected.get(filename)+'\nEdited directly in '+filename+'.\n';
   expected.set(filename,value);await editor.fill(value);
  }
  await page.locator('[data-code-copy="1"]').click();assert.equal(await page.evaluate(()=>window.copiedDefinition),expected.get('IDENTITY.md'));
  await save.click();await page.waitForFunction(()=>document.querySelector('.studio-document-status')?.textContent.startsWith('Saved.'));
  assert(await save.isDisabled());
  const corePaths=['AGENTS.md','IDENTITY.md','SOUL.md'];
  for(const doc of (await apiRead()).documents)assert.equal(doc.content,corePaths.includes(doc.path)?expected.get(doc.path):original.documents.find(d=>d.path===doc.path).content,'Instructions saves only its visible files');
  await page.keyboard.press('Escape');await page.locator('#studio-agent-name').click();await source.waitFor();
  await page.locator('[data-identity-document="4"]').click();assert.equal(await source.inputValue(),expected.get('MEMORY.md'),'Other file drafts survive an Instructions save');
  await save.click();await page.waitForFunction(()=>document.querySelector('.studio-document-status')?.textContent.startsWith('Saved.'));
  assert.deepEqual(new Map((await apiRead()).documents.map(d=>[d.path,d.content])),expected);
  await page.keyboard.press('Escape');await page.reload();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Jinny');
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-edit-agent').click();
  await page.locator('#studio-tone-prompt').fill('Friendly and concise.\n한국어로 답해줘.');
  await page.locator('#studio-purpose').fill('Build small accessible webpages.');
  await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.tonePrompt),'Friendly and concise.\n한국어로 답해줘.');
  assert.deepEqual(new Map((await apiRead()).documents.map(d=>[d.path,d.content])),expected,'Profile edits preserve manually edited Markdown');
  await page.locator('#studio-agent-name').click();await source.waitFor();assert.equal(await source.inputValue(),expected.get('SOUL.md'));
  // Concurrent changes reject the stale draft and Discard loads the newer file.
  await source.fill('# My conflicting draft\n');
  const soul=(await apiRead()).documents[0],newer='# Newer server instructions\n';
  const external=await page.request.post(origin+'/api/agent-documents',{headers:{...writeHeaders,...readHeaders},data:{documents:[{path:soul.path,revision:soul.revision,content:newer}]}});assert(external.ok(),await external.text());
  await save.click();await page.locator('.studio-document-status[data-error=true]').waitFor();
  assert.equal(await source.inputValue(),'# My conflicting draft\n');assert.equal((await apiRead()).documents[0].content,newer);
  await page.locator('[data-identity-discard]').click();assert.equal(await source.inputValue(),newer);
  await source.fill(newer+'\nPrefer concise answers.\n');await source.press('ControlOrMeta+s');
  await page.waitForFunction(()=>document.querySelector('.studio-document-status')?.textContent.startsWith('Saved.'));
  // Closing while saving cannot erase a new draft in a reopened editor.
  let release,arrived;
  const incoming=new Promise(resolve=>{arrived=resolve;});
  await page.route('**/api/agent-documents',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   arrived();await new Promise(resolve=>{release=resolve;});await route.continue();
  });
  await source.fill('# Save across reopening\n');await save.click();await incoming;
  await page.keyboard.press('Escape');await page.locator('#studio-agent-name').click();
  await modal.getByText('Loading agent files…').waitFor();release();
  await source.waitFor();assert.equal(await source.inputValue(),'# Save across reopening\n');
  await page.unroute('**/api/agent-documents');assert(await save.isDisabled());
  const artifacts=process.env.BAC_TEST_ARTIFACT_DIR||path.resolve('../agent-document-editing');fs.mkdirSync(artifacts,{recursive:true});
  await page.locator('[data-identity-document="2"]').click();await modal.screenshot({path:path.join(artifacts,'desktop.png')});
  await page.setViewportSize({width:600,height:850});await modal.screenshot({path:path.join(artifacts,'narrow.png')});
  const box=await source.boundingBox();assert(box.width>200&&box.height>250,'Editor remains usable on narrow screens');
  assert(await modal.evaluate(e=>e.scrollWidth<=e.clientWidth+1));
  await page.setViewportSize({width:1500,height:1000});await page.keyboard.press('Escape');
  await page.locator('.world-room-map [data-world-scenario=plan]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.evaluate(()=>{document.getElementById('agent-campus').dispatchEvent(new CustomEvent('bac:collection-select',{detail:BacStudio.inspect().agentId}));});
  await page.locator('#studio-crew-instructions').click();await instructionSource.waitFor();
  assert.equal(await modal.locator('h3').textContent(),'Jinny');assert.equal(await panels.count(),3);
  assert.equal(await instructionSource.inputValue(),expected.get('AGENTS.md'));
  await instructionSource.fill(expected.get('AGENTS.md')+'\nStage 3 edit.\n');await save.click();
  await page.waitForFunction(()=>document.querySelector('.studio-document-status')?.textContent.startsWith('Saved.'));
  assert((await apiRead()).documents.find(d=>d.path==='AGENTS.md').content.endsWith('Stage 3 edit.\n'));
  await modal.screenshot({path:path.join(artifacts,'instructions-desktop.png')});
  await page.setViewportSize({width:600,height:850});await modal.screenshot({path:path.join(artifacts,'instructions-narrow.png')});
  assert(await modal.evaluate(e=>e.scrollWidth<=e.clientWidth+1));
  await page.locator('[data-code-source="2"]').scrollIntoViewIfNeeded();
  assert((await page.locator('[data-code-source="2"]').boundingBox()).height>150);
  assert.deepEqual(errors,[]);
  console.log('PASS: all visible Markdown edits; file switching/reopening; three-column Instructions edit/save; visible-file-only saves; Copy; literal HTML; batch save/reload; conflict recovery; keyboard save; reopen during save; desktop/narrow layout; Stage 3 hired-agent edits. Isolated HTTP/SQLite with simulated inference.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}}
})().catch(error=>{console.error(error);process.exitCode=1;});
