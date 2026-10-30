// Real UI/WebGL with controlled API snapshots; never runs a model request.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18289),server=spawn('python3',['-B','tests/fixture_visitor_teams.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('VISITOR FIXTURE READY')){clearTimeout(t);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  for(const [name,role] of [['Jinny','프로그래머'],['Orbit','웹 조사원']]){
   await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill(name);
   await page.getByRole('button',{name:role,exact:true}).click();await page.locator('input[name=protection][value=standard]').check();
   await page.locator('#studio-create').click();await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().room==='lounge',name);
  }
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const select=async name=>page.evaluate(name=>{const key=BacStudio.inspect().agents.find(a=>a.name===name).key;document.getElementById('agent-campus').dispatchEvent(new CustomEvent('bac:collection-select',{detail:key}));},name);
  await select('Jinny');
  await page.locator('#studio-crew-edit-agent').click();
  await page.locator('#studio-onboarding').waitFor({state:'visible'});
  assert.equal(await page.locator('#studio-name').inputValue(),'Jinny');
  assert.equal(await page.locator('#studio-skill-picker input[value=builder]').isDisabled(),true);
  await page.locator('#studio-name').fill('Jinny Updated');
  await page.locator('#studio-create').click();
  await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'mission');
  assert.equal(await page.locator('#studio-crew-name').textContent(),'Jinny Updated');
  assert.match(await page.locator('#studio-crew-agent-skills').textContent(),/Coding/);
  await select('Orbit');await page.locator('#studio-crew-edit-agent').click();
  await page.locator('#studio-onboarding').waitFor({state:'visible'});
  assert.equal(await page.locator('#studio-name').inputValue(),'Orbit');
  await page.locator('#studio-cancel-create').click();
  assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'mission');
  await page.screenshot({path:'/tmp/stage3-agent-controls.png'});
  await page.locator('#studio-crew-instructions').click();
  await page.locator('#studio-identity-viewer .studio-identity-heading').waitFor();
  assert.equal(await page.locator('#studio-identity-viewer h3').textContent(),'Orbit');
  await page.keyboard.press('Escape');
  await page.route('**/api/state*',async route=>{const headers={...route.request().headers()};delete headers['if-none-match'];const response=await route.fetch({headers}),body=await response.json();body.agents.forEach(a=>a.pending=1);await route.fulfill({response,json:body});});
  await page.evaluate(()=>BacStudio.refresh());
  assert.equal(await page.locator('#studio-crew-edit-agent').isDisabled(),true);
  assert.deepEqual(errors,[]);
  console.log('PASS: Stage 3 correct hired target, fixed skills, save/cancel stays in Open Task, updated badges, instructions, busy edit lock. Isolated browser fixture.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});
