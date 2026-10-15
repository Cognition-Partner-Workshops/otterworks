import { test, expect } from "@playwright/test";
import { uniqueEmail, registerUser, loginUser, expectDashboard } from "./fixtures/test-helpers";

const API_URL = process.env.OTTERWORKS_API_BASE_URL ?? "http://localhost:8080";

async function registerViaApi(request: import("@playwright/test").APIRequestContext) {
  const email = uniqueEmail();
  const password = "Passw0rd!23";
  const response = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { email, password, displayName: "E2E Auth User" },
  });
  expect(response.status()).toBe(201);
  return { email, password };
}

test.describe("Auth session (live backend)", () => {
  test.beforeEach(async ({ request }) => {
    const health = await request.get(`${API_URL}/health`).catch(() => null);
    test.skip(!health || !health.ok(), "API gateway not reachable");
  });

  test("register lands on dashboard and stores both tokens", async ({ page }) => {
    await registerUser(page, { name: "E2E Register" });
    await expectDashboard(page);
    const tokens = await page.evaluate(() => [
      localStorage.getItem("otter_access_token"),
      localStorage.getItem("otter_refresh_token"),
    ]);
    expect(tokens[0]).toBeTruthy();
    expect(tokens[1]).toBeTruthy();
  });

  test("login with valid credentials lands on dashboard", async ({ page, request }) => {
    const { email, password } = await registerViaApi(request);
    await loginUser(page, email, password);
    await expectDashboard(page);
  });

  test("wrong password shows error and stores no token", async ({ page, request }) => {
    const { email } = await registerViaApi(request);
    await loginUser(page, email, "WrongPassw0rd!");
    await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
    expect(await page.evaluate(() => localStorage.getItem("otter_access_token"))).toBeNull();
  });

  test("sign out clears tokens and returns to login", async ({ page, request }) => {
    const { email, password } = await registerViaApi(request);
    await loginUser(page, email, password);
    await expectDashboard(page);
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
    const tokens = await page.evaluate(() => [
      localStorage.getItem("otter_access_token"),
      localStorage.getItem("otter_refresh_token"),
    ]);
    expect(tokens).toEqual([null, null]);
  });

  test("session survives a page reload", async ({ page, request }) => {
    const { email, password } = await registerViaApi(request);
    await loginUser(page, email, password);
    await expectDashboard(page);
    await page.reload();
    await expectDashboard(page);
    expect(await page.evaluate(() => localStorage.getItem("otter_access_token"))).toBeTruthy();
  });

  test("invalid stored token is cleared and user is sent to login", async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => {
      localStorage.setItem("otter_access_token", "not-a-valid-jwt");
      localStorage.setItem("otter_refresh_token", "not-a-valid-jwt");
    });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
    expect(await page.evaluate(() => localStorage.getItem("otter_access_token"))).toBeNull();
  });

  test("unauthenticated visit to a protected page redirects to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });
});
