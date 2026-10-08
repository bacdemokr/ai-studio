const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});const errors=[];let events=[],owner;
  const base=process.env.BASE_URL||'http://127.0.0.1:8094';
  const session=await (await page.request.get(base+'/api/session')).json();
  const created=await page.request.post(base+'/api/onboard',{headers:{'X-BaC-CSRF':session.csrf},data:{name:'Shield',persona:'guide',skills:['weather'],protection:'standard'}});
  assert(created.ok(),'Create a real fixture profile before overriding its policy evidence');
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)console.log('HTTP',r.status(),new URL(r.url()).pathname)});
  page.on('console',e=>{if(e.type()==='error')errors.push(e.text())});
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();owner=state.agentId;
   const profile={name:'Shield',persona:'guide',skills:['weather'],protection:'openshell',avatar:{body:'round',color:'cyan',accessory:'headset'}};
   await route.fulfill({response,json:{...state,profile,agents:[{...profile,key:owner,pending:0}],protectionEvents:events}});
  });
  await page.goto(base);await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-scenario=event-brief]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  function deny(id,role){const now=Date.now()/1000;return{id,owner,role,action:'deny',source:'OpenShell policy log',host:'example.com',time:now,observedAt:now};}
  events=[deny('crew-hit',1)];await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.visible));
  assert.equal(await page.locator('.world-protection-hit:visible').count(),1);
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.phase==='impact'));
  await page.waitForTimeout(180);
  await page.screenshot({path:'../../work/dylan-shield-hit.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.phase==='blocked'));
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0,'polling must not replay');
  // Permission changes alone have no event. A later real allowed request travels out.
  assert.equal(await page.locator('.world-protection-allow:visible').count(),0);
  events.push({...deny('crew-allowed',1),action:'allow',host:'blogs.nvidia.com'});await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.action==='allow'&&h.visible));
  assert.match(await page.locator('.world-protection-allow:visible').innerText(),/Request allowed.*blogs.nvidia.com.*external website/s);
  assert.equal(await page.evaluate(()=>BacCampus.protectionReplyDelay(BacStudio.inspect().agentId,1)),null,'allowed requests must not hold replies');
  const rotation=await page.evaluate(()=>BacCampus.inspect().protectionHits.find(h=>h.action==='allow').globeRotation);
  await page.waitForTimeout(450);
  assert.notEqual(await page.evaluate(()=>BacCampus.inspect().protectionHits.find(h=>h.action==='allow').globeRotation),rotation);
  await page.screenshot({path:'../../work/dylan-outbound-world.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0,'allowed events must not replay');
  await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>BacCampus.inspect().motion===false);
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  events=[...events,deny('personal-hit',null)];await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===null&&h.visible));
  assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.find(h=>h.role===null).animated,false);
  await page.screenshot({path:'../../work/lounge-shield-hit.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  events.push({...deny('personal-allowed',null),action:'allow'});await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===null&&h.action==='allow'&&h.visible));
  const still=await page.evaluate(()=>BacCampus.inspect().protectionHits.find(h=>h.action==='allow'));
  assert.equal(still.animated,false);assert.equal(still.phase,'allowed');
  await page.waitForTimeout(400);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().protectionHits.find(h=>h.action==='allow').globeRotation),still.globeRotation);
  await page.screenshot({path:'../../work/lounge-outbound-world.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  // Reduced-motion feedback expires at 3s; its duplicate-suppression window is 4.5s.
  await page.waitForTimeout(1700);
  await page.evaluate(owner=>{
   BacCampus.setCollection([{key:owner,name:'Direct',persona:'guide',skills:['weather'],protection:'standard',avatar:{body:'round',color:'cyan',accessory:'headset'}}],owner);
   BacCampus.observeExternalActivity([{id:'direct-web',kind:'chat',liveActivity:{available:true,calls:[{tool:'web_fetch',target:'https://example.org/weather',status:'running'}]}}],owner);
  },owner);
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.source==='OpenClaw tool activity'&&h.visible));
  assert.match(await page.locator('.world-protection-allow:visible').innerText(),/Internet activity.*example.org.*Direct access · web tool/s);
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  events=[deny('stale',1)];events[0].time-=100;events[0].observedAt-=100;
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0);
  assert.deepEqual(errors,[]);console.log('PASS: crew and personal denial/allow effects, rotating external globe, outbound route, no allow reply delay, dedupe, expiry and reduced motion. Injected fixture evidence.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
