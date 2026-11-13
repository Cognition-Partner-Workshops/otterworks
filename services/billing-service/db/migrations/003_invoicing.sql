CREATE TABLE IF NOT EXISTS billing_svc.invoices (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    period_id uuid NOT NULL REFERENCES billing_svc.rating_periods(id),
    issued_at timestamptz NOT NULL,
    subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0),
    tax numeric(12, 2) NOT NULL CHECK (tax >= 0),
    total numeric(12, 2) NOT NULL CHECK (total >= 0),
    status text NOT NULL CHECK (status IN ('draft', 'issued', 'paid', 'overdue'))
);

CREATE TABLE IF NOT EXISTS billing_svc.invoice_lines (
    id uuid PRIMARY KEY,
    invoice_id uuid NOT NULL REFERENCES billing_svc.invoices(id) ON DELETE CASCADE,
    line_no integer NOT NULL CHECK (line_no > 0),
    line_type text NOT NULL CHECK (line_type IN ('plan', 'usage', 'tax', 'credit')),
    description text NOT NULL,
    amount numeric(12, 2) NOT NULL,
    UNIQUE (invoice_id, line_no)
);

CREATE TABLE IF NOT EXISTS billing_svc.credit_notes (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    issued_on date NOT NULL,
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    remaining_amount numeric(12, 2) NOT NULL CHECK (remaining_amount >= 0),
    CHECK (remaining_amount <= amount)
);
