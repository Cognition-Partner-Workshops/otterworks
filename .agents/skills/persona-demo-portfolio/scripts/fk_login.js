// node fk_login.js
// Signs the main Chrome profile into Field Kit with the magic link in FIELD_KIT_AUTH_URL,
// so later scripts can copy its cookies. If the link page says the key is invalid or
// revoked, paste the same URL into the access key box on fieldkit.devin.ai/sso.html by hand.
const { playwright } = require('./persona_page.js');
(async () => {
  const url = process.env.FIELD_KIT_AUTH_URL;
  if (!url) throw new Error('FIELD_KIT_AUTH_URL is not set');
  const { chromium } = playwright();
  const browser = await chromium.connectOverCDP(process.env.CDP_URL || 'http://localhost:29229');
  const ctx = browser.contexts()[0];
  const p = await ctx.newPage();
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(6000);
  const cookies = (await ctx.cookies()).filter(c => c.domain.includes('fieldkit.devin.ai'));
  console.log(JSON.stringify({ landed: p.url(), fieldKitCookies: cookies.length }));
  await p.close();
  process.exit(cookies.length ? 0 : 2);
})().catch(e => { console.error(e.message); process.exit(1); });
