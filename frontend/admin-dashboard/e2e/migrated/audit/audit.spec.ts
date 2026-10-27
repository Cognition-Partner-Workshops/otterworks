import { LEGACY_SOURCE, actionFilterOptions, expect, legacyAudit, test } from "./fixtures";
import { typeIntoFilter } from "../support/material";
import { legacyDetails } from "../support/traceability";

test.describe("Selenium AuditTest", () => {
  test("SEL-AuditTest-auditPageShowsHeading auditPageShowsHeading", {
    ...legacyDetails({ suite: "selenium", id: "SEL-AuditTest-auditPageShowsHeading", group: "selenium-AuditTest", source: LEGACY_SOURCE, method: "auditPageShowsHeading" }),
  }, async ({ auditPage }) => {
    await test.step("SEL-AuditTest-auditPageShowsHeading-STEP-01 Open /audit", async () => {
      await auditPage.open();
    });
    await test.step("SEL-AuditTest-auditPageShowsHeading-STEP-02 Verify heading Audit Logs", async () => {
      await expect(auditPage.heading).toHaveText(legacyAudit.Heading);
    });
  });

  test("SEL-AuditTest-auditSearchAcceptsText auditSearchAcceptsText", {
    ...legacyDetails({ suite: "selenium", id: "SEL-AuditTest-auditSearchAcceptsText", group: "selenium-AuditTest", source: LEGACY_SOURCE, method: "auditSearchAcceptsText" }),
  }, async ({ auditPage, auditSearchEvents }) => {
    const { matching, other } = auditSearchEvents;
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-01 Open /audit", async () => {
      await auditPage.open();
      await expect(auditPage.eventRow(other.id)).toBeVisible();
    });
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-02 Enter document in search", async () => {
      await typeIntoFilter(auditPage.searchBox, legacyAudit.SearchValue);
    });
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-03 Verify search filters audit events", async () => {
      await expect(auditPage.searchBox).toHaveValue(legacyAudit.SearchValue);
      await expect(auditPage.eventRow(matching.id)).toBeVisible();
      await expect(auditPage.eventRow(other.id)).toHaveCount(0);
    });
  });

  test("SEL-AuditTest-actionFilterIsAvailable actionFilterIsAvailable", {
    ...legacyDetails({ suite: "selenium", id: "SEL-AuditTest-actionFilterIsAvailable", group: "selenium-AuditTest", source: LEGACY_SOURCE, method: "actionFilterIsAvailable" }),
  }, async ({ auditPage }) => {
    await test.step("SEL-AuditTest-actionFilterIsAvailable-STEP-01 Open /audit", async () => {
      await auditPage.open();
    });
    await test.step("SEL-AuditTest-actionFilterIsAvailable-STEP-02 Verify Action filter is available", async () => {
      await expect(auditPage.actionFilter).toBeEnabled();
      await auditPage.actionFilter.click();
      await expect(auditPage.actionOptions).toHaveText(actionFilterOptions);
    });
  });
});
