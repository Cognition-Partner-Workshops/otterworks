CREATE TABLE IF NOT EXISTS billing_svc.invoices (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES billing_svc.tenants(id),
    issued_on date NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL CHECK (period_end >= period_start),
    total numeric(12,2) NOT NULL,
    summary text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS billing_svc.invoice_lines (
    invoice_id uuid NOT NULL REFERENCES billing_svc.invoices(id),
    line_no integer NOT NULL,
    description text NOT NULL,
    amount numeric(12,2) NOT NULL,
    PRIMARY KEY (invoice_id, line_no)
);
