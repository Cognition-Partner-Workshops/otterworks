import { randomUUID } from "node:crypto";
import { expect, test as base, type APIRequestContext, type Page } from "@playwright/test";

// These helpers use live gateway/admin APIs; admin-service verifies JWT signatures but does not enforce roles.
export const OFFLINE_MOCK_USER_ID = "a0000000-0000-0000-0000-000000000001";

export interface GatewayUser {
  id: string;
  email: string;
  displayName: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

export interface AdminSession extends GatewayUser {
  headers: { Authorization: string };
}

interface FeatureFlagOverrides {
  name: string;
  description: string;
  enabled: boolean;
  rollout_percentage: number;
}

export async function registerGatewayUser(
  request: APIRequestContext,
  options?: { label?: string; displayName?: string },
): Promise<GatewayUser> {
  const email = `${options?.label ?? "admin-e2e"}-${randomUUID()}@example.com`;
  const password = "Admin-Migration-Test-2026!";
  const displayName = options?.displayName ?? "Admin Migration";
  const response = await request.post("/api/v1/auth/register", {
    data: { email, password, displayName },
  });
  await expect(response).toBeOK();

  const body = await response.json() as {
    accessToken: string;
    refreshToken: string;
    user: { id: string; email: string; displayName: string };
  };
  const payload = JSON.parse(Buffer.from(body.accessToken.split(".")[1], "base64url").toString()) as {
    sub: string;
  };
  expect(body.user.email).toBe(email);
  expect(payload.sub).toBe(body.user.id);
  expect(body.user.id).not.toBe(OFFLINE_MOCK_USER_ID);

  return {
    id: body.user.id,
    email: body.user.email,
    displayName: body.user.displayName,
    password,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

export async function signInAdminSession(
  request: APIRequestContext,
  page: Page,
  options?: { label?: string; displayName?: string },
): Promise<AdminSession> {
  const user = await registerGatewayUser(request, options);
  const headers = { Authorization: `Bearer ${user.accessToken}` };
  const response = await request.get("/api/v1/admin/users", { headers });
  await expect(response).toBeOK();

  await page.addInitScript(({ id, email, displayName, accessToken }) => {
    localStorage.setItem("ow_admin_token", accessToken);
    localStorage.setItem("ow_admin_user", JSON.stringify({
      id,
      email,
      displayName,
      role: "admin",
      token: accessToken,
    }));
  }, { ...user, accessToken: user.accessToken });

  return { ...user, headers };
}

export async function signInThroughLoginForm(
  page: Page,
  user: Pick<GatewayUser, "email" | "password">,
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill(user.password);
  const loginResponsePromise = page.waitForResponse(response =>
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === "/api/v1/auth/login",
  );
  await page.getByRole("button", { name: "Sign In" }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.status()).toBe(200);

  const body = await loginResponse.json() as {
    accessToken: string;
    user: { id: string };
  };
  await expect(page).not.toHaveURL(/\/login/);
  await expectGatewaySession(page, { id: body.user.id, accessToken: body.accessToken });
}

export async function expectGatewaySession(
  page: Page,
  session: Pick<GatewayUser, "id" | "accessToken">,
): Promise<void> {
  await expect.poll(async () => page.evaluate(() => {
    const token = localStorage.getItem("ow_admin_token");
    const serializedUser = localStorage.getItem("ow_admin_user");
    if (!serializedUser) return { token, id: null };
    try {
      return { token, id: (JSON.parse(serializedUser) as { id?: string }).id ?? null };
    } catch {
      return { token, id: null };
    }
  })).toEqual({ token: session.accessToken, id: session.id });

  const storedUser = await page.evaluate(() => JSON.parse(localStorage.getItem("ow_admin_user") ?? "null") as { id?: string } | null);
  expect(storedUser?.id).not.toBe(OFFLINE_MOCK_USER_ID);
}

export async function createFeatureFlag(
  request: APIRequestContext,
  session: AdminSession,
  overrides: Partial<FeatureFlagOverrides> = {},
): Promise<{ id: string; name: string; [k: string]: unknown }> {
  const response = await request.post("/api/v1/admin/features", {
    headers: session.headers,
    data: {
      feature: {
        name: overrides.name ?? `e2e_flag_${randomUUID().replaceAll("-", "").slice(0, 8)}`,
        description: overrides.description ?? "Created by migrated admin tests",
        enabled: overrides.enabled ?? true,
        rollout_percentage: overrides.rollout_percentage ?? 0,
      },
    },
  });
  expect(response.status()).toBe(201);
  return await response.json() as { id: string; name: string; [k: string]: unknown };
}

export async function deleteFeatureFlag(
  request: APIRequestContext,
  session: AdminSession,
  id: string,
): Promise<void> {
  const response = await request.delete(`/api/v1/admin/features/${id}`, { headers: session.headers });
  await expect(response).toBeOK();
}

export const adminTest = base.extend<{
  adminSession: AdminSession;
  adminData: {
    createFeatureFlag(overrides?: Partial<FeatureFlagOverrides>): Promise<{ id: string; name: string; [k: string]: unknown }>;
  };
}>({
  adminSession: async ({ request, page }, use) => {
    await use(await signInAdminSession(request, page));
  },
  adminData: async ({ request, adminSession }, use) => {
    const createdIds: string[] = [];
    await use({
      createFeatureFlag: async overrides => {
        const feature = await createFeatureFlag(request, adminSession, overrides);
        createdIds.push(feature.id);
        return feature;
      },
    });
    for (const id of createdIds) {
      await deleteFeatureFlag(request, adminSession, id);
    }
  },
});
