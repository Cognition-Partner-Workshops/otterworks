CREATE TABLE warehouse_batches (
    id           BIGSERIAL PRIMARY KEY,
    file_name    TEXT NOT NULL,
    status       TEXT NOT NULL,
    order_count  INTEGER NOT NULL,
    line_count   INTEGER NOT NULL,
    error        TEXT,
    payload      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX warehouse_batches_created ON warehouse_batches (created_at DESC);
