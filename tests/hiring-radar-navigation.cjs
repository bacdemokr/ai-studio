// Disposable scenario fixture: real UI/3D, no live models or attendee data.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  // Hiring catches exceptions and shows a toast, so pageerror alone misses regressions.
  await page.exposeFunction('recordHiringError',message=>errors.push(message));
  await page.addInitScript(()=>{
   new MutationObserver(()=>{
    const notice=document.querySelector('#studio-alert');
    if(notice&&!notice.hidden&&notice.dataset.kind==='error'){
     const message=notice.querySelector('.studio-alert-message')?.textContent;
     if(message&&message!==window.lastHiringError){window.lastHiringError=message;window.recordHiringError(message);}
    }
   }).observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','data-kind']});
  });
  const base=process.env.BASE_URL||'http://127.0.0.1:8083';
  await page.goto(base);await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  async function room(id){
   await page.locator('.world-room-map [data-world-room='+id+']').click();
   await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  }
  async function preview(){
   assert.deepEqual(errors,[],'no caught Hiring errors or uncaught scene errors');
   const scene=await page.evaluate(()=>BacCampus.inspect());
   assert.equal(scene.draftPreview?.visible,true,'Hiring must have an attached, visible character');
   assert.deepEqual(scene.draftPreview.avatar,{...scene.draft.avatar,protection:scene.draft.protection||'standard'});
  }
  await room('workshop');
  await page.locator('#studio-body-picker [data-body=round]').click();
  await page.locator('#studio-color-picker [data-avatar-color=coral]').click();
  // The role stays Weather buddy; Heartbeat comes from the additional skill.
  await page.locator('#studio-skill-picker input[value=radar]').check();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='loading');
  const radar=await page.evaluate(()=>BacStudio.inspect().agentId);
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.locator('.world-room-map [data-world-room=workshop]').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-onboarding').inert&&!BacCampus.inspect().navigation.travelling);
  await preview();
  assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'workshop');
  assert.equal(await page.locator('.studio-heartbeat-status').count(),1,'Heartbeat is mounted even in Hiring');

  for(const body of ['classic','round','rover','operative','claw','crab']){
   await page.locator('#studio-body-picker [data-body='+body+']').click();await preview();
   assert.equal(await page.evaluate(()=>BacCampus.inspect().draftPreview.avatar.body),body);
  }
  for(const tone of ['kind','direct','playful','cynical']){
   const button=page.locator('#studio-tone-picker [data-tone='+tone+']');await button.click();
   assert.equal(await button.getAttribute('aria-pressed'),'true');await preview();
  }
  assert.equal(await page.locator('.studio-heartbeat-status').getAttribute('aria-pressed'),null);

  // A subsequent non-Radar agent leaves the old monitor mounted but hidden.
  await page.locator('#studio-name').fill('Follow-up helper');
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().arrival,null,{timeout:20000});
  assert.equal(await page.locator('#studio-radar-monitor').isVisible(),false);
  assert.equal(await page.locator('.studio-heartbeat-status').count(),1);
  await page.locator('#studio-edit-agent').click();
  await page.locator('#studio-body-picker [data-body=operative]').click();
  await page.locator('#studio-tone-picker [data-tone=direct]').click();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.avatar.body==='operative'&&BacStudio.inspect().profile?.tone==='direct');
  await preview();

  await page.locator('#studio-agent-list [data-agent-key="'+radar+'"]').click();
  await page.waitForFunction(key=>BacStudio.inspect().agentId===key,radar);
  await page.locator('#studio-radar-monitor button').click();
  await page.waitForFunction(()=>document.querySelector('.studio-heartbeat-status')?.textContent==='Paused');
  await page.locator('#studio-edit-agent').click();
  await page.locator('#studio-tone-picker [data-tone=playful]').click();
  await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.tone==='playful');
  await room('workshop');await preview();
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.skills.includes('radar'));
  await room('workshop');await preview();
  assert.equal(await page.locator('.studio-heartbeat-status').getAttribute('data-heartbeat-state'),'paused');
  assert.deepEqual(errors,[]);
  console.log('PASS: mixed-skill Radar hire, immediate Lounge/Hiring return, six avatars/four tones, next hire, hidden Heartbeat, editing, pause and reload keep the draft visible with no errors.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
