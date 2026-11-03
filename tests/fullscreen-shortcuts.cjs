// Real keyboard navigation with isolated data and simulated model connections.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=18312,server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','pipe']});let browser;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('READY')){clearTimeout(timer);resolve();}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  for(const fallback of [false,true]){
   const context=await browser.newContext({viewport:{width:1500,height:960}}),page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(12000);
   if(fallback)await page.addInitScript(()=>{Element.prototype.requestFullscreen=()=>Promise.reject(new Error('Fullscreen fixture fallback'));});
   await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.personalModels);
   const room=()=>page.evaluate(()=>BacStudio.inspect().room);
   const settled=next=>page.waitForFunction(next=>BacStudio.inspect().room===next&&!BacCampus.inspect().navigation.travelling,next);
   const focusView=()=>page.locator('#campus-viewport').focus();
   await page.locator('.world-room-map [data-world-room=workshop]').click();await settled('workshop');await focusView();
   await page.keyboard.press('Shift+Digit2');assert.equal(await room(),'workshop','Shortcut is fullscreen-only');
   await page.locator('#studio-focus').click();
   if(!fallback)await page.waitForFunction(()=>!!document.fullscreenElement);
   assert(await page.locator('#agent-campus').evaluate(e=>e.classList.contains('studio-world-open')));
   assert.equal(await page.evaluate(()=>!!document.fullscreenElement),!fallback);
   await page.keyboard.press('Shift+Digit2');await settled('lounge');
   await page.keyboard.press('Shift+Digit3');await settled('mission');
   assert.equal(await page.evaluate(()=>BacCampus.inspect().navigation.activeScenario),'plan');
   await page.keyboard.press('Shift+Digit1');await settled('workshop');
   await page.locator('#studio-name').fill('Draft');await page.keyboard.press('Shift+Digit2');
   assert.equal(await room(),'workshop','Typing must not navigate');assert.equal(await page.locator('#studio-name').inputValue(),'Draft@');
   const text=page.locator('#studio-purpose');await text.fill('Role');await page.keyboard.press('Shift+Digit3');
   assert.equal(await room(),'workshop');assert.equal(await text.inputValue(),'Role#');
   await page.evaluate(()=>{const e=document.createElement('div');e.id='shortcut-editable';e.contentEditable='true';document.getElementById('agent-campus').append(e);e.focus();});
   await page.keyboard.press('Shift+Digit2');assert.equal(await room(),'workshop');await page.locator('#shortcut-editable').evaluate(e=>e.remove());
   await focusView();
   for(const modifiers of [{repeat:true},{isComposing:true},{ctrlKey:true},{altKey:true},{metaKey:true}]){
    await page.locator('#campus-viewport').evaluate((e,m)=>e.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'@',code:'Digit2',shiftKey:true,...m})),modifiers);
    assert.equal(await room(),'workshop');
   }
   await page.locator('#studio-config').click();await page.locator('#studio-dialog').waitFor({state:'visible'});
   await page.locator('#studio-dialog-close').focus();await page.keyboard.press('Shift+Digit2');
   assert.equal(await room(),'workshop','Dialogs must not navigate behind the modal');await page.locator('#studio-dialog-close').click();
   await focusView();await page.keyboard.press('Shift+Digit2');await settled('lounge');
   assert(await page.locator('#agent-campus').evaluate(e=>e.classList.contains('studio-world-open')),'Navigation preserves fullscreen');
   await page.locator('#studio-focus').click();await focusView();await page.keyboard.press('Shift+Digit1');assert.equal(await room(),'lounge','Shortcut stops on fullscreen exit');
   assert.deepEqual(errors,[]);await context.close();
   console.log('PASS: '+(fallback?'fallback':'native')+' fullscreen stage shortcuts, typing/dialog/IME/modifier/repeat guards, normal navigation and exit.');
  }
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
