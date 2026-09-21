// Focused route regression; use a disposable fixture on port 8082.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');
  await page.waitForFunction(()=>window.BacCampus&&window.BacStudio?.inspect().runtime.testFixture);
  const settled=()=>page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const click=id=>page.locator('.world-room-map [data-world-room='+id+']').click();
  await settled();await click('workshop');await settled();
  const nav=await page.evaluate(()=>BacCampus.inspect().navigation);
  assert.equal(nav.corridors.length,2);assert.equal(nav.doorways.length,4);
  assert(!nav.doorways.some(d=>d.from!=='lounge'&&d.to!=='lounge'));
  for(const [from,to] of [['workshop','mission'],['mission','workshop']]){
   await click(to);
   await page.waitForFunction(([from,to])=>{const n=BacCampus.inspect().navigation;return n.route.length===2&&n.route[0].from===from&&n.route[0].to==='lounge'&&n.route[1].to===to;},[from,to]);
   await page.waitForFunction(to=>{const n=BacCampus.inspect().navigation;return n.route.length===1&&n.route[0].from==='lounge'&&n.route[0].to===to;},to);
   await settled();
   assert.equal(await page.evaluate(()=>BacCampus.inspect().room),to);
  }
  // Changing one's mind mid-trip stays on the current corridor and clears stale destinations.
  await click('mission');await click('workshop');await settled();
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().navigation.focus),[0,1,18.6]);
  await page.emulateMedia({reducedMotion:'reduce'});await click('mission');await settled();
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().navigation.focus),[24,.25,.6]);
  assert.deepEqual(errors,[]);
  console.log('PASS: two roads/four doors, 1→2→3 and 3→2→1, interrupted travel, reduced motion.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
