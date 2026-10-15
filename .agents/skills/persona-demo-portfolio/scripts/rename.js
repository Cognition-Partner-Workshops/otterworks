// node rename.js <area> <identity> <plan.json>
// plan.json maps a 32-character session id to its new title. Signs in once as the persona,
// opens each session, clicks the title in the header and types the new one into the Rename
// box. Nothing is posted to the session and no API key is involved.
const fs = require('fs');
const { personaPage, APP } = require('./persona_page.js');
(async () => {
  const [area, identity, planFile] = process.argv.slice(2);
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
  const { ctx, p } = await personaPage(area, identity);
  for (const [sid, title] of Object.entries(plan)) {
    try {
      await p.goto(`${APP}/sessions/${sid}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await p.waitForTimeout(5000);
      const before = (await p.title()).replace(/ - Devin$/, '');
      if (before === title) { console.log(JSON.stringify({ sid, unchanged: title })); continue; }
      const header = p.locator('header').first();
      await header.locator('div, span, h1').filter({ hasText: before.slice(0, 40) }).last().click();
      const box = p.locator('input[aria-label=Rename]');
      await box.waitFor({ timeout: 10000 });
      await box.fill(title);
      await box.press('Enter');
      await p.waitForTimeout(2500);
      await p.reload({ waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(4000);
      const after = (await p.title()).replace(/ - Devin$/, '');
      console.log(JSON.stringify({ sid, before, after, ok: after === title }));
    } catch (e) { console.log(JSON.stringify({ sid, error: e.message.split('\n')[0] })); }
  }
  await ctx.close(); process.exit(0);
})().catch(e => { console.error(e.message); process.exit(1); });
