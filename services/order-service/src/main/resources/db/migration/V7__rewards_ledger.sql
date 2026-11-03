CREATE TABLE rewards_ledger (
    id           BIGSERIAL PRIMARY KEY,
    customer_id  UUID NOT NULL REFERENCES customers(id),
    order_id     UUID REFERENCES orders(id),
    kind         TEXT NOT NULL,
    points       INTEGER NOT NULL,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX rewards_ledger_customer ON rewards_ledger (customer_id, created_at DESC);
CREATE INDEX rewards_ledger_order ON rewards_ledger (order_id);

-- Backfill earn rows for orders placed before the ledger existed.
INSERT INTO rewards_ledger (customer_id, order_id, kind, points, note, created_at)
SELECT customer_id, id, 'EARN', total_cents / 100, 'backfill', created_at
FROM orders WHERE customer_id IS NOT NULL;
