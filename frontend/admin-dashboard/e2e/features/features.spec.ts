import { test, expect, details } from "../support/admin-session";

test("ADM-FEAT-001 disable a feature flag", details("ADM-FEAT-001", "features", "features"), async ({ page, request, adminData, adminSession }) => {
  const flag = await adminData.createFeatureFlag();
  await test.step("Switch off this uniquely named feature", async () => {
    await page.goto("/features");
    // Material cards lack a region role and feature switches lack accessible names.
    const card = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: flag.name, exact: true }) });
    const toggle = card.getByRole("switch");
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/features/${flag.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).enabled;
    }).toBe(false);
  });
});

test("ADM-FEAT-002 re-enable a feature after disabling it", details("ADM-FEAT-002", "features", "features"), async ({ page, request, adminData, adminSession }) => {
  const flag = await adminData.createFeatureFlag();
  await page.goto("/features");
  // Material cards lack a region role and feature switches lack accessible names.
  const toggle = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: flag.name, exact: true }) }).getByRole("switch");
  await test.step("Disable this fixture feature", async () => {
    await expect(toggle).toBeChecked();
    const update = page.waitForResponse(r => r.url().endsWith(`/features/${flag.id}`) && r.request().method() === "PUT");
    await toggle.click();
    expect((await update).status()).toBe(200);
    await expect(toggle).not.toBeChecked();
    await expect.poll(async () => (await (await request.get(`/api/v1/admin/features/${flag.id}`, { headers: adminSession.headers })).json()).enabled).toBe(false);
  });
  await test.step("Enable the same feature again and persist its state", async () => {
    const update = page.waitForResponse(r => r.url().endsWith(`/features/${flag.id}`) && r.request().method() === "PUT");
    await toggle.click();
    expect((await update).status()).toBe(200);
    await expect(toggle).toBeChecked();
    // features.component.ts:133-141 never updates flag.enabled; the second PUT repeats enabled=false.
    test.fail();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/features/${flag.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).enabled;
    }).toBe(true);
  });
});
