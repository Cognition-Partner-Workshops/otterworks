import { expect, type Page } from "@playwright/test";
import { adminTest, openAdminPage, waitForAdminApi, type AdminSession } from "../support/admin-session";

// Legacy data, verbatim from tests/legacy-suites/selenium/.../HealthTest.java and pages/HealthPage.java.
export const LegacyHealth = {
  path: "/health",
  heading: "System Health",
  // HealthPage.refreshButton targets the button holding the 'refresh' mat-icon; its accessible name is "Refresh".
  refreshIcon: "refresh",
  refreshButtonName: "Refresh",
  // HealthPage.healthySummary (.summary-card.healthy) is the card labelled "Healthy".
  healthySummaryLabel: "Healthy",
} as const;

export const HEALTH_API_PATH = "/api/v1/admin/health/services";

export interface HealthCounts {
  healthy: number;
  degraded: number;
  down: number;
}

interface HealthServicesBody {
  services?: { status: string }[];
  database?: { status: string };
  redis?: { status: string };
}

// Mirrors AdminApiService.mapHealthServices: services healthy/unhealthy/other -> healthy/down/degraded;
// database and redis are appended as healthy or down.
export function countsFromHealthBody(body: HealthServicesBody): HealthCounts {
  const statuses = (body.services ?? []).map(s =>
    s.status === "healthy" ? "healthy" : s.status === "unhealthy" ? "down" : "degraded",
  );
  for (const infra of [body.database, body.redis]) {
    if (infra) statuses.push(infra.status === "healthy" ? "healthy" : "down");
  }
  return {
    healthy: statuses.filter(s => s === "healthy").length,
    degraded: statuses.filter(s => s === "degraded").length,
    down: statuses.filter(s => s === "down").length,
  };
}

const SUMMARY_LABELS = ["Healthy", "Degraded", "Down"] as const;
type SummaryLabel = typeof SUMMARY_LABELS[number];

export class HealthPage {
  constructor(private readonly page: Page, private readonly session: AdminSession) {}

  get heading() {
    return this.page.getByRole("heading", { level: 1, name: LegacyHealth.heading, exact: true });
  }

  get refreshButton() {
    return this.page.getByRole("main").getByRole("button", { name: LegacyHealth.refreshButtonName, exact: true });
  }

  // Accessibility gap: summary cards are unlabelled <div>s with no role, so the card is found by its
  // visible label text, anchored to the count that precedes it ("<n> Healthy" ends the card's text)
  // and excluding the wrapper that also holds the other two labels.
  summaryCard(label: SummaryLabel, count: number) {
    const otherLabels = SUMMARY_LABELS.filter(other => other !== label).join("|");
    return this.page
      .getByRole("main")
      .locator("div")
      .filter({ has: this.page.getByText(label, { exact: true }), hasText: new RegExp(`(^|\\D)${count}\\s*${label}\\s*$`) })
      .filter({ hasNotText: new RegExp(otherLabels) });
  }

  async expectSummary(counts: HealthCounts): Promise<void> {
    await expect(this.summaryCard("Healthy", counts.healthy)).toBeVisible();
    await expect(this.summaryCard("Degraded", counts.degraded)).toBeVisible();
    await expect(this.summaryCard("Down", counts.down)).toBeVisible();
  }

  /** Waits for the real GET /api/v1/admin/health/services issued by `trigger`; returns the counts it implies. */
  async healthResponseFrom(trigger: () => Promise<unknown>): Promise<{ status: number; authorization: string; counts: HealthCounts }> {
    const response = await waitForAdminApi(
      this.page,
      this.session,
      { pathname: HEALTH_API_PATH },
      trigger,
    );
    return {
      status: response.status(),
      authorization: (await response.request().allHeaders())["authorization"]!,
      counts: countsFromHealthBody(await response.json() as HealthServicesBody),
    };
  }

  async open() {
    const response = await openAdminPage(this.page, this.session, {
      path: LegacyHealth.path,
      apiPath: HEALTH_API_PATH,
    });
    return {
      status: response.status(),
      authorization: (await response.request().allHeaders())["authorization"]!,
      counts: countsFromHealthBody(await response.json() as HealthServicesBody),
    };
  }
}

export const test = adminTest.extend<{ healthPage: HealthPage }>({
  healthPage: async ({ page, adminSession }, use) => {
    await use(new HealthPage(page, adminSession));
  },
});

export { expect };
