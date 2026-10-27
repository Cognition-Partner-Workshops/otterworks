import { expectGatewaySession } from "../support/admin-session";
import { LEGACY_SOURCE, actionFilterOptions, expect, legacyAudit, test } from "./fixtures";

test.describe("Selenium AuditTest", () => {
  test("SEL-AuditTest-auditPageShowsHeading auditPageShowsHeading", {
    tag: ["@SEL-AuditTest-auditPageShowsHeading", "@selenium-AuditTest"],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#auditPageShowsHeading` },
  }, async ({ page, adminSession, auditPage }) => {
    await test.step("SEL-AuditTest-auditPageShowsHeading-STEP-01 Open /audit", async () => {
      await auditPage.open();
      await expect(page).toHaveURL(/\/audit$/);
      await expectGatewaySession(page, adminSession);
    });
    await test.step("SEL-AuditTest-auditPageShowsHeading-STEP-02 Verify heading Audit Logs", async () => {
      await expect(auditPage.heading).toHaveText(legacyAudit.Heading);
    });
  });

  test("SEL-AuditTest-auditSearchAcceptsText auditSearchAcceptsText", {
    tag: ["@SEL-AuditTest-auditSearchAcceptsText", "@selenium-AuditTest"],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#auditSearchAcceptsText` },
  }, async ({ page, adminSession, auditPage, auditSearchEvents }) => {
    const { matching, other } = auditSearchEvents;
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-01 Open /audit", async () => {
      await auditPage.open();
      await expectGatewaySession(page, adminSession);
      await expect(auditPage.eventRow(other.id)).toBeVisible();
    });
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-02 Enter document in search", async () => {
      // The component filters on (keyup), so type key by key like the legacy sendKeys.
      await auditPage.searchBox.clear();
      await auditPage.searchBox.pressSequentially(legacyAudit.SearchValue);
    });
    await test.step("SEL-AuditTest-auditSearchAcceptsText-STEP-03 Verify search filters audit events", async () => {
      await expect(auditPage.searchBox).toHaveValue(legacyAudit.SearchValue);
      await expect(auditPage.eventRow(matching.id)).toBeVisible();
      await expect(auditPage.eventRow(other.id)).toHaveCount(0);
    });
  });

  test("SEL-AuditTest-actionFilterIsAvailable actionFilterIsAvailable", {
    tag: ["@SEL-AuditTest-actionFilterIsAvailable", "@selenium-AuditTest"],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#actionFilterIsAvailable` },
  }, async ({ page, adminSession, auditPage }) => {
    await test.step("SEL-AuditTest-actionFilterIsAvailable-STEP-01 Open /audit", async () => {
      await auditPage.open();
      await expectGatewaySession(page, adminSession);
    });
    await test.step("SEL-AuditTest-actionFilterIsAvailable-STEP-02 Verify Action filter is available", async () => {
      await expect(auditPage.actionFilter).toBeEnabled();
      await auditPage.actionFilter.click();
      await expect(auditPage.actionOptions).toHaveText(actionFilterOptions);
    });
  });
});
