import { test, expect } from "./fixtures";
import { details, expectGatewaySession } from "../support/admin-session";

test("ADM-USR-001 find a user and open their profile", details("ADM-USR-001", "users", "users"), async ({ page, fixtureUser, adminSession }) => {
  await test.step("Search for this fixture user", async () => {
    await page.goto("/users");
    await expectGatewaySession(page, adminSession);
    await page.getByLabel("Search users").pressSequentially(fixtureUser.name);
    await page.getByRole("row").filter({ hasText: fixtureUser.email }).click();
  });
  await test.step("Read the user's profile and storage allocation", async () => {
    await expect(page).toHaveURL(`/users/${fixtureUser.id}`);
    await expect(page.getByRole("heading", { name: fixtureUser.name, exact: true })).toBeVisible();
    // Profile email and storage values have no named semantic roles.
    await expect(page.getByText(fixtureUser.email, { exact: true })).toBeVisible();
    await expect(page.getByText("1 GB", { exact: true })).toBeVisible();
    await expect(page.getByText("5 GB", { exact: true })).toBeVisible();
  });
});

test("ADM-USR-002 suspend and restore a user", details("ADM-USR-002", "users", "user-detail"), async ({ page, request, fixtureUser, adminSession }) => {
  await page.goto(`/users/${fixtureUser.id}`);
  await test.step("Suspend the fixture user and confirm the decision", async () => {
    await page.getByRole("button", { name: "Suspend User" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Suspend", exact: true }).click();
    // Profile status badges have no status role.
    await expect(page.getByText("suspended", { exact: true })).toBeVisible();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/users/${fixtureUser.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).status;
    }).toBe("suspended");
  });
  await test.step("Restore the fixture user", async () => {
    await page.getByRole("button", { name: "Restore User" }).click();
    // Profile status badges have no status role.
    await expect(page.getByText("active", { exact: true })).toBeVisible();
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/admin/users/${fixtureUser.id}`, { headers: adminSession.headers });
      await expect(response).toBeOK();
      return (await response.json()).status;
    }).toBe("active");
  });
});
