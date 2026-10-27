// Paste into Safari's Web Inspector console on http://localhost:3000/<page>.
// Loads axe-core from the Vite dev server, runs the same WCAG A/AA tags as the
// Playwright check, outlines each violating element and lists the findings.
(async () => {
  document.getElementById("axe-overlay-panel")?.remove();
  document.querySelectorAll("[data-axe-flag]").forEach((el) => {
    el.style.outline = ""; el.removeAttribute("data-axe-flag");
  });
  if (!window.axe) {
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "/node_modules/axe-core/axe.min.js";
      s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  const results = await window.axe.run(document, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  const panel = document.createElement("div");
  panel.id = "axe-overlay-panel";
  panel.setAttribute("aria-hidden", "true");
  panel.style.cssText =
    "position:fixed;right:12px;bottom:12px;z-index:2147483647;max-width:440px;max-height:60vh;overflow:auto;" +
    "font:13px/1.4 -apple-system,sans-serif;background:#111;color:#fff;padding:12px 14px;border-radius:6px;box-shadow:0 4px 18px rgba(0,0,0,.4)";
  const ua = navigator.userAgent.match(/Version\/[\d.]+ Safari/)?.[0] ?? navigator.userAgent;
  const lines = [`<b>axe-core ${window.axe.version}</b> · ${ua}<br>${location.pathname} · WCAG 2.1 A/AA`];
  if (results.violations.length === 0) {
    lines.push(`<div style="color:#4ade80;font-weight:600;margin-top:6px">0 violations</div>`);
  }
  for (const v of results.violations) {
    lines.push(`<div style="margin-top:8px;color:#f87171;font-weight:600">${v.id} (${v.impact}) — ${v.nodes.length} element(s)</div>`);
    for (const n of v.nodes) {
      const el = document.querySelector(n.target.join(" "));
      if (el) { el.style.outline = "3px solid #ef4444"; el.style.outlineOffset = "2px"; el.setAttribute("data-axe-flag", v.id); }
      const cc = n.any.find((c) => c.id === "color-contrast")?.data;
      const detail = cc ? ` — ${cc.fgColor} on ${cc.bgColor} = ${cc.contrastRatio}:1 (needs ${cc.expectedContrastRatio})` : "";
      lines.push(`<div style="opacity:.85">• ${n.target.join(" ")}${detail}</div>`);
    }
  }
  panel.innerHTML = lines.join("");
  document.body.appendChild(panel);
  console.log("axe violations", results.violations.map((v) => ({ id: v.id, impact: v.impact, targets: v.nodes.map((n) => n.target.join(" ")) })));
  return results.violations.length;
})();
