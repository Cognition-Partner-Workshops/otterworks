import { test, expect } from "./fixtures";
import { legacyDetails } from "../support/traceability";

function source(id: string) {
  const tosca = legacyDetails({
    suite: "tosca",
    id,
    group: "tosca-Settings",
    source: `tests/legacy-suites/tosca/TestCases/Settings/${id}.xml`,
  });
  if (id === "TC-SET-003") {
    const cypress = legacyDetails({
      suite: "cypress",
      id: "CY-settings-01",
      group: "cypress-settings",
      source: "tests/legacy-suites/cypress/cypress/e2e/settings.cy.js",
      method: "updates the profile name",
    });
    return { tag: [...tosca.tag, ...cypress.tag], annotation: [tosca.annotation, cypress.annotation] };
  }
  return {
    tag: tosca.tag,
    annotation: tosca.annotation,
  };
}

test("TC-SET-001 View profile settings", source("TC-SET-001"), async ({ page, Profile, settingsPage }) => {
  await test.step("TC-SET-001-STEP-01 Verify SettingsHeading", async () => {
    await expect(settingsPage.heading).toBeVisible();
  });
  await test.step("TC-SET-001-STEP-02 Verify FullName", async () => {
    await expect(settingsPage.fullName).toHaveValue(Profile.Name);
  });
  await test.step("TC-SET-001-STEP-03 Verify EmailAddress", async () => {
    await expect(settingsPage.email).toHaveValue(Profile.Email);
  });
});

test("TC-SET-002 Update email notification preference", source("TC-SET-002"), async ({ page, request, Notifications, settingsPage }) => {
  await test.step("TC-SET-002-STEP-01 Verify SettingsHeading", async () => {
    await expect(settingsPage.heading).toBeVisible();
  });

  await expect(settingsPage.emailNotifications).toHaveCount(1);

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
    await settingsPage.emailNotifications.click();
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

test("TC-SET-003 Save profile details", source("TC-SET-003"), async ({ page, request, SaveProfile, settingsPage }) => {
  // client-app/src/lib/api.ts:106 sends PATCH; auth-service/src/main/java/com/otterworks/auth/controller/AuthController.java:54 only maps PUT.
  test.fail(true, "App defect: PATCH /api/v1/auth/profile is not supported; auth-service maps only PUT /profile.");
  const fullName = settingsPage.fullName;

  await test.step("CY-settings-01-STEP-01 Visit /settings and verify profile", async () => {
    await expect(page).toHaveURL("/settings");
    await expect(settingsPage.heading).toBeVisible();
    await expect(fullName).toHaveValue(SaveProfile.Name);
    await expect(settingsPage.email).toHaveValue(SaveProfile.Email);
  });
  await test.step("TC-SET-003-STEP-01 Input FullName", async () => {
    await fullName.fill(SaveProfile.UpdatedName);
  });
  await test.step("CY-settings-01-STEP-03 Clear Full name", async () => {
    await fullName.clear();
    await expect(fullName).toHaveValue("");
  });
  await test.step("CY-settings-01-STEP-04 Type Full name", async () => {
    await fullName.pressSequentially(SaveProfile.UpdatedName);
    await expect(fullName).toHaveValue(SaveProfile.UpdatedName);
  });

  await test.step("TC-SET-003-STEP-02 Click SaveChanges", async () => {
    const profileResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/v1/auth/profile") && response.request().method() === "PATCH",
    );
    await test.step("CY-settings-01-STEP-05 Click Save changes", async () => {
      await settingsPage.saveChanges.click();
    });
    const profileResponse = await profileResponsePromise;
    await test.step("CY-settings-01-STEP-06 Verify profile update request", async () => {
      expect(profileResponse.request().postDataJSON()).toMatchObject({
        displayName: SaveProfile.UpdatedName,
      });
      expect(profileResponse.status(), "PATCH /api/v1/auth/profile status").toBe(200);
    });
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
  await test.step("CY-settings-01-STEP-07 Verify profile name saved", async () => {
    const profile = await request.get("/api/v1/auth/profile", {
      headers: { Authorization: `Bearer ${SaveProfile.accessToken}` },
    });
    await expect(profile).toBeOK();
    expect(await profile.json()).toMatchObject({
      id: SaveProfile.id,
      displayName: SaveProfile.UpdatedName,
    });
    await page.reload();
    await expect(fullName).toHaveValue(SaveProfile.UpdatedName);
  });
});
