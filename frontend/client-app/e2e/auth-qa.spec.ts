import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import {
  uniqueEmail,
  registerUser,
  loginUser,
  expectDashboard,
} from "./fixtures/test-helpers";

const API_URL = process.env.API_URL || "http://localhost:8080";
const PASSWORD = "Passw0rd!23";

interface ApiUser {
  email: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

async function apiRegister(request: APIRequestContext): Promise<ApiUser> {
  const email = uniqueEmail();
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, displayName: "QA E2E" },
  });
  expect(res.status()).toBe(201);
  const body = await res.json();
  return {
    email,
    password: PASSWORD,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

async function storedTokens(page: Page) {
  return page.evaluate(() => ({
    access: localStorage.getItem("otter_access_token"),
    refresh: localStorage.getItem("otter_refresh_token"),
  }));
}

function fakeExpiredJwt(): string {
  const b64 = (o: object) =>
    Buffer.from(JSON.stringify(o)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  return [
    b64({ alg: "HS384" }),
    b64({ sub: "expired-user", type: "access", exp: now - 3600 }),
    "sig",
  ].join(".");
}

test.describe("Auth QA", () => {
  test("registering through the UI signs the user in and stores both tokens", async ({
    page,
  }) => {
    await registerUser(page, { name: "QA Register" });
    await expectDashboard(page);
    const tokens = await storedTokens(page);
    expect(tokens.access).toBeTruthy();
    expect(tokens.refresh).toBeTruthy();
  });

  test("registering an existing email shows an error and stays on /register", async ({
    page,
    request,
  }) => {
    const user = await apiRegister(request);
    await registerUser(page, { email: user.email });
    await expect(page.getByText("Registration failed")).toBeVisible();
    await expect(page).toHaveURL(/\/register/);
  });

  test("7-character password is rejected client-side, 8 is accepted", async ({
    page,
  }) => {
    await registerUser(page, { password: "Abc123!" });
    await expect(
      page.getByText("Password must be at least 8 characters"),
    ).toBeVisible();
    await registerUser(page, { password: "Abc123!x" });
    await expectDashboard(page);
  });

  test("login with a gateway-registered user reaches the dashboard", async ({
    page,
    request,
  }) => {
    const user = await apiRegister(request);
    await loginUser(page, user.email, user.password);
    await expectDashboard(page);
    const tokens = await storedTokens(page);
    expect(tokens.access).toBeTruthy();
  });

  test("wrong password shows an error and stores no token", async ({
    page,
    request,
  }) => {
    const user = await apiRegister(request);
    await loginUser(page, user.email, "WrongPassw0rd!");
    await expect(page.getByText("Invalid email or password")).toBeVisible();
    expect((await storedTokens(page)).access).toBeNull();
  });

  for (const path of ["/dashboard", "/documents", "/files", "/settings"]) {
    test(`signed-out visit to ${path} redirects to /login`, async ({
      page,
    }) => {
      await page.goto(path);
      await page.waitForURL((url) => url.pathname === "/login", {
        timeout: 15_000,
      });
    });
  }

  test("expired session token is cleared and the user is sent to /login", async ({
    page,
  }) => {
    await page.goto("/login");
    const expired = fakeExpiredJwt();
    await page.evaluate((t) => {
      localStorage.setItem("otter_access_token", t);
      localStorage.setItem("otter_refresh_token", t);
    }, expired);
    await page.goto("/dashboard");
    await page.waitForURL((url) => url.pathname === "/login", {
      timeout: 15_000,
    });
    expect((await storedTokens(page)).access).toBeNull();
  });

  test("the stored refresh token can mint a new session via the gateway", async ({
    page,
    request,
  }) => {
    const user = await apiRegister(request);
    await loginUser(page, user.email, user.password);
    await expectDashboard(page);
    const { refresh } = await storedTokens(page);
    const res = await request.post(`${API_URL}/api/v1/auth/refresh`, {
      headers: { Authorization: `Bearer ${refresh}` },
    });
    expect(res.status()).toBe(200);
  });

  test("sign out clears tokens and returns to /login", async ({
    page,
    request,
  }) => {
    const user = await apiRegister(request);
    await loginUser(page, user.email, user.password);
    await expectDashboard(page);
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.waitForURL((url) => url.pathname === "/login");
    const tokens = await storedTokens(page);
    expect(tokens.access).toBeNull();
    expect(tokens.refresh).toBeNull();
    await page.goto("/dashboard");
    await page.waitForURL((url) => url.pathname === "/login", {
      timeout: 15_000,
    });
  });

  test("sign out revokes the refresh token server-side", async ({
    page,
    request,
  }) => {
    test.fail(
      true,
      "[REAL] ui-logout-no-token: UI logout POSTs /auth/logout without a Bearer token",
    );
    const user = await apiRegister(request);
    await loginUser(page, user.email, user.password);
    await expectDashboard(page);
    const { refresh } = await storedTokens(page);
    const logoutReq = page.waitForRequest((r) =>
      r.url().endsWith("/api/v1/auth/logout"),
    );
    await page.getByRole("button", { name: "Sign out" }).click();
    const sent = await logoutReq;
    await page.waitForURL((url) => url.pathname === "/login");
    expect(sent.headers()["authorization"]).toBeTruthy();
    const res = await request.post(`${API_URL}/api/v1/auth/refresh`, {
      headers: { Authorization: `Bearer ${refresh}` },
    });
    expect(res.status()).toBe(400);
  });

  test("login accepts the registered email in a different case", async ({
    page,
    request,
  }) => {
    test.fail(true, "[REAL] auth-email-case: email lookup is case-sensitive");
    const user = await apiRegister(request);
    await loginUser(page, user.email.toUpperCase(), user.password);
    await expectDashboard(page);
  });
});
