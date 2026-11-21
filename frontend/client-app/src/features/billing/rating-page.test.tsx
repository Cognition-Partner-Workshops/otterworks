import { http, HttpResponse } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import BillingRatingPage from "./rating-page";
import { billingServer } from "../../test-setup";

const TENANT = "00000000-0000-0000-0000-000000000002";
const BASE = "http://localhost:3000/billing-api/api/tenants/:tenantId";

function renderPage(tenantId = TENANT) {
  return render(
    <MemoryRouter initialEntries={[`/billing/rating/${tenantId}`]}>
      <Routes>
        <Route path="/billing/rating/:tenantId" element={<BillingRatingPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function useRatingHandlers() {
  billingServer.use(
    http.get(`${BASE}/rating`, ({ params, request }) => {
      const url = new URL(request.url);
      return HttpResponse.json({
        tenant_id: params.tenantId,
        period_start: url.searchParams.get("period_start"),
        period_end: url.searchParams.get("period_end"),
        used_units: 700,
        quota_units: 500,
        rollover_units: 0,
        billable_units: 100,
        first_tier_units: 101,
        second_tier_units: 99,
        overage_amount: "4.37",
      });
    }),
    http.get(`${BASE}/usage-summary`, () =>
      HttpResponse.json([{ kind: "api", event_count: 1, units: 700 }]),
    ),
  );
}

describe("Billing usage rating", () => {
  it("renders the rating and usage summary for the period", async () => {
    useRatingHandlers();
    renderPage();
    expect(await screen.findByText("4.37")).toBeInTheDocument();
    expect(screen.getByText("Billable units").nextSibling).toHaveTextContent("100");
    expect(screen.getByRole("cell", { name: "api" })).toBeInTheDocument();
  });

  it("finalizes the rating and shows the stored result", async () => {
    useRatingHandlers();
    billingServer.use(
      http.post(`${BASE}/rating/finalize`, async ({ request }) => {
        const body = (await request.json()) as Record<string, string>;
        expect(body).toEqual({ period_start: "2026-02-01", period_end: "2026-02-28" });
        const row = {
          used_units: 700,
          quota_units: 500,
          rollover_units: 0,
          billable_units: 100,
          overage_amount: "4.37",
        };
        return HttpResponse.json({ ...row, rating_result: [row] });
      }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Finalize rating" }));
    expect(await screen.findByLabelText("Finalized rating")).toHaveTextContent(
      "Stored 100 billable units",
    );
  });

  it("shows a retryable error when the rating fails", async () => {
    let attempts = 0;
    billingServer.use(
      http.get(`${BASE}/rating`, () => {
        attempts += 1;
        return attempts === 1
          ? HttpResponse.json({ detail: "boom" }, { status: 503 })
          : HttpResponse.json({
              tenant_id: TENANT,
              period_start: "2026-02-01",
              period_end: "2026-02-28",
              used_units: 1,
              quota_units: 100,
              rollover_units: 0,
              billable_units: 0,
              first_tier_units: 0,
              second_tier_units: 0,
              overage_amount: "0.00",
            });
      }),
      http.get(`${BASE}/usage-summary`, () => HttpResponse.json([])),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No usage in this period.")).toBeInTheDocument();
  });

  it("rejects an invalid tenant id without calling the service", async () => {
    renderPage("not-a-tenant");
    expect(await screen.findByRole("alert")).toHaveTextContent("valid tenant id");
  });
});
