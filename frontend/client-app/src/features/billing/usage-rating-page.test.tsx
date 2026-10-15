import { http, HttpResponse } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import BillingUsageRatingPage from "./usage-rating-page";
import { billingServer } from "../../test-setup";

const TENANT = "00000000-0000-0000-0000-000000000007";
const BASE = `http://localhost:3000/billing-api/api/tenants/${TENANT}`;
const RESULT = {
  used_units: 260,
  quota_units: 100,
  rollover_units: 0,
  billable_units: 160,
  overage_amount: "10.43",
};

function renderPage(tenantId = TENANT) {
  return render(
    <MemoryRouter initialEntries={[`/billing/rating/${tenantId}`]}>
      <Routes>
        <Route path="/billing/rating/:tenantId" element={<BillingUsageRatingPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function useRatingHandlers() {
  billingServer.use(
    http.get(`${BASE}/usage-rating`, ({ request }) => {
      const url = new URL(request.url);
      expect(url.searchParams.get("period_start")).toBe("2026-02-01");
      expect(url.searchParams.get("period_end")).toBe("2026-02-28");
      return HttpResponse.json({
        ...RESULT,
        tenant_id: TENANT,
        period_start: "2026-02-01",
        period_end: "2026-02-28",
        first_tier_units: 101,
        second_tier_units: 59,
      });
    }),
    http.get(`${BASE}/usage-summary`, () =>
      HttpResponse.json([{ kind: "api", event_count: 1, units: 260 }]),
    ),
  );
}

describe("Billing usage rating", () => {
  it("renders the rating and usage summary", async () => {
    useRatingHandlers();
    renderPage();
    expect(await screen.findByLabelText("Usage rating")).toHaveTextContent("10.43");
    expect(screen.getByLabelText("Usage summary")).toHaveTextContent("api");
    expect(screen.getByLabelText("Usage summary")).toHaveTextContent("260");
  });

  it("finalizes the period", async () => {
    useRatingHandlers();
    billingServer.use(
      http.post(`${BASE}/rating-finalizations`, async ({ request }) => {
        expect(await request.json()).toEqual({
          period_start: "2026-02-01",
          period_end: "2026-02-28",
        });
        return HttpResponse.json({ ...RESULT, rating_result: [RESULT] });
      }),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Finalize period" }));
    expect(await screen.findByLabelText("Finalized rating")).toHaveTextContent("billable 160");
  });

  it("shows an error when the tenant has no overlapping subscription", async () => {
    billingServer.use(
      http.get(`${BASE}/usage-rating`, () =>
        HttpResponse.json({ detail: "no subscription" }, { status: 404 }),
      ),
      http.get(`${BASE}/usage-summary`, () => HttpResponse.json([])),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The usage rating could not be loaded.",
    );
  });

  it("rejects an invalid tenant id without calling the service", async () => {
    renderPage("not-a-tenant");
    expect(await screen.findByRole("alert")).toHaveTextContent("A valid tenant id is required.");
  });
});
