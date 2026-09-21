const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1500,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await p.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
 await p.evaluate(async()=>{const s=await fetch('/api/session').then(r=>r.json());for(const [name,persona,tone] of [['Warm','guide','kind'],['Skeptic','analyst','cynical']]){const r=await fetch(name==='Warm'?'/api/onboard':'/api/agents',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({name,persona,tone,verbosity:'brief',skills:['documents'],protection:'standard'})});if(!r.ok)throw new Error(await r.text());}});
 await p.reload();await p.waitForFunction(()=>BacStudio.inspect().profile);await p.locator('.world-room-map [data-world-room=lounge]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 const selected=await p.evaluate(()=>BacStudio.inspect().agentId);
 await p.locator('#studio-prompt').fill('What should we build next?');await p.locator('#studio-run-options').click();await p.locator('#studio-send-all').click();await p.locator('#studio-compare-open').click();
 await p.waitForFunction(()=>[...document.querySelectorAll('.compare-status')].length===2&&[...document.querySelectorAll('.compare-status')].every(e=>e.textContent==='done'));
 assert(await p.locator('#studio-compare').isVisible());assert.equal(await p.locator('.studio-compare-grid article').count(),2);assert.equal(await p.evaluate(()=>BacStudio.inspect().agentId),selected);
 assert.match(await p.locator('#studio-compare').innerText(),/Skeptic/);assert.match(await p.locator('#studio-compare').innerText(),/Cynical/);
 assert.deepEqual(errors,[]);console.log('PASS: identical prompt queued for two distinct agents, independent result cards, persona labels, selected agent preserved.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
