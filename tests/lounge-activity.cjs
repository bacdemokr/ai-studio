const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',['-B','-c',`
import sys,json
sys.path.insert(0,'tests')
from test_demo_improvements import DemoImprovements
c=DemoImprovements();c.setUp()
try:
 c.studio.configure(c.guest,dict(name='Scout',persona='analyst',skills=['weather']))
 states=[]
 def snapshot():
  state=c.studio.state(c.guest);state['runtime']={'ready':False,'model':False,'gateway':True};states.append(state)
 snapshot()
 request=c.studio.enqueue(c.owner,{'kind':'chat','prompt':'Only this agent should work.'})
 prep=c.studio.prepare_demo(c.owner,{})
 snapshot()
 with c.studio.db() as db:db.execute("UPDATE jobs SET status='running' WHERE id=?",(prep['id'],))
 snapshot()
 with c.studio.db() as db:
  db.execute("UPDATE jobs SET status='done' WHERE id IN (?,?)",(prep['id'],request['id']))
 event=c.studio.enqueue(c.owner,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})
 snapshot()
 with c.studio.db() as db:
  payload=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(event['id'],)).fetchone()[0])
  payload['roundtable']['replies'][c.guest]={'status':'running'}
  db.execute("UPDATE jobs SET status='running',payload=? WHERE id=?",(json.dumps(payload),event['id']))
 snapshot()
 with c.studio.db() as db:
  payload['roundtable']['replies'][c.guest]={'status':'done','answer':'I hope for good weather.'}
  db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),event['id']))
 snapshot()
 c.studio.enqueue(c.guest,{'kind':'chat','prompt':'Check the weather.'})
 snapshot()
 print(json.dumps({'states':states,'key':c.guest,'workingKey':c.owner}))
finally:c.doCleanups()
`],{encoding:'utf8'}));
 let state=fixture.states[0];
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:state.runtime}));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const status=page.locator('[data-resident="'+fixture.key+'"] small'),banner=page.locator('#studio-task-state');
  assert.equal(await status.innerText(),'Ready');assert(await banner.isHidden());
  for(const i of [1,2,3,4]){
   state=fixture.states[i];await page.evaluate(()=>BacStudio.refresh());
   assert.equal(await status.innerText(),i<=2?'Ready':'Busy');assert(await banner.isHidden());
   if(i<=2)assert.equal(await page.locator('[data-resident="'+fixture.workingKey+'"] small').innerText(),'Busy');
   assert.equal(await page.getByText('Mission assigned',{exact:true}).count(),0);
   assert(await page.locator('#studio-assigned-crew').isHidden());
  }
  state=fixture.states[5];await page.evaluate(()=>BacStudio.refresh());
  assert.equal(await status.innerText(),'Ready');assert(await banner.isHidden());assert(await page.locator('#studio-assigned-crew').isHidden());
  state=fixture.states[6];await page.evaluate(()=>BacStudio.refresh());
  assert.equal(await status.innerText(),'Busy');assert.equal(await banner.innerText(),'Busy');
  assert.deepEqual(errors,[]);
  console.log('PASS: Background preparation stays Ready; Ready/Busy only; completed guest is Ready and accepts a new request while the shared event is still running.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
