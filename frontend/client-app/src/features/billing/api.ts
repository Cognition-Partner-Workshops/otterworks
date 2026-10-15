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

export type UsageRating = {
  tenant_id: string;
  period_start: string;
  period_end: string;
  used_units: number;
  quota_units: number;
  rollover_units: number;
  billable_units: number;
  first_tier_units: number;
  second_tier_units: number;
  overage_amount: string;
};

export type UsageSummaryRow = {
  kind: string;
  event_count: number;
  units: number;
};

export type RatingResult = {
  used_units: number;
  quota_units: number;
  rollover_units: number;
  billable_units: number;
  overage_amount: string;
};

export type RatingFinalization = RatingResult & {
  rating_result: RatingResult[];
};

function periodQuery(periodStart: string, periodEnd: string) {
  return `period_start=${encodeURIComponent(periodStart)}&period_end=${encodeURIComponent(periodEnd)}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BILLING_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new BillingApiError(
      `Billing service returned ${response.status}`,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export const billingApi = {
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
  usageRating: (tenantId: string, periodStart: string, periodEnd: string) =>
    request<UsageRating>(
      `/api/tenants/${encodeURIComponent(tenantId)}/usage-rating?${periodQuery(periodStart, periodEnd)}`
    ),
  usageSummary: (tenantId: string, periodStart: string, periodEnd: string) =>
    request<UsageSummaryRow[]>(
      `/api/tenants/${encodeURIComponent(tenantId)}/usage-summary?${periodQuery(periodStart, periodEnd)}`
    ),
  finalizeRating: (tenantId: string, periodStart: string, periodEnd: string) =>
    request<RatingFinalization>(
      `/api/tenants/${encodeURIComponent(tenantId)}/rating-finalizations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period_start: periodStart, period_end: periodEnd }),
      }
    ),
};
