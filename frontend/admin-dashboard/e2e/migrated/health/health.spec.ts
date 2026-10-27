import { expect, LegacyHealth, test } from "./fixtures";
import { legacyDetails } from "../support/traceability";

const SOURCE = "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/HealthTest.java";

test.describe("Selenium HealthTest", () => {
  test("SEL-HealthTest-healthPageShowsHeading healthPageShowsHeading", {
    ...legacyDetails({ suite: "selenium", id: "SEL-HealthTest-healthPageShowsHeading", group: "selenium-HealthTest", source: SOURCE, method: "healthPageShowsHeading" }),
  }, async ({ healthPage }) => {
    await test.step("SEL-HealthTest-healthPageShowsHeading-STEP-01 Open /health", async () => {
      const loaded = await healthPage.open();
      expect(loaded.status).toBe(200);
    });
    await test.step("SEL-HealthTest-healthPageShowsHeading-STEP-02 Verify heading System Health", async () => {
      await expect(healthPage.heading).toHaveText(LegacyHealth.heading);
    });
  });

  test("SEL-HealthTest-healthSummaryIsDisplayed healthSummaryIsDisplayed", {
    ...legacyDetails({ suite: "selenium", id: "SEL-HealthTest-healthSummaryIsDisplayed", group: "selenium-HealthTest", source: SOURCE, method: "healthSummaryIsDisplayed" }),
  }, async ({ adminSession, healthPage }) => {
    let loaded!: Awaited<ReturnType<typeof healthPage.open>>;
    await test.step("SEL-HealthTest-healthSummaryIsDisplayed-STEP-01 Open /health", async () => {
      loaded = await healthPage.open();
      expect(loaded.status).toBe(200);
      expect(loaded.authorization).toBe(`Bearer ${adminSession.accessToken}`);
    });
    await test.step("SEL-HealthTest-healthSummaryIsDisplayed-STEP-02 Verify health summary", async () => {
      await healthPage.expectSummary(loaded.counts);
    });
  });

  test("SEL-HealthTest-healthDataCanBeRefreshed healthDataCanBeRefreshed", {
    ...legacyDetails({ suite: "selenium", id: "SEL-HealthTest-healthDataCanBeRefreshed", group: "selenium-HealthTest", source: SOURCE, method: "healthDataCanBeRefreshed" }),
  }, async ({ adminSession, healthPage }) => {
    await test.step("SEL-HealthTest-healthDataCanBeRefreshed-STEP-01 Open /health", async () => {
      const loaded = await healthPage.open();
      expect(loaded.status).toBe(200);
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
