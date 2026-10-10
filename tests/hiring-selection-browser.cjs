// Disposable fixture_heartbeat.py only. Use real pointer events and actual
// Hiring, not element.click() or a reload of already-created agents.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(10000);
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:18087');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  const tag=key=>page.locator('[data-resident="'+key+'"]');
  const selected=key=>page.waitForFunction(k=>BacStudio.inspect().agentId===k&&document.querySelector('[data-resident="'+k+'"]').getAttribute('aria-pressed')==='true',key);
  async function creator(name){
   await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-name').fill(name);await page.locator('[data-role-template="3"]').click();
  }
  async function hire(name){
   await creator(name);await page.locator('#studio-create').click();
   await page.waitForFunction(n=>BacStudio.inspect().profile?.name===n&&BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival&&!BacCampus.inspect().navigation.travelling,name,{timeout:20000});
   return page.evaluate(()=>BacStudio.inspect().agentId);
  }
  const a=await hire('Fresh A'),b=await hire('Fresh B');
  await page.evaluate(()=>{window.selectionEvents=[];document.querySelector('#agent-campus').addEventListener('bac:collection-select',e=>selectionEvents.push(e.detail));});
  async function pointerGesture(key,dx,dy=0){
   const button=tag(key);await button.hover();const box=await button.boundingBox();
   await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
   await page.mouse.move(box.x+box.width/2+dx,box.y+box.height/2+dy,{steps:4});await page.mouse.up();
  }
  for(const dx of [0,3,6,8,12]){
   await tag(a).click();await selected(a);
   const count=await page.evaluate(()=>selectionEvents.length);
   await pointerGesture(b,dx);await selected(b);
   assert.equal(await page.evaluate(()=>selectionEvents.length),count+1,'one selection per pointer gesture');
  }
  console.log('PASS: freshly hired 3D labels select with 0-12px pointer movement.');

  // Deliberate placement still moves the resident without orbiting the camera.
  await tag(a).click();await selected(a);await tag(b).hover();
  const before=await page.evaluate(()=>BacCampus.inspect());
  await pointerGesture(b,100,35);await selected(b);
  const after=await page.evaluate(()=>BacCampus.inspect());
  assert.notDeepEqual(after.residents.find(r=>r.key===b).position,before.residents.find(r=>r.key===b).position);
  assert.deepEqual(after.camera,before.camera);
  await page.evaluate(()=>BacStudio.refresh());
  assert.deepEqual(await page.evaluate(k=>BacCampus.inspect().residents.find(r=>r.key===k).position,b),after.residents.find(r=>r.key===b).position);
  await tag(a).focus();await page.keyboard.press('Enter');await selected(a);
  await tag(b).focus();await page.keyboard.press('Space');await selected(b);
  await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement);
  await pointerGesture(a,8);await selected(a);
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);
  console.log('PASS: dragging retains placement and camera; keyboard and fullscreen selection work.');

  // Keep the last name-tag choice while a slow hire is completing. Choosing
  // the current agent must override the automatic choice of the newcomer too.
  await creator('Fresh C');const saved=deferred(),release=deferred();
  await page.route('**/api/agents',async route=>{const response=await route.fetch();saved.resolve();await release.promise;await route.fulfill({response});},{times:1});
  await page.locator('#studio-create').click();await saved.promise;
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await tag(b).click();await tag(a).click();release.resolve();
  await page.waitForFunction(()=>BacStudio.inspect().agents.length===3&&!document.querySelector('#studio-onboarding').inert);
  await selected(a);assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.name),'Fresh A');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agents.filter(a=>a.name==='Fresh C').length),1);
  console.log('PASS: hiring preserves the last 3D selection, including the previously active agent.');

  // A preparation status poll between press and release must not remove the
  // sidebar button. This also exercises the same workspace switch handler.
  let revision=0;
  await page.route('**/api/state',async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),state=await response.json();
   state.agents[0].workspacePreparation='fixture-'+(++revision);await route.fulfill({response,json:state});
  });
  const card=page.locator('[data-agent-key="'+b+'"]');await card.scrollIntoViewIfNeeded();const box=await card.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.evaluate(()=>BacStudio.refresh());await page.mouse.up();await selected(b);
  await page.unroute('**/api/state');
  assert.deepEqual(errors,[]);
  console.log('PASS: background preparation updates do not drop a held sidebar click; no browser errors.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
