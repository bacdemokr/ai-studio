const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const p=await browser.newPage({viewport:{width:1450,height:1100}}),errors=[],writes=[];let owner='',status='unavailable',failRead=true,finish,gets=0;
  p.on('pageerror',e=>errors.push(e.message));
  await p.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();owner=state.agentId;
   const profile={id:'bac-'+owner,name:'Orbit',persona:'guide',skills:['weather'],protection:'openshell',avatar:{body:'crab',color:'violet',accessory:'cap'}};
   await route.fulfill({response,json:{...state,profile,jobs:[],agents:[{...profile,key:owner,pending:0,activity:null}]}});
  });
  await p.route('**/api/agent-policy',async route=>{
   if(route.request().method()==='POST'){
    writes.push({body:route.request().postDataJSON(),owner:route.request().headers()['x-bac-agent']});
    await new Promise(resolve=>finish=resolve);status='applied';return route.fulfill({json:{applied:true}});
   }
   gets++;
   if(failRead)return route.fulfill({status:503,json:{error:'OpenShell did not respond.'}});
   await route.fulfill({json:{agentId:owner,mode:'openshell',status,checkFailure:status==='unavailable'?'timeout':undefined,requested:[],catalog:{},sandboxes:status==='applied'?[{running:true}]:[]}});
  });
  await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Orbit');
  await p.locator('.world-room-map [data-world-room=lounge]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await p.locator('#studio-agent-policy').click();await p.locator('[data-policy-check]').waitFor();
  assert.equal(await p.locator('[data-policy-section]').count(),0,'Failed fetch must not invent empty approval lists');
  assert.equal(await p.getByText('Host troubleshooting',{exact:true}).count(),1);
  failRead=false;status='awaiting-first-mission';await p.locator('[data-policy-check]').click();
  const prepare=p.getByRole('button',{name:'Prepare workspace',exact:true});await prepare.waitFor();assert(await prepare.isEnabled());
  assert.equal(writes.length,0,'Checking must never change access');await prepare.click();
  await p.waitForFunction(()=>document.querySelector('[data-policy-retry]')?.disabled);
  assert.deepEqual(writes,[{body:{retry:true},owner}]);finish();
  await p.waitForFunction(()=>document.querySelector('[data-policy-section=approved] h3')?.textContent.startsWith('Approved access'));
  assert.equal(await p.locator('[data-policy-retry]').count(),0);
  status='unavailable';await p.locator('#studio-surface-close').click();await p.locator('#studio-agent-policy').click();
  await p.getByText('OpenShell did not respond in time. Your saved approvals are unchanged.',{exact:true}).waitFor();
  assert(await p.locator('[data-policy-check]').isEnabled());assert(gets>=3);
  await p.locator('#studio-policy-content').screenshot({path:require('node:path').resolve('../../work/policy-recovery.png')});
  assert.deepEqual(errors,[]);console.log('PASS: actionable check, empty-workspace preparation without new grants, progress, recovery, and honest failed-fetch display. Mock APIs; no user permissions changed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
