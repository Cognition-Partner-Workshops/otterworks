import { test, expect } from "./fixtures";

function source(id: string) {
  return {
    tag: [`@${id}`, "@tosca-Settings"],
    annotation: {
      type: "tosca",
      description: `tests/legacy-suites/tosca/TestCases/Settings/${id}.xml`,
    },
  };
}

test("TC-SET-001 View profile settings", source("TC-SET-001"), async ({ page, Profile }) => {
  await test.step("TC-SET-001-STEP-01 Verify SettingsHeading", async () => {
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  });
  await test.step("TC-SET-001-STEP-02 Verify FullName", async () => {
    await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(Profile.Name);
  });
  await test.step("TC-SET-001-STEP-03 Verify EmailAddress", async () => {
    await expect(page.getByLabel("Email", { exact: true })).toHaveValue(Profile.Email);
  });
});

test("TC-SET-002 Update email notification preference", source("TC-SET-002"), async ({ page, request, Notifications }) => {
  await test.step("TC-SET-002-STEP-01 Verify SettingsHeading", async () => {
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  });

  // The toggle button has no accessible name or aria-checked state, so scope it to its text-only row.
  const emailNotifications = page
    .getByRole("main")
    .locator("div")
    .filter({ hasText: /^Email notificationsReceive notifications via email$/ })
    .getByRole("button");
  await expect(emailNotifications).toHaveCount(1);

  await expect.poll(async () => {
    const response = await request.get("/api/v1/settings", { headers: Notifications.headers });
    await expect(response).toBeOK();
    const settings = (await response.json()) as { notificationEmail: boolean };
    return settings.notificationEmail;
  }).toBe(true);

  await test.step("TC-SET-002-STEP-02 Click EmailNotifications", async () => {
    const updateResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/v1/settings") && response.request().method() === "PATCH",
    );
    await emailNotifications.click();
    const updateResponse = await updateResponsePromise;
    expect(updateResponse.ok()).toBe(true);
  });

  await test.step("TC-SET-002-STEP-03 Verify EmailNotifications", async () => {
    await expect.poll(async () => {
      const response = await request.get("/api/v1/settings", { headers: Notifications.headers });
      await expect(response).toBeOK();
      const settings = (await response.json()) as { notificationEmail: boolean };
      return settings.notificationEmail;
    }).toBe(Notifications.Expected === "Enabled");
  });
});

test("TC-SET-003 Save profile details", source("TC-SET-003"), async ({ page, request, SaveProfile }) => {
  // client-app/src/lib/api.ts:106 sends PATCH; auth-service/src/main/java/com/otterworks/auth/controller/AuthController.java:54 only maps PUT.
  test.fail();
  const fullName = page.getByLabel("Full name", { exact: true });
  const saveChanges = page.getByRole("button", { name: "Save changes", exact: true });

  await test.step("TC-SET-003-STEP-01 Input FullName", async () => {
    await fullName.fill(SaveProfile.UpdatedName);
  });

  await test.step("TC-SET-003-STEP-02 Click SaveChanges", async () => {
    const profileResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/v1/auth/profile") && response.request().method() === "PATCH",
    );
    await saveChanges.click();
    const profileResponse = await profileResponsePromise;
    expect(profileResponse.ok()).toBe(true);
    await expect(page.getByText("Profile updated successfully.", { exact: true })).toBeVisible();
  });

  await test.step("TC-SET-003-STEP-03 Verify FullName", async () => {
    await page.reload();
    await expect(fullName).toHaveValue(SaveProfile.UpdatedName);

    await expect.poll(async () => {
      const response = await request.get("/api/v1/auth/profile", { headers: SaveProfile.headers });
      await expect(response).toBeOK();
      const profile = (await response.json()) as { displayName: string };
      return profile.displayName;
    }).toBe(SaveProfile.UpdatedName);
  });
});
