import { expect, test } from "./fixtures";

const SOURCE = "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/LoginTest.java";

test.describe("Selenium LoginTest", () => {
  test("SEL-LoginTest-loginFormShowsEmailField loginFormShowsEmailField", {
    tag: ["@SEL-LoginTest-loginFormShowsEmailField", "@selenium-LoginTest"],
    annotation: { type: "selenium", description: `${SOURCE}#loginFormShowsEmailField` },
  }, async ({ loginPage, legacyLogin }) => {
    await test.step("SEL-LoginTest-loginFormShowsEmailField-STEP-01 Open /login", async () => {
      await loginPage.open(legacyLogin.path);
    });
    await test.step("SEL-LoginTest-loginFormShowsEmailField-STEP-02 Verify Email field", async () => {
      await expect(loginPage.emailInput).toBeVisible();
      await expect(loginPage.emailInput).toBeEditable();
      await expect(loginPage.emailInput).toHaveAttribute("type", "email");
    });
  });

  test("SEL-LoginTest-emptyCredentialsShowValidationMessage emptyCredentialsShowValidationMessage", {
    tag: ["@SEL-LoginTest-emptyCredentialsShowValidationMessage", "@selenium-LoginTest"],
    annotation: { type: "selenium", description: `${SOURCE}#emptyCredentialsShowValidationMessage` },
  }, async ({ page, loginPage, legacyLogin }) => {
    const loginRequests: string[] = [];
    page.on("request", request => {
      if (new URL(request.url()).pathname === "/api/v1/auth/login") loginRequests.push(request.method());
    });
    await test.step("SEL-LoginTest-emptyCredentialsShowValidationMessage-STEP-01 Open /login", async () => {
      await loginPage.open(legacyLogin.path);
      await expect(loginPage.emailInput).toHaveValue("");
      await expect(loginPage.passwordInput).toHaveValue("");
    });
    await test.step("SEL-LoginTest-emptyCredentialsShowValidationMessage-STEP-02 Click Sign In", async () => {
      await loginPage.signInButton.click();
    });
    await test.step("SEL-LoginTest-emptyCredentialsShowValidationMessage-STEP-03 Verify validation message", async () => {
      await expect(loginPage.validationMessage(legacyLogin.emptyCredentialsMessage)).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`${legacyLogin.path}$`));
      // The form is rejected client-side: nothing was sent to the gateway (or the offline mock).
      expect(loginRequests).toEqual([]);
    });
  });

  test("SEL-LoginTest-passwordVisibilityCanBeChanged passwordVisibilityCanBeChanged", {
    tag: ["@SEL-LoginTest-passwordVisibilityCanBeChanged", "@selenium-LoginTest"],
    annotation: { type: "selenium", description: `${SOURCE}#passwordVisibilityCanBeChanged` },
  }, async ({ loginPage, legacyLogin }) => {
    await test.step("SEL-LoginTest-passwordVisibilityCanBeChanged-STEP-01 Open /login", async () => {
      await loginPage.open(legacyLogin.path);
    });
    await test.step("SEL-LoginTest-passwordVisibilityCanBeChanged-STEP-02 Enter Password", async () => {
      await loginPage.passwordInput.fill(legacyLogin.password);
      await expect(loginPage.passwordInput).toHaveAttribute("type", "password");
    });
    await test.step("SEL-LoginTest-passwordVisibilityCanBeChanged-STEP-03 Click password visibility toggle", async () => {
      await loginPage.passwordVisibilityToggle.click();
    });
    await test.step("SEL-LoginTest-passwordVisibilityCanBeChanged-STEP-04 Verify Password type", async () => {
      await expect(loginPage.passwordInput).toHaveAttribute("type", legacyLogin.revealedPasswordType);
      await expect(loginPage.passwordInput).toHaveValue(legacyLogin.password);
    });
  });
});
