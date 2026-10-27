import { test, expect, details } from "../support/admin-session";

test("ADM-AUD-001 find a feature creation in the audit trail", details("ADM-AUD-001", "audit", "audit"), async ({ page, adminData }) => {
  const flag = await adminData.createFeatureFlag();
  await test.step("Search audit events for the unique feature description", async () => {
    await page.goto("/audit");
    await page.getByLabel("Search audit events").pressSequentially(flag.description);
    const row = page.getByRole("row").filter({ hasText: flag.id });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("create");
    await expect(row).toContainText("FeatureFlag");
    await expect(row).toContainText(flag.description);
  });
});
