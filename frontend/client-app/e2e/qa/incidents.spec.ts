import { test, expect, type Page } from "@playwright/test";
import { registerUser, expectDashboard } from "../fixtures/test-helpers";

/**
 * QA: incident-responder observability pipeline (make incident-up UI=1).
 * Critical paths only: the user-facing list the n-plus-one scenario degrades,
 * and the Prometheus / Alertmanager / Grafana / Jaeger surfaces a responder uses.
 * Set INCIDENT_EXPECT=firing while n-plus-one is armed, or =clear after disarm.
 */

const PROMETHEUS_URL = process.env.PROMETHEUS_URL || "http://localhost:9090";
const ALERTMANAGER_URL = process.env.ALERTMANAGER_URL || "http://localhost:9093";
const GRAFANA_URL = process.env.GRAFANA_URL || "http://localhost:3001";
const JAEGER_URL = process.env.JAEGER_URL || "http://localhost:16686";
const GRAFANA_USER = process.env.GRAFANA_USER || "admin";
const GRAFANA_PASSWORD = process.env.GRAFANA_PASSWORD || "otterworks";
const INCIDENT_EXPECT = process.env.INCIDENT_EXPECT || "any";

const DASHBOARD_UID = "otterworks-incident-responder";
const PAGED_ALERT = "DocumentListLatencyHigh";

async function grafanaLogin(page: Page) {
  await page.goto(`${GRAFANA_URL}/login`);
  await page.getByTestId("data-testid Username input field").fill(GRAFANA_USER);
  await page.getByTestId("data-testid Password input field").fill(GRAFANA_PASSWORD);
  await page.getByTestId("data-testid Login button").click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

test.describe("QA incidents: user-facing document list", () => {
  test("document list loads through the gateway and exposes SQL fan-out telemetry", async ({
    page,
  }) => {
    await registerUser(page);
    await expectDashboard(page);

    const listResponse = page.waitForResponse(
      (r) => /\/api\/v1\/documents\/?(\?|$)/.test(r.url()) && r.request().method() === "GET",
      { timeout: 20_000 }
    );
    await page.goto("/documents");
    const response = await listResponse;
    expect(response.status()).toBe(200);
    const queries = Number(response.headers()["x-db-queries"]);
    expect(queries).toBeGreaterThanOrEqual(1);
    await expect(page.getByRole("heading", { name: /documents/i }).first()).toBeVisible();
  });
});

test.describe("QA incidents: responder tooling", () => {
  test("Prometheus alerts page lists the incident rules and reflects scenario state", async ({
    page,
    request,
  }) => {
    await page.goto(`${PROMETHEUS_URL}/alerts`);
    await expect(page.getByText(PAGED_ALERT).first()).toBeVisible();
    await expect(page.getByText("DocumentListQueryFanout").first()).toBeVisible();

    const res = await request.get(`${PROMETHEUS_URL}/api/v1/alerts`);
    expect(res.ok()).toBeTruthy();
    const alerts: { labels: Record<string, string>; state: string }[] = (await res.json()).data
      .alerts;
    const firing = alerts.some((a) => a.labels.alertname === PAGED_ALERT && a.state === "firing");
    if (INCIDENT_EXPECT === "firing") expect(firing).toBe(true);
    if (INCIDENT_EXPECT === "clear") expect(firing).toBe(false);
  });

  test("Alertmanager UI is up and holds the page when firing", async ({ page, request }) => {
    await page.goto(`${ALERTMANAGER_URL}/#/alerts`);
    await expect(page.getByText(/alertmanager/i).first()).toBeVisible();

    const res = await request.get(`${ALERTMANAGER_URL}/api/v2/alerts?active=true`);
    expect(res.ok()).toBeTruthy();
    const alerts: { labels: Record<string, string> }[] = await res.json();
    const paged = alerts.some(
      (a) => a.labels.alertname === PAGED_ALERT && a.labels.page === "devin"
    );
    if (INCIDENT_EXPECT === "firing") {
      expect(paged).toBe(true);
      await page.reload();
      await expect(page.getByText(PAGED_ALERT).first()).toBeVisible({ timeout: 15_000 });
    }
    if (INCIDENT_EXPECT === "clear") expect(paged).toBe(false);
  });

  test("Grafana incident-responder dashboard renders the n-plus-one panels", async ({
    page,
    request,
  }) => {
    const auth = Buffer.from(`${GRAFANA_USER}:${GRAFANA_PASSWORD}`).toString("base64");
    const res = await request.get(`${GRAFANA_URL}/api/dashboards/uid/${DASHBOARD_UID}`, {
      headers: { Authorization: `Basic ${auth}` },
    });
    expect(res.ok()).toBeTruthy();
    const titles: string[] = (await res.json()).dashboard.panels.map(
      (p: { title: string }) => p.title
    );
    expect(titles).toEqual(
      expect.arrayContaining(["Firing alerts (what paged Devin)", "Trace waterfall"])
    );

    await grafanaLogin(page);
    await page.goto(`${GRAFANA_URL}/d/${DASHBOARD_UID}?orgId=1&from=now-30m&to=now`);
    await expect(page.getByText("OtterWorks - Incident Responder").first()).toBeVisible({
      timeout: 20_000,
    });
    for (const title of [
      "GET /api/v1/documents/ - latency p50 / p95 / p99",
      "SQL statements per list request (N+1 fan-out)",
    ]) {
      await expect(page.getByRole("heading", { name: title })).toBeVisible({ timeout: 20_000 });
    }
    await expect(page.getByText("No data").first()).toBeHidden();
  });

  test("Jaeger shows document-service list traces with SQL child spans", async ({
    page,
    request,
  }) => {
    const res = await request.get(
      `${JAEGER_URL}/api/traces?service=document-service&operation=${encodeURIComponent(
        "GET /api/v1/documents/"
      )}&limit=20&lookback=1h`
    );
    expect(res.ok()).toBeTruthy();
    const traces: { traceID: string; spans: { operationName: string }[] }[] = (await res.json())
      .data;
    const fanout = traces.find((t) => t.spans.some((s) => s.operationName.startsWith("SELECT")));
    expect(fanout, "expected a list trace with SQL spans").toBeTruthy();

    await page.goto(`${JAEGER_URL}/trace/${fanout!.traceID}`);
    await expect(page.getByText("document-service").first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/SELECT otterworks/).first()).toBeVisible();
  });
});
