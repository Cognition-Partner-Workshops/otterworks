-- Fleet portal schema (Java country). Applied before 002_seed.sql.
DROP TABLE IF EXISTS mileage_claim, car_return, car_request, assignment, vehicle, employee, fleet_rule CASCADE;

CREATE TABLE fleet_rule (
    country       CHAR(2)       PRIMARY KEY,
    min_grade     SMALLINT      NOT NULL,
    benefit_pct   NUMERIC(5,2)  NOT NULL,
    commute_pct   NUMERIC(5,3)  NOT NULL,
    mileage_rate  NUMERIC(6,3)  NOT NULL,
    currency      CHAR(3)       NOT NULL
);

CREATE TABLE employee (
    id            BIGSERIAL     PRIMARY KEY,
    employee_no   VARCHAR(8)    NOT NULL UNIQUE,
    first_name    VARCHAR(40)   NOT NULL,
    last_name     VARCHAR(40)   NOT NULL,
    grade         SMALLINT      NOT NULL,
    cost_center   VARCHAR(8)    NOT NULL,
    site          VARCHAR(30)   NOT NULL,
    commute_km    INTEGER       NOT NULL DEFAULT 0,
    hire_date     DATE          NOT NULL,
    leave_date    DATE,
    status        CHAR(1)       NOT NULL
);

CREATE TABLE vehicle (
    id                 BIGSERIAL     PRIMARY KEY,
    plate              VARCHAR(12)   NOT NULL UNIQUE,
    make               VARCHAR(30)   NOT NULL,
    model              VARCHAR(40)   NOT NULL,
    list_price         NUMERIC(10,2) NOT NULL,
    co2_g_km           INTEGER       NOT NULL,
    fuel               CHAR(1)       NOT NULL,
    registered_on      DATE          NOT NULL,
    owner_employee_id  BIGINT        REFERENCES employee(id)
);

CREATE TABLE assignment (
    id            BIGSERIAL  PRIMARY KEY,
    employee_id   BIGINT     NOT NULL REFERENCES employee(id),
    vehicle_id    BIGINT     NOT NULL REFERENCES vehicle(id),
    start_date    DATE       NOT NULL,
    end_date      DATE
);

CREATE TABLE car_request (
    id            BIGSERIAL    PRIMARY KEY,
    employee_id   BIGINT       NOT NULL REFERENCES employee(id),
    vehicle_id    BIGINT       REFERENCES vehicle(id),
    requested_on  DATE         NOT NULL,
    status        VARCHAR(12)  NOT NULL
);

CREATE TABLE car_return (
    id              BIGSERIAL     PRIMARY KEY,
    assignment_id   BIGINT        NOT NULL REFERENCES assignment(id),
    return_date     DATE          NOT NULL,
    odometer_km     INTEGER       NOT NULL,
    condition_note  VARCHAR(200)
);

CREATE TABLE mileage_claim (
    id            BIGSERIAL     PRIMARY KEY,
    employee_id   BIGINT        NOT NULL REFERENCES employee(id),
    claim_date    DATE          NOT NULL,
    km            INTEGER       NOT NULL,
    purpose       VARCHAR(60)   NOT NULL,
    amount        NUMERIC(10,2) NOT NULL,
    status        VARCHAR(10)   NOT NULL
);

CREATE INDEX assignment_employee_idx ON assignment (employee_id);
CREATE INDEX mileage_claim_employee_idx ON mileage_claim (employee_id, claim_date);
