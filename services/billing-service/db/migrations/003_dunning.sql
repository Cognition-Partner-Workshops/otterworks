CREATE TABLE IF NOT EXISTS billing_svc.invoices (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    period_id uuid NOT NULL,
    issued_at timestamptz NOT NULL,
    subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0),
    tax numeric(12, 2) NOT NULL CHECK (tax >= 0),
    total numeric(12, 2) NOT NULL CHECK (total >= 0),
    status text NOT NULL CHECK (status IN ('draft', 'issued', 'paid', 'overdue'))
);

CREATE TABLE IF NOT EXISTS billing_svc.dunning_attempts (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    invoice_id uuid NOT NULL REFERENCES billing_svc.invoices(id),
    attempt_no integer NOT NULL CHECK (attempt_no > 0),
    scheduled_for date NOT NULL,
    status text NOT NULL CHECK (status IN ('scheduled', 'sent', 'skipped')),
    UNIQUE (invoice_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS billing_svc.notifications (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    kind text NOT NULL CHECK (kind IN ('invoice', 'dunning', 'suspension')),
    sent_at timestamptz NOT NULL,
    UNIQUE (tenant_id, kind, sent_at)
);
