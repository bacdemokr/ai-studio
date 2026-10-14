// Real app UI with isolated connections and controlled saved results; no live model calls.
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18269),shots=process.env.BAC_TEST_SCREENSHOTS;let browser;
 if(shots)fs.mkdirSync(shots,{recursive:true});
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',c=>{clearTimeout(t);reject(Error('Fixture exited '+c));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const now=Date.now()/1000,model='nvidia/nvidia/nemotron-3-ultra-nvfp4',endpoint='External · NVIDIA Inference · https://inference-api.nvidia.com/v1';
  const fileText='# NVIDIA research\n\nThree findings with source links.\n\nFixture content for UI validation.',html='<!doctype html><html><body><h1>NVIDIA research</h1><button onclick="this.textContent=\'Details shown\'">Show details</button></body></html>';
  const metrics=Object.fromEntries([['Casey',model,39652,1458,41110,13,0],['Scout','nvidia/nvidia/nemotron-3.5-lightning',126172,8934,135106,52,8],['Cody',model,119108,13529,132637,68,5],['Jinny','azure/openai/gpt-5.6-terra',4024,67,6234,4,2],['Orbit',model,0,78,78,3,3]].map(([name,model,input,output,total,runSeconds,role])=>[name,{agent:name.toLowerCase(),name,model,endpoint,input,output,total,runSeconds,role}]));
  const tasks=[{role:8,task:'Research three NVIDIA technologies and cite the sources.',requiredFiles:['artifacts/research.md'],inputs:[]},{role:5,task:'Build a self-contained webpage from the research.',requiredFiles:['artifacts/index.html'],inputs:['artifacts/research.md']}];
  let completed={id:'panel-fixture',kind:'crew-chat',status:'done',created:now-152,updated:now,events:[],payload:{crewRole:0,teamMode:'mixed',prompt:'/goal Research NVIDIA and build a webpage.',metrics,collaboration:{task:'Research NVIDIA and build a webpage.',summary:'Scout researches the sources, then Cody builds the page.',tasks,calledRoles:[8,5],activeRole:null,outputs:{8:{answer:'Saved three sourced findings.',files:['artifacts/research.md']},5:{answer:'Created the webpage.',files:['artifacts/index.html']}},handoffs:{8:['artifacts/research.md'],5:['artifacts/index.html']},webpages:{5:['artifacts/index.html']},responseReady:true,finalAnswer:'The NVIDIA guide is ready.\n\n- Three concise technology summaries with sources.\n- A responsive webpage with expandable details.\n\nOpen the webpage or read the research brief below.'}},result:{files:['artifacts/index.html','artifacts/research.md']}};
  await page.route('**/api/state',async route=>{const headers={...route.request().headers()};delete headers['if-none-match'];const r=await route.fetch({headers}),s=await r.json();if(headers['x-bac-scenario']==='plan'){s.crewChats=completed?[completed]:[];s.fileWorkspaces=['0'];}await route.fulfill({json:s});});
  await page.route('**/api/workspace-files?*',r=>r.fulfill({json:{files:[{path:'artifacts/research.md',kind:'artifacts',size:fileText.length},{path:'artifacts/index.html',kind:'artifacts',size:html.length},{path:'inbox/brief.txt',kind:'inbox',size:125}]}}));
  await page.route('**/api/file?*',r=>{const name=new URL(r.request().url()).searchParams.get('path');return r.fulfill({json:{content:name.endsWith('.html')?html:fileText,mime:name.endsWith('.html')?'text/html':'text/plain'}});});
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-scenario="plan"]').click();await page.waitForFunction(()=>BacStudio.inspect().room==='mission'&&!BacCampus.inspect().navigation.travelling);
  const capture=async name=>{if(shots)await page.screenshot({path:shots+'/'+name+'.png'});};
  for(const panel of ['usage','control','deliverables']){
   await page.locator('[data-surface="'+panel+'"]').click();await page.locator('#studio-surface').waitFor();await capture(panel);
   if(panel==='usage'){
    assert.match(await page.locator('#studio-usage-time').innerText(),/315,165/);assert.match(await page.locator('#studio-usage-time').innerText(),/2m 32s/);
    const detail=page.locator('.studio-usage-connection').first();assert.equal(await detail.locator('dl').isVisible(),false);
    await detail.locator('summary').focus();await page.keyboard.press('Enter');assert.equal(await detail.locator('dl').isVisible(),true);assert.match(await detail.innerText(),new RegExp(model));assert.match(await detail.innerText(),/https:\/\/inference-api.nvidia.com\/v1/);await capture('usage-expanded');
    await page.keyboard.press('Enter');assert.equal(await detail.locator('dl').isVisible(),false);
   }
   if(panel==='deliverables')assert((await page.locator('#studio-surface').boundingBox()).height<650,'Short results should not leave a full-height empty dialog');
   await page.locator('#studio-surface-close').click();
  }
  await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();await page.locator('[data-browse-file="artifacts/research.md"]').waitFor();await capture('files');
  await page.locator('[data-browse-file="artifacts/research.md"]').click();await page.locator('#studio-download').waitFor();await capture('document');assert.equal(await page.locator('#studio-dialog-body pre').innerText(),fileText);
  const download=page.waitForEvent('download');await page.locator('#studio-download').click();const saved=await download;assert.equal(saved.suggestedFilename(),'research.md');assert.equal(fs.readFileSync(await saved.path(),'utf8'),fileText);await page.locator('#studio-dialog-close').click();
  await page.locator('[data-surface=deliverables]').click();await page.locator('#studio-plan-results [data-preview-file]').click();await page.locator('#studio-app-frame[data-ready=true]').waitFor();await page.frameLocator('#studio-app-frame').getByRole('button',{name:'Show details'}).click();assert.equal(await page.frameLocator('#studio-app-frame').getByRole('button').innerText(),'Details shown');
  await page.locator('[data-preview-width=mobile]').click();await capture('webpage');await page.locator('#studio-dialog-close').click();await page.locator('#studio-surface-close').click();
  await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();await capture('settings');await page.locator('#studio-dialog-close').click();
  for(const width of [1024,390]){
   await page.setViewportSize({width,height:844});await page.locator('[data-surface=usage]').click();await capture('usage-'+width);const box=await page.locator('#studio-surface').boundingBox();assert(box.x>=0&&box.x+box.width<=width+1,'Panel stays inside the viewport');
   assert(await page.locator('#studio-surface-body').evaluate(n=>n.scrollWidth<=n.clientWidth+1),'Usage has no horizontal overflow');
   await page.locator('.studio-usage-connection').last().scrollIntoViewIfNeeded();assert(await page.locator('.studio-usage-connection').last().isVisible());await page.locator('#studio-surface-close').click();
  }
  // Missing counts remain unknown, reported zero stays zero, and model switches remain inspectable.
  completed.updated++;
  completed.payload.metrics={first:{agent:'casey',name:'Casey',model:'provider/first-model',endpoint,input:0,output:5,total:5,runSeconds:2},second:{agent:'casey',name:'Casey',model:'provider/second-model',endpoint,input:10,output:2,total:12,runSeconds:1},unknown:{agent:'orbit',name:'Orbit',model:'long-provider/'+('long-model-name-'.repeat(12)),endpoint}};
  completed.payload.collaboration.task='A long task with '+('unbroken-word'.repeat(30));await page.evaluate(()=>BacStudio.refresh());
  await page.locator('[data-surface=usage]').click();assert.match(await page.locator('#studio-usage-time').innerText(),/token totals are partial/);
  const rows=page.locator('.studio-usage-time tbody tr');assert.equal(await rows.count(),2);assert.equal(await rows.first().locator('[data-label=Total]').innerText(),'17');assert.equal(await rows.last().locator('[data-label=Input]').innerText(),'—');
  await rows.first().locator('summary').click();assert.match(await rows.first().innerText(),/provider\/first-model, provider\/second-model/);assert(await page.locator('#studio-surface-body').evaluate(n=>n.scrollWidth<=n.clientWidth+1));await capture('usage-partial-390');await page.locator('#studio-surface-close').click();
  completed.updated++;completed.payload.metrics={};completed.status='error';completed.result.files=[];Object.assign(completed.payload.collaboration,{finalAnswer:'',outputs:{},webpages:{}});await page.evaluate(()=>BacStudio.refresh());await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-surface=usage]').click();assert.match(await page.locator('#studio-usage-time').innerText(),/No usage reported/);await capture('usage-empty');await page.locator('#studio-surface-close').click();
  await page.locator('[data-surface=deliverables]').click();assert.match(await page.locator('#studio-plan-results').innerText(),/This request did not finish/);assert.equal(await page.locator('#studio-plan-results [data-preview-file]').count(),0);await page.locator('#studio-surface-close').click();
  completed=null;await page.evaluate(()=>BacStudio.refresh());assert.equal(await page.locator('[data-surface=usage]').isVisible(),false);await page.locator('[data-surface=control]').click();assert.match(await page.locator('#studio-board').innerText(),/No active plan/);await capture('control-empty');await page.locator('#studio-surface-close').click();
  assert.deepEqual(errors,[]);console.log('PASS: Usage metrics, keyboard connection details, partial/empty/error results, responsive layouts, Mission Control, files/download content, interactive HTML preview and Settings. Simulated saved results.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
