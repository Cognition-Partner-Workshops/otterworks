import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Incident-responder operator journey on the local incident stack
 * (`make incident-up`): the Grafana dashboard, Prometheus alert rules,
 * Alertmanager and Jaeger an on-call responder opens when document-service
 * pages. Skips when the stack is not running.
 *
 * Set INCIDENT_EXPECT_FIRING=<AlertName> while a scenario is armed
 * (`make incident-arm SCENARIO=...`) to also assert the page is live in
 * Prometheus and Alertmanager. The flaws behind those alerts are PLANTED on
 * main; these specs only check that they page.
 */

const PROM = process.env.INCIDENT_PROM_URL || "http://localhost:9090";
const ALERTMANAGER = process.env.INCIDENT_ALERTMANAGER_URL || "http://localhost:9093";
const GRAFANA = process.env.INCIDENT_GRAFANA_URL || "http://localhost:3001";
const JAEGER = process.env.INCIDENT_JAEGER_URL || "http://localhost:16686";
const GRAFANA_USER = process.env.INCIDENT_GRAFANA_USER || "admin";
const GRAFANA_PASSWORD = process.env.INCIDENT_GRAFANA_PASSWORD || "otterworks";
const EXPECT_FIRING = process.env.INCIDENT_EXPECT_FIRING || "";

const INCIDENT_ALERTS = [
  "DocumentListLatencyHigh",
  "DocumentListQueryFanout",
  "RequestLogVolumeNearFull",
  "DocumentServiceErrorRateHigh",
  "DocumentServiceMemoryHigh",
  "DocumentStatsRollupDuplicated",
];

async function reachable(request: APIRequestContext, url: string): Promise<boolean> {
  try {
    const res = await request.get(url, { timeout: 3_000 });
    return res.status() < 500;
  } catch {
    return false;
  }
}

test.describe("Incident responder observability", () => {
  test.beforeEach(async ({ request }) => {
    test.skip(
      !(await reachable(request, `${PROM}/-/ready`)),
      "incident stack not running; start it with `make incident-up`",
    );
  });

  test.describe("Grafana", () => {
    test("incident dashboard shows the responder panels", async ({ page }) => {
      await page.goto(`${GRAFANA}/login`);
      await page.locator('input[name="user"]').fill(GRAFANA_USER);
      await page.locator('input[name="password"]').fill(GRAFANA_PASSWORD);
      await page.getByRole("button", { name: "Log in" }).click();
      await page.waitForURL((url) => !url.pathname.startsWith("/login"));
      await page.goto(`${GRAFANA}/d/otterworks-incident-responder`);
      await expect(page.getByText("OtterWorks - Incident Responder").first()).toBeVisible({
        timeout: 20_000,
      });
      for (const panel of [/request rate/i, /latency p50/i, /SQL statements per list request/i]) {
        await expect(page.getByText(panel).first()).toBeVisible();
      }
    });
  });

  test("Prometheus loads every incident alert rule", async ({ page }) => {
    await page.goto(`${PROM}/alerts`);
    for (const name of INCIDENT_ALERTS) {
      await expect(page.getByText(name, { exact: false }).first()).toBeVisible();
    }
  });

  test("Alertmanager UI is up and routes the incident receivers", async ({ page, request }) => {
    await page.goto(`${ALERTMANAGER}/#/status`);
    await expect(page.getByText("devin-oncall").first()).toBeVisible({ timeout: 15_000 });
    const status = await request.get(`${ALERTMANAGER}/api/v2/status`);
    expect(status.ok()).toBeTruthy();
    expect((await status.json()).cluster.status).toBe("ready");
  });

  test("Jaeger lists document-service traces", async ({ page, request }) => {
    const services = await request.get(`${JAEGER}/api/services`);
    expect((await services.json()).data).toContain("document-service");
    await page.goto(`${JAEGER}/search?service=document-service&limit=5&lookback=1h`);
    await expect(page.getByText(/document-service/).first()).toBeVisible({ timeout: 15_000 });
  });

  test("armed scenario pages in Prometheus and Alertmanager", async ({ page, request }) => {
    test.skip(!EXPECT_FIRING, "set INCIDENT_EXPECT_FIRING=<AlertName> with a scenario armed");

    const alerts = await request.get(`${PROM}/api/v1/alerts`);
    const firing = (await alerts.json()).data.alerts.filter(
      (a: { state: string; labels: { alertname: string } }) =>
        a.state === "firing" && a.labels.alertname === EXPECT_FIRING,
    );
    expect(firing.length, `${EXPECT_FIRING} firing in Prometheus`).toBeGreaterThan(0);
    expect(firing[0].labels.service).toBe("document-service");

    await page.goto(`${ALERTMANAGER}/#/alerts?filter=%7Balertname%3D%22${EXPECT_FIRING}%22%7D`);
    await expect(page.getByText(EXPECT_FIRING).first()).toBeVisible({ timeout: 20_000 });
  });
});
