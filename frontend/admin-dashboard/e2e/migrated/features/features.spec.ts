import { waitForAdminApi } from "../support/admin-session";
import { expect, FeaturesLegacyData, test } from "./fixtures";
import { legacyDetails } from "../support/traceability";

const SOURCE = "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/FeaturesTest.java";

test.describe("Selenium FeaturesTest", () => {
  test("SEL-FeaturesTest-featurePageShowsHeading featurePageShowsHeading", {
    ...legacyDetails({ suite: "selenium", id: "SEL-FeaturesTest-featurePageShowsHeading", group: "selenium-FeaturesTest", source: SOURCE, method: "featurePageShowsHeading" }),
  }, async ({ featuresPage }) => {
    await test.step("SEL-FeaturesTest-featurePageShowsHeading-STEP-01 Open /features", async () => {
      await featuresPage.open();
    });

    await test.step("SEL-FeaturesTest-featurePageShowsHeading-STEP-02 Verify heading text", async () => {
      await expect(featuresPage.heading).toHaveText(FeaturesLegacyData.heading);
    });
  });

  test("SEL-FeaturesTest-featureSearchCanBeApplied featureSearchCanBeApplied", {
    ...legacyDetails({ suite: "selenium", id: "SEL-FeaturesTest-featureSearchCanBeApplied", group: "selenium-FeaturesTest", source: SOURCE, method: "featureSearchCanBeApplied" }),
  }, async ({ featuresPage, searchFlags }) => {
    await test.step("SEL-FeaturesTest-featureSearchCanBeApplied-STEP-01 Open /features", async () => {
      await featuresPage.open();
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
    ...legacyDetails({ suite: "selenium", id: "SEL-FeaturesTest-featureToggleCanBeSelected", group: "selenium-FeaturesTest", source: SOURCE, method: "featureToggleCanBeSelected" }),
  }, async ({ page, request, adminSession, featuresPage, disabledFlag }) => {
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-01 Open /features", async () => {
      await featuresPage.open();
    });

    // Legacy guarded the body with `if (featureCount() > 0)`; the seeded flag makes the card unconditional.
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-02 Verify flag card present", async () => {
      await featuresPage.search(disabledFlag.name);
      await expect(featuresPage.flagHeading(disabledFlag.name)).toBeVisible();
      await expect(featuresPage.switches).toHaveCount(1);
      await expect(featuresPage.switches).not.toBeChecked();
    });

    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-03 Click feature toggle", async () => {
      await waitForAdminApi(
        page,
        adminSession,
        { method: "PUT", pathname: `/api/v1/admin/features/${disabledFlag.id}` },
        () => featuresPage.switches.click(),
      );
    });

    // Legacy only re-counted cards (> 0); the name promises the toggle took effect, so assert the flag is now on.
    await test.step("SEL-FeaturesTest-featureToggleCanBeSelected-STEP-04 Verify feature toggled on", async () => {
      await expect(featuresPage.switches).toBeChecked();
      await expect.poll(async () => {
        const response = await request.get(`/api/v1/admin/features/${disabledFlag.id}`, { headers: adminSession.headers });
        expect(response.status()).toBe(200);
        return ((await response.json()) as { enabled: boolean }).enabled;
      }).toBe(true);
      await featuresPage.open();
      await featuresPage.search(disabledFlag.name);
      await expect(featuresPage.flagHeading(disabledFlag.name)).toBeVisible();
      await expect(featuresPage.switches).toBeChecked();
    });
  });
});
