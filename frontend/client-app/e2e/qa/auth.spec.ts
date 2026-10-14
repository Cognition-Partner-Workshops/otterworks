import { test, expect, type Page } from "@playwright/test";
import {
  clearAuth,
  expectDashboard,
  loginUser,
  registerUser,
  uniqueEmail,
} from "../fixtures/test-helpers";

const seededEmail = process.env.OTTERWORKS_WEB_LOGIN_EMAIL;
const seededPassword = process.env.OTTERWORKS_WEB_LOGIN_PASSWORD;

async function readTokens(page: Page) {
  return page.evaluate(() => ({
    access: localStorage.getItem("otter_access_token"),
    refresh: localStorage.getItem("otter_refresh_token"),
  }));
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  const tokens = await readTokens(page);
  expect(tokens.access).toBeNull();
  expect(tokens.refresh).toBeNull();
}

test.describe("QA: authentication critical paths", () => {
  test("unauthenticated visit to a protected route redirects to login", async ({ page }) => {
    await page.goto("/login");
    await clearAuth(page);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("register, persist session across reload, sign out, then protected route redirects", async ({ page }) => {
    await registerUser(page, { name: "QA Register User", email: uniqueEmail() });
    await expectDashboard(page);
    const tokens = await readTokens(page);
    expect(tokens.access).toBeTruthy();
    expect(tokens.refresh).toBeTruthy();

    await page.reload();
    await expectDashboard(page);

    await signOut(page);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test("existing user can sign in with valid credentials", async ({ page, request }) => {
    const email = uniqueEmail();
    const password = "Passw0rd!23";
    const res = await request.post("/api/v1/auth/register", {
      data: { email, password, displayName: "QA Login User" },
    });
    expect(res.status()).toBe(201);

    await loginUser(page, email, password);
    await expectDashboard(page);
    await signOut(page);
  });

  test("invalid credentials show an error and do not create a session", async ({ page }) => {
    await loginUser(page, uniqueEmail(), "WrongPassword123!");
    await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
    expect((await readTokens(page)).access).toBeNull();
  });

  test("expired or tampered stored token is cleared and user is sent to login", async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => {
      const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
      const expired = `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: "x", type: "access", exp: 1 })}.sig`;
      localStorage.setItem("otter_access_token", expired);
      localStorage.setItem("otter_refresh_token", expired);
    });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
    expect((await readTokens(page)).access).toBeNull();
  });

  test("seeded admin can sign in and sign out", async ({ page }) => {
    test.skip(!seededEmail || !seededPassword, "seeded admin credentials not provided");
    await loginUser(page, seededEmail!, seededPassword!);
    await expectDashboard(page);
    await page.reload();
    await expectDashboard(page);
    await signOut(page);
  });
});
