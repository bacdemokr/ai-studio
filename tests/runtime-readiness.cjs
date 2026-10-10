// The fixture supplies the page; runtime startup is deliberately delayed.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage();let probes=0,started=false;
 const status=()=>{const ready=started&&++probes>2;return {installed:true,gateway:ready,model:true,ready};};
 await page.route('**/api/session',async route=>{const response=await route.fetch(),data=await response.json();data.runtime={...data.runtime,...status()};await route.fulfill({json:data});});
 await page.route('**/api/settings/start',async route=>{started=true;await route.fulfill({json:{started:true}});});
 await page.route('**/api/runtime',async route=>{const response=await route.fetch();await route.fulfill({json:{...await response.json(),...status()}});});
 await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
 await page.locator('#studio-config').click();await page.locator('#studio-start-agents').click();
 await page.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Starting agent runtime…');assert(await page.locator('#studio-dialog').evaluate(e=>e.open));
 await page.waitForFunction(()=>document.querySelector('#studio-settings-status')?.textContent==='Model and agent runtime connected.');
 assert(await page.locator('#studio-start-agents').isHidden());assert(probes>=3);console.log('PASS: unified settings retains Start agents and waits for gateway readiness. Stubbed startup only.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
