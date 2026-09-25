const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async response=>{if(response.url().endsWith('/api/upload')&&response.status()!==200)console.error('Upload rejected',response.status(),(await response.json()).error||'ok');});
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8097');
 await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
 async function api(route,body,owner){return page.evaluate(async({route,body,owner})=>{
  const session=await (await fetch('/api/session')).json();
  const response=await fetch('/api/'+route,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,...(owner?{'X-BaC-Agent':owner}:{})},...(body?{body:JSON.stringify(body)}:{})});
  return {status:response.status,data:await response.json()};
 },{route,body,owner});}
 let approved=false,release,fail=false;
 const gate=new Promise(resolve=>release=resolve);
 const policy=()=>({status:'applied',requested:approved?['host:one.test']:[],catalog:{'host:one.test':{title:'one.test',hosts:['one.test']}},pendingAccess:approved?[]:[{host:'one.test'}],sandboxes:['fixture']});
 await page.route('**/api/agent-policy',async route=>{
  if(route.request().method()==='POST'){await gate;if(fail)return route.fulfill({status:503,json:{error:'Test apply failure'}});approved=true;}
  return route.fulfill({json:policy()});
 });
 const first=(await api('session')).data.agentId;
 assert.equal((await api('onboard',{name:'Upload A',skills:['documents']},first)).status,200);
 const second=(await api('agents',{name:'Upload B',skills:['documents'],protection:'openshell'},first)).data.agentId;
 await page.reload();await page.waitForSelector('[data-agent-key="'+second+'"]',{state:'attached'});
 await page.locator('.world-room-map [data-world-room=lounge]').click();
 await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.locator('[data-agent-key="'+second+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload B');
 await page.waitForFunction(()=>document.querySelector('#studio-agent-policy .policy-pending-badge')?.textContent==='1');
 assert.match(await page.locator('#studio-agent-policy').getAttribute('aria-label'),/1 website awaiting approval/);
 await page.locator('#studio-agent-policy').click();
 await page.locator('[data-policy-permission="host:one.test"][data-policy-allow="true"]').click();
 await page.locator('.policy-loading').waitFor({state:'visible'});
 assert.equal(await page.locator('#studio-policy-content').getAttribute('aria-busy'),'true');
 assert.match(await page.locator('.policy-loading').innerText(),/Applying permissions/);
 assert.equal(await page.locator('#studio-policy-content .studio-policy-error').count(),0);
 assert.equal(await page.locator('[data-policy-permission]').count(),0);
 await page.screenshot({path:'/tmp/bac-policy-applying.png'});
 release();await page.locator('[data-policy-permission="host:one.test"][data-policy-allow="false"]').waitFor({state:'visible'});
 assert.equal(await page.locator('.policy-loading').count(),0);
 fail=true;await page.locator('[data-policy-permission="host:one.test"][data-policy-allow="false"]').click();
 await page.locator('#studio-policy-content [role="alert"]').waitFor({state:'visible'});
 assert.match(await page.locator('#studio-policy-content [role="alert"]').innerText(),/Test apply failure/);
 assert.equal(await page.locator('.policy-loading').count(),0);
 assert.deepEqual(errors,[]);
 console.log('PASS: pending approval shows spinner, success restores controls, failure remains actionable');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
