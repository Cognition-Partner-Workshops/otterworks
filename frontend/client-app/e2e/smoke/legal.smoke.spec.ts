import { test, expect } from "./legal.fixtures";

const pages = [
  { route: "/terms", heading: "Terms of Service", firstClause: "1. Acceptance of Terms." },
  { route: "/privacy", heading: "Privacy Policy", firstClause: "1. Information We Collect." },
];

for (const { route, heading, firstClause } of pages) {
  test(`legal ${route} shows the ${heading} to a signed-in customer`, {
    tag: ["@smoke", "@page-legal"],
    annotation: { type: "route", description: route },
  }, async ({ page, customer: _signedIn }) => {
    const profile = page.waitForResponse((r) => r.url().endsWith("/api/v1/auth/profile"));
    await page.goto(route);
    expect((await profile).status()).toBe(200);

    await expect(page).toHaveURL(new RegExp(`${route}$`));
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(main).toContainText(firstClause);
  });
}
