ALTER TABLE mileage_claim
    ADD COLUMN vehicle_id BIGINT REFERENCES vehicle(id),
    ADD COLUMN rate NUMERIC(6, 3),
    ADD COLUMN amount NUMERIC(10, 2),
    ADD COLUMN paid_period CHAR(6),
    ADD COLUMN purpose VARCHAR(255),
    ADD COLUMN submitted_at TIMESTAMPTZ,
    ADD COLUMN decided_at TIMESTAMPTZ;

UPDATE mileage_claim
SET status = CASE UPPER(TRIM(status))
    WHEN 'A' THEN 'APPROVED'
    WHEN 'APPROVED' THEN 'APPROVED'
    WHEN 'P' THEN 'PENDING'
    WHEN 'SUBMITTED' THEN 'PENDING'
    WHEN 'R' THEN 'REJECTED'
    WHEN 'REJECTED' THEN 'REJECTED'
    ELSE status
END;

UPDATE mileage_claim
SET paid_period = to_char(claim_date, 'YYYYMM')
WHERE paid_period IS NULL;

ALTER TABLE mileage_claim
    ALTER COLUMN paid_period SET NOT NULL,
    ADD CONSTRAINT mileage_claim_status_check
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    ADD CONSTRAINT mileage_claim_distance_check
        CHECK (distance > 0),
    ADD CONSTRAINT mileage_claim_paid_period_check
        CHECK (paid_period ~ '^[0-9]{6}$');

CREATE INDEX mileage_claim_employment_date_idx ON mileage_claim (employment_id, claim_date);
CREATE INDEX mileage_claim_status_idx ON mileage_claim (status);
