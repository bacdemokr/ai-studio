// Exercise real layout rules: DOM-only timer tests cannot detect fullscreen CSS hiding it.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let withPlan=true;
  const job={id:'timer-fixture',created:Date.now()/1000-34,status:'running',payload:{prompt:'/plan Test timer',collaboration:{task:'Test timer',activeRole:0,outputs:{},handoffs:{},checks:[],tasks:[],calledRoles:[]}},events:[]};
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,async route=>{
   const response=await route.fetch(),state=await response.json();
   await route.fulfill({json:{...state,profile:{name:'Sage',skills:[],persona:'maker',avatar:{body:'classic',color:'green'}},crewChats:withPlan?[job]:[],crewChatReset:{}}});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8197');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const timer=page.locator('#studio-team-total-time');
  async function check(){await timer.waitFor({state:'visible'});const r=await timer.boundingBox();assert(r.width>0);assert(await timer.evaluate(e=>e.previousElementSibling?.id==='studio-crew-name'));assert.equal(await timer.evaluate(e=>getComputedStyle(e).position),'static');}
  await check();
  await page.locator('#studio-focus').click();
  await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
  await page.locator('[data-campus-agent="0"]').click();
  async function noOverlap(){
   const t=await timer.boundingBox();
   for(const selector of ['[data-surface="deliverables"]','[data-surface="control"]','#studio-bac-reset']){
    const b=await page.locator(selector).boundingBox();assert(b,'Action must remain visible');
    assert(t.x+t.width<=b.x||b.x+b.width<=t.x||t.y+t.height<=b.y||b.y+b.height<=t.y,'Timer covers '+selector);
   }
  }
  await noOverlap();
  for(const width of [1100,1920]){await page.setViewportSize({width,height:1000});await noOverlap();}
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-surface="deliverables"]').click();
  await page.locator('#studio-surface').waitFor({state:'visible'});
  await page.locator('#studio-surface-close').click();
  await page.locator('[data-surface="control"]').click();
  assert.equal(await timer.getAttribute('popover'),null);
  await page.locator('#studio-surface-close').click();await check();
  await page.locator('#studio-crew-conversation').evaluate(e=>e.scrollTop=e.scrollHeight);await check();
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);await check();
  withPlan=false;await page.evaluate(()=>BacStudio.refresh());await timer.waitFor({state:'hidden'});
  assert.match(await page.locator('.campus-agent-label[data-crew-member="0"]').innerText(),/Casey/);
  assert.equal(await page.locator('#studio-crew-name').innerText(),'Casey');
  assert(!await page.locator('.campus-agent-label[data-crew-member="0"]').innerText().then(s=>s.includes('Sage')));
  assert.deepEqual(errors,[]);console.log('PASS: inline timer normal/fullscreen/scroll/reset and personal name cannot replace Casey');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
