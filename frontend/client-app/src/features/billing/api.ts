export const BILLING_BASE_URL =
  import.meta.env.VITE_BILLING_SERVICE_URL ||
  `${window.location.origin}/billing-api`;

export class BillingApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export type Plan = {
  plan_id: string;
  code: string;
  tier: string;
  monthly_fee: string;
  included_units: number;
  overage_rate: string;
};

export type Entitlement = {
  tenant_id: string;
  plan_code: string;
  tier: string;
  monthly_fee: string;
  included_units: number;
  subscription_status: string;
  effective_on: string;
};

export type Subscription = {
  plan_id: string;
  starts_on: string;
  ends_on: string | null;
  status: string;
};

export type PlanChangeResult = {
  latest_plan: string;
  latest_start: string;
  subscriptions: Subscription[];
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BILLING_BASE_URL}${path}`, options);
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body
      && typeof body.detail === "string" ? body.detail : null;
    throw new BillingApiError(
      detail || `Billing service returned ${response.status}`,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export const billingApi = {
  quotePlanChange: (tenantId: string, planId: string, on: string) =>
    request<PlanChangeQuote>(`/api/tenants/${encodeURIComponent(tenantId)}/plan-change-quote?${new URLSearchParams({ plan_id: planId, on })}`),
  applyPlanChange: (tenantId: string, planId: string, requestedOn: string) =>
    request<CustomerPlanChangeResult>(`/api/tenants/${encodeURIComponent(tenantId)}/plan-changes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: planId, requested_on: requestedOn }),
    }),
  listInvoices: (tenantId: string) =>
    request<Invoice[]>(`/api/tenants/${encodeURIComponent(tenantId)}/invoices`),
  listPlans: () => request<Plan[]>("/api/plans"),
  entitlement: (tenantId: string, on: string) =>
    request<Entitlement>(
      `/api/tenants/${encodeURIComponent(tenantId)}/entitlement?on=${encodeURIComponent(on)}`
    ),
  changePlan: (tenantId: string, planId: string, effectiveOn: string) =>
    request<PlanChangeResult>(
      `/api/tenants/${encodeURIComponent(tenantId)}/plan-change`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, effective_on: effectiveOn }),
      }
    ),
};

export type InvoiceLine = { description: string; amount: string };
export type Invoice = {
  id: string;
  tenant_id: string;
  issued_on: string;
  period_start: string;
  period_end: string;
  total: string;
  summary: string;
  lines: InvoiceLine[];
};
export type CustomerPlan = { code: string; name: string; monthly_fee: string };
export type PlanChangeQuote = {
  kind: "upgrade" | "downgrade";
  current_plan: CustomerPlan;
  new_plan: CustomerPlan;
  requested_on: string;
  effective_on: string;
  cycle_start: string;
  cycle_end: string;
  days_in_cycle: number;
  days_remaining: number;
  amount_due: string;
  lines: InvoiceLine[];
  summary: string;
};
export type CustomerPlanChangeResult = PlanChangeQuote & {
  invoice: Invoice | null;
  subscriptions: Subscription[];
};
