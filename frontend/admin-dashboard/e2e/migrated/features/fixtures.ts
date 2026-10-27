import { randomUUID } from "node:crypto";
import { adminTest } from "../support/admin-session";
import { FeaturesPage } from "./features-page";

// Legacy data: literals from tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/
// tests/FeaturesTest.java and pages/FeaturesPage.java, kept verbatim.
export const FeaturesLegacyData = {
  route: "/features",
  heading: "Feature Flags",
  searchTerm: "search",
  // FeaturesPage.searchInput identity; the input's accessible name is its mat-label "Search features" instead.
  searchPlaceholder: "Search by name or description",
} as const;

export interface SeededFlag {
  id: string;
  name: string;
  enabled: boolean;
}

function uniqueSuffix(): string {
  return randomUUID().replaceAll("-", "").slice(0, 8);
}

// Seeded names start with "a_" so they sort onto the first page: the Features page shows only the first 20 flags
// of GET /api/v1/admin/features (ordered by name, default per_page 20, no paging UI).
export const test = adminTest.extend<{
  featuresPage: FeaturesPage;
  searchFlags: { matching: SeededFlag; nonMatching: SeededFlag };
  disabledFlag: SeededFlag;
}>({
  featuresPage: async ({ page, adminSession }, use) => {
    void adminSession;
    await use(new FeaturesPage(page));
  },
  searchFlags: async ({ adminData }, use) => {
    const suffix = uniqueSuffix();
    const matching = await adminData.createFeatureFlag({
      name: `a_features_${FeaturesLegacyData.searchTerm}_${suffix}`,
      description: "Seeded by the migrated Features suite (matches the term)",
      enabled: true,
    });
    const nonMatching = await adminData.createFeatureFlag({
      name: `a_features_other_${suffix}`,
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
      name: `a_features_toggle_${uniqueSuffix()}`,
      description: "Seeded disabled by the migrated Features suite",
      enabled: false,
    });
    await use({ id: flag.id, name: flag.name, enabled: false });
  },
});

export { expect } from "@playwright/test";
