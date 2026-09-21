const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8080');
 await page.waitForFunction(()=>window.BacStudio&&window.BacCampus?.inspect().navigation?.overview);
 await page.waitForTimeout(700);
 assert.equal(await page.locator('.world-campus-room:visible').count(),3);
 assert.equal(await page.locator('#studio-workshop').isVisible(),false);
 if(process.env.SCREENSHOT_PATH)await page.screenshot({path:process.env.SCREENSHOT_PATH});
 await page.locator('.world-campus-room[data-world-room=workshop]').click();
 await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling&&!BacCampus.inspect().navigation.overview);
 assert(await page.locator('#studio-workshop').isVisible());
 await page.waitForTimeout(3500);assert.equal(await page.evaluate(()=>BacCampus.inspect().navigation.overview),false);
 await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation?.overview);
 assert.deepEqual(errors,[]);console.log('PASS: overview on load/reload, all rooms visible, Hiring selection and polling preserve room.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
