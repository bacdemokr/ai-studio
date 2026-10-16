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
  assert.equal(await page.locator('#studio-skill-picker input[value="data-analysis"]').isVisible(),true);
  assert.equal(await page.locator('#studio-skill-picker input[value="interface-design"]').isVisible(),true);
  await page.getByRole('button',{name:/^Playful/}).click();
  const selected=()=>page.locator('#studio-skill-picker input:checked').evaluateAll(nodes=>nodes.map(n=>n.value));
  const cases=[['Programmer',['builder']],['Web researcher',['web']],['Data analyst',['data-analysis']],['Arxivbot',['web']],['Weather buddy',['weather']],['Tech Radar',['radar']],['Slack Announcer',['writer']]];
  for(const [name,skills] of cases){
   await page.getByRole('button',{name,exact:true}).click();assert.deepEqual(await selected(),skills);
   const fixed=await page.locator('#studio-skill-picker input:disabled').evaluateAll(nodes=>nodes.map(n=>n.value));
   assert.deepEqual(fixed,['Programmer','Web researcher','Data analyst'].includes(name)?skills:[],name+' fixed skill');
   if(fixed.length){await page.locator('#studio-skill-picker input[value="'+fixed[0]+'"]').evaluate(input=>input.click());assert.deepEqual(await selected(),skills,'Fixed skill cannot be unchecked');}
   await page.locator('#studio-apply-prompt').click();assert.deepEqual(await selected(),skills,name+' must retain its own skills after Apply');
   assert.match(await page.locator('#studio-purpose').inputValue(),/Playful/);
  }
  for(const role of ['I am a programmer.','Help me with coding.','Help me with programming.']){
   await page.locator('#studio-purpose').fill('Tone: Playful (Light & witty)\nRole: '+role);
   await page.locator('#studio-apply-prompt').click();assert.deepEqual(await selected(),['builder'],role);
  }
  await page.getByRole('button',{name:'Programmer',exact:true}).click();await page.locator('#studio-apply-prompt').click();
  await page.locator('#studio-skill-picker input[value="web"]').check();
  await page.locator('#studio-apply-prompt').click();assert.deepEqual(await selected(),['web','builder'],'Apply preserves extra skills');
  await page.locator('#studio-skill-picker input[value="web"]').uncheck();
  await page.locator('#studio-name').fill('Jinny');await page.locator('input[name=protection][value=standard]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&BacStudio.inspect().profile?.name==='Jinny');
  const original=await page.evaluate(()=>BacStudio.inspect().profile);assert.deepEqual(original.skills,['builder']);assert.equal(original.tone,'playful');
  await page.locator('#studio-edit-agent').click();await page.getByRole('button',{name:'Web researcher',exact:true}).click();await page.locator('#studio-apply-prompt').click();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.join(',')==='web');assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.tone),'playful');
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.join(',')==='web');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-skill-picker input[value="web"]').isDisabled(),true);
  await page.locator('#studio-skill-picker input[value="data-analysis"]').check();
  await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.includes('data-analysis'));
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-skill-picker input[value="web"]').isDisabled(),true);
  assert.equal(await page.locator('#studio-skill-picker input[value="data-analysis"]').isChecked(),true);
  if(process.env.BAC_TEST_ARTIFACT_DIR)await page.locator('#studio-skill-picker').screenshot({path:process.env.BAC_TEST_ARTIFACT_DIR+'/fixed-skills.png'});
  await page.getByRole('button',{name:'Data analyst',exact:true}).click();
  await page.locator('#studio-name').fill('Dana');
  await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Dana'&&BacStudio.inspect().profile?.skills.join(',')==='data-analysis');
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.join(',')==='data-analysis');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-skill-picker input[value="data-analysis"]').isDisabled(),true);
  assert.equal(await page.locator('#studio-skill-picker input[value="web"]').isDisabled(),false);
  await page.locator('#studio-skill-picker input[value="builder"]').check();
  await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.includes('builder'));
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-skill-picker input[value="data-analysis"]').isDisabled(),true);
  assert.equal(await page.locator('#studio-skill-picker input[value="builder"]').isChecked(),true);
  await page.locator('#studio-purpose').fill('Tone: Playful (Light & witty)\nRole: Help me think through everyday decisions.');
  assert.equal(await page.locator('#studio-skill-picker input:disabled').count(),0);
  for(const box of await page.locator('#studio-skill-picker input').all())await box.setChecked(false);
  await page.locator('#studio-create').click();await page.locator('#studio-onboarding').waitFor({state:'hidden'});
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.length===0);
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.length===0);
  assert.deepEqual(errors,[]);console.log('PASS: fixed Programmer/Coding, Web researcher/Web research and Data analyst/Data interpretation; extra skills; role switching; all 7 presets; analyst save/reload; custom no-skill create/edit/reload.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
