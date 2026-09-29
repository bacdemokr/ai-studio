const assert=require('node:assert/strict'),{chromium}=require('playwright'),{execFileSync}=require('node:child_process');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',['-c',`import sys,tempfile,json
sys.path[:0]=['scripts','tests']
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as d:
 s=Studio(d,Adapter(),start_worker=False);o=s.session()[0]['id'];s.onboard(o,{'name':'One','persona':'guide','skills':['weather']});s.add_agent(o,{'name':'Two','persona':'guide','skills':['weather']});states=[s.state(o)];results=[]
 for a in states[0]['agents']:
  r=s.delete_agent(a['key'],{'name':a['name']});results.append(r);states.append(s.state(r['agentId']))
 for v in states:v.update(canConfigure=True,csrf='test',runtime={'ready':True,'model':True,'gateway':True})
 print(json.dumps({'states':states,'results':results}))`],{encoding:'utf8'}));
 const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{const p=await b.newPage({viewport:{width:1500,height:1100}}),errors=[];p.on('pageerror',e=>errors.push(e.message));let step=0,fail=true;
 await p.route(/\/api\/(session|state)$/,r=>r.fulfill({json:{...fixture.states[step],bacResetting:bacPending>0?(bacPending--,true):false}}));
 await p.route('**/api/settings',r=>r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{},event:{city:'Zurich',language:'English',venue:''}}}));
 await p.route('**/api/delete-agent',r=>{if(step===1&&fail){fail=false;return r.fulfill({status:503,json:{error:'Cleanup needs retry.'}})}assert.equal(r.request().postDataJSON().name,fixture.states[step].agents[0].name);return r.fulfill({json:fixture.results[step++]})});
 let bacCalls=0,bacBusy=false,bacPending=0;await p.route('**/api/bac-reset',r=>{bacCalls++;if(bacPending>0){return r.fulfill({json:{reset:false,resetting:true}});}return bacBusy?r.fulfill({status:409,json:{error:'BaC is still running. Nothing was reset.'}}):r.fulfill({json:{reset:true}});});
 await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio);
 async function openReset(){await p.locator('#studio-config').click();await p.locator('#studio-settings-reset-tab').click();assert.equal(await p.locator('#studio-settings-reset-panel button').count(),3);}
 await p.route('**/api/jobs',r=>r.fulfill({json:{id:'fixture-compare'}}));
 await p.evaluate(()=>BacStudio.setRoom('lounge'));await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await p.locator('#studio-prompt').fill('Old comparison');
 await p.evaluate(()=>document.querySelector('#studio-chat').requestSubmit(document.querySelector('#studio-send-all')));
 await p.waitForFunction(()=>!document.querySelector('#studio-send-all').disabled);
 assert.equal(await p.locator('#studio-compare-open').isHidden(),false);
 await openReset();assert.equal(step,0);
 await p.locator('#studio-agent-reset').click();await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent.includes('Cleanup needs retry'));assert.equal(step,1);
 assert(await p.locator('#studio-config-form').isVisible());assert.equal(await p.locator('#studio-reset-confirm').count(),0);
 await p.locator('#studio-agent-reset').click();await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Lounge agents reset.');
 assert.equal(step,2);assert(await p.locator('#studio-compare-open').evaluate(e=>e.hidden),'Reset must clear previous comparison before another agent is hired');assert(await p.locator('#studio-agent-reset').isDisabled());assert.equal(await p.evaluate(()=>BacStudio.inspect().profile),null);
 assert(!(await p.locator('#studio-dialog').evaluate(e=>e.open)),'Bulk cleanup must release the modal');await p.reload();await p.waitForFunction(()=>window.BacStudio);assert.equal(await p.evaluate(()=>BacCampus.inspect().residents.length),0);
 // One click resets both; a failed BaC reset must not delete Lounge agents.
 step=0;fail=false;await p.reload();await p.waitForFunction(()=>window.BacStudio);bacBusy=true;await openReset();
 await p.locator('#studio-reset-all').click();await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent.includes('Nothing was reset'));assert.equal(step,0);
 bacBusy=false;await p.evaluate(()=>{document.querySelector('#studio-reset-all').click();document.querySelector('#studio-reset-all').click();});
 await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Reset complete.');assert.equal(step,2);assert.equal(bacCalls,2,'Repeated clicks must not duplicate the reset');
 await openReset();await p.locator('#studio-reset-all').click();await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Reset complete.');assert.equal(bacCalls,3);
 bacPending=2;await p.locator('#studio-bac-reset').click();
 await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Stopping BaC work and resetting…');
 assert(await p.locator('#studio-bac-reset').isDisabled());
 await p.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='BaC reset.');
 assert.equal(bacCalls,4);assert.equal(await p.locator('#studio-bac-reset').isDisabled(),false);
 assert.deepEqual(errors,[]);console.log('PASS: direct reset without confirmation, inline partial failure/retry, zero agents, Reset all, busy rejection and duplicate-click prevention. Disposable data and mocked HTTP only.');

 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
