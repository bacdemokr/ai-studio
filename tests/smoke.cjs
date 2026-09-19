const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
    const errors = [];
    const externalRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    const url = process.env.BASE_URL || pathToFileURL(path.resolve(__dirname, '../app/index.html')).href;
    page.on('request', request => {
      if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) {
        externalRequests.push(request.url());
      }
    });
    const click = selector => page.locator(selector).first().click();
    const next = () => click('[data-action="next"]');
    const artifact = () => page.locator('[data-out="artifact"]').innerText();
    const english = async () => assert(!/[가-힣]/.test(await page.locator('#bac-planner').innerText()));
    await page.goto(url);
    await click('[data-mode="crew"]');
    assert.equal(await page.locator('[name="region"]').inputValue(), 'Europe (EMEA)');
    assert.equal(await page.locator('[name="location"]').inputValue(), 'Zurich');
    assert.equal(await page.locator('[name="language"]').inputValue(), 'en');
    await english();
    await click('button[type="submit"]');
    await next();
    await next();
    assert(await page.locator('[data-part="capacity"]').isVisible());
    assert(await page.locator('[data-action="next"]').isDisabled());
    assert.match(await artifact(), /DGX Spark 3/);
    assert.match(await artifact(), /Staff 8/);
    await click('[data-view-switch="board"]');
    assert.equal(await page.locator('#bac-planner').getAttribute('data-view'), 'board');
    await click('[data-action="extend"]');
    assert.match(await artifact(), /DGX Spark 2/);
    assert.match(await artifact(), /Staff 7/);
    await next();
    assert.match(await artifact(), /Zurich/);
    assert.match(await artifact(), /210 minutes/);
    await next();
    await next();
    await click('[data-action="approve"]');
    assert.match(await page.locator('[data-out="flow-text"]').innerText(), /No real email/);
    await english();

    await click('[data-action="onboard"]');
    await page.locator('[data-input="agent-name"]').fill('Riley');
    await click('[data-action="solo"]');
    assert.match(await page.locator('[data-out="solo-output"]').innerText(), /Example response/);
    await click('[data-action="join"]');
    assert.match(await page.locator('[data-out="profile-title"]').innerText(), /Riley/);
    await next();
    await page.locator('[name="region"]').selectOption('North America');
    await page.locator('[name="location"]').fill('Austin');
    await click('button[type="submit"]');
    await next(); await next(); await next();
    assert.match(await artifact(), /Austin/);
    assert.match(await artifact(), /North America/);
    await next(); await next();
    await click('[data-action="deny"]');
    assert.match(await page.locator('[data-out="flow-text"]').innerText(), /Drafts were kept locally/);

    for (const width of [736, 360]) {
      await page.setViewportSize({ width, height: 1200 });
      await page.emulateMedia({ colorScheme: width === 360 ? 'dark' : 'light' });
      for (const view of ['village', 'board']) {
        await click('[data-view-switch="' + view + '"]');
        await click('[data-artifact="operations"]');
        await english();
        assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)), 'Page overflow');
        assert(!(await page.locator('[data-out="artifact"]').evaluate(el => el.scrollWidth > el.clientWidth + 1)), 'Artifact overflow');
      }
    }

    await page.reload();
    await click('[data-mode="crew"]');
    assert.equal(await page.locator('[name="location"]').inputValue(), 'Zurich');
    await page.locator('details').first().evaluate(el => { el.open = true; });
    await page.locator('[name="share0"]').fill('40');
    await click('button[type="submit"]');
    assert.match(await page.locator('[data-out="form-error"]').innerText(), /100%/);
    assert.deepEqual(errors, []);
    assert.deepEqual(externalRequests, [], 'The standalone application must not need external resources');
    console.log('PASS: defaults, sizing, capacity recovery, shared A/C views, approvals and denials, onboarding, localization, validation, responsive layouts and offline resources.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
