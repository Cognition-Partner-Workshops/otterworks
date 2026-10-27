import { expectGatewaySession } from "../support/admin-session";
import { expect, LegacyHealth, test } from "./fixtures";

const SOURCE = "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/HealthTest.java";

test.describe("Selenium HealthTest", () => {
  test("SEL-HealthTest-healthPageShowsHeading healthPageShowsHeading", {
    tag: ["@SEL-HealthTest-healthPageShowsHeading", "@selenium-HealthTest"],
    annotation: { type: "selenium", description: `${SOURCE}#healthPageShowsHeading` },
  }, async ({ page, adminSession, healthPage }) => {
    await test.step("SEL-HealthTest-healthPageShowsHeading-STEP-01 Open /health", async () => {
      await page.goto(LegacyHealth.path);
      await expect(page).toHaveURL(LegacyHealth.path);
      await expectGatewaySession(page, adminSession);
    });
    await test.step("SEL-HealthTest-healthPageShowsHeading-STEP-02 Verify heading System Health", async () => {
      await expect(healthPage.heading).toHaveText(LegacyHealth.heading);
    });
  });

  test("SEL-HealthTest-healthSummaryIsDisplayed healthSummaryIsDisplayed", {
    tag: ["@SEL-HealthTest-healthSummaryIsDisplayed", "@selenium-HealthTest"],
    annotation: { type: "selenium", description: `${SOURCE}#healthSummaryIsDisplayed` },
  }, async ({ page, adminSession, healthPage }) => {
    let loaded!: Awaited<ReturnType<typeof healthPage.open>>;
    await test.step("SEL-HealthTest-healthSummaryIsDisplayed-STEP-01 Open /health", async () => {
      loaded = await healthPage.open();
      expect(loaded.status).toBe(200);
      expect(loaded.authorization).toBe(`Bearer ${adminSession.accessToken}`);
      await expectGatewaySession(page, adminSession);
    });
    await test.step("SEL-HealthTest-healthSummaryIsDisplayed-STEP-02 Verify health summary", async () => {
      await healthPage.expectSummary(loaded.counts);
    });
  });

  test("SEL-HealthTest-healthDataCanBeRefreshed healthDataCanBeRefreshed", {
    tag: ["@SEL-HealthTest-healthDataCanBeRefreshed", "@selenium-HealthTest"],
    annotation: { type: "selenium", description: `${SOURCE}#healthDataCanBeRefreshed` },
  }, async ({ page, adminSession, healthPage }) => {
    await test.step("SEL-HealthTest-healthDataCanBeRefreshed-STEP-01 Open /health", async () => {
      const loaded = await healthPage.open();
      expect(loaded.status).toBe(200);
      await expectGatewaySession(page, adminSession);
      await healthPage.expectSummary(loaded.counts);
    });
    let refreshed!: Awaited<ReturnType<typeof healthPage.open>>;
    await test.step("SEL-HealthTest-healthDataCanBeRefreshed-STEP-02 Click Refresh", async () => {
      refreshed = await healthPage.healthResponseFrom(() => healthPage.refreshButton.click());
      expect(refreshed.status).toBe(200);
      expect(refreshed.authorization).toBe(`Bearer ${adminSession.accessToken}`);
    });
    await test.step("SEL-HealthTest-healthDataCanBeRefreshed-STEP-03 Verify heading System Health and refreshed summary", async () => {
      await expect(healthPage.heading).toHaveText(LegacyHealth.heading);
      await healthPage.expectSummary(refreshed.counts);
    });
  });
});
