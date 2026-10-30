// Isolated real UI/API/WebGL; simulated connection, no model or native runtime calls.
const assert=require('node:assert/strict'),fs=require('node:fs'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
const catalog=require('../src/avatar-catalog.json');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18318),server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1050},deviceScaleFactor:2,reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-body-picker button').count(),9);
  for(const body of catalog.bodies){
   await page.locator('#studio-body-picker [data-body="'+body.id+'"]').click();
   assert.deepEqual(await page.locator('#studio-color-picker button').evaluateAll(nodes=>nodes.map(n=>n.dataset.avatarColor)),body.palettes);
   assert.equal(await page.evaluate(()=>BacCampus.inspect().draftPreview.avatar.color),body.palettes[0]);
   if(process.env.BAC_TEST_ARTIFACT_DIR){
    fs.mkdirSync(process.env.BAC_TEST_ARTIFACT_DIR,{recursive:true});
    await page.locator('#studio-accessory').selectOption(body.id==='bunny'?'pestle':body.id.startsWith('hanbok-')?'norigae':'pouch');
    await page.waitForTimeout(250);
    await page.screenshot({path:process.env.BAC_TEST_ARTIFACT_DIR+'/'+body.id+'.png'});
   }
   for(const color of body.palettes){
    await page.locator('#studio-color-picker [data-avatar-color="'+color+'"]').click();
    assert.equal(await page.evaluate(()=>BacCampus.inspect().draftPreview.avatar.color),color);
    assert.equal(await page.locator('#studio-palette-name').textContent(),catalog.palettes[color].label);
    assert.match(await page.locator('#studio-color-picker [data-avatar-color="'+color+'"]').evaluate(e=>getComputedStyle(e).backgroundImage),/linear-gradient/);
   }
   assert.deepEqual(await page.locator('#studio-accessory option').evaluateAll(nodes=>nodes.map(n=>n.value)),['none',...body.accessories]);
   for(const accessory of body.accessories){
    await page.locator('#studio-accessory').selectOption(accessory);
    const draft=await page.evaluate(()=>BacCampus.inspect().draftPreview.avatar);
    assert.equal(draft.body,body.id);assert.equal(draft.accessory,accessory);
   }
   await page.locator('[name=protection][value=openshell]').check();assert.equal(await page.evaluate(()=>BacCampus.inspect().draftShield),true);
   await page.locator('[name=protection][value=standard]').check();assert.equal(await page.evaluate(()=>BacCampus.inspect().draftShield),false);
  }
  await page.locator('#studio-body-picker [data-body=classic]').click();await page.locator('#studio-accessory').selectOption('headset');
  await page.locator('#studio-body-picker [data-body=bunny]').click();assert.equal(await page.locator('#studio-accessory').inputValue(),'none');
  await page.locator('#studio-accessory').selectOption('scarf');await page.locator('#studio-body-picker [data-body="fox-companion"]').click();assert.equal(await page.locator('#studio-accessory').inputValue(),'scarf');
  const layout=[];
  for(const width of [1100,1500,1900]){
   await page.setViewportSize({width,height:1050});
   const picker=await page.locator('#studio-body-picker').boundingBox();assert(picker.height<=210,'Nine choices stay compact');
   assert.equal(await page.locator('#studio-body-picker').evaluate(e=>e.scrollWidth>e.clientWidth),false);
   assert.equal(await page.locator('.studio-appearance-details').evaluate(e=>e.scrollWidth>e.clientWidth),false);layout.push({width,height:picker.height});
  }
  await page.setViewportSize({width:1500,height:1050});
  if(process.env.BAC_TEST_ARTIFACT_DIR){fs.mkdirSync(process.env.BAC_TEST_ARTIFACT_DIR,{recursive:true});await page.locator('.studio-appearance').screenshot({path:process.env.BAC_TEST_ARTIFACT_DIR+'/picker.png'});fs.writeFileSync(process.env.BAC_TEST_ARTIFACT_DIR+'/layout.json',JSON.stringify(layout,null,2));}
  await page.locator('#studio-color-picker [data-avatar-color=fox-arctic]').click();
  await page.locator('#studio-name').fill('Rusty test');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Rusty test'&&BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival,null,{timeout:20000});
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.avatar.body),'fox-companion');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.avatar.color),'fox-arctic');
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-body-picker [data-body=bunny]').click();await page.locator('#studio-accessory').selectOption('carrot');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.avatar.body==='bunny');await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.avatar.accessory==='carrot');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.avatar.color),'bunny-snow');
  // Old outfits stay editable and survive unrelated edits, even when absent from the new menu.
  for(const avatar of [{body:'rover',color:'amber',accessory:'cap'},{body:'cat',color:'cyan',accessory:'antenna'}]){
   const status=await page.evaluate(async avatar=>{const s=await(await fetch('/api/session')).json();return (await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Agent':BacStudio.inspect().agentId},body:JSON.stringify({...BacStudio.inspect().profile,avatar})})).status;},avatar);assert.equal(status,200);
   await page.reload();await page.waitForFunction(a=>BacStudio.inspect().profile?.avatar.body===a.body,avatar);
   await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-edit-agent').click();assert.equal(await page.locator('#studio-accessory').inputValue(),avatar.accessory);
   assert.equal(await page.locator('#studio-color-picker [aria-pressed=true]').getAttribute('data-avatar-color'),avatar.color);
   if(avatar.body==='rover')assert(await page.locator('#studio-saved-appearance').isVisible());
   await page.locator('#studio-name').fill('Saved '+avatar.body);await page.locator('#studio-create').click();
   await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name,'Saved '+avatar.body);assert.deepEqual(await page.evaluate(()=>BacStudio.inspect().profile.avatar),avatar);
  }
  assert.deepEqual(errors,[]);console.log('PASS: nine compact choices, all character palettes, accessories and shields; hire/edit/reload and legacy outfits/colors preserved.');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});
