// Real UI/HTTP with isolated data and simulated inference. Never changes the live demo.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process'),{chromium}=require('playwright');
const presets=JSON.parse(execFileSync('python3',['-c','import sys,json;sys.path.insert(0,"scripts");from role_boundaries import ROLE_TEMPLATES;print(json.dumps(ROLE_TEMPLATES))'],{encoding:'utf8'}));
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18327),server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1050},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const shot=async(name,locator)=>{if(process.env.BAC_TEST_ARTIFACT_DIR){fs.mkdirSync(process.env.BAC_TEST_ARTIFACT_DIR,{recursive:true});await locator.screenshot({path:path.join(process.env.BAC_TEST_ARTIFACT_DIR,name+'.png')});}};
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>BacStudio?.inspect().runtime.personalModels);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.match(await page.locator('#studio-tone-prompt').inputValue(),/[가-힣]/);
  assert.equal(await page.locator('#studio-purpose').inputValue(),presets[0].purpose);
  assert.equal(await page.locator('#studio-body-picker button').count(),9);
  const catalog=require('../src/avatar-catalog.json');
  for(const body of catalog.bodies){
   await page.locator('[data-body="'+body.id+'"]').first().click();
   assert.equal(await page.locator('#studio-name').inputValue(),body.name,'Character default name: '+body.id);
  }
  await page.locator('[data-body=classic]').first().click();
  assert.equal(await page.locator('#studio-name').inputValue(),'스파크');

  for(const tone of ['kind','direct','playful','cynical']){
   await page.locator('[data-tone='+tone+']').click();assert.match(await page.locator('#studio-tone-prompt').inputValue(),/[가-힣]/);
  }
  for(const preset of presets){
   await page.getByRole('button',{name:preset.label,exact:true}).click();
   assert.equal(await page.locator('#studio-purpose').inputValue(),preset.purpose);
   assert.match(preset.label,/[가-힣]/);
  }
  await page.locator('#studio-tone-prompt').scrollIntoViewIfNeeded();await shot('hiring-tone-role',page.locator('#studio-workshop'));
  const paper=page.locator('.world-room-paper:not(.world-term-paper)'),term=page.locator('.world-term-paper');
  await page.locator('[data-room-info=workshop]').click();
  assert.match(await paper.innerText(),/모습과 이름, 말투와 역할/);
  for(const name of ['agent','skill','openshell']){
   await page.locator('[data-paper-term='+name+']').click();
   assert.match(await term.locator('h2').innerText(),/[가-힣]/);
   const paragraphs=await term.locator('.world-term-paper-body p').allTextContents();
   assert(paragraphs.every(text=>/[가-힣]/.test(text)));
   if(name==='agent')assert.match(await term.locator('.agent-blueprint').innerText(),/역할과 말투/);
   if(name==='openshell')assert.match(await term.locator('pre').innerText(),/openshell sandbox create/);
   await shot('guide-'+name,term);await page.keyboard.press('Escape');
  }
  await shot('guide-hiring',paper);await page.keyboard.press('Escape');
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-room-info=lounge]').click();assert.match(await paper.innerText(),/고용한 에이전트와 대화/);await shot('guide-lounge',paper);await page.keyboard.press('Escape');
  await page.locator('.world-room-map [data-world-scenario=plan]').click();await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='plan'&&!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-room-info=mission]').click();assert.match(await paper.innerText(),/기본값인 “고용한 에이전트만”/);await shot('guide-open-task',paper);await page.keyboard.press('Escape');
  assert.equal(await page.locator('[data-goal-example]').count(),6);assert.equal(await page.locator('[data-goal-example=stores]').count(),0);
  await page.locator('#studio-crew-model').click();assert.equal(await page.locator('.team-model-dialog h3').evaluate(e=>getComputedStyle(e).fontSize),'22px');await page.keyboard.press('Escape');
  // Existing English presets stay recognized without rewriting saved custom content.
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const programmer=presets.find(p=>p.requiredSkills.includes('builder'));
  await page.getByRole('button',{name:programmer.label,exact:true}).click();await page.locator('#studio-name').fill('한글 도우미');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='한글 도우미'&&!BacCampus.inspect().arrival&&!BacCampus.inspect().navigation.travelling);
  const setProfile=async update=>{
   const status=await page.evaluate(async update=>{const s=await(await fetch('/api/session')).json();return (await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Agent':BacStudio.inspect().agentId},body:JSON.stringify({...BacStudio.inspect().profile,...update})})).status;},update);
   assert.equal(status,200);await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile);
   await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  };
  const legacy=programmer.purposeAliases[0];
  await setProfile({purpose:legacy,tone:'cynical',tonePrompt:'Cynical (Dry humor & skepticism)'});
  await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-purpose').inputValue(),programmer.purpose);
  assert.equal(await page.locator('#studio-tone-prompt').inputValue(),'시니컬하게 (건조한 유머와 의심)');
  assert(await page.locator('#studio-skill-picker input[value=builder]').isDisabled());
  await page.locator('#studio-cancel-create').click();assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.purpose),legacy);
  const custom={purpose:'내 작업을 한 단계씩 정리해줘.\n추측하지 말고 먼저 물어봐줘.',tonePrompt:'차분하게.\nAnswer in English only when asked.'};
  await setProfile(custom);await page.locator('#studio-edit-agent').click();
  assert.equal(await page.locator('#studio-purpose').inputValue(),custom.purpose);assert.equal(await page.locator('#studio-tone-prompt').inputValue(),custom.tonePrompt);
  await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.tonePrompt.includes('Answer in English'));
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.purpose),custom.purpose);
  assert.deepEqual(errors,[]);console.log('PASS: Korean default tones/roles, all three room guides and glossary, six Korean goals, latest visitor appearance/model UI, legacy English preset recognition, custom prose preserved.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
