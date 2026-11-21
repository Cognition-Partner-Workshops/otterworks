import { test, expect, details, signInThroughLoginForm } from "../support/admin-session";

test("ADM-AUTH-001 sign in with a registered gateway user", details("ADM-AUTH-001", "auth", "login"), async ({ page, gatewayUser }) => {
  await test.step("Sign in through the login form and verify gateway token identity", async () => {
    await signInThroughLoginForm(page, gatewayUser);
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  });
});

test("ADM-AUTH-002 sign out and reject a guarded route", details("ADM-AUTH-002", "auth", "login"), async ({ page, gatewayUser }) => {
  await test.step("Sign in through the form", async () => {
    await signInThroughLoginForm(page, gatewayUser);
  });
  await test.step("Sign out from the user menu", async () => {
    await page.getByRole("button", { name: "User menu" }).click();
    await page.getByRole("menuitem", { name: "Logout" }).click();
    await expect(page).toHaveURL("/login");
    await expect.poll(() => page.evaluate(() => localStorage.getItem("ow_admin_token"))).toBeNull();
  });
  await test.step("Open a guarded screen after signing out", async () => {
    await page.goto("/users");
    await expect(page).toHaveURL("/login");
    await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  });
});

test("ADM-AUTH-003 reject an incorrect password", details("ADM-AUTH-003", "auth", "login"), async ({ page, gatewayUser }) => {
  await test.step("Submit a wrong password for a real gateway identity", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(gatewayUser.email);
    await page.getByLabel("Password", { exact: true }).fill("Incorrect-Password-2026!");
    const response = page.waitForResponse(r => r.url().endsWith("/api/v1/auth/login") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Sign In", exact: true }).click();
    expect((await response).status()).toBe(400);
  });
  await test.step("See a rejection without installing any session", async () => {
    // auth.service.ts:53,93-107: gateway errors fall back to mockLogin, accepting any non-empty password.
    test.fail();
    try {
      // The login error message has no alert/status role.
      await expect(page.getByText("Invalid credentials", { exact: true })).toBeVisible();
      await expect(page).toHaveURL("/login");
      await expect.poll(() => page.evaluate(() => localStorage.getItem("ow_admin_token"))).toBeNull();
    } finally {
      const identity = await page.evaluate(() => {
        const token = localStorage.getItem("ow_admin_token");
        return {
          userId: JSON.parse(localStorage.getItem("ow_admin_user") || "null")?.id ?? null,
          tokenSubject: token ? JSON.parse(atob(token.split(".")[1])).sub : null,
          hasToken: token !== null,
        };
      });
      await test.info().attach("rejected-login-identity", { body: JSON.stringify(identity), contentType: "application/json" });
    }
  });
});
