import { expectGatewaySession } from "../support/admin-session";
import { expect, FeaturesLegacyData, test } from "./fixtures";

const SOURCE = "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/FeaturesTest.java";

test.describe("Selenium FeaturesTest", () => {
  test("SEL-FeaturesTest-featurePageShowsHeading featurePageShowsHeading", {
    tag: ["@SEL-FeaturesTest-featurePageShowsHeading", "@selenium-FeaturesTest"],
    annotation: { type: "selenium", description: `${SOURCE}#featurePageShowsHeading` },
  }, async ({ page, adminSession, featuresPage }) => {
    await test.step("SEL-FeaturesTest-featurePageShowsHeading-STEP-01 Open /features", async () => {
      await featuresPage.goto();
      await expectGatewaySession(page, adminSession);
    });

    await test.step("SEL-FeaturesTest-featurePageShowsHeading-STEP-02 Verify heading text", async () => {
      await expect(featuresPage.heading).toHaveText(FeaturesLegacyData.heading);
    });
  });

  test("SEL-FeaturesTest-featureSearchCanBeApplied featureSearchCanBeApplied", {
    tag: ["@SEL-FeaturesTest-featureSearchCanBeApplied", "@selenium-FeaturesTest"],
    annotation: { type: "selenium", description: `${SOURCE}#featureSearchCanBeApplied` },
  }, async ({ page, adminSession, featuresPage, searchFlags }) => {
    await test.step("SEL-FeaturesTest-featureSearchCanBeApplied-STEP-01 Open /features", async () => {
      await featuresPage.goto();
      await expectGatewaySession(page, adminSession);
      await expect(featuresPage.flagHeading(searchFlags.matching.name)).toBeVisible();
      await expect(featuresPage.flagHeading(searchFlags.nonMatching.name)).toBeVisible();
    });

    await test.step("SEL-FeaturesTest-featureSearchCanBeApplied-STEP-02 Enter search term", async () => {
      await featuresPage.search(FeaturesLegacyData.searchTerm);
    });

    await test.step("SEL-FeaturesTest-featureSearchCanBeApplied-STEP-03 Verify search input value", async () => {
      await expect(featuresPage.searchBox).toHaveValue(FeaturesLegacyData.searchTerm);
    });

    // Not in the legacy body (it only read the input back): the name promises the search is applied to the list.
    await test.step("SEL-FeaturesTest-featureSearchCanBeApplied-STEP-04 Verify flag list is filtered", async () => {
      await expect(featuresPage.flagHeading(searchFlags.matching.name)).toBeVisible();
      await expect(featuresPage.flagHeading(searchFlags.nonMatching.name)).toHaveCount(0);
    });
  });

  test("SEL-FeaturesTest-featureToggleCanBeSelected featureToggleCanBeSelected", {
    tag: ["@SEL-FeaturesTest-featureToggleCanBeSelected", "@selenium-FeaturesTest"],
    annotation: { type: "selenium", description: `${SOURCE}#featureToggleCanBeSelected` },
  }, async ({ page, request, adminSession, featuresPage, disabledFlag }) => {
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-01 Open /features", async () => {
      await featuresPage.goto();
      await expectGatewaySession(page, adminSession);
    });

    // Legacy guarded the body with `if (featureCount() > 0)`; the seeded flag makes the card unconditional.
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-02 Verify flag card present", async () => {
      await featuresPage.search(disabledFlag.name);
      await expect(featuresPage.flagHeading(disabledFlag.name)).toBeVisible();
      await expect(featuresPage.switches).toHaveCount(1);
      await expect(featuresPage.switches).not.toBeChecked();
    });

    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-03 Click feature toggle", async () => {
      const updateResponse = page.waitForResponse(response =>
        response.request().method() === "PUT" &&
        new URL(response.url()).pathname === `/api/v1/admin/features/${disabledFlag.id}`,
      );
      await featuresPage.switches.click();
      expect((await updateResponse).status()).toBe(200);
    });

    // Legacy only re-counted cards (> 0); the name promises the toggle took effect, so assert the flag is now on.
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-04 Verify feature toggled on", async () => {
      await expect(featuresPage.switches).toBeChecked();
      await expect.poll(async () => {
        const response = await request.get(`/api/v1/admin/features/${disabledFlag.id}`, { headers: adminSession.headers });
        expect(response.status()).toBe(200);
        return ((await response.json()) as { enabled: boolean }).enabled;
      }).toBe(true);
      await featuresPage.goto();
      await featuresPage.search(disabledFlag.name);
      await expect(featuresPage.flagHeading(disabledFlag.name)).toBeVisible();
      await expect(featuresPage.switches).toBeChecked();
    });
  });
});
