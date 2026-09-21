const assert=require('node:assert/strict'),{chromium}=require('playwright'),{execFileSync}=require('node:child_process');
(async()=>{
 const state=JSON.parse(execFileSync('python3',['-c',`import sys,tempfile,json
sys.path[:0]=['scripts','tests']
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as d:
 s=Studio(d,Adapter(),start_worker=False);o=s.session()[0]['id'];s.onboard(o,{'name':'Drag test','persona':'guide','skills':['weather'],'protection':'standard'});v=s.state(o);v.update(csrf='fixture',runtime={'ready':True,'model':True,'testFixture':True});print(json.dumps(v))`],{encoding:'utf8'}));
 const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{const p=await b.newPage({viewport:{width:1600,height:1100}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/api/session',r=>r.fulfill({json:state}));await p.route('**/api/state',r=>r.fulfill({json:state}));
 await p.goto('http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacCampus?.inspect().residents?.length===1);
 async function lounge(){await p.locator('.world-room-map [data-world-room=lounge]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);}
 await lounge();const tag=p.locator('.world-resident').first();await tag.hover();
 const before=await p.evaluate(()=>BacCampus.inspect()),box=await tag.boundingBox();
 await p.mouse.move(box.x+box.width/2,box.y+box.height/2);await p.mouse.down();await p.mouse.move(box.x+box.width/2+110,box.y+box.height/2+45,{steps:12});await p.mouse.up();
 const after=await p.evaluate(()=>BacCampus.inspect());assert.notDeepEqual(after.residents[0].position,before.residents[0].position);assert.deepEqual(after.camera,before.camera);
 await p.mouse.move(5,5);await p.waitForTimeout(1800);assert.deepEqual((await p.evaluate(()=>BacCampus.inspect())).residents[0].position,after.residents[0].position);
 await p.reload();await p.waitForFunction(()=>window.BacCampus?.inspect().residents?.length===1);await lounge();assert.deepEqual((await p.evaluate(()=>BacCampus.inspect())).residents[0].position,after.residents[0].position);
 await tag.click();assert.deepEqual(errors,[]);await p.screenshot({path:'/private/tmp/lounge-drag.png'});console.log('PASS: drag moves agent, leaves camera fixed, keeps placement through polling and reload, preserves click selection.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
