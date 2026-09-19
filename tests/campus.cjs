const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-webgl','--ignore-gpu-blocklist','--enable-unsafe-swiftshader']});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},acceptDownloads:true});
    const errors=[],remote=[];
    const url=process.env.BASE_URL||pathToFileURL(path.resolve(__dirname,'../app/index.html')).href;
    const shot=async name=>{if(process.env.SCREENSHOT_DIR){fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,name+'.png'),fullPage:true});}};
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(/^https?:/.test(request.url())&&new URL(request.url()).origin!==new URL(url).origin)remote.push(request.url());});
    await page.goto(url);
    await page.waitForFunction(()=>document.getElementById('agent-campus').dataset.renderer==='webgl');
    assert(await page.locator('#agent-campus').isVisible());
    const first=await page.evaluate(()=>BacCampus.inspect().robots);
    await page.waitForFunction(initial=>JSON.stringify(BacCampus.inspect().robots)!==JSON.stringify(initial),first,{timeout:12000});
    await page.locator('[data-campus-agent="3"]').click();
    assert.equal(await page.locator('#campus-agent-name').innerText(),'Momo');
    await page.locator('#campus-motion').click();
    const paused=await page.evaluate(()=>BacCampus.inspect().robots);
    await page.waitForTimeout(350);
    assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().robots),paused,'Pause must freeze the scene');
    await page.locator('#campus-motion').click();
    await shot('campus');
    const embedded=await page.locator('#campus-viewport').boundingBox();
    await page.locator('#studio-focus').click();
    await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
    let expanded=await page.locator('#campus-viewport').boundingBox();
    let windowSize=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    assert(expanded.width>=windowSize.width-2,'The 3D viewport must use the full screen width');
    assert(expanded.height>windowSize.height*.8,'The 3D viewport must use most of the screen height');
    assert(expanded.width*expanded.height>embedded.width*embedded.height*1.5,'Fullscreen must materially enlarge the actual renderer');
    assert(!(await page.locator('#studio-passport').isVisible()));
    assert.equal(await page.locator('#studio-focus').getAttribute('aria-expanded'),'true');
    // Hotspots and their dialogs remain usable in the native fullscreen subtree.
    await page.locator('[data-world-skill="runtime"]').click();await page.locator('#studio-dialog').waitFor({state:'visible'});await page.locator('#studio-dialog-close').click();
    assert.equal(await page.evaluate(()=>document.fullscreenElement?.id),'agent-campus');
    const expandedFrame=await page.evaluate(()=>BacCampus.inspect().clock);
    await page.waitForFunction(before=>BacCampus.inspect().clock>before+.2,expandedFrame,{timeout:12000});
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.world-expanded'));
    assert(await page.locator('#studio-passport').isVisible());
    await page.waitForTimeout(180);
    const restored=await page.locator('#campus-viewport').boundingBox();
    assert(Math.abs(restored.width-embedded.width)<1&&Math.abs(restored.height-embedded.height)<1,
      'Leaving fullscreen must restore the embedded dimensions: '+JSON.stringify({embedded,restored}));
    // Click+Enter and a double-click are alternatives to the visible button.
    await page.locator('#campus-viewport canvas').click({position:{x:20,y:180}});await page.keyboard.press('Enter');
    await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
    await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.querySelector('.world-expanded'));
    await page.locator('#campus-viewport canvas').dblclick({position:{x:20,y:180}});await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
    await page.locator('#studio-focus').click();await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.world-expanded'));
    // Unsupported/denied native fullscreen still fills the window and restores scrolling.
    await page.evaluate(()=>{window.testFullscreen=document.getElementById('agent-campus').requestFullscreen;document.getElementById('agent-campus').requestFullscreen=()=>Promise.reject(new Error('Test: fullscreen denied'));});
    await page.locator('#studio-focus').click();assert(await page.locator('.world-expanded').isVisible());
    assert.equal(await page.evaluate(()=>document.fullscreenElement),null);
    for(const size of [{width:900,height:420},{width:390,height:844}]){
      await page.setViewportSize(size);await page.waitForFunction(()=>document.querySelector('#campus-viewport canvas').getBoundingClientRect().width===innerWidth);
      const frame=await page.locator('#campus-viewport').boundingBox(),exit=await page.locator('#studio-focus').boundingBox();
      assert(frame.width>=size.width-2&&frame.height>size.height*.65,'Small screens must retain a large usable viewport');
      assert(exit.y>=0&&exit.y+exit.height<=size.height,'Exit must remain on screen');
      assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
    }
    await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.body.style.overflow),'');
    assert.equal(await page.evaluate(()=>document.querySelector('[data-mode="playground"]').inert),false);
    await page.evaluate(()=>document.getElementById('agent-campus').requestFullscreen=window.testFullscreen);await page.setViewportSize({width:1440,height:1100});
    await page.waitForTimeout(180);
    const resizedBack=await page.locator('#campus-viewport').boundingBox();
    assert(Math.abs(resizedBack.width-embedded.width)<1&&Math.abs(resizedBack.height-embedded.height)<1,'Fullscreen resizes must not enlarge the restored layout');
    assert.equal(await page.locator('[data-world-skill]').count(),9);
    await page.locator('#studio-board-tab').click();assert(await page.locator('#studio-board').isVisible());
    await page.locator('#studio-campus-tab').click();assert(await page.locator('#campus-viewport').isVisible());
    await page.locator('[data-mode="playground"]').click();
    await page.locator('[data-mission="analyst"]').click();
    await page.locator('[data-equip="analyst"]').check();
    await page.locator('#pg-run').click();
    assert.match(await page.locator('#pg-result').innerText(),/120/);
    await page.locator('#pg-csv-file').setInputFiles({name:'interests.csv',mimeType:'text/csv',buffer:Buffer.from('topic,attendees\n"Coding, agents",10\nData,20\n"Coding, agents",10\n')});
    await page.waitForFunction(()=>document.getElementById('pg-csv').value.includes('Coding, agents'));
    await page.locator('#pg-run').click();
    assert.match(await page.locator('#pg-result').innerText(),/40/);
    const reportPromise=page.waitForEvent('download');await page.locator('#pg-download').click();const report=await reportPromise;
    assert.equal(report.suggestedFilename(),'bac-audience-report.md');
    const reportText=fs.readFileSync(await report.path(),'utf8');
    assert.match(reportText,/Coding, agents \| 20 \| 50.0%/);
    await shot('data-analyst');
    await page.locator('#pg-csv').fill('topic,attendees\nInvalid,-3');await page.locator('#pg-run').click();
    assert(await page.locator('#pg-error').isVisible());assert.equal(await page.locator('#pg-download').count(),0);
    await page.locator('#pg-csv').fill('topic,attendees\n<img src=x onerror=alert(1)>,10');await page.locator('#pg-run').click();
    assert.equal(await page.locator('#pg-result img').count(),0);
    await page.locator('[data-mission="poster"]').click();await page.locator('[data-equip="poster"]').check();
    await page.locator('#pg-use-brief').click();
    assert.equal(await page.locator('#pg-poster-city').inputValue(),'Zurich');
    await page.locator('#pg-run').click();
    const posterPromise=page.waitForEvent('download');await page.locator('#pg-download').click();const poster=await posterPromise;
    assert.equal(poster.suggestedFilename(),'bac-event-poster.png');
    const png=fs.readFileSync(await poster.path());assert.equal(png.subarray(1,4).toString(),'PNG');assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1350);
    await shot('poster-studio');
    await page.locator('#pg-poster-title').fill('Edited');assert.equal(await page.locator('#pg-download').count(),0,'Edited inputs must invalidate old artifact');
    for(const width of [736,360]){
      await page.setViewportSize({width,height:1000});
      for(const mode of ['campus','playground','crew']){await page.locator('[data-mode="'+mode+'"]').click();assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),mode+' overflow at '+width);}
      await page.locator('[data-mode="campus"]').click();await shot('campus-'+width);
    }
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.waitForFunction(()=>BacCampus.inspect().motion===false);
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    const fallback=await browser.newPage();
    await fallback.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind.startsWith('webgl')?null:original.call(this,kind,...args);};});
    await fallback.goto(url);assert.equal(await fallback.locator('#agent-campus').getAttribute('data-renderer'),'fallback');
    assert(await fallback.locator('#campus-fallback').isVisible());assert(await fallback.locator('#studio-name').isVisible());
    await fallback.close();
    console.log('PASS: real WebGL, robot movement, pause, native fullscreen sizing/keyboard/double-click/exit, fullscreen dialogs, denied-fullscreen fallback on desktop/mobile, world hotspots, board switching, CSV upload and report, PNG download, XSS protection, responsive layouts, reduced motion and WebGL fallback.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
