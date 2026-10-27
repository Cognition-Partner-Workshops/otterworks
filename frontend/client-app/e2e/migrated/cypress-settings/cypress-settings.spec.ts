import { test, expect } from "./fixtures";

const LEGACY_SOURCE = "tests/legacy-suites/cypress/cypress/e2e/settings.cy.js";

test(
  "CY-settings-01 updates the profile name",
  {
    tag: ["@CY-settings-01", "@cypress-settings"],
    annotation: { type: "cypress", description: `${LEGACY_SOURCE}#updates the profile name` },
  },
  async ({ page, request, profileUser }) => {
    test.fail(
      true,
      "App defect: authApi.updateProfile (src/lib/api.ts) sends PATCH /api/v1/auth/profile, but auth-service " +
        "AuthController maps only PUT /profile; PATCH raises HttpRequestMethodNotSupportedException, which " +
        "GlobalExceptionHandler turns into HTTP 500, so the name is never saved.",
    );
    const fullName = page.getByRole("textbox", { name: "Full name" });

    await test.step("CY-settings-01-STEP-01 Visit /settings", async () => {
      await page.goto("/settings");
      await expect(page).toHaveURL("/settings");
      await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
    });

    await test.step("CY-settings-01-STEP-02 Wait settings", async () => {
      await expect(page.getByRole("heading", { name: "Notification preferences" })).toBeVisible();
      await expect(fullName).toHaveValue(profileUser.DisplayName);
      await expect(page.getByRole("textbox", { name: "Email" })).toHaveValue(profileUser.Email);
    });

    await test.step("CY-settings-01-STEP-03 Clear Full name", async () => {
      await fullName.clear();
      await expect(fullName).toHaveValue("");
    });

    await test.step("CY-settings-01-STEP-04 Type Full name", async () => {
      await fullName.pressSequentially(profileUser.NewDisplayName);
      await expect(fullName).toHaveValue(profileUser.NewDisplayName);
    });

    const profileUpdate = page.waitForResponse(
      (response) => response.url().endsWith("/api/v1/auth/profile") && response.request().method() === "PATCH",
    );

    await test.step("CY-settings-01-STEP-05 Click Save changes", async () => {
      await page.getByRole("button", { name: "Save changes" }).click();
    });

    await test.step("CY-settings-01-STEP-06 Verify profileUpdate request body displayName", async () => {
      const response = await profileUpdate;
      expect(response.request().postDataJSON()).toMatchObject({ displayName: profileUser.NewDisplayName });
      expect(response.status(), "PATCH /api/v1/auth/profile status").toBe(200);
    });

    await test.step("CY-settings-01-STEP-07 Verify profile name saved", async () => {
      // The success message is a plain paragraph with no status role or live region.
      await expect(page.getByText("Profile updated successfully.")).toBeVisible();
      const profile = await request.get("/api/v1/auth/profile", {
        headers: { Authorization: `Bearer ${profileUser.accessToken}` },
      });
      await expect(profile).toBeOK();
      expect(await profile.json()).toMatchObject({ id: profileUser.Id, displayName: profileUser.NewDisplayName });
      await page.reload();
      await expect(fullName).toHaveValue(profileUser.NewDisplayName);
    });
  },
);
