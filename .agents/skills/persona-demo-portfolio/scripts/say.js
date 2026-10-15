// node say.js <area> <identity> <session_id> "<message>"
// Signs in as the persona and posts one message to the session, as the human it was asked of.
const { personaPage, APP } = require('./persona_page.js');
(async () => {
  const [area, identity, sid, message] = process.argv.slice(2);
  const { ctx, p } = await personaPage(area, identity, `${APP}/sessions/${sid}`);
  const box = p.locator('main [contenteditable=true], main textarea').last();
  await box.click();
  await box.fill(message);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(4000);
  const shown = await p.locator('main').innerText().then(t => t.includes(message.slice(0, 60))).catch(() => false);
  console.log(JSON.stringify({ sid, posted: shown }));
  await ctx.close(); process.exit(shown ? 0 : 2);
})().catch(e => { console.error(e.message); process.exit(1); });
