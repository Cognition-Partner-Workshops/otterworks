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

export type RatingPeriod = {
  period_start: string;
  period_end: string;
};

export type RatingResult = {
  used_units: number;
  quota_units: number;
  rollover_units: number;
  billable_units: number;
  overage_amount: string;
};

export type UsageRating = RatingResult & RatingPeriod & {
  tenant_id: string;
  first_tier_units: number;
  second_tier_units: number;
};

export type UsageSummary = {
  kind: string;
  event_count: number;
  units: number;
};

export type FinalizedRating = RatingResult & {
  rating_result: RatingResult[];
};

function periodQuery(period: RatingPeriod): string {
  return new URLSearchParams(period).toString();
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
  rating: (tenantId: string, period: RatingPeriod) =>
    request<UsageRating>(
      `/api/tenants/${encodeURIComponent(tenantId)}/rating?${periodQuery(period)}`,
    ),
  usageSummary: (tenantId: string, period: RatingPeriod) =>
    request<UsageSummary[]>(
      `/api/tenants/${encodeURIComponent(tenantId)}/usage-summary?${periodQuery(period)}`,
    ),
  finalizeRating: (tenantId: string, period: RatingPeriod) =>
    request<FinalizedRating>(
      `/api/tenants/${encodeURIComponent(tenantId)}/rating/finalize`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(period),
      },
    ),
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
