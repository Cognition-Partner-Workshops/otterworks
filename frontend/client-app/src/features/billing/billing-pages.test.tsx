import { http, HttpResponse, delay } from "msw";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import BillingChangePlanPage from "./change-plan-page";
import BillingEntitlementPage from "./entitlement-page";
import { billingServer } from "../../test-setup";
import { localToday, money } from "./format";
import type { Invoice, PlanChangeQuote } from "./api";

const TENANT_A = "00000000-0000-0000-0000-000000000001";
const TENANT_B = "00000000-0000-0000-0000-000000000002";
const STARTER = "10000000-0000-0000-0000-000000000001";
const GROWTH = "10000000-0000-0000-0000-000000000002";
const SCALE = "10000000-0000-0000-0000-000000000003";
const base = "http://localhost:3000/billing-api";
const upgrade: PlanChangeQuote = {
  kind: "upgrade",
  current_plan: { code: "STARTER", name: "Starter", monthly_fee: "49.00" },
  new_plan: { code: "GROWTH", name: "Growth", monthly_fee: "149.00" },
  requested_on: "2026-03-15", effective_on: "2026-03-15",
  cycle_start: "2026-03-01", cycle_end: "2026-03-31",
  days_in_cycle: 31, days_remaining: 17, amount_due: "54.84",
  lines: [
    { description: "Credit for unused time on Starter", amount: "-26.87" },
    { description: "Growth plan for the rest of this billing period", amount: "81.71" },
  ],
  summary: "Your plan changes from Starter to Growth with a prorated charge of $54.84.",
};
const downgrade: PlanChangeQuote = {
  ...upgrade, kind: "downgrade", current_plan: { code: "SCALE", name: "Scale", monthly_fee: "499.00" },
  effective_on: "2026-04-01", amount_due: "0.00", lines: [],
  summary: "You keep Scale until Apr 1, 2026 and won't be charged today.",
};
const invoice: Invoice = {
  id: "invoice-one", tenant_id: TENANT_A, issued_on: "2026-03-15",
  period_start: "2026-03-15", period_end: "2026-03-31", total: "54.84",
  summary: upgrade.summary, lines: upgrade.lines,
};

function Switcher({ entitlement = false }: { entitlement?: boolean }) {
  const navigate = useNavigate();
  return <button onClick={() => navigate(`/billing/${entitlement ? "entitlement" : "change"}/${TENANT_B}`)}>Switch tenant</button>;
}

function renderChangePlan(preselect = GROWTH) {
  return render(<MemoryRouter initialEntries={[`/billing/change/${TENANT_A}?plan=${preselect}`]}>
    <Switcher />
    <Routes><Route path="/billing/change/:tenantId" element={<BillingChangePlanPage />} /></Routes>
  </MemoryRouter>);
}

