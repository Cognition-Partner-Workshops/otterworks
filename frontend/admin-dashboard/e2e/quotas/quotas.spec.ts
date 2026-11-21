import { test, expect } from "../users/fixtures";
import { details } from "../support/admin-session";

test("ADM-QUOTA-001 change a user's storage quota", details("ADM-QUOTA-001", "quotas", "quotas"), async ({ page, request, fixtureUser, adminSession }) => {
  await test.step("Find the fixture user and allocate ten gigabytes", async () => {
    await page.goto("/quotas");
    await page.getByLabel("Search users").pressSequentially(fixtureUser.name);
    const row = page.getByRole("row").filter({ hasText: fixtureUser.email });
    await row.getByRole("combobox").click();
    await page.getByRole("option", { name: "10 GB", exact: true }).click();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/quotas/${fixtureUser.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).quota_bytes;
    }).toBe(10 * 1024 ** 3);
    // quotas.component.ts:175-178 saves the API value but never updates user.storageQuota; the Quota cell stays stale.
    test.fail();
    await expect(row.getByRole("cell").filter({ hasNot: page.getByRole("combobox"), hasText: /^10 GB$/ })).toBeVisible();
  });
});
