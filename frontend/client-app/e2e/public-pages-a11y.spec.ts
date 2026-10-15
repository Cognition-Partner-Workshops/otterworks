import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { existsSync, writeFileSync } from "node:fs";
import path from "node:path";

const built = process.env.PUBLIC_PAGES_BUILT === "1" &&
  existsSync(path.resolve(__dirname, "../dist/index.html"));
const pages = ["/", "/login", "/register", "/terms", "/privacy"];

test.describe("Public pages @public-pages-a11y @built", () => {
  test.skip(!built, "Requires npm run build and PUBLIC_PAGES_BUILT=1; no backend needed");

  for (const width of [1440, 390]) {
    for (const colorScheme of ["light", "dark"] as const) {
      test.describe(`${width}px ${colorScheme}`, () => {
        test.use({ viewport: { width, height: 900 }, colorScheme });

        for (const route of pages) {
          test(`${route} has no axe violations`, async ({ page }, testInfo) => {
            await page.goto(route);
            await expect(page.locator("main")).toBeVisible();
            await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
            await page.evaluate(() => document.fonts.ready);
            if (route === "/") {
              const header = await page.locator("header").boundingBox();
              const brand = await page.getByText("OtterWorks, Inc.", { exact: true }).boundingBox();
              expect(header).not.toBeNull();
              expect(brand).not.toBeNull();
              expect(brand!.y).toBeGreaterThanOrEqual(0);
              expect(brand!.y + brand!.height).toBeLessThanOrEqual(header!.y + header!.height);
            }
            const results = await new AxeBuilder({ page }).analyze();
            const report = testInfo.outputPath("axe.json");
            writeFileSync(report, JSON.stringify({ route, width, colorScheme, results }, null, 2));
            await testInfo.attach("axe-results", { path: report, contentType: "application/json" });

            expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
          });
        }
      });
    }
  }
});
