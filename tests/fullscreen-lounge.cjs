// Temporary HTTP fixture: dialogs remain within the fullscreen studio.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:960}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/agent-policy',route=>route.fulfill({json:{status:'applied',requested:[],catalog:{},pendingAccess:[],sandboxes:['fixture']}}));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8097');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture&&!document.querySelector('#agent-campus').dataset.boot);
  const travel=async room=>{await page.locator('.world-room-map [data-world-room='+room+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);};
  const stillFull=async()=>assert(await page.locator('#agent-campus').evaluate(n=>n.classList.contains('studio-world-open')));
  await travel('workshop');await page.locator('#studio-focus').click();
  await page.locator('#studio-body-picker [data-body=claw]').click();
  await page.locator('#studio-name').fill('Fullscreen Pixel');
  await page.locator('input[name=protection][value=openshell]').check();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Fullscreen Pixel'&&BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival);
  await stillFull();assert(await page.locator('#studio-passport').isVisible());
  await page.locator('#studio-agent-policy').click();
  await page.waitForSelector('#studio-policy-content [data-policy-section]');
  assert.equal(await page.locator('#studio-surface-title').innerText(),'OpenShell Policy');await stillFull();
  assert(await page.locator('#studio-surface').evaluate(n=>document.getElementById('agent-campus').contains(n)));
  await page.locator('#studio-surface-close').click();
  await page.locator('#studio-config').click();await page.waitForSelector('#studio-config-form');await stillFull();
  assert(await page.locator('#studio-dialog').evaluate(n=>document.getElementById('agent-campus').contains(n)));
  await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-name').fill('Fullscreen Pixel edited');
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Fullscreen Pixel edited'&&BacStudio.inspect().room==='lounge');await stillFull();
  await page.screenshot({path:'/tmp/bac-fullscreen-lounge.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS: current avatars, protected Hiring, policy dialog, Settings and editing preserve fullscreen');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
