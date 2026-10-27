ALTER TABLE benefit_period
    ADD COLUMN status VARCHAR(6) NOT NULL DEFAULT 'OPEN',
    ADD COLUMN closed_at TIMESTAMPTZ,
    ADD COLUMN record_count INTEGER,
    ADD COLUMN total_taxable NUMERIC(14, 2),
    ADD COLUMN total_mileage NUMERIC(14, 2),
    ADD CONSTRAINT benefit_period_status_check CHECK (status IN ('OPEN', 'CLOSED'));

ALTER TABLE employment
    ADD COLUMN commute_distance INTEGER NOT NULL DEFAULT 0,
    ADD CONSTRAINT employment_commute_distance_check CHECK (commute_distance >= 0);
