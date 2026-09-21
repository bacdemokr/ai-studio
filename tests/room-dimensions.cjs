const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}});
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacCampus?.inspect().navigation?.overview);
 for(const [width,height] of [[1500,1000],[1280,800],[1000,768]]){
  await page.setViewportSize({width,height});let reference;
  for(const room of ['workshop','lounge','mission','workshop']){
   await page.locator('.world-room-map [data-world-room='+room+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.waitForTimeout(100);
   const rect=await page.locator('#campus-viewport').boundingBox();reference??=rect;
   assert(Math.abs(rect.width-reference.width)<1&&Math.abs(rect.height-reference.height)<1,JSON.stringify({room,rect,reference}));
   const stage=await page.locator('.campus-stage').boundingBox();assert(stage.y+stage.height<=height+1,'Scene below fold: '+JSON.stringify({room,stage,height}));
   const panel=room==='workshop'?'#studio-workshop':room==='lounge'?'#studio-passport':'#studio-crew-passport';
   assert.equal(await page.locator(panel).evaluate(e=>getComputedStyle(e).overflowY),'auto');
  }
 }
 await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement);await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);await page.waitForTimeout(100);
 const rect=await page.locator('#campus-viewport').boundingBox();assert(Math.abs(rect.height-372)<1);
 console.log('PASS: identical 3D width/height across all rooms at desktop/tablet widths, scrolling side panels, fullscreen restoration.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
