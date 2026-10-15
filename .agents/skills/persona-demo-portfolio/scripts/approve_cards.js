// node approve_cards.js <area> <identity> <session_id> [session_id ...]
// Signs in as the persona and presses the approval cards a session is holding
// (automations, scans, child sessions, tool permissions). Prints what it pressed.
const { personaPage, APP, text } = require('./persona_page.js');
const LABELS = ['Add to automation', 'Update automation', 'Run now', 'Run automation', 'Approve', 'Allow for this session', 'Confirm'];
(async () => {
  const [area, identity, ...sids] = process.argv.slice(2);
  const { ctx, p } = await personaPage(area, identity);
  for (const sid of sids) {
    await p.goto(`${APP}/sessions/${sid}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await p.waitForTimeout(6000);
    const pressed = [];
    for (let round = 0; round < 3; round++) {
      let hit = false;
      for (const label of LABELS) {
        const b = p.getByRole('button', { name: label, exact: true }).first();
        if (await b.isVisible().catch(() => false)) {
          await b.click();
          pressed.push(label);
          hit = true;
          await p.waitForTimeout(3000);
        }
      }
      if (!hit) break;
    }
    console.log(JSON.stringify({ sid, pressed, title: (await p.title()).replace(/ - Devin$/, '') }));
  }
  await ctx.close(); process.exit(0);
})().catch(e => { console.error(e.message); process.exit(1); });
