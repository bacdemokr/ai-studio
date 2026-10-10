// Disposable browser fixture: verify rendered pixels, not only selected form values.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  // Hold only the ambient scene loop. Selection, polling and browser input continue.
  await page.addInitScript(()=>{
   const nextFrame=window.requestAnimationFrame.bind(window);
   window.requestAnimationFrame=callback=>nextFrame(function run(time){
    if(window.holdSceneFrames&&callback.name==='animate')nextFrame(run);
    else callback(time);
   });
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.locator('.world-room-map [data-world-room=workshop]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-body-picker [data-body=rover]').click();
  await page.locator('#studio-color-picker [data-avatar-color=amber]').click();
  await page.waitForTimeout(100);
  await page.evaluate(()=>window.holdSceneFrames=true);
  const canvas=page.locator('#campus-viewport canvas');
  let previous=await canvas.screenshot();
  async function changed(label,select){
   await select();
   const current=await canvas.screenshot();
   assert(!current.equals(previous),label+' must redraw the 3D preview while ambient frames are held');
   previous=current;
  }
  for(const body of ['operative','claw','crab','round','classic','rover']){
   await changed(body,()=>page.locator('#studio-body-picker [data-body='+body+']').click());
   assert.equal(await page.locator('#studio-body-picker [data-body='+body+']').getAttribute('aria-pressed'),'true');
  }
  for(const color of ['green','cyan','coral','violet','ice','amber'])
   await changed(color,()=>page.locator('#studio-color-picker [data-avatar-color='+color+']').click());
  for(const accessory of ['headset','glasses','cap','antenna','none'])
   await changed(accessory,()=>page.locator('#studio-accessory').selectOption(accessory));
  await page.locator('#studio-focus').click();
  await page.waitForTimeout(150);
  previous=await canvas.screenshot();
  await changed('fullscreen Smith',()=>page.locator('#studio-body-picker [data-body=operative]').click());
  await page.waitForTimeout(2000); // State polling must not restore the previous avatar.
  assert.equal(await page.locator('#studio-body-picker [data-body=operative]').getAttribute('aria-pressed'),'true');
  assert((await canvas.screenshot()).equals(previous),'polling must preserve the rendered draft');
  await page.evaluate(()=>window.holdSceneFrames=false);
  await page.locator('#campus-motion').click();
  await page.waitForTimeout(100);
  previous=await canvas.screenshot();
  await changed('paused Claw',()=>page.locator('#studio-body-picker [data-body=claw]').click());
  assert.deepEqual(errors,[]);
  console.log('PASS: all six bodies/colors and five accessories redraw without ambient frames; fullscreen, polling and paused motion preserve preview updates.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
