const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try {
    const page = await browser.newPage({viewport:{width:1320,height:1100}});
    const errors = [], remote = [];
    const url = process.env.BASE_URL || pathToFileURL(path.resolve(__dirname,'../app/index.html')).href;
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {if(/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) remote.push(request.url());});
    const click = selector => page.locator(selector).first().click();
    const result = () => page.locator('#pg-result').innerText();
    const run = () => click('#pg-run');
    const mission = id => click('[data-mission="'+id+'"]');
    await page.goto(url);
    await click('[data-mode="playground"]');
    assert(await page.locator('#bac-playground').isVisible());
    assert(!(await page.locator('[data-part="planner"]').isVisible()));
    await page.locator('#pg-name').fill('Riley');
    await page.locator('#pg-persona').selectOption('precise');
    await run();
    assert.match(await result(), /Fictional forecast/);
    assert.match(await result(), /16 °C/);
    assert.match(await result(), /Based on the supplied practice data/);
    await page.locator('[data-equip="weather"]').uncheck();
    await run();
    assert.match(await page.locator('#pg-error').innerText(), /Equip Weather lookout/);
    await page.locator('[data-equip="weather"]').check();
    await page.locator('#pg-block').check();
    await run();
    assert(await page.locator('#pg-permission').isVisible());
    await click('#pg-deny');
    assert.match(await result(), /Kept blocked/);
    await run();
    await click('#pg-allow');
    assert.match(await result(), /Fictional forecast/);
    await page.locator('#pg-block').uncheck();

    await mission('memory');
    await page.locator('[data-equip="memory"]').check();
    await page.locator('#pg-note').fill('I like short demos with clear evidence.');
    await run();
    assert.match(await result(), /Saved in this session/);
    await mission('search');
    await run();
    assert.equal(await page.locator('.pg-evidence article').count(),3);
    assert.match(await result(), /short demos with clear evidence/);
    await click('.pg-evidence summary');
    assert(await page.locator('.pg-evidence details').first().getAttribute('open') !== null);
    if (process.env.SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'playground-desktop.png'),fullPage:true});
    }

    await mission('telegram');
    await page.locator('[data-equip="telegram"]').check();
    await run();
    assert.match(await page.locator('#pg-error').innerText(), /Pair the practice phone/);
    await click('#pg-pair');
    await page.locator('#pg-message').selectOption('note');
    await run();
    assert.match(await result(), /short demos with clear evidence/);
    await click('#pg-allow');
    assert.match(await result(), /not delivered/);
    await run();
    await page.locator('#pg-message').selectOption('intro');
    assert(!(await page.locator('#pg-permission').isVisible()),'Changed request must invalidate approval');
    await page.locator('#pg-allow').evaluate(button=>button.click());
    assert.doesNotMatch(await result(), /Phone preview/);

    await click('#pg-join');
    assert(await page.locator('[data-part="onboard"]').isVisible());
    assert.equal(await page.locator('[data-input="agent-name"]').inputValue(),'Riley');
    assert.equal(await page.locator('[data-input="agent-persona"]').inputValue(),'precise');
    assert.match(await page.locator('[data-out="agent-skills"]').innerText(),/Telegram buddy/);
    await click('[data-action="join"]');
    assert.match(await page.locator('[data-out="profile-title"]').innerText(),/Riley/);
    assert.match(await page.locator('[data-out="profile-facts"]').innerText(),/Weather lookout/);
    await click('button[type="submit"]');
    await click('[data-action="next"]'); await click('[data-action="next"]');
    await click('[data-action="extend"]');
    await click('[data-mode="playground"]');
    await page.locator('#pg-message').selectOption('plan');
    await run();
    assert.match(await result(),/210 minutes/);
    assert.match(await result(),/Zurich/);
    await click('#pg-allow');

    for (const width of [736,360]) {
      await page.setViewportSize({width,height:1100});
      await page.emulateMedia({colorScheme:width===360?'dark':'light'});
      for (const id of ['weather','search','telegram','memory']) {
        await mission(id); await run();
        assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),id+' horizontal overflow');
      }
      if(process.env.SCREENSHOT_DIR && width===360) await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'playground-mobile.png'),fullPage:true});
    }
    await click('#pg-forget');
    assert.match(await page.locator('#pg-memory-summary').innerText(),/Nothing remembered/);
    await page.reload();
    assert.equal(await page.locator('#pg-name').inputValue(),'Jinny');
    assert.match(await page.locator('#pg-memory-summary').innerText(),/Nothing remembered/);
    assert.deepEqual(errors,[]);
    assert.deepEqual(remote,[]);
    console.log('PASS: four skill missions, skill gating, access decisions, stale approvals, session notes, identity/skills handoff, updated shared brief, responsive layouts and offline operation.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
