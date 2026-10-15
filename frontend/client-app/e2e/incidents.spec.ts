import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { uniqueEmail } from "./fixtures/test-helpers";

// Incident-responder area (incident/README.md): what a user feels in the web
// app, and what the on-call responder sees in Prometheus, Alertmanager and
// Grafana. Observability checks skip when the incident overlay is not up
// (`make incident-up`).

const GATEWAY_URL = process.env.GATEWAY_URL || "http://localhost:8080";
const PROM_URL = process.env.INCIDENT_PROM_URL || "http://localhost:9090";
const ALERTMANAGER_URL = process.env.INCIDENT_ALERTMANAGER_URL || "http://localhost:9093";
const GRAFANA_URL = process.env.INCIDENT_GRAFANA_URL || "http://localhost:3001";
const GRAFANA_USER = process.env.GRAFANA_ADMIN_USER || "admin";
const GRAFANA_PASSWORD = process.env.GRAFANA_ADMIN_PASSWORD || "otterworks";

interface Session {
  accessToken: string;
  refreshToken: string;
  userId: string;
}

async function registerViaGateway(request: APIRequestContext): Promise<Session> {
  const response = await request.post(`${GATEWAY_URL}/api/v1/auth/register`, {
    data: { email: uniqueEmail(), password: "Passw0rd!23", displayName: "Incident QA" },
  });
  expect(response.status()).toBe(201);
  const body = await response.json();
  return { accessToken: body.accessToken, refreshToken: body.refreshToken, userId: body.user.id };
}

async function signIn(page: Page, session: Session) {
  await page.addInitScript((s) => {
    localStorage.setItem("otter_access_token", s.accessToken);
    localStorage.setItem("otter_refresh_token", s.refreshToken);
  }, session);
}

async function createDocument(request: APIRequestContext, session: Session, title: string) {
  const response = await request.post(`${GATEWAY_URL}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: { title, content: "Incident QA body" },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).id as string;
}

async function reachable(request: APIRequestContext, url: string): Promise<boolean> {
  try {
    const response = await request.get(url, { timeout: 5_000 });
    return response.status() < 500;
  } catch {
    return false;
  }
}

test.describe("Incidents: user-visible symptoms", () => {
  test("signed-in user sees their documents list load", async ({ page, request }) => {
    const session = await registerViaGateway(request);
    const titles = ["Incident QA alpha", "Incident QA beta", "Incident QA gamma"];
    for (const title of titles) await createDocument(request, session, title);
    await signIn(page, session);

    const listResponse = page.waitForResponse(
      (r) => r.url().includes("/api/v1/documents") && r.request().method() === "GET"
    );
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    const response = await listResponse;
    expect(response.status()).toBe(200);
    for (const title of titles) {
      await expect(page.getByText(title).first()).toBeVisible({ timeout: 15_000 });
    }
  });

  test("document export works from the API the export button uses", async ({ request }) => {
    const session = await registerViaGateway(request);
    const id = await createDocument(request, session, "Incident QA export");
    const response = await request.get(`${GATEWAY_URL}/api/v1/documents/${id}/export`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
      params: { format: "html" },
    });
    expect(response.status()).toBe(200);
    expect(await response.text()).toContain("Incident QA export");
  });
});

test.describe("Incidents: on-call observability", () => {
  test("Prometheus alerts page lists the incident rules", async ({ page, request }) => {
    test.skip(!(await reachable(request, `${PROM_URL}/-/ready`)), "Prometheus not running");
    await page.goto(`${PROM_URL}/alerts`);
    for (const alert of [
      "DocumentListLatencyHigh",
      "RequestLogVolumeNearFull",
      "DocumentServiceMemoryHigh",
      "DocumentStatsRollupDuplicated",
    ]) {
      await expect(page.getByText(alert, { exact: false }).first()).toBeVisible();
    }
  });

  test("Alertmanager status shows the Devin and Slack receivers", async ({ page, request }) => {
    test.skip(
      !(await reachable(request, `${ALERTMANAGER_URL}/-/ready`)),
      "Alertmanager not running"
    );
    await page.goto(`${ALERTMANAGER_URL}/#/status`);
    await expect(page.getByText("devin-oncall").first()).toBeVisible();
    await expect(page.getByText("slack-oncall").first()).toBeVisible();
  });

  test("Grafana form login opens the incident responder dashboard", async ({ page, request }) => {
    test.skip(!(await reachable(request, `${GRAFANA_URL}/api/health`)), "Grafana not running");
    await page.goto(`${GRAFANA_URL}/login`);
    await page.locator("input[name='user']").fill(GRAFANA_USER);
    await page.locator("input[name='password']").fill(GRAFANA_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();
    await page.waitForURL((url) => !url.pathname.startsWith("/login"));
    // Grafana may prompt for a new admin password on first login.
    const skipButton = page.getByRole("button", { name: "Skip" });
    if (await skipButton.isVisible().catch(() => false)) await skipButton.click();

    await page.goto(`${GRAFANA_URL}/d/otterworks-incident-responder`);
    await expect(page.getByText("OtterWorks - Incident Responder").first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("SQL statements per list request").first()).toBeVisible();
  });
});
