import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { billingServer } from "../../test-setup";
import BillingRatingPage from "./rating-page";

const BASE = "http://localhost:3000/billing-api/api/tenants/:tenantId";
const TENANT = "00000000-0000-0000-0000-000000000001";
const OTHER = "00000000-0000-0000-0000-000000000002";
const PERIOD = { period_start: "2026-02-01", period_end: "2026-02-28" };
const RATING = {
  tenant_id: TENANT, ...PERIOD, used_units: 260, quota_units: 100,
  rollover_units: 200, billable_units: 0, first_tier_units: 0,
  second_tier_units: 0, overage_amount: "0.00",
};
const STORED = {
  used_units: 260, quota_units: 100, rollover_units: 0,
  billable_units: 0, overage_amount: "0.00",
};

function renderPage() {
  return render(<MemoryRouter><BillingRatingPage /></MemoryRouter>);
}

async function loaded() {
  return screen.findByRole("region", { name: "Usage rating result" });
}

beforeEach(() => {
  billingServer.use(
    http.get(`${BASE}/rating`, () => HttpResponse.json(RATING)),
    http.get(`${BASE}/usage-summary`, () => HttpResponse.json([
      { kind: "api", event_count: 2, units: 230 },
      { kind: "storage", event_count: 1, units: 30 },
    ])),
    http.post(`${BASE}/rating/finalize`, () =>
      HttpResponse.json({ ...STORED, rating_result: [STORED] })),
  );
});

describe("Billing usage rating", () => {
  it("loads the default tenant and period, rating fields and per-kind summary", async () => {
    renderPage();
    expect(screen.getByLabelText("Tenant id")).toHaveValue(TENANT);
    expect(screen.getByLabelText("Period start")).toHaveValue(PERIOD.period_start);
    expect(screen.getByLabelText("Period end")).toHaveValue(PERIOD.period_end);
    const result = await loaded();
    for (const label of ["Used units", "Quota units", "Rollover units", "Billable units",
      "First-tier units", "Second-tier units", "Overage amount"]) {
      expect(within(result).getByText(label)).toBeInTheDocument();
    }
    expect(within(result).getByText("260")).toBeInTheDocument();
    expect(within(result).getByText("$0.00")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Usage by kind" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByRole("row", { name: "api 2 230" })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "storage 1 30" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View plans" })).toHaveAttribute("href", "/billing/plans");
  });

  it("requests both endpoints with the edited tenant and period and clears stale results", async () => {
    const requests: string[] = [];
    billingServer.use(
      http.get(`${BASE}/rating`, ({ request }) => {
        requests.push(request.url);
        return HttpResponse.json(RATING);
      }),
      http.get(`${BASE}/usage-summary`, ({ request }) => {
        requests.push(request.url);
        return HttpResponse.json([]);
      }),
    );
    renderPage();
    await loaded();
    fireEvent.change(screen.getByLabelText("Tenant id"), { target: { value: OTHER } });
    expect(screen.queryByRole("region", { name: "Usage rating result" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-01-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-01-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Load rating" }));
    await loaded();
    for (const path of ["rating", "usage-summary"]) {
      expect(requests).toContain(`http://localhost:3000/billing-api/api/tenants/${OTHER}/${path}?period_start=2026-01-01&period_end=2026-01-31`);
    }
  });

  it("shows an empty summary without confusing it with a request failure", async () => {
    billingServer.use(http.get(`${BASE}/usage-summary`, () => HttpResponse.json([])));
    renderPage();
    await loaded();
    expect(screen.getByText("No usage events in this period.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it.each([
    ["rating", 404], ["rating", 503], ["usage-summary", 422], ["usage-summary", 500],
  ])("shows and dismisses %s HTTP %s errors, then allows retry", async (path, status) => {
    billingServer.use(http.get(`${BASE}/${path}`, () =>
      HttpResponse.json({ detail: "unavailable" }, { status })));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(`HTTP ${status}`);
    expect(screen.queryByRole("region", { name: "Usage rating result" })).not.toBeInTheDocument();
    expect(screen.queryByText("No usage events in this period.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss error" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    billingServer.use(http.get(`${BASE}/${path}`, () =>
      HttpResponse.json(path === "rating" ? RATING : [])));
    fireEvent.click(screen.getByRole("button", { name: "Load rating" }));
    await loaded();
  });

  it("shows network errors", async () => {
    billingServer.use(http.get(`${BASE}/rating`, () => HttpResponse.error()));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Rating and usage summary could not be loaded.");
  });

  it("ignores an old response after changing selection and loading again", async () => {
    billingServer.use(http.get(`${BASE}/rating`, async ({ params }) => {
      if (params.tenantId === TENANT) await delay(150);
      return HttpResponse.json({ ...RATING, used_units: params.tenantId === TENANT ? 111 : 222 });
    }));
    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("Loading rating");
    fireEvent.change(screen.getByLabelText("Tenant id"), { target: { value: OTHER } });
    fireEvent.click(screen.getByRole("button", { name: "Load rating" }));
    const result = await loaded();
    expect(within(result).getByText("222")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(screen.queryByText("111")).not.toBeInTheDocument();
    expect(within(result).getByText("222")).toBeInTheDocument();
  });

  it.each([
    ["Tenant id", "invalid"], ["Period end", "2026-01-31"],
  ])("validates %s before sending another request", async (label, value) => {
    let requests = 0;
    billingServer.use(http.get(`${BASE}/rating`, () => {
      requests += 1;
      return HttpResponse.json(RATING);
    }));
    renderPage();
    await loaded();
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Load rating" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid tenant id and a period");
    expect(requests).toBe(1);
  });

  it("finalizes the selected period and displays stored rollover rather than applied credit", async () => {
    let submitted: unknown;
    let tenant: unknown;
    billingServer.use(http.post(`${BASE}/rating/finalize`, async ({ request, params }) => {
      tenant = params.tenantId;
      submitted = await request.json();
      await delay(50);
      return HttpResponse.json({ ...STORED, rating_result: [STORED] });
    }));
    renderPage();
    const rating = await loaded();
    fireEvent.click(screen.getByRole("button", { name: "Finalize rating" }));
    expect(screen.getByRole("button", { name: "Finalizing…" })).toBeDisabled();
    expect(screen.getByLabelText("Tenant id")).toBeDisabled();
    const persisted = await screen.findByRole("region", { name: "Persisted rating result" });
    expect(submitted).toEqual(PERIOD);
    expect(tenant).toBe(TENANT);
    expect(within(rating).getByText("Rollover units").parentElement).toHaveTextContent("200");
    expect(within(persisted).getByText("Rollover units").parentElement).toHaveTextContent("0");
    expect(within(persisted).getByRole("status")).toHaveTextContent("Rating finalized for 2026-02-01 through 2026-02-28.");
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-02-27" } });
    expect(screen.queryByRole("region", { name: "Persisted rating result" })).not.toBeInTheDocument();
  });

  it.each([422, 503])("clears a previous finalize success on an HTTP %s failure", async (status) => {
    renderPage();
    await loaded();
    fireEvent.click(screen.getByRole("button", { name: "Finalize rating" }));
    await screen.findByRole("region", { name: "Persisted rating result" });
    billingServer.use(http.post(`${BASE}/rating/finalize`, () =>
      HttpResponse.json({ detail: "failure" }, { status })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Finalize rating" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Finalize rating" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(`Rating could not be finalized (HTTP ${status}).`);
    expect(screen.queryByRole("region", { name: "Persisted rating result" })).not.toBeInTheDocument();
  });
});
