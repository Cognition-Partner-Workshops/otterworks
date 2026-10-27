import { test, expect } from "./fixtures";

const SOURCE = "tests/legacy-suites/cypress/cypress/e2e/sign-in.cy.js";

function source(id: string, title: string) {
  return { tag: [`@${id}`, "@cypress-sign-in"], annotation: { type: "cypress", description: `${SOURCE}#${title}` } };
}

test(
  "CY-sign-in-01 opens the dashboard with a valid account",
  source("CY-sign-in-01", "opens the dashboard with a valid account"),
  async ({ page, validAccount }) => {
    const login = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/api/v1/auth/login"));
    const profile = page.waitForResponse((r) => r.request().method() === "GET" && r.url().endsWith("/api/v1/auth/profile"));
    let accessToken = "";

    await test.step("CY-sign-in-01-STEP-01 Visit /login", async () => {
      await page.goto("/login");
      await expect(page.getByLabel("Email")).toBeVisible();
    });
    await test.step("CY-sign-in-01-STEP-02 Type email", async () => {
      await page.getByLabel("Email").fill(validAccount.email);
    });
    await test.step("CY-sign-in-01-STEP-03 Type password", async () => {
      await page.getByLabel("Password").fill(validAccount.password);
    });
    await test.step("CY-sign-in-01-STEP-04 Click button Sign in", async () => {
      await page.getByRole("button", { name: "Sign in" }).click();
    });
    await test.step("CY-sign-in-01-STEP-05 Wait login response", async () => {
      const response = await login;
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(body.user.id).toBe(validAccount.id);
      accessToken = body.accessToken;
    });
    await test.step("CY-sign-in-01-STEP-06 Wait profile response", async () => {
      const response = await profile;
      expect(response.status()).toBe(200);
      expect(await response.json()).toMatchObject({ id: validAccount.id, email: validAccount.email, displayName: validAccount.displayName });
      await expect.poll(() => page.evaluate(() => localStorage.getItem("otter_access_token"))).toBe(accessToken);
    });
    await test.step("CY-sign-in-01-STEP-07 Verify pathname /dashboard", async () => {
      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
    });
    await test.step("CY-sign-in-01-STEP-08 Verify display name visible", async () => {
      // The header's signed-in name is a plain span with no accessible role or name.
      await expect(page.getByRole("banner").getByText(validAccount.displayName, { exact: true })).toBeVisible();
    });
  },
);

test(
  "CY-sign-in-02 requires an email address",
  source("CY-sign-in-02", "requires an email address"),
  async ({ page, missingEmail }) => {
    const loginRequests: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/v1/auth/login")) loginRequests.push(r.url());
    });

    await test.step("CY-sign-in-02-STEP-01 Visit /login", async () => {
      await page.goto("/login");
      await expect(page.getByLabel("Email")).toBeVisible();
    });
    await test.step("CY-sign-in-02-STEP-02 Type password", async () => {
      await page.getByLabel("Password").fill(missingEmail.password);
    });
    await test.step("CY-sign-in-02-STEP-03 Click button Sign in", async () => {
      await page.getByRole("button", { name: "Sign in" }).click();
    });
    await test.step("CY-sign-in-02-STEP-04 Verify email error visible", async () => {
      // The validation message is a plain paragraph, not linked to the input (no aria-describedby/role=alert).
      await expect(page.getByText(missingEmail.emailError, { exact: true })).toBeVisible();
      await expect(page).toHaveURL(/\/login$/);
      expect(loginRequests).toEqual([]);
    });
  },
);
