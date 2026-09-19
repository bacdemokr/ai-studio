// Real renderer/UI; disposable model fixture. Navigation must preserve agent state.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  const settled=()=>page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const nav=()=>page.evaluate(()=>BacCampus.inspect().navigation);
  const go=async room=>{await page.locator('.world-room-map [data-world-room='+room+']').click();await settled();};
  await settled();
  assert.deepEqual((await nav()).visibleRooms,['workshop','lounge','mission']);
  assert.equal((await nav()).doorways.length,6);
  await page.locator('#studio-name').fill('Connected Scout');await page.locator('[data-avatar-color=cyan]').click();
  const layout=await nav();
  assert.deepEqual(layout.rooms,{workshop:[0,0,18],lounge:[0,0,0],mission:[24,0,0]});
  assert.equal(layout.corridors.length,3);
  const pairs=new Set(layout.doorways.map(d=>d.from+'>'+d.to));
  for(const from of Object.keys(layout.rooms))for(const to of Object.keys(layout.rooms))if(from!==to)assert(pairs.has(from+'>'+to),'missing direct door '+from+'>'+to);
  const start=layout.focus[2];
  await page.locator('.world-doorway[data-doorway-from=workshop][data-world-room=lounge]').click();
  assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'lounge');
  await page.waitForFunction(x=>{const n=BacCampus.inspect().navigation;return n.travelling&&n.focus[2]<x-.5&&n.focus[2]>1.1},start);
  await settled();assert.equal((await nav()).focus[0],0);
  await go('workshop');assert.equal(await page.locator('#studio-name').inputValue(),'Connected Scout');assert.equal(await page.locator('[data-avatar-color=cyan]').getAttribute('aria-pressed'),'true');
  await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Connected Scout');await settled();await page.locator('#studio-alert button').click();
  const identity=await page.evaluate(()=>BacStudio.inspect().agentId);
  assert.equal(await page.locator('[data-resident]').count(),1);
  // Every room remains in the floor plan. Overview and doors stay inside fullscreen.
  await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
  await page.locator('button[data-world-overview]').click();await settled();assert((await nav()).overview);
  assert.equal(await page.locator('.world-campus-room:visible').count(),3);
  await page.locator('.world-campus-room[data-world-room=mission]').click();await settled();
  assert.equal(await page.evaluate(()=>document.fullscreenElement?.id),'agent-campus');assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'mission');
  await page.locator('.world-doorway[data-doorway-from=mission][data-world-room=lounge]').click();await settled();
  assert.equal(await page.evaluate(()=>document.fullscreenElement?.id),'agent-campus');assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),identity);
  // Visit every directed doorway, including the new direct Onboarding–BaC route.
  for(const next of ['workshop','mission','workshop','lounge','mission','lounge']){
   const from=await page.evaluate(()=>BacStudio.inspect().room);
   await page.locator('.world-doorway[data-doorway-from='+from+'][data-world-room='+next+']').click();
   assert.equal(await page.evaluate(()=>BacStudio.inspect().room),next);
   await settled();assert.equal(await page.evaluate(()=>document.fullscreenElement?.id),'agent-campus');assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),identity);
  }
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);
  const before=await page.locator('#campus-viewport').boundingBox();await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);await page.waitForTimeout(150);
  const after=await page.locator('#campus-viewport').boundingBox();assert(Math.abs(before.height-after.height)<1);
  // A newer destination replaces an in-flight trip; pauses stop robots, not navigation.
  await page.locator('#campus-motion').click();
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.locator('.world-room-map [data-world-room=workshop]').click();await settled();
  assert.deepEqual((await nav()).focus,[0,1,18.6]);assert.equal(await page.evaluate(()=>BacCampus.inspect().motion),false);
  for(const width of [1280,736,390]){
   await page.setViewportSize({width,height:950});
   for(const room of ['lounge','mission','workshop']){
    await go(room);assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'overflow '+width+' '+room);
    const doors=await page.locator('.world-doorway:visible').all();assert.equal(doors.length,2);
    const boxes=await Promise.all(doors.map(d=>d.boundingBox()));
    const [a,b]=boxes;assert(a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y,'overlapping doors '+width+' '+room+' '+JSON.stringify(boxes));
   }
   await page.locator('button[data-world-overview]').click();await settled();
   const viewport=await page.locator('#campus-viewport').boundingBox();
   const hud=await page.locator('button[data-world-overview]').boundingBox();
   for(const card of await page.locator('.world-campus-room').all()){
    const box=await card.boundingBox();assert(box.x>=viewport.x-1&&box.x+box.width<=viewport.x+viewport.width+1,'overview label outside viewport');
    assert(box.y>=hud.y+hud.height||box.x>=hud.x+hud.width||box.x+box.width<=hud.x,'overview label overlaps navigation control: '+JSON.stringify({width,box,hud}));
   }
   await go('lounge');
  }
  await page.emulateMedia({reducedMotion:'reduce'});await go('mission');assert(!(await nav()).travelling);assert.equal((await nav()).focus[0],24);
  await page.locator('button[data-room=policies]').click();assert(await page.locator('#studio-policies').isVisible());await page.locator('button[data-room=lounge]').click();assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),identity);
  assert.deepEqual(errors,[]);
  console.log('PASS: L-shaped rooms, all six direct doorways, three physical corridors, interpolated camera travel, persistent drafts/identity, overview selection, doorway navigation in fullscreen, rapid navigation, pause/reduced motion, responsive room labels and Policies return.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
