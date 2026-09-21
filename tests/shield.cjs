const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1500,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacCampus?.inspect().navigation?.overview);
 await p.locator('.world-room-map [data-world-room=workshop]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 for(const body of ['classic','round','rover','cat','fox','crab']){
 await p.locator('[data-body='+body+']').click();await p.locator('[name=protection][value=openshell]').check();assert.equal(await p.evaluate(()=>BacCampus.inspect().draftShield),true);
 await p.locator('[name=protection][value=standard]').check();assert.equal(await p.evaluate(()=>BacCampus.inspect().draftShield),false);
 }
 await p.locator('[name=protection][value=openshell]').check();await p.locator('#campus-viewport').scrollIntoViewIfNeeded();
 if(process.env.SCREENSHOT_PATH)await p.screenshot({path:process.env.SCREENSHOT_PATH});
 assert.deepEqual(errors,[]);console.log('PASS: shield appears and disappears immediately for all six character bodies; no renderer errors.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
