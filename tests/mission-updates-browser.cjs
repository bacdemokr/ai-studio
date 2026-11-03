const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const source=fs.readFileSync('src/studio-crew.js','utf8');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 const page=await browser.newPage({reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<main id="agent-campus"><div id="studio-surface-body" style="height:420px;overflow:auto;position:relative"><div id="lanes"></div><div id="studio-mission-updates" hidden><button>New updates ↓</button></div></div></main>');
 await page.addStyleTag({content:'.mission-reasoning-text{height:140px;overflow:auto;white-space:pre-wrap} article{margin:12px 0;padding:12px} #studio-mission-updates{position:sticky;bottom:12px;height:0;display:flex;justify-content:center} #studio-mission-updates[hidden]{display:none} #studio-mission-updates button{transform:translateY(-100%)}'});
 await page.addScriptTag({content:source.slice(source.indexOf('function updateMissionControlTrace('),source.indexOf('function renderMissionControl('))});
 const line=n=>Array.from({length:n},(_,i)=>'Public text line '+i).join('\n');
 const row=(key,body)=>'<article data-trace-key="'+key+'" data-trace-kind="contribution">'+body+'</article>';
 const intro=row('intro','<div style="height:500px">Plan</div>');
 const reason=n=>row('reason','<details open data-trace-details="call"><summary>Working</summary><div class="mission-reasoning-text" data-reasoning-scroll="call:1:summary">'+line(n)+'</div></details>');
 const patch=(html,id='job',notify=true)=>page.evaluate(({html,id,notify})=>updateMissionControlTrace(document.getElementById('lanes'),id,html,notify),{html,id,notify});
 const notice=page.locator('#studio-mission-updates'),button=notice.locator('button'),viewport=page.locator('#studio-surface-body');
 await patch(intro+reason(30));assert(await button.isHidden());
 await viewport.evaluate(e=>e.scrollTop=120);await page.waitForTimeout(50);const before=await viewport.evaluate(e=>e.scrollTop);
 await patch(intro+reason(50));assert.equal(await viewport.evaluate(e=>e.scrollTop),before);assert(await button.isVisible());
 await button.click();assert(await button.isHidden());assert.equal(await page.locator('[data-reasoning-scroll]').evaluate(e=>Math.round(e.scrollHeight-e.clientHeight-e.scrollTop)),0);
 // New inner text must not pull the reader down, even from the old bottom.
 const priorInner=await page.locator('[data-reasoning-scroll]').evaluate(e=>e.scrollTop);const priorOuter=await viewport.evaluate(e=>e.scrollTop);
 await patch(intro+reason(70));assert.equal(await page.locator('[data-reasoning-scroll]').evaluate(e=>e.scrollTop),priorInner);assert.equal(await viewport.evaluate(e=>e.scrollTop),priorOuter);assert(await button.isVisible());
 await page.locator('[data-reasoning-scroll]').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForTimeout(80);assert(await button.isHidden());
 // A new final result is announced without opening it or moving the viewport.
 const final=row('final','<details class="mission-trace-detail" data-trace-details="response"><summary>Final response</summary><p>Delivered HTML</p></details>');
 await patch(intro+reason(70)+final);assert(await button.isVisible());assert.equal(await page.locator('[data-trace-details=response]').getAttribute('open'),null);
 await button.focus();await page.keyboard.press('Enter');assert(await button.isHidden());assert.equal(await page.locator('[data-trace-details=response]').getAttribute('open'),'');
 await patch(intro+reason(90));assert(await button.isVisible());
 await patch(intro+reason(90),'job',false);assert(await button.isHidden()); // view toggle, not new content
 await patch(intro+reason(100),'new-job');assert(await button.isHidden());
 await viewport.evaluate(e=>e.style.display='none');await patch(intro+reason(110),'new-job');assert(await button.isHidden());
 assert.deepEqual(errors,[]);
 console.log('PASS: no automatic outer/inner scrolling; compact update indicator; explicit/keyboard jump; manual reading clears; view/job/hidden reset.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
