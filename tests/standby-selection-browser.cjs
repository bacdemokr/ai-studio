// Disposable browser + dispatcher coverage. Model replies are simulated.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18265),host=process.env.BAC_TEST_HOST||'127.0.0.1';let browser;
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port),BAC_TEST_VISITOR_DELAY:'6'},stdio:['ignore','pipe','pipe']});server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',c=>{clearTimeout(t);reject(Error('Fixture exited '+c));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[],writes=[],jobs=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/agent-model'))writes.push({target:r.headers()['x-bac-agent'],...r.postDataJSON()});if(r.url().endsWith('/api/jobs')&&r.method()==='POST')jobs.push(r.postDataJSON());});
  const navigate=async scenario=>{await page.locator('.world-room-map [data-world-scenario="'+scenario+'"]').click();await page.waitForFunction(s=>BacCampus.inspect().navigation.activeScenario===s&&!BacCampus.inspect().navigation.travelling,scenario);};
  const hire=async name=>{await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill(name);await page.getByRole('button',{name:'Slack Announcer',exact:true}).click();await page.locator('#studio-create').click();await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().agents.every(a=>!a.pending),name);return page.evaluate(()=>BacStudio.inspect().agentId);};
  await page.goto('http://'+host+':'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  const pixel=await hire('Pixel'),orbit=await hire('Orbit');await navigate('plan');
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  const label=key=>page.locator('[data-visitor-agent="'+key+'"]'),badge=page.locator('#studio-crew-model'),picker=page.locator('.team-model-dialog'),search=picker.locator('input');
  const selected=name=>page.waitForFunction(name=>document.querySelector('#studio-crew-name').textContent===name,name,{timeout:6000});
  await label(pixel).click();await selected('Pixel');assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'mission');assert(await badge.isEnabled());
  await page.waitForFunction(key=>document.querySelector('[data-visitor-agent="'+key+'"]').classList.contains('selected'),pixel);assert(!await page.locator('#studio-crew-chat').isVisible());
  await page.evaluate(()=>BacStudio.refresh());await selected('Pixel');assert.equal(jobs.length,0,'Selecting an idle visitor must not start work');
  await badge.click();await search.fill('fixture-b');await picker.locator('[data-model-choice="api/nvidia/fixture-b"]').click();await picker.waitFor({state:'hidden'});
  assert.deepEqual(writes.at(-1),{target:pixel,model:'api/nvidia/fixture-b'});assert.equal(await badge.innerText(),'fixture-b');
  const documents=page.waitForRequest(r=>r.url().includes('/api/agent-documents'));
  await page.locator('#studio-crew-name').click();assert.equal((await documents).headers()['x-bac-agent'],pixel);await page.locator('#studio-identity-viewer').waitFor();assert.match(await page.locator('#studio-identity-viewer').innerText(),/Pixel/);await page.locator('#studio-dialog-close').click();await selected('Pixel');
  await label(orbit).focus();await page.keyboard.press('Enter');await selected('Orbit');assert.equal(await badge.innerText(),'fixture-a');
  await badge.click();await search.fill('fixture');assert(await picker.locator('[data-model-choice="api/nvidia/fixture-a"]').getAttribute('aria-pressed')==='true');await page.keyboard.press('Escape');
  await page.locator('[data-campus-agent="0"]').click();await selected('Casey');assert(await page.locator('#studio-crew-chat').isVisible());assert(await badge.isEnabled());
  // Body meshes, not just labels, must be selectable before the first plan.
  const point=await page.evaluate(key=>BacCampus.inspect().visitorTravel.find(v=>v.key===key).screenCenter,pixel),canvas=await page.locator('#campus-viewport canvas').boundingBox();
  assert(point,'Visitor exposes its projected body center for hit-testing');await page.mouse.click(canvas.x+point[0],canvas.y+point[1]);await selected('Pixel');
  if(process.env.BAC_TEST_SCREENSHOT)await page.screenshot({path:process.env.BAC_TEST_SCREENSHOT});
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);await navigate('plan');await label(pixel).click();await selected('Pixel');assert.equal(await badge.innerText(),'fixture-b');
  // If an idle visitor is removed while its picker is open, do not redirect the save to Casey.
  await badge.click();await search.fill('fixture');
  await page.route('**/api/state',async route=>{const headers={...route.request().headers()};delete headers['if-none-match'];const response=await route.fetch({headers}),data=await response.json();data.agents=data.agents.map(a=>a.key===pixel?{...a,deleting:true}:a);await route.fulfill({json:data});});
  await page.evaluate(()=>BacStudio.refresh());await selected('Casey');assert(await picker.locator('[data-model-choice="api/nvidia/fixture-a"]').isDisabled());
  await picker.locator('[data-model-close]').click();await page.unroute('**/api/state');await page.evaluate(()=>BacStudio.refresh());await label(pixel).waitFor();
  // An existing personal draft must not overwrite Casey's draft or another hire.
  await page.locator('[data-campus-agent="0"]').click();await selected('Casey');await page.locator('#studio-crew-prompt').fill('/goal A saved draft');await label(orbit).click();await selected('Orbit');await page.locator('[data-campus-agent="0"]').click();await selected('Casey');assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/goal A saved draft');
  await page.locator('#studio-crew-prompt').fill('/goal Have Pixel build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.some(v=>v.name==='Pixel'&&v.phase==='working'));
  await label(pixel).click();await selected('Pixel');assert(await badge.isDisabled(),'Assigned visitor stays locked during work');
  await label(orbit).click();await selected('Orbit');assert(await badge.isVisible(),'Unassigned hires remain selectable while the roster is reserved');if(await badge.isDisabled())assert.match(await badge.getAttribute('title'),/finishes its current work/);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));await page.waitForFunction(()=>!document.querySelector('#studio-crew-model').disabled);
  await label(pixel).click();await selected('Pixel');assert(await badge.isEnabled());assert(await page.locator('#studio-crew-chat').isVisible(),'Completed participant keeps its existing contribution view');
  await label(orbit).click();await selected('Orbit');await page.locator('.world-room-map [data-world-room="lounge"]').click();await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().navigation.travelling);
  await navigate('event-brief');assert.notEqual(await page.locator('#studio-crew-name').innerText(),'Orbit');assert(await badge.isDisabled());assert(await page.locator('#studio-crew-chat').isVisible());
  await navigate('plan');await selected('Casey');assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,host,checks:['pre-plan name and mesh selection','keyboard selection','idle model edit targets only selected hire','selection survives polling','reload preserves model','Casey draft preserved','assigned/idle lock isolation','completed contribution view','Lounge and Event Brief navigation','no browser errors']}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
