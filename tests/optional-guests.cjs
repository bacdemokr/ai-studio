const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',['-B','-c',`
import sys,json
sys.path.insert(0,'tests')
from test_demo_improvements import DemoImprovements
from event_planner import TEMPLATES,TOPICS,HARNESS,plan
c=DemoImprovements();c.setUp()
try:
 c.studio.configure(c.guest,dict(name='Scout',persona='analyst',skills=['weather']))
 c.studio.enqueue(c.guest,{'kind':'reminder','prompt':'A separate lounge task','delay':60})
 initial=c.studio.state(c.owner)
 prep=c.studio.prepare_demo(c.owner,{})
 c.run_next()
 prepared=c.studio.state(c.owner)
 b,capacity=plan({'schema':2,'themeCount':3})
 print(json.dumps({'initial':initial,'prepared':prepared,'catalog':{'templates':TEMPLATES,'topics':TOPICS,'harnesses':HARNESS},'plan':{'brief':b,'capacity':capacity},'prep':prep['id']}))
finally:c.doCleanups()
`],{encoding:'utf8'}));
 let state=fixture.initial,ready=false,fail=true;const requests=[],launches=[];
 const runtime=()=>({ready,model:ready,gateway:true,testFixture:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/session',r=>r.fulfill({json:{...state,runtime:runtime()}}));
  await page.route('**/api/state',r=>r.fulfill({json:state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:runtime()}));
  await page.route('**/api/event-catalog',r=>r.fulfill({json:fixture.catalog}));
  await page.route('**/api/event-plan',r=>r.fulfill({json:fixture.plan}));
  await page.route('**/api/prepare-demo',r=>{
   requests.push(r.request().postDataJSON());
   if(fail)return r.fulfill({status:409,json:{error:'The BaC crew is busy. Finish its current work first.'}});
   state=structuredClone(fixture.prepared);
   state.preparation.payload.enabledRoles=requests.at(-1).enabledRoles;
   return r.fulfill({json:{id:fixture.prep}});
  });
  await page.route('**/api/jobs',r=>{launches.push(r.request().postDataJSON());return r.fulfill({json:{id:'fixture-event-request'}});});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();await page.locator('#studio-demo-preparation').waitFor();
  assert.equal(requests.length,0);assert(await page.locator('#studio-launch-event').isDisabled());
  // Connecting after opening the form triggers the initial readiness check.
  ready=true;
  await page.locator('#studio-demo-preparation [role=alert]').waitFor({timeout:15000});
  assert.match(await page.locator('#studio-demo-preparation').innerText(),/BaC crew is busy/);
  await page.evaluate(()=>BacStudio.refresh());
  assert.match(await page.locator('#studio-demo-preparation').innerText(),/Needs attention/);
  assert.equal(requests.length,1,'Failure must not create an automatic retry loop');
  fail=false;await page.locator('#studio-prepare-demo').click();
  await page.waitForFunction(()=>!document.getElementById('studio-launch-event').disabled);
  const readiness=page.locator('#studio-demo-preparation');
  assert.match(await readiness.innerText(),/BaC crew.*Ready/s);
  assert.equal(await page.locator('[data-demo-guest]:disabled').count(),1);
  assert.equal(await page.locator('#studio-launch-event').innerText(),'Start the event plan');
  assert.match(await readiness.locator('.demo-guest[data-available=false]').innerText(),/Scout.*Busy/s);
  await page.locator('[data-demo-guest]:enabled').uncheck();
  await page.evaluate(()=>BacStudio.refresh());
  assert.equal(await page.locator('[data-demo-guest]:checked').count(),0);
  assert.deepEqual(requests.at(-1).enabledRoles,[0,1,2,3]);
  // Newly selected roles require a matching preparation; only selected roles are sent.
  await page.locator('[name=crewRole][value="2"]').uncheck();await page.locator('[name=crewRole][value="3"]').uncheck();
  await page.locator('#studio-prepare-demo').click();await page.waitForFunction(()=>!document.getElementById('studio-launch-event').disabled);
  assert.deepEqual(requests.at(-1).enabledRoles,[0,1]);
  await page.locator('[name=crewRole][value="3"]').check();assert(await page.locator('#studio-launch-event').isDisabled());
  await page.locator('#studio-prepare-demo').click();await page.waitForFunction(()=>!document.getElementById('studio-launch-event').disabled);
  await readiness.screenshot({path:require('node:path').resolve('../../work/optional-guests-readiness.png')});
  assert.equal(await page.locator('[name=language]').count(),0);
  await page.waitForFunction(()=>!document.getElementById('studio-launch-event').disabled);
  await page.locator('#studio-launch-event').click();assert.equal(launches.length,1);
  assert.equal(launches[0].brief.language,'English');
  assert.deepEqual(launches[0].guestKeys,[]);
  assert.equal(launches[0].preparationId,fixture.prep);assert.deepEqual(launches[0].enabledRoles,[0,1,3]);
  assert.deepEqual(errors,[]);
  console.log('PASS: model reconnect starts preparation; errors remain visible without retry loops; busy Scout is skipped; selected roles and preparation ID gate launch. Explicit fixture, no model inference.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
