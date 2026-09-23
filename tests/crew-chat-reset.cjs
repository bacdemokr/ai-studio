const assert=require('node:assert/strict'),{chromium}=require('playwright'),{execFileSync}=require('node:child_process');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',['-c',`import sys,tempfile,json
sys.path[:0]=['scripts','tests']
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as d:
 s=Studio(d,Adapter(),start_worker=False);o=s.session()[0]['id']
 for role in range(4):
  s.enqueue(o,{'kind':'crew-chat','crewRole':role,'prompt':'Old direct message '+str(role)});s.execute(s.next_job())
 s.enqueue(o,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}});s.execute(s.next_job())
 before=s.state(o);result=s.reset_crew_chats(o,reset_event=True);after=s.state(o)
 for state in [before,after]:state.update(canConfigure=True,csrf='test',runtime={'ready':False,'model':False,'gateway':False})
 print(json.dumps(dict(before=before,after=after,result=result)))`],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];let current=fixture.before,calls=0,busy=true;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route(/\/api\/(session|state)$/,r=>r.fulfill({json:current}));
  await page.route('**/api/telegram',r=>r.fulfill({json:{connected:false}}));
  await page.route('**/api/runtime',r=>r.fulfill({json:current.runtime}));
  await page.route('**/api/settings',r=>r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{},event:{city:'Zurich',language:'English',venue:''}}}));
  await page.route('**/api/bac-reset',r=>{calls++;if(busy)return r.fulfill({status:409,json:{error:'Finish or stop the crew’s pending work before resetting its chats. Nothing was reset.'}});current=fixture.after;return r.fulfill({json:fixture.result});});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Old direct message 0/);
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Event mission/);
  await page.locator('#studio-config').click();await page.locator('#studio-settings-reset-tab').click();assert.equal(calls,0);
  await page.locator('#studio-bac-reset').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent.includes('Nothing was reset'));
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Old direct message 0/);
  assert(await page.locator('#studio-config-form').isVisible());assert.equal(await page.locator('#studio-bac-reset-confirm').count(),0);
  busy=false;await page.locator('#studio-bac-reset').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent==='BaC reset.');
  await page.locator('#studio-dialog-close').click();
  for(const role of [0,1,2,3]){await page.locator(`[data-crew-member="${role}"]`).click();assert.equal(await page.locator('#studio-crew-conversation .chat-turn').count(),0);}
  assert.equal(current.jobs.length,0,'Previous event board cleared');assert.deepEqual(current.files,fixture.before.files,'Saved event files preserved');
  await page.reload();await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-crew-conversation .chat-turn').count(),0);
  assert.equal(await page.locator('#studio-event-reset').count(),0);
  assert.equal(await page.locator('#studio-crew-chat-reset').count(),0);
  assert.deepEqual(errors,[]);console.log('PASS: combined BaC reset: one-click execution, busy rejection, board and chats cleared, reload persistence, saved files retained. Disposable backend data and mocked browser API.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
