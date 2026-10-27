import { randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { expect, test as base, type APIRequestContext, type Page } from "@playwright/test";

export const OFFLINE_MOCK_USER_ID = "a0000000-0000-0000-0000-000000000001";
const execFileAsync = promisify(execFile);
const api = "/api/v1/admin";

export interface GatewayUser {
  id: string;
  email: string;
  displayName: string;
  password: string;
  accessToken: string;
}
export interface AdminSession extends GatewayUser {
  headers: { Authorization: string };
}
export interface FeatureFlag { id: string; name: string; description: string; enabled: boolean }
export interface Announcement { id: string; title: string; status: string }

export function uniqueName(prefix: string): string {
  return `${prefix}-${randomUUID()}`;
}

export async function database(sql: string): Promise<void> {
  await execFileAsync("docker", [
    "exec", process.env.ADMIN_PG_CONTAINER || "otterworks-postgres",
    "psql", "-X", "-v", "ON_ERROR_STOP=1",
    "-U", process.env.ADMIN_PG_USER || "otterworks",
    "-d", process.env.ADMIN_PG_DATABASE || "otterworks", "-c", sql,
  ]);
}

export function sqlLiteral(value: string): string {
  return "'" + value.replaceAll("'", "''") + "'";
}

export async function registerGatewayUser(request: APIRequestContext): Promise<GatewayUser> {
  const email = `${uniqueName("admin-e2e")}@example.com`;
  const password = "Admin-E2E-2026!";
  const displayName = uniqueName("Operator");
  const response = await request.post("/api/v1/auth/register", { data: { email, password, displayName } });
  await expect(response).toBeOK();
  const body = await response.json();
  const claims = JSON.parse(Buffer.from(body.accessToken.split(".")[1], "base64url").toString());
  expect(claims.sub).toBe(body.user.id);
  expect(body.user.id).not.toBe(OFFLINE_MOCK_USER_ID);
  return { id: body.user.id, email, displayName, password, accessToken: body.accessToken };
}

export async function signInAdminSession(page: Page, user: GatewayUser): Promise<AdminSession> {
  await page.addInitScript(user => {
    // Once per tab: navigation after logout must not reinstall authentication.
    if (sessionStorage.getItem("admin-e2e-initialized")) return;
    sessionStorage.setItem("admin-e2e-initialized", "true");
    localStorage.setItem("ow_admin_token", user.accessToken);
    localStorage.setItem("ow_admin_user", JSON.stringify({
      id: user.id, email: user.email, displayName: user.displayName, role: "admin", token: user.accessToken,
    }));
  }, user);
  return { ...user, headers: { Authorization: `Bearer ${user.accessToken}` } };
}

export async function expectGatewaySession(page: Page, user: Pick<GatewayUser, "id" | "accessToken">): Promise<void> {
  await expect.poll(() => page.evaluate(() => ({
    token: localStorage.getItem("ow_admin_token"),
    id: JSON.parse(localStorage.getItem("ow_admin_user") || "null")?.id ?? null,
  }))).toEqual({ token: user.accessToken, id: user.id });
  expect(user.id).not.toBe(OFFLINE_MOCK_USER_ID);
}

export async function signInThroughLoginForm(page: Page, user: GatewayUser): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  const login = page.waitForResponse(r => r.url().endsWith("/api/v1/auth/login") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  const response = await login;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.user.id).toBe(user.id);
  await expect(page).toHaveURL("/");
  await expectGatewaySession(page, { id: user.id, accessToken: body.accessToken });
}

export function details(id: string, area: string, component: string) {
  return {
    tag: [`@${id}`, `@admin-${area}`],
    annotation: { type: "screen", description: `src/app/pages/${component}/${component}.component.ts` },
  };
}

export async function createFeatureFlag(request: APIRequestContext, session: AdminSession): Promise<FeatureFlag> {
  const response = await request.post(`${api}/features`, {
    headers: session.headers,
    data: { feature: { name: "aaa_e2e_" + randomUUID().replaceAll("-", ""), description: uniqueName("audit-description"), enabled: true, rollout_percentage: 0 } },
  });
  await expect(response).toBeOK();
  return response.json();
}

interface AdminData {
  createFeatureFlag(): Promise<FeatureFlag>;
  createAnnouncement(): Promise<Announcement>;
  trackAnnouncement(id: string): void;
}
export const test = base.extend<{
  gatewayUser: GatewayUser;
  adminSession: AdminSession;
  adminData: AdminData;
}>({
  gatewayUser: async ({ request }, use) => {
    const user = await registerGatewayUser(request);
    try { await use(user); }
    finally {
      // Auth exposes no delete-user API. Remove only this registered fixture identity.
      await database(`DELETE FROM audit_logs WHERE actor_id = ${sqlLiteral(user.id)};
        DELETE FROM users WHERE id = ${sqlLiteral(user.id)} AND email = ${sqlLiteral(user.email)};`);
    }
  },
  adminSession: async ({ page, gatewayUser }, use) => {
    const session = await signInAdminSession(page, gatewayUser);
    await page.goto("/");
    await expectGatewaySession(page, session);
    await use(session);
  },
  adminData: async ({ request, adminSession }, use) => {
    const flags: string[] = [];
    const announcements = new Set<string>();
    try {
      await use({
        createFeatureFlag: async () => {
          const flag = await createFeatureFlag(request, adminSession);
          flags.push(flag.id);
          return flag;
        },
        createAnnouncement: async () => {
          const response = await request.post(`${api}/announcements`, {
            headers: adminSession.headers,
            data: { announcement: { title: uniqueName("Announcement"), body: "E2E daily admin notice", severity: "info", status: "draft" } },
          });
          await expect(response).toBeOK();
          const announcement: Announcement = await response.json();
          announcements.add(announcement.id);
          return announcement;
        },
        trackAnnouncement: id => { announcements.add(id); },
      });
    } finally {
      for (const id of flags) {
        await expect(await request.delete(`${api}/features/${id}`, { headers: adminSession.headers })).toBeOK();
      }
      for (const id of announcements) {
        const response = await request.delete(`${api}/announcements/${id}`, { headers: adminSession.headers });
        expect([204, 404]).toContain(response.status());
      }
    }
  },
});
export { expect } from "@playwright/test";
