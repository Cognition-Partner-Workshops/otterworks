CREATE SCHEMA idms_naive;

CREATE TABLE idms_naive.employee (
    empid VARCHAR(8) PRIMARY KEY,
    surname VARCHAR(20) NOT NULL,
    forename VARCHAR(15) NOT NULL,
    grade SMALLINT NOT NULL,
    cost_centre VARCHAR(6) NOT NULL,
    hire_date DATE,
    leave_date DATE,
    status CHAR(1) NOT NULL,
    monthly_contribution NUMERIC(7,2) NOT NULL,
    location CHAR(4) NOT NULL
);

CREATE TABLE idms_naive.vehicle (
    vehid VARCHAR(8) PRIMARY KEY,
    plate VARCHAR(8) NOT NULL,
    make VARCHAR(12) NOT NULL,
    model VARCHAR(16) NOT NULL,
    list_price NUMERIC(9,2) NOT NULL,
    co2 INTEGER NOT NULL,
    benefit_percent NUMERIC(4,2) NOT NULL,
    fuel CHAR(1) NOT NULL,
    registration_date DATE,
    owner_empid VARCHAR(8) REFERENCES idms_naive.employee(empid)
);

CREATE TABLE idms_naive.assignment (
    asgid VARCHAR(10) PRIMARY KEY,
    empid VARCHAR(8) NOT NULL REFERENCES idms_naive.employee(empid),
    vehicle_id VARCHAR(8) NOT NULL REFERENCES idms_naive.vehicle(vehid),
    start_date DATE NOT NULL,
    end_date DATE,
    reason CHAR(2) NOT NULL
);

CREATE UNIQUE INDEX one_open_assignment_per_employee
    ON idms_naive.assignment (empid)
    WHERE end_date IS NULL;

CREATE TABLE idms_naive.mileage_claim (
    clmid VARCHAR(10) PRIMARY KEY,
    empid VARCHAR(8) NOT NULL REFERENCES idms_naive.employee(empid),
    vehicle_id VARCHAR(8) NOT NULL REFERENCES idms_naive.vehicle(vehid),
    claim_date DATE NOT NULL,
    miles INTEGER NOT NULL,
    status CHAR(1) NOT NULL,
    purpose VARCHAR(10) NOT NULL
);

CREATE TABLE idms_naive.benefit_period (
    period INTEGER PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    mileage_rate NUMERIC(4,3) NOT NULL,
    status CHAR(1) NOT NULL,
    run_date DATE
);

CREATE SCHEMA global_merge;

CREATE TABLE global_merge.global_employee (
    employee_no VARCHAR(8) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    grade SMALLINT,
    cost_center VARCHAR(8),
    site VARCHAR(30),
    amount NUMERIC(12,2)
);
