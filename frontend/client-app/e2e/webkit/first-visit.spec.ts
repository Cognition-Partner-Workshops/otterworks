import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

const pages = [
  {
    name: "Landing",
    path: "/",
    heading: { role: "heading", name: "OtterWorks" },
    slug: "landing",
  },
  {
    name: "Sign in",
    path: "/login",
    heading: { role: "button", name: "Sign in" },
    slug: "sign-in",
  },
  {
    name: "Create account",
    path: "/register",
    heading: { role: "button", name: "Create account" },
    slug: "create-account",
  },
] as const;

test.describe("First-visit pages in WebKit", () => {
  for (const pageCase of pages) {
    test(
      `${pageCase.name} has no WCAG A/AA axe violations`,
      { tag: ["@a11y", "@webkit"] },
      async ({ page }, testInfo) => {
        await test.step(`goto ${pageCase.path}`, async () => {
          await page.goto(pageCase.path);
        });

        const readiness = page.getByRole(pageCase.heading.role, {
          name: pageCase.heading.name,
          exact: true,
        });
        await test.step(
          `wait for ${pageCase.heading.role} "${pageCase.heading.name}"`,
          async () => {
            await expect(readiness).toBeVisible();
          },
        );

        const results = await test.step("run axe", async () => {
          const analysis = await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
            .analyze();
          const resultsPath = testInfo.outputPath("axe-results.json");
          await writeFile(resultsPath, JSON.stringify(analysis, null, 2));
          await testInfo.attach("axe-results", {
            path: resultsPath,
            contentType: "application/json",
          });
          return analysis;
        });

        expect(
          results.violations.map((violation) => ({
            id: violation.id,
            impact: violation.impact,
            targets: violation.nodes.map((node) => node.target.join(" ")),
          })),
        ).toEqual([]);
      },
    );

    test(
      `${pageCase.name} matches the WebKit macOS baseline`,
      { tag: ["@visual", "@webkit"] },
      async ({ page }) => {
        await test.step(`goto ${pageCase.path}`, async () => {
          await page.goto(pageCase.path);
        });

        const readiness = page.getByRole(pageCase.heading.role, {
          name: pageCase.heading.name,
          exact: true,
        });
        await test.step(
          `wait for ${pageCase.heading.role} "${pageCase.heading.name}"`,
          async () => {
            await expect(readiness).toBeVisible();
          },
        );

        await test.step("capture screenshot baseline", async () => {
          await expect(page).toHaveScreenshot(`${pageCase.slug}.png`, {
            fullPage: true,
            animations: "disabled",
            caret: "hide",
          });
        });
      },
    );
  }
});
