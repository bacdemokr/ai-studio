const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8097');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.evaluate(async()=>{
   const s=await(await fetch('/api/session')).json();
   await fetch('/api/onboard',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({name:'Solo',skills:['web']})});
  });
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Solo');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-prompt').fill('Please plan a short workshop');
  await page.locator('#studio-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-conversation').textContent.includes('Verified contribution from Solo'));
  await page.locator('#studio-prompt').fill('/plan Prepare a practical workshop proposal.');
  await page.locator('#studio-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey'&&document.querySelector('[data-collaboration-job]'));
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('A combined proposal'),null,{timeout:30000});
  const captain=await page.locator('#studio-crew-conversation').innerText();
  assert.match(captain,/Captain’s plan/);assert.match(captain,/Dylan · Contribution/);assert.match(captain,/Alex · Contribution/);assert.match(captain,/Morgan · Contribution/);
  await page.locator('[data-crew-member="2"]').click();
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Casey → Alex/);
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Verified contribution from Alex/);
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Dylan’s contribution/);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-crew-member="0"]').click();
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/A combined proposal/);
  await page.locator('[data-crew-member="3"]').click();
  await page.locator('#studio-crew-prompt').fill('/plan');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-chat-error').hidden);
  assert.match(await page.locator('#studio-crew-chat-error').innerText(),/Task after \/plan/);
  await page.locator('#studio-crew-prompt').fill('/plan Draft another proposal');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-name').textContent==='Casey');
  await page.waitForSelector('[data-crew-chat-stop]');await page.locator('[data-crew-chat-stop]').last().click();
  await page.waitForFunction(async()=>{const s=await(await fetch('/api/state')).json();return s.crewChats.some(j=>j.status==='cancelled');});
  await page.screenshot({path:'../../work/collaboration-plan-preview.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS: solo chat, /plan routing, specialist handoffs, final response, reload, empty command and cancellation.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
