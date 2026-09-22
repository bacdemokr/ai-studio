const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1450,height:1050}}),errors=[];p.on('pageerror',e=>errors.push(e.message));let owner='',status='applied',requested=[],finish;
 await p.route(/\/api\/(session|state)$/,async r=>{const response=await r.fetch({headers:{...r.request().headers(),'if-none-match':''}}),json=await response.json();owner=json.agentId;const profile={id:'bac-'+owner,name:'Shield',persona:'guide',skills:['web'],protection:'openshell',avatar:{body:'classic',color:'green',accessory:'antenna'}};Object.assign(json,{profile,agents:[{...profile,key:owner,pending:0}],jobs:[]});await r.fulfill({response,json});});
 await p.route('**/api/agent-policy',async r=>{
  if(r.request().method()==='POST'){requested=['host:www.naver.com'];status='needs-review';await new Promise(resolve=>finish=resolve);return r.fulfill({status:503,json:{error:'Fixture activation failed.'}});}
  return r.fulfill({json:{agentId:owner,mode:'openshell',status,requested,sandboxes:[{}],catalog:{'host:www.naver.com':{title:'www.naver.com',hosts:['www.naver.com']}},pendingAccess:[{host:'www.naver.com',reason:'suggested'}]}});
 });
 await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');await p.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
 await p.locator('.world-room-map [data-world-room=lounge]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await p.locator('#studio-agent-policy').click();
 const approve=p.locator('[data-policy-permission="host:www.naver.com"]');await approve.waitFor();assert.ok((await p.locator('#studio-policy-content').innerText()).includes('not a confirmed policy block'));
 await approve.click();await p.getByText('Applying access and checking OpenShell. Approval is effective after verification.',{exact:true}).waitFor();assert.equal(await approve.isDisabled(),true);
 while(!finish)await p.waitForTimeout(20);finish();
 await p.getByText('Fixture activation failed.',{exact:true}).waitFor();assert.ok((await p.locator('[data-policy-section=approved] h3').innerText()).startsWith('Saved websites · not verified'));
 assert.ok((await p.locator('#studio-policy-content').innerText()).includes('Saved · not active until verified'));
 status='applied';await p.locator('#studio-surface-close').click();await p.locator('#studio-agent-policy').click();await p.waitForFunction(()=>document.querySelector('[data-policy-section=approved] h3')?.textContent.startsWith('Approved websites'));
 assert.deepEqual(errors,[]);console.log('PASS: suggested access is not a confirmed block; applying disables controls; failure reloads saved/unverified state; refresh shows verified state. Mock policy only.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
