import { test, expect, details, uniqueName } from "../support/admin-session";

test("ADM-ANN-001 create a draft announcement", details("ADM-ANN-001", "announcements", "announcements"), async ({ page, request, adminData, adminSession }) => {
  const title = uniqueName("UI Announcement");
  await test.step("Write and create a new announcement", async () => {
    await page.goto("/announcements");
    await page.getByRole("button", { name: /New Announcement/ }).click();
    await page.getByLabel("Title", { exact: true }).fill(title);
    await page.getByLabel("Content", { exact: true }).fill("A unique notice for the daily admin suite.");
    const created = page.waitForResponse(r => r.url().endsWith("/api/v1/admin/announcements") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    const response = await created;
    const announcement = await response.json();
    adminData.trackAnnouncement(announcement.id);
    expect(response.status()).toBe(201);
    // Material cards lack a region role and announcement badges lack a status role.
    const card = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: title, exact: true }) });
    await expect(card.getByText("draft", { exact: true })).toBeVisible();
    const saved = await request.get(`/api/v1/admin/announcements/${announcement.id}`, { headers: adminSession.headers });
    await expect(saved).toBeOK();
    expect(await saved.json()).toMatchObject({ title, status: "draft" });
  });
});

test("ADM-ANN-002 publish a draft announcement", details("ADM-ANN-002", "announcements", "announcements"), async ({ page, request, adminData, adminSession }) => {
  const announcement = await adminData.createAnnouncement();
  await test.step("Publish this draft announcement", async () => {
    await page.goto("/announcements");
    // Material cards lack a region role and announcement badges lack a status role.
    const card = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: announcement.title, exact: true }) });
    await card.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(card.getByText("published", { exact: true })).toBeVisible();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/announcements/${announcement.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).status;
    }).toBe("published");
  });
});

test("ADM-ANN-003 delete an announcement", details("ADM-ANN-003", "announcements", "announcements"), async ({ page, request, adminData, adminSession }) => {
  const announcement = await adminData.createAnnouncement();
  await test.step("Delete this fixture announcement and confirm", async () => {
    await page.goto("/announcements");
    // Material cards lack a region role.
    const card = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: announcement.title, exact: true }) });
    await card.getByRole("button", { name: "Delete", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page.getByRole("heading", { name: announcement.title, exact: true })).toHaveCount(0);
    await expect.poll(async () => (await request.get(`/api/v1/admin/announcements/${announcement.id}`, { headers: adminSession.headers })).status()).toBe(404);
  });
});
