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

 try{
  const p=await b.newPage({viewport:{width:1500,height:1100}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  let deleting=false,complete=false,deletions=0,bacCalls=0;
  await p.route(/\/api\/(session|state)$/,r=>r.fulfill({json:{...(complete?fixture.states[2]:{...fixture.states[0],agents:fixture.states[0].agents.map(a=>({...a,deleting,deletionWaiting:deleting}))}),scenarios:[{id:'plan',hasWork:true}]}}));
 await p.route('**/api/settings/connections',r=>r.fulfill({json:{connections:{local:{ready:true,enabled:true,provider:'local',model:'fixture',message:'Ready'},api:{ready:false,enabled:false,message:'Not configured'}},loungePreference:'auto',scenarioPreferences:{}}}));
  await p.route('**/api/settings',r=>r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{},event:{city:'Zurich',language:'English',venue:''}}}));
  await p.route('**/api/delete-agent',r=>{deleting=true;deletions++;return r.fulfill({json:{deleting:true}})});
  await p.route('**/api/bac-reset',r=>{bacCalls++;return r.fulfill({json:{reset:true}})});
  await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:18087');await p.waitForFunction(()=>window.BacStudio);
  async function openReset(){await p.locator('#studio-config').click();await p.locator('[data-connection-tab=reset]').click();}
  await openReset();await p.locator('#studio-agent-reset').click();
  await p.waitForFunction(()=>!document.querySelector('#studio-dialog').open);
  await openReset();
  assert.match(await p.locator('#studio-settings-status').innerText(),/Reset in progress/);
  for(const id of ['agent-reset','settings-plan-reset','reset-all']){
   assert(await p.locator('#studio-'+id).isDisabled(),id+' must stay locked while background cleanup runs');
   await p.locator('#studio-'+id).evaluate(e=>e.click());
  }
  await p.waitForTimeout(1100);assert.equal(deletions,2);assert.equal(bacCalls,0);
  complete=true;
  await p.waitForFunction(()=>!document.querySelector('#studio-settings-plan-reset').disabled);
  if(!await p.locator('#studio-dialog').evaluate(d=>d.open))await openReset();
  assert(await p.locator('#studio-agent-reset').isDisabled());
  await p.locator('[data-connection-tab=reset]').click();
  await p.locator('#studio-settings-plan-reset').click();await p.getByText('Open Task reset.',{exact:true}).waitFor();assert.equal(bacCalls,1);
  await p.locator('#studio-reset-all').click();await p.getByText('All stages reset.',{exact:true}).waitFor();assert.equal(bacCalls,2);
  assert.deepEqual(errors,[]);console.log('PASS: reopened Reset controls remain locked during background cleanup, recover afterward, and preserve stage scope.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
