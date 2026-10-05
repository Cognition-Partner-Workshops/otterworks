-- rating
CREATE TABLE IF NOT EXISTS billing_svc.usage_events (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    occurred_at timestamptz NOT NULL,
    units integer NOT NULL CHECK (units > 0),
    kind text NOT NULL CHECK (kind IN ('api', 'storage', 'compute'))
);

CREATE TABLE IF NOT EXISTS billing_svc.rating_periods (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    period_start date NOT NULL,
    period_end date NOT NULL,
    UNIQUE (tenant_id, period_start),
    CHECK (period_end >= period_start)
);

CREATE TABLE IF NOT EXISTS billing_svc.rating_results (
    id uuid PRIMARY KEY,
    period_id uuid NOT NULL REFERENCES billing_svc.rating_periods(id),
    subscription_id uuid NOT NULL REFERENCES billing_svc.subscriptions(id),
    used_units integer NOT NULL CHECK (used_units >= 0),
    quota_units integer NOT NULL CHECK (quota_units >= 0),
    rollover_units integer NOT NULL CHECK (rollover_units >= 0),
    billable_units integer NOT NULL CHECK (billable_units >= 0),
    overage_amount numeric(12, 2) NOT NULL CHECK (overage_amount >= 0),
    created_at timestamptz NOT NULL
);
