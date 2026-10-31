// Real UI/HTTP with disposable data and simulated model replies.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18447),origin='http://127.0.0.1:'+port;
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser,release;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited'));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[],writes=[];
  page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
  const modal=page.locator('#studio-dialog'),surface=page.locator('#studio-surface');
  const outside=async locator=>{const r=await locator.boundingBox();await page.mouse.click(r.x-8,r.y+r.height/2);};
  const worldOutside=async()=>{const r=await page.locator('#campus-viewport').boundingBox();await page.mouse.click(r.x+8,r.y+8);};
  await page.goto(origin);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const room=page.locator('.world-room-paper:not(.world-term-paper)'),term=page.locator('.world-term-paper'),overview=page.locator('.world-term-overview');
  await page.locator('[data-room-info=workshop]').click();await page.locator('[data-paper-term=agent]').click();
  await page.locator('[data-term-overview=agent]').click();assert(await overview.isVisible());
  await overview.locator('h2').click();assert(await overview.isVisible(),'Inside click keeps overview open');
  await worldOutside();assert(await overview.isHidden());assert(await term.isVisible());assert(await room.isVisible());
  await worldOutside();assert(await term.isHidden());assert(await room.isVisible());
  await worldOutside();assert(await room.isHidden());
  await page.getByRole('button',{name:'Programmer',exact:true}).click();await page.locator('#studio-name').fill('Dismiss test');
  await page.locator('input[name=protection][value=standard]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&BacStudio.inspect().profile?.name==='Dismiss test'&&!BacStudio.inspect().jobs.some(j=>['queued','running'].includes(j.status)));
  await page.locator('#studio-agent-code').click();const editor=page.locator('[data-code-source="0"]');await editor.waitFor();
  const draft=(await editor.inputValue())+'\nKeep this unsaved draft.\n';await editor.fill(draft);
  await outside(modal);await modal.waitFor({state:'hidden'});
  await page.locator('#studio-agent-code').click();await editor.waitFor();assert.equal(await editor.inputValue(),draft,'Outside dismissal preserves document draft');
  await outside(modal);await modal.waitFor({state:'hidden'});
  const beforeDelete=writes.filter(p=>p==='/api/delete-agent').length;
  await page.locator('#studio-delete-agent').click();await outside(modal);await modal.waitFor({state:'hidden'});
  assert.equal(writes.filter(p=>p==='/api/delete-agent').length,beforeDelete,'Dismissing confirmation never deletes');
  await page.locator('.world-room-map [data-world-scenario=plan]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-crew-team-mode [data-team-mode=mixed]').click();
  await page.locator('#studio-crew-prompt').fill('/goal Build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.'));
  for(const panel of ['control','deliverables','usage']){
   await page.locator('[data-surface="'+panel+'"]').click();await surface.waitFor();
   await surface.locator('header h2').click();assert(await surface.isVisible(),'Header click keeps '+panel+' open');
   if(panel==='control'){
    const r=await surface.boundingBox();await page.mouse.move(r.x+40,r.y+40);await page.mouse.down();await page.mouse.move(r.x-8,r.y+40,{steps:5});await page.mouse.up();
    assert(await surface.isVisible(),'Dragging from inside to outside does not dismiss');
   }
   await outside(surface);await surface.waitFor({state:'hidden'});
   await page.waitForFunction(()=>!BacStudio.inspect().board); // Native close event is queued.
  }
  // Nested modal: dismiss the upper confirmation without closing the trace.
  await page.locator('[data-surface=control]').click();
  await page.locator('#studio-bac-reset').evaluate(button=>button.click());await modal.waitFor();
  await outside(modal);await modal.waitFor({state:'hidden'});assert(await surface.isVisible());
  await outside(surface);await surface.waitFor({state:'hidden'});
  // Saving a model uses the same cancellation guard for Escape and backdrop.
  await page.locator('#studio-crew-model').click();await modal.waitFor();
  let arrived;const incoming=new Promise(resolve=>{arrived=resolve;});
  await page.route('**/api/team-model',async route=>{arrived();await new Promise(resolve=>{release=resolve;});await route.continue();});
  await page.locator('[data-model-choice]:not([aria-pressed=true]):not(:disabled)').first().click();await incoming;
  await outside(modal);assert(await modal.isVisible(),'Saving model cannot be dismissed by backdrop');
  release();await modal.waitFor({state:'hidden'});await page.unroute('**/api/team-model');
  await page.locator('#studio-crew-model').click();await outside(modal);await modal.waitFor({state:'hidden'});
  await page.locator('[data-surface=control]').click();await page.keyboard.press('Escape');await surface.waitFor({state:'hidden'});
  await page.evaluate(()=>BacStudio.setRoom('policies'));await surface.waitFor();
  assert.equal(await page.locator('#studio-surface-title').innerText(),'OpenShell Policy');
  await outside(surface);await surface.waitFor({state:'hidden'});
  await page.evaluate(()=>document.getElementById('agent-campus').requestFullscreen());
  await page.evaluate(()=>BacStudio.showBoard(true));await surface.waitFor();
  await outside(surface);await surface.waitFor({state:'hidden'});
  assert(await page.evaluate(()=>!!document.fullscreenElement),'Closing a panel preserves fullscreen');
  await page.evaluate(()=>document.exitFullscreen());
  assert.deepEqual(errors,[]);
  console.log('PASS: Mission Control/Results/Usage/Policy outside dismissal; fullscreen; nested dialogs; inside clicks and drag safety; model save guard; document drafts; deletion cancellation; layered glossary/overview; Escape.');
 }finally{release?.();if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1});
