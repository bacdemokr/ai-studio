// Real HTTP/UI journey with simulated inference. Does not use a live model or user data.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=18244,server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('#studio-config').click();await page.locator('[data-connection-edit=local]').click();
  await page.locator('#studio-connect-model').fill('fixture-b');await page.locator('#studio-connect-apply').click();await page.waitForFunction(()=>document.querySelector('#studio-connect-status').textContent==='Connected.');await page.locator('#studio-dialog-close').click();
  await page.evaluate(()=>BacStudio.setRoom('workshop'));assert.equal(await page.locator('#studio-agent-model-summary').innerText(),'Local');
  await page.locator('#studio-name').fill('Pixel');await page.getByRole('button',{name:'Programmer',exact:true}).click();await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.model),'local');
  const key=await page.evaluate(()=>BacStudio.inspect().agentId),badge=page.locator('#studio-crew-model'),picker=page.locator('.team-model-dialog');
  let hasPlan=false;
  async function enterTask(){await page.locator('.world-room-map [data-world-scenario="plan"]').click();await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan'&&!BacCampus.inspect().navigation.travelling);await page.locator(hasPlan?'[data-campus-agent="5"]':'[data-visitor-agent="'+key+'"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');}
  async function lounge(){await page.locator('.world-room-map [data-world-room="lounge"]').click();await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().navigation.travelling);}
  async function chat(prompt,expected,team=false){await page.locator(team?'#studio-crew-prompt':'#studio-prompt').fill(prompt);await page.locator(team?'#studio-crew-send':'#studio-send').click();await page.waitForFunction(text=>BacStudio.inspect().jobs?.some(j=>j.payload.prompt===text&&j.status==='done'),prompt);const job=await page.evaluate(text=>BacStudio.inspect().jobs.find(j=>j.payload.prompt===text),prompt);assert.equal(job.result.answer,'Simulated model: '+expected);assert.equal(job.payload.modelStage,team?'team':undefined);}
  async function pick(id,search){await badge.click();await picker.locator('input').fill(search);await picker.locator('[data-model-choice="'+id+'"]').click();await picker.waitFor({state:'hidden'});}
  await chat('Lounge before task','fixture-b');
  await enterTask();assert.equal(await badge.innerText(),'fixture-a');
  await page.locator('[data-campus-agent="0"]').click();await page.locator('#studio-crew-prompt').fill('/goal Have Pixel build a counter.');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('The team delivered the counter.')&&BacStudio.inspect().agents.every(a=>!a.pending));hasPlan=true;
  await page.locator('[data-campus-agent="5"]').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Pixel');
  await chat('Direct Open Task automatic','fixture-a',true);await lounge();await chat('Lounge after task','fixture-b');
  await enterTask();await pick('local','local');assert.match(await badge.innerText(),/^Local/);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.taskModel),'local');
  await badge.click();await picker.locator('input').fill('Automatic');assert.match(await picker.locator('[data-model-choice="auto"]').innerText(),/fixture-a/,'Automatic describes the API default, not the Local override');
  await picker.locator('[data-model-choice="auto"]').click();await picker.waitFor({state:'hidden'});assert.equal(await badge.innerText(),'fixture-a');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agents.find(a=>a.key===BacStudio.inspect().agentId).taskModel),undefined);
  await lounge();await page.locator('#studio-edit-agent').click();await page.locator('#studio-agent-model-panel summary').click();await page.locator('#studio-agent-model-search').fill('fixture-b');await page.locator('[data-agent-model-choice="api/nvidia/fixture-b"]').click();await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  await enterTask();assert.equal(await badge.innerText(),'fixture-b','Explicit hiring API model takes precedence over the API default');
  await pick('api/nvidia/fixture-a','fixture-a');assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.model),'api/nvidia/fixture-b');
  await lounge();await chat('Explicit API Lounge restored','fixture-b');
  await enterTask();assert.equal(await badge.innerText(),'fixture-a','The separate Open Task override persists on return');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['Both connections: default hire is Local','Lounge Local / Open Task API / Lounge Local','Direct chat captures the stage despite navigation','Manual Local override allowed','Automatic reset updates the displayed and saved choice','Explicit hiring API model preserved','Task override does not change Lounge model','Task override persists across visits','No browser errors']}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1;});
