const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
const page=await browser.newPage({viewport:{width:1725,height:1070}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime);
const real=await page.evaluate(()=>fetch('/api/telemetry').then(r=>r.json()));assert('cpu' in real.host);assert(real.total===null); // New browser has no recorded runs.
await page.route('**/api/telemetry',route=>route.fulfill({json:{host:{cpu:24.5,memory:48.2},total:48000,unreportedCalls:0,agents:['Casey','Dylan','Alex','Morgan','Riley','Wade'].map((name,i)=>({name,crew:true,context:2048+i*1000,limit:32768,total:8000,calls:1}))}}));
await page.locator('#studio-focus').click();await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
await page.locator('#studio-telemetry summary').click();await page.waitForFunction(()=>document.querySelectorAll('.usage-agent').length===6);assert.match(await page.locator('#studio-telemetry summary').innerText(),/Context 21.5% max/);
assert.match(await page.locator('.usage-panel').innerText(),/48K/);
const panel=await page.locator('.usage-panel').boundingBox();assert(panel.x>=0&&panel.y>=0&&panel.x+panel.width<=1725&&panel.y+panel.height<=1070);
assert(await page.locator('#studio-crew-passport').isVisible());await page.screenshot({path:'../../work/telemetry-fullscreen.png'});
assert.deepEqual(errors,[]);console.log('PASS: authenticated host metrics, no invented tokens, six agent context meters and fullscreen panel bounds. Visual data is mocked.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
