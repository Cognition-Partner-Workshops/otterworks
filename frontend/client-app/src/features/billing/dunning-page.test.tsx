import { http, HttpResponse } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import BillingDunningPage from "./dunning-page";
import { billingServer } from "../../test-setup";

const BASE = "http://localhost:3000/billing-api/api/dunning";
const TENANT = "00000000-0000-0000-0000-000000000005";

function renderPage() {
  return render(
    <MemoryRouter>
      <BillingDunningPage />
    </MemoryRouter>,
  );
}

describe("Billing dunning", () => {
  it("lists overdue accounts for the chosen date", async () => {
    let asOf = "";
    billingServer.use(
      http.get(`${BASE}/overdue`, ({ request }) => {
        asOf = new URL(request.url).searchParams.get("as_of") ?? "";
        return HttpResponse.json([
          {
            tenant_id: TENANT,
            invoice_id: "60000000-0000-0000-0000-000000000002",
            total: "161.29",
            days_overdue: 15,
            tenant_status: "active",
          },
        ]);
      }),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "List overdue accounts" }));
    expect(await screen.findByText(/15 days overdue/)).toBeInTheDocument();
    expect(asOf).toBe("2026-02-28");
  });

  it("shows scheduled attempts", async () => {
    billingServer.use(
      http.post(`${BASE}/schedule`, async ({ request }) => {
        expect(await request.json()).toEqual({ as_of: "2026-02-14" });
        const attempt = {
          invoice_id: "60000000-0000-0000-0000-000000000001",
          attempt_no: 1,
          scheduled_for: "2026-02-16",
          status: "scheduled",
        };
        return HttpResponse.json({ scheduled: [attempt], last_scheduled: attempt, attempts: [attempt] });
      }),
    );
    renderPage();
    fireEvent.change(screen.getByLabelText("As of"), { target: { value: "2026-02-14" } });
    fireEvent.click(screen.getByRole("button", { name: "Schedule dunning" }));
    expect(await screen.findByText("1 attempts scheduled.")).toBeInTheDocument();
    expect(screen.getByText(/attempt 1: 2026-02-16 \(scheduled\)/)).toBeInTheDocument();
  });

  it("shows suspension notifications", async () => {
    billingServer.use(
      http.post(`${BASE}/suspend`, () =>
        HttpResponse.json({
          suspended_tenants: [TENANT],
          suspended_subscriptions: [],
          notifications: [
            {
              id: "8cd558f5-d843-8d3d-be19-fb94c21ab81f",
              tenant_id: TENANT,
              kind: "suspension",
              sent_at: "2026-02-28T00:00:00Z",
            },
          ],
        }),
      ),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suspend overdue tenants" }));
    expect(await screen.findByText("1 tenants suspended.")).toBeInTheDocument();
    expect(screen.getByText(/suspension notice sent 2026-02-28T00:00:00Z/)).toBeInTheDocument();
  });

  it("explains a rolled-back suspension and can be dismissed", async () => {
    billingServer.use(
      http.post(`${BASE}/suspend`, () => HttpResponse.json({ detail: "conflict" }, { status: 409 })),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suspend overdue tenants" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Suspension was rolled back");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss error" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reports a schedule conflict as a scheduling failure", async () => {
    billingServer.use(
      http.post(`${BASE}/schedule`, () => HttpResponse.json({ detail: "conflict" }, { status: 409 })),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Schedule dunning" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Dunning was not scheduled");
    expect(alert).not.toHaveTextContent("Suspension");
  });

  it("clears results from the previous date when the date changes", async () => {
    billingServer.use(
      http.post(`${BASE}/suspend`, () =>
        HttpResponse.json({ suspended_tenants: [TENANT], suspended_subscriptions: [], notifications: [] }),
      ),
    );
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suspend overdue tenants" }));
    expect(await screen.findByText("1 tenants suspended.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("As of"), { target: { value: "2026-03-01" } });
    expect(screen.queryByText("1 tenants suspended.")).not.toBeInTheDocument();
  });

  it("locks the date while a billing run is in flight", async () => {
    billingServer.use(http.post(`${BASE}/schedule`, () => new Promise<Response>(() => {})));
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Schedule dunning" }));
    expect(await screen.findByRole("button", { name: "Scheduling…" })).toBeDisabled();
    expect(screen.getByLabelText("As of")).toBeDisabled();
  });
});
