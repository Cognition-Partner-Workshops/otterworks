import { expect, type Locator, type Page } from "@playwright/test";
import { adminTest } from "../support/admin-session";

export const LEGACY_SOURCE =
  "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/AuditTest.java";

// Legacy data from AuditTest.java / AuditPage.java, verbatim.
export const legacyAudit = {
  Path: "/audit",
  Heading: "Audit Logs",
  SearchValue: "document",
  ActionFilterLabel: "Action",
  // AuditPage.java located the search input by this placeholder; it is identity, not a locator here.
  // The input's accessible name comes from its mat-label (audit.component.ts).
  LegacySearchPlaceholder: "Search by user, action, or resource",
  SearchLabel: "Search audit events",
} as const;

// Options rendered by the Action mat-select in frontend/admin-dashboard/src/app/pages/audit/audit.component.ts.
export const actionFilterOptions = [
  "All Actions", "Create", "Update", "Delete", "Share", "Login", "Upload", "Download", "Suspend",
];

export class AuditPage {
  readonly heading: Locator;
  readonly searchBox: Locator;
  readonly actionFilter: Locator;
  readonly actionOptions: Locator;

  constructor(readonly page: Page) {
    this.heading = page.getByRole("heading", { level: 1, name: legacyAudit.Heading, exact: true });
    this.searchBox = page.getByRole("textbox", { name: legacyAudit.SearchLabel });
    this.actionFilter = page.getByRole("combobox", { name: legacyAudit.ActionFilterLabel });
    this.actionOptions = page.getByRole("listbox", { name: legacyAudit.ActionFilterLabel }).getByRole("option");
  }

  async open(): Promise<void> {
    const auditLogs = this.page.waitForResponse(response =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/admin/audit-logs",
    );
    await this.page.goto(legacyAudit.Path);
    expect((await auditLogs).status()).toBe(200);
  }

  eventRow(resourceId: string): Locator {
    return this.page.getByRole("row").filter({ hasText: resourceId });
  }
}

type FeatureFlag = { id: string; name: string };

export const test = adminTest.extend<{
  auditPage: AuditPage;
  // Two real audit events (feature_flag.created) for this test's own gateway user:
  // `matching` carries the legacy search value in its changes_made description, `other` does not.
  auditSearchEvents: { matching: FeatureFlag; other: FeatureFlag };
}>({
  auditPage: async ({ page, adminSession }, use) => {
    void adminSession;
    await use(new AuditPage(page));
  },
  auditSearchEvents: async ({ adminData }, use) => {
    const matching = await adminData.createFeatureFlag({
      description: `Legacy audit search ${legacyAudit.SearchValue} event`,
    });
    const other = await adminData.createFeatureFlag({ description: "Legacy audit search control event" });
    await use({ matching, other });
  },
});
export { expect } from "@playwright/test";
