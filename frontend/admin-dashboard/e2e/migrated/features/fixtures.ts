import { adminTest, uniqueFlagName } from "../support/admin-session";
import { FeaturesPage } from "./features-page";

// Legacy data: literals from tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/
// tests/FeaturesTest.java and pages/FeaturesPage.java, kept verbatim.
export const FeaturesLegacyData = {
  route: "/features",
  heading: "Feature Flags",
  searchTerm: "search",
  // FeaturesPage.searchInput identity; the input's accessible name is its mat-label "Search features" instead.
  LegacySearchPlaceholder: "Search by name or description",
} as const;

export interface SeededFlag {
  id: string;
  name: string;
  enabled: boolean;
}

export const test = adminTest.extend<{
  featuresPage: FeaturesPage;
  searchFlags: { matching: SeededFlag; nonMatching: SeededFlag };
  disabledFlag: SeededFlag;
}>({
  featuresPage: async ({ page, adminSession }, use) => {
    await use(new FeaturesPage(page, adminSession));
  },
  searchFlags: async ({ adminData }, use) => {
    // Seeded names start with "a_" so they sort onto the first page (GET /api/v1/admin/features shows 20).
    const matching = await adminData.createFeatureFlag({
      name: uniqueFlagName(`a_features_${FeaturesLegacyData.searchTerm}`),
      description: "Seeded by the migrated Features suite (matches the term)",
      enabled: true,
    });
    const nonMatching = await adminData.createFeatureFlag({
      name: uniqueFlagName("a_features_other"),
      description: "Seeded by the migrated Features suite (does not match the term)",
      enabled: true,
    });
    await use({
      matching: { id: matching.id, name: matching.name, enabled: true },
      nonMatching: { id: nonMatching.id, name: nonMatching.name, enabled: true },
    });
  },
  disabledFlag: async ({ adminData }, use) => {
    const flag = await adminData.createFeatureFlag({
      name: uniqueFlagName("a_features_toggle"),
      description: "Seeded disabled by the migrated Features suite",
      enabled: false,
    });
    await use({ id: flag.id, name: flag.name, enabled: false });
  },
});

export { expect } from "@playwright/test";
