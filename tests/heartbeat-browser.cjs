const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});try{
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.BASE_URL||'http://127.0.0.1:8087');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
await page.context().grantPermissions(['clipboard-read','clipboard-write']);
const telegramWrites=[];page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname.startsWith('/api/telegram'))telegramWrites.push(new URL(request.url()).pathname);});
await page.getByRole('button',{name:'Settings',exact:true}).click();await page.locator('[data-connection-tab=telegram]').click();await page.locator('#studio-settings-telegram-panel').waitFor({state:'visible'});
assert.deepEqual(await page.locator('[data-settings-tab]').allTextContents(),['Model','Location','Telegram','Reset']);
assert(await page.locator('#studio-settings-model-panel').isHidden());
assert(await page.locator('#studio-telegram-test').isHidden());assert(await page.locator('#studio-telegram-disconnect').isHidden());
assert(await page.locator('#studio-telegram-status').isHidden());
await page.screenshot({path:'/tmp/bac-telegram-before-connect.png'});
// Exercise the native clipboard path rather than only filling the field.
// Nothing should connect, reset focus, or animate the covered scene while editing.
const modalClock=await page.evaluate(()=>BacCampus.inspect().clock);
await page.evaluate(()=>{window.telegramPasteCount=0;document.querySelector('#studio-telegram-token').addEventListener('paste',()=>window.telegramPasteCount++);});
for(let attempt=0;attempt<3;attempt++){
 if(await page.evaluate(()=>!!navigator.clipboard))await page.evaluate(()=>navigator.clipboard.writeText('123456789:'+'x'.repeat(30)));
 else{
  // HTTP LAN origins have no Clipboard API. Seed the native clipboard from
  // a user click, then test the same real paste event into the token field.
  await page.evaluate(()=>{
   const button=document.createElement('button');button.id='qa-seed-clipboard';button.textContent='Seed fixture clipboard';
   button.onclick=()=>{const field=document.createElement('textarea');field.value='123456789:'+'x'.repeat(30);button.after(field);field.select();window.qaClipboardSeeded=document.execCommand('copy');field.remove();};
   document.querySelector('#studio-dialog').append(button);
  });
  await page.locator('#qa-seed-clipboard').click();assert(await page.evaluate(()=>window.qaClipboardSeeded));
  await page.locator('#qa-seed-clipboard').evaluate(e=>e.remove());
 }
 await page.locator('#studio-telegram-token').focus();
 await page.keyboard.press(process.platform==='darwin'?'Meta+A':'Control+A');
 await page.keyboard.press(process.platform==='darwin'?'Meta+V':'Control+V');
 assert.equal(await page.locator('#studio-telegram-token').inputValue(),'123456789:'+'x'.repeat(30));
}
await page.waitForTimeout(3200); // Cross two state polling ticks with the draft focused.
assert.equal(await page.evaluate(()=>document.activeElement.id),'studio-telegram-token');
assert.equal(await page.evaluate(()=>window.telegramPasteCount),3);
assert.equal(await page.evaluate(()=>BacCampus.inspect().clock),modalClock);
assert.deepEqual(telegramWrites,[]);
await page.locator('#studio-settings-location-tab').click();await page.locator('#studio-settings-telegram-tab').click();
assert.equal(await page.locator('#studio-telegram-token').inputValue(),'123456789:'+'x'.repeat(30));
await page.locator('#studio-telegram-token').fill('123456789:'+'z'.repeat(30));await page.locator('#studio-telegram-chat').fill('12345');await page.locator('#studio-save-settings').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent.includes('could not confirm'));
await page.locator('#studio-telegram-token').fill('123456789:'+'x'.repeat(30));await page.locator('#studio-save-settings').click();await page.waitForFunction(()=>document.querySelector('#studio-telegram-status').textContent.includes('Connected to'));
assert.equal(await page.locator('#studio-telegram-token').inputValue(),'');await page.locator('#studio-telegram-test').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent==='Test message sent.');
assert(!await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}).includes('123456789:')));
await page.screenshot({path:'/tmp/bac-heartbeat-telegram.png'});
await page.locator('#studio-dialog').evaluate(node=>node.close());
await page.waitForFunction(previous=>BacCampus.inspect().clock>previous,modalClock);
await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
await page.locator('#studio-name').fill('Echo');await page.getByRole('button',{name:'Tech Radar',exact:true}).click();await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Echo');await page.waitForFunction(()=>BacStudio.inspect().room==='lounge');
await page.waitForFunction(()=>document.querySelector('#studio-conversation').textContent.includes('TEST FIXTURE:'));
await page.locator('#studio-radar-monitor button').click();await page.waitForFunction(()=>document.querySelector('#studio-radar-monitor').textContent.includes('Paused'));
await page.waitForTimeout(3500);assert.equal(await page.locator('.chat-turn').count(),1);
await page.locator('#studio-radar-monitor button').click();await page.waitForFunction(()=>!document.querySelector('#studio-radar-monitor').textContent.includes('Paused'));
assert.match(await page.locator('.heartbeat-source').innerText(),/Technical discovery.*Published/s);
assert.match(await page.locator('.heartbeat-source a').getAttribute('href'),/^https:\/\/(developer.nvidia.com|huggingface.co)\/blog\//);
assert.equal(await page.locator('.chat-turn .chat-user').count(),0);assert.match(await page.locator('.chat-turn').innerText(),/Heartbeat/);assert.match(await page.locator('.chat-turn').innerText(),/Sent to Telegram/);
await page.screenshot({path:'/tmp/bac-tech-radar-chat.png'});
await page.waitForTimeout(3500);assert.equal(await page.locator('.chat-turn').count(),1);
await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Echo');await page.getByRole('button',{name:'Settings',exact:true}).click();await page.locator('[data-connection-tab=telegram]').click();await page.locator('#studio-settings-telegram-panel').waitFor({state:'visible'});assert(await page.locator('#studio-telegram-status').isHidden());
assert(await page.locator('#studio-telegram-test').isHidden());assert(await page.locator('#studio-telegram-disconnect').isHidden());
await page.locator('#studio-telegram-token').fill('123456789:'+'x'.repeat(30));await page.locator('#studio-telegram-chat').fill('12345');await page.locator('#studio-save-settings').click();
await page.waitForFunction(()=>!document.querySelector('#studio-telegram-controls').hidden);
assert(await page.locator('#studio-telegram-test').isVisible());
await page.locator('#studio-telegram-disconnect').click();await page.waitForFunction(()=>document.querySelector('#studio-telegram-controls').hidden);
assert(await page.locator('#studio-telegram-status').isHidden());assert.equal(await page.locator('#studio-settings-status').textContent(),'Disconnected.');
assert(await page.locator('#studio-save-settings').isEnabled());
await page.locator('#studio-dialog').evaluate(node=>node.close());
await page.locator('.world-room-map [data-world-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
assert.equal(await page.getByRole('button',{name:'Three Takeaways',exact:true}).count(),0);
await page.locator('#studio-name').fill('Paper');await page.getByRole('button',{name:'Arxivbot',exact:true}).click();
assert(await page.locator('#studio-skill-picker input[value=web]').isChecked());
assert(!await page.locator('#studio-skill-picker input[value=radar]').isChecked());
assert(!await page.locator('#studio-skill-picker input[value=documents]').isChecked());
await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Paper'&&BacStudio.inspect().room==='lounge');
const paperProfile=await page.evaluate(()=>BacStudio.inspect().profile);
assert.deepEqual(paperProfile.skills,['web']);assert.match(paperProfile.purpose,/find three relevant arXiv papers/);
assert(await page.locator('#studio-radar-monitor').isHidden());
await page.screenshot({path:'/tmp/bac-arxivbot.png'});
assert.deepEqual(errors,[]);console.log('PASS: Telegram native paste without requests or draft loss, paused/resumed scene, invalid token feedback, session-only token, explicit test, Tech Radar hire, pause/resume, native-summary chat rendering, one relay, reload disconnection and on-demand Arxivbot without heartbeat.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
