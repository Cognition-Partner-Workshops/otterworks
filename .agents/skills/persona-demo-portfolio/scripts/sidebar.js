// node sidebar.js <area> <identity> [out.png]
// Signs in as the persona and prints the sessions its sidebar shows (title and path).
const { personaPage, APP } = require('./persona_page.js');
(async () => {
  const [area, identity, out] = process.argv.slice(2);
  const { ctx, p } = await personaPage(area, identity, `${APP}/`);
  await p.waitForTimeout(5000);
  console.log('landed:', p.url());
  if (out) await p.screenshot({ path: out, fullPage: false });
  const rows = await p.locator('a[href*="/sessions/"]').evaluateAll(as =>
    as.map(a => [a.innerText.replace(/\s+/g, ' ').trim(), a.getAttribute('href')]).filter(r => r[0]));
  const seen = new Set();
  for (const [title, href] of rows) {
    const key = href + title;
    if (seen.has(key)) continue;
    seen.add(key);
    console.log(`  ${title} ${href}`);
  }
  console.log(`sessions: ${seen.size}`);
  await ctx.close(); process.exit(0);
})().catch(e => { console.error(e.message); process.exit(1); });
