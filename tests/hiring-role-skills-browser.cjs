// Actual Hiring controls, simulated model connection; no inference or external sends.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18246);
 const server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-room=workshop]').click();
  await page.getByRole('button',{name:/^Playful/}).click();
  const selected=()=>page.locator('#studio-skill-picker input:checked').evaluateAll(nodes=>nodes.map(n=>n.value));
  const cases=[['Programmer',['builder']],['Web researcher',['web']],['Arxivbot',['web']],['Weather buddy',['weather']],['Tech Radar',['radar']],['Slack Announcer',['writer']]];
  for(const [name,skills] of cases){
   await page.getByRole('button',{name,exact:true}).click();assert.deepEqual(await selected(),skills);
   await page.locator('#studio-apply-prompt').click();assert.deepEqual(await selected(),skills,name+' must retain its own skills after Apply');
   assert.match(await page.locator('#studio-purpose').inputValue(),/Playful/);
  }
  for(const role of ['I am a programmer.','Help me with coding.','Help me with programming.']){
   await page.locator('#studio-purpose').fill('Tone: Playful (Light & witty)\nRole: '+role);
   await page.locator('#studio-apply-prompt').click();assert.deepEqual(await selected(),['builder'],role);
  }
  await page.getByRole('button',{name:'Programmer',exact:true}).click();await page.locator('#studio-apply-prompt').click();
  await page.locator('#studio-name').fill('Jinny');await page.locator('input[name=protection][value=standard]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&BacStudio.inspect().profile?.name==='Jinny');
  const original=await page.evaluate(()=>BacStudio.inspect().profile);assert.deepEqual(original.skills,['builder']);assert.equal(original.tone,'playful');
  await page.locator('#studio-edit-agent').click();await page.getByRole('button',{name:'Web researcher',exact:true}).click();await page.locator('#studio-apply-prompt').click();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.join(',')==='web');assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.tone),'playful');
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.join(',')==='web');
  assert.deepEqual(errors,[]);console.log('PASS: all 6 presets preserve skill selection after Apply; custom programmer/coding/programming; create/edit/reload preserve role, tone and skills.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
