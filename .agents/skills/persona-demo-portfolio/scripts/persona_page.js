// Shared helper: open a Devin webapp page signed in as a Field Kit persona.
// Connects to the Chrome already running on the box over CDP, copies the Field Kit
// cookies from its main profile into a fresh isolated context, completes the SSO
// form for the given area and identity, and returns the page.
const CDP = process.env.CDP_URL || 'http://localhost:29229';
const APP = process.env.DEVIN_APP_URL || 'https://partner-workshops.devinenterprise.com';

function playwright() {
  const candidates = [process.env.PLAYWRIGHT_DIR, 'playwright',
    '/home/ubuntu/repos/field-kit/node_modules/playwright',
    '/home/ubuntu/repos/otterworks/frontend/client-app/node_modules/playwright'];
  for (const c of candidates) {
    if (!c) continue;
    try { return require(c); } catch (e) { /* try the next one */ }
  }
  throw new Error('playwright not found: set PLAYWRIGHT_DIR or run npm i playwright');
}

async function personaPage(area, identity, url) {
  const { chromium } = playwright();
  const browser = await chromium.connectOverCDP(CDP);
  const main = browser.contexts()[0];
  const keep = (await main.cookies()).filter(c => c.domain.includes('fieldkit.devin.ai'));
  if (!keep.length) throw new Error('no Field Kit cookies in the main Chrome profile; run fk_login.js first');
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await ctx.addCookies(keep);
  const p = await ctx.newPage();
  await p.goto(`${APP}/auth/login?redirect=/&reauth=true`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.click('text=Log in with SSO');
  await p.waitForURL(/fieldkit\.devin\.ai/, { timeout: 30000 });
  await p.waitForSelector('select[name=persona]', { timeout: 30000 });
  await p.selectOption('select:not([name=persona])', area);
  await p.waitForTimeout(300);
  await p.selectOption('select[name=persona]', identity);
  await p.click('button[type=submit]');
  await p.waitForURL(new RegExp(APP.replace(/https?:\/\//, '').replace(/\./g, '\\.') + '/'), { timeout: 60000 });
  await p.waitForTimeout(4000);
  if (url) {
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(6000);
  }
  return { ctx, p, app: APP };
}

const text = async (loc) => (await loc.innerText().catch(() => '')).replace(/\s+/g, ' ');

module.exports = { personaPage, playwright, text, APP };
