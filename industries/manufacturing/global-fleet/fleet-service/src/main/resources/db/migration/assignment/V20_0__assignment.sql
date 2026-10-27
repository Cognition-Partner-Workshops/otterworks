ALTER TABLE vehicle
    ADD COLUMN make VARCHAR(64),
    ADD COLUMN model VARCHAR(64),
    ADD COLUMN co2_g_km INTEGER,
    ADD COLUMN fuel CHAR(1),
    ADD CONSTRAINT vehicle_list_price_positive CHECK (list_price IS NULL OR list_price > 0),
    ADD CONSTRAINT vehicle_co2_nonnegative CHECK (co2_g_km IS NULL OR co2_g_km >= 0),
    ADD CONSTRAINT vehicle_fuel_check CHECK (fuel IS NULL OR fuel IN ('D', 'P', 'H', 'E'));

ALTER TABLE assignment
    ADD COLUMN legacy_ref VARCHAR(10) UNIQUE,
    ADD CONSTRAINT assignment_legacy_ref_check
        CHECK (legacy_ref IS NULL OR legacy_ref ~ '^A[0-9]{9}$'),
    ADD CONSTRAINT assignment_reason_check CHECK (reason IS NULL OR reason IN ('NC', 'RP', 'PL'));

CREATE UNIQUE INDEX assignment_one_open_per_vehicle
    ON assignment (vehicle_id)
    WHERE end_date IS NULL;

ALTER TABLE car_request
    ADD COLUMN vehicle_id BIGINT REFERENCES vehicle(id),
    ADD COLUMN assignment_id BIGINT UNIQUE REFERENCES assignment(id),
    ADD COLUMN submission_key UUID UNIQUE,
    ADD CONSTRAINT car_request_status_check CHECK (status IN ('DELIVERED'));

CREATE TABLE car_request_draft (
    id UUID PRIMARY KEY,
    person_id BIGINT NOT NULL UNIQUE REFERENCES person(id),
    step VARCHAR(16) NOT NULL CHECK (step IN ('EMPLOYEE', 'VEHICLE', 'CONFIRM')),
    vehicle_choice VARCHAR(8) CHECK (vehicle_choice IN ('POOL', 'NEW')),
    pool_vehicle_id BIGINT,
    plate VARCHAR(64),
    make VARCHAR(64),
    model VARCHAR(64),
    list_price NUMERIC(12, 2),
    co2_g_km INTEGER,
    fuel CHAR(1),
    benefit_percent NUMERIC(5, 2),
    reason CHAR(2),
    start_date DATE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    version BIGINT NOT NULL
);

CREATE TABLE double_holder_confirmation (
    employment_legacy_ref VARCHAR(64) PRIMARY KEY,
    assignment_legacy_ref VARCHAR(10) NOT NULL,
    confirmed_return_date DATE NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL
);