async function confirmUpgrade() {
  const button = await screen.findByRole("button", { name: "Upgrade now and pay $54.84" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}

beforeEach(() => {
  billingServer.use(
    http.get(`${base}/api/plans`, () => HttpResponse.json([
      { plan_id: STARTER, code: "STARTER", monthly_fee: "49.00" },
      { plan_id: GROWTH, code: "GROWTH", monthly_fee: "149.00" },
      { plan_id: SCALE, code: "SCALE", monthly_fee: "499.00" },
    ])),
    http.get(`${base}/api/tenants/:tenantId/entitlement`, ({ params }) => HttpResponse.json({
      tenant_id: params.tenantId, plan_code: "STARTER", monthly_fee: "49.00",
      tier: "starter", subscription_status: "active", effective_on: "2026-03-15", included_units: 100,
    })),
    http.get(`${base}/api/tenants/:tenantId/plan-change-quote`, () => HttpResponse.json(upgrade)),
    http.get(`${base}/api/tenants/:tenantId/invoices`, () => HttpResponse.json([])),
    http.post(`${base}/api/tenants/:tenantId/plan-changes`, () => HttpResponse.json({
      ...upgrade, invoice, subscriptions: [],
    })),
  );
});

describe("Customer billing flow", () => {
  it("preselects a plan, previews an upgrade and confirms invoice lines and total", async () => {
    let posted: unknown;
    let invoiceLoads = 0;
    billingServer.use(
      http.post(`${base}/api/tenants/:tenantId/plan-changes`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ ...upgrade, invoice, subscriptions: [] });
      }),
      http.get(`${base}/api/tenants/:tenantId/invoices`, () => HttpResponse.json(++invoiceLoads === 1 ? [] : [invoice])),
    );
    renderChangePlan();
    await screen.findByRole("region", { name: "Plan change preview" });
    expect(screen.getByLabelText("Plan")).toHaveValue(GROWTH);
    expect(screen.getByLabelText("Change date")).toHaveValue(localToday());
    fireEvent.change(screen.getByLabelText("Change date"), { target: { value: "2026-03-15" } });
    const preview = await screen.findByRole("region", { name: "Plan change preview" });
    expect(preview).toHaveTextContent("Upgrade");
    expect(preview).toHaveTextContent("17 of 31 days");
    expect(preview).toHaveTextContent("Due today: $54.84");
    expect(within(preview).getByText("-$26.87")).toBeInTheDocument();
    expect(within(preview).getByText("$81.71")).toBeInTheDocument();
    await confirmUpgrade();
    const confirmation = await screen.findByRole("region", { name: "Plan change confirmation" });
    expect(confirmation).toHaveTextContent("Upgrade confirmed");
    expect(confirmation).toHaveTextContent("Credit for unused time on Starter");
    expect(confirmation).toHaveTextContent("Total: $54.84");
    expect(posted).toEqual({ plan_id: GROWTH, requested_on: "2026-03-15" });
    await waitFor(() => expect(screen.getByRole("region", { name: "Invoices" })).toHaveTextContent("Total: $54.84"));
    expect(invoiceLoads).toBe(2);
  });

  it("previews and schedules a downgrade with zero due today", async () => {
    billingServer.use(
      http.get(`${base}/api/tenants/:tenantId/plan-change-quote`, () => HttpResponse.json(downgrade)),
      http.post(`${base}/api/tenants/:tenantId/plan-changes`, () => HttpResponse.json({ ...downgrade, invoice: null, subscriptions: [] })),
    );
    renderChangePlan();
    const preview = await screen.findByRole("region", { name: "Plan change preview" });
    expect(preview).toHaveTextContent("Downgrade");
    expect(preview).toHaveTextContent("Starts on Apr 1, 2026");
    expect(preview).toHaveTextContent("$0.00 due today");
    fireEvent.click(screen.getByRole("button", { name: "Schedule downgrade" }));
    const confirmation = await screen.findByRole("region", { name: "Plan change confirmation" });
    expect(confirmation).toHaveTextContent("Scheduled: Growth starts on Apr 1, 2026");
    expect(confirmation).toHaveTextContent("$0.00 due today");
  });

  it("shows the server's 409 quote detail in BillingAlert", async () => {
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/plan-change-quote`, () =>
      HttpResponse.json({ detail: "You're already on this plan" }, { status: 409 })));
    renderChangePlan(STARTER);
    expect(await screen.findByRole("alert")).toHaveTextContent("You're already on this plan");
    expect(screen.queryByRole("region", { name: "Plan change preview" })).not.toBeInTheDocument();
  });

  it("clears a previous success when a later plan submission fails", async () => {
    let attempts = 0;
    billingServer.use(http.post(`${base}/api/tenants/:tenantId/plan-changes`, () =>
      ++attempts === 1 ? HttpResponse.json({ ...upgrade, invoice, subscriptions: [] }) :
        HttpResponse.json({ detail: "This exact change was already requested" }, { status: 409 })));
    renderChangePlan();
    await confirmUpgrade();
    await screen.findByRole("region", { name: "Plan change confirmation" });
    await confirmUpgrade();
    expect(await screen.findByRole("alert")).toHaveTextContent("This exact change was already requested");
    expect(screen.queryByRole("region", { name: "Plan change confirmation" })).not.toBeInTheDocument();
  });

  it("clears the previous tenant entitlement while switching tenants", async () => {
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/entitlement`, async ({ params }) => {
      if (params.tenantId === TENANT_B) await delay(80);
      return HttpResponse.json({ tenant_id: params.tenantId, plan_code: params.tenantId === TENANT_A ? "STARTER" : "GROWTH", monthly_fee: "49.00" });
    }));
    render(<MemoryRouter initialEntries={[`/billing/entitlement/${TENANT_A}`]}>
      <Switcher entitlement />
      <Routes><Route path="/billing/entitlement/:tenantId" element={<BillingEntitlementPage />} /></Routes>
    </MemoryRouter>);
    expect(await screen.findByText("STARTER")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Change plan" })).toHaveAttribute("href", `/billing/change/${TENANT_A}`);
    fireEvent.click(screen.getByRole("button", { name: "Switch tenant" }));
    expect(screen.queryByText("STARTER")).not.toBeInTheDocument();
    expect(await screen.findByText("GROWTH")).toBeInTheDocument();
  });

  it("ignores a plan response after switching tenants", async () => {
    let started = false;
    billingServer.use(http.post(`${base}/api/tenants/:tenantId/plan-changes`, async () => {
      started = true;
      await delay(100);
      return HttpResponse.json({ ...upgrade, invoice, subscriptions: [] });
    }));
    renderChangePlan();
    await confirmUpgrade();
    await waitFor(() => expect(started).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Switch tenant" }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 150)));
    expect(screen.queryByRole("region", { name: "Plan change confirmation" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Invoices" })).not.toHaveTextContent("Total:");
  });

  it("ignores a submission response after the simulated date changes", async () => {
    let started = false;
    billingServer.use(http.post(`${base}/api/tenants/:tenantId/plan-changes`, async () => {
      started = true;
      await delay(100);
      return HttpResponse.json({ ...upgrade, invoice, subscriptions: [] });
    }));
    renderChangePlan();
    await confirmUpgrade();
    await waitFor(() => expect(started).toBe(true));
    fireEvent.change(screen.getByLabelText("Change date"), { target: { value: "2026-03-16" } });
    await act(() => new Promise((resolve) => setTimeout(resolve, 150)));
    expect(screen.queryByRole("region", { name: "Plan change confirmation" })).not.toBeInTheDocument();
  });

  it("clears successful results and invoices immediately when the tenant changes", async () => {
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/invoices`, ({ params }) => HttpResponse.json(params.tenantId === TENANT_A ? [invoice] : [])));
    renderChangePlan();
    await confirmUpgrade();
    await screen.findByRole("region", { name: "Plan change confirmation" });
    fireEvent.click(screen.getByRole("button", { name: "Switch tenant" }));
    expect(screen.queryByRole("region", { name: "Plan change confirmation" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Invoices" })).not.toHaveTextContent("Total:");
  });

  it("ignores a superseded quote after changing the selected plan", async () => {
    let started = false;
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/plan-change-quote`, async ({ request }) => {
      if (new URL(request.url).searchParams.get("plan_id") === GROWTH) {
        started = true;
        await delay(100);
        return HttpResponse.json(upgrade);
      }
      return HttpResponse.json({ ...upgrade, new_plan: { ...upgrade.new_plan, name: "Scale" }, summary: "Newer Scale quote" });
    }));
    renderChangePlan();
    await waitFor(() => expect(started).toBe(true));
    fireEvent.change(await screen.findByLabelText("Plan"), { target: { value: SCALE } });
    expect(await screen.findByText("Newer Scale quote")).toBeInTheDocument();
    await act(() => new Promise((resolve) => setTimeout(resolve, 150)));
    expect(screen.queryByText(upgrade.summary)).not.toBeInTheDocument();
  });

  it("ignores a late quote error after the change date is superseded", async () => {
    let started = false;
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/plan-change-quote`, async ({ request }) => {
      if (new URL(request.url).searchParams.get("on") !== "2026-03-15") {
        started = true;
        await delay(100);
        return HttpResponse.json({ detail: "Old date error" }, { status: 409 });
      }
      return HttpResponse.json(upgrade);
    }));
    renderChangePlan();
    await waitFor(() => expect(started).toBe(true));
    fireEvent.change(await screen.findByLabelText("Change date"), { target: { value: "2026-03-15" } });
    await screen.findByRole("region", { name: "Plan change preview" });
    await act(() => new Promise((resolve) => setTimeout(resolve, 150)));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not let a late initial invoices request overwrite a refreshed invoice", async () => {
    let loads = 0;
    billingServer.use(http.get(`${base}/api/tenants/:tenantId/invoices`, async () => {
      if (++loads === 1) { await delay(150); return HttpResponse.json([]); }
      return HttpResponse.json([invoice]);
    }));
    renderChangePlan();
    await confirmUpgrade();
    await waitFor(() => expect(screen.getByRole("region", { name: "Invoices" })).toHaveTextContent("Total: $54.84"));
    await act(() => new Promise((resolve) => setTimeout(resolve, 200)));
    expect(screen.getByRole("region", { name: "Invoices" })).toHaveTextContent("Total: $54.84");
  });

  it("shows empty plans and invoice failures without a confirm action", async () => {
    billingServer.use(
      http.get(`${base}/api/plans`, () => HttpResponse.json([])),
      http.get(`${base}/api/tenants/:tenantId/invoices`, () => HttpResponse.json({ detail: "Invoices unavailable" }, { status: 503 })),
    );
    renderChangePlan("");
    expect(await screen.findByText("No plans are available.")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Invoices unavailable");
    expect(screen.queryByRole("button", { name: /Upgrade now/ })).not.toBeInTheDocument();
  });

  it("formats server money strings without losing precision", () => {
    expect(money("1234.56")).toBe("$1,234.56");
    expect(money("-26.87")).toBe("-$26.87");
    expect(money("9999999999999999.99")).toBe("$9,999,999,999,999,999.99");
  });
});
