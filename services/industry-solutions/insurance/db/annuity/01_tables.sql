WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE TABLE annuity_policy (
    contract_no NUMBER(10) PRIMARY KEY,
    product_code VARCHAR2(16) NOT NULL,
    product_name VARCHAR2(80) NOT NULL,
    plan_code VARCHAR2(8) NOT NULL,
    qualification_code VARCHAR2(8) NOT NULL,
    status_code VARCHAR2(2) NOT NULL
        CHECK (status_code IN ('IF', 'PI', 'LP', 'SR', 'TM', 'DP')),
    issue_date DATE NOT NULL,
    effective_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    issue_state VARCHAR2(2) NOT NULL,
    owner_name VARCHAR2(100) NOT NULL,
    annuitant_name VARCHAR2(100) NOT NULL,
    currency_code VARCHAR2(3) NOT NULL,
    GRX_IND CHAR(1) NOT NULL CHECK (GRX_IND IN ('0', '1', '3'))
);

CREATE TABLE policy_values (
    contract_no NUMBER(10) PRIMARY KEY REFERENCES annuity_policy (contract_no),
    valuation_date DATE NOT NULL,
    account_value NUMBER(15,2) NOT NULL,
    surrender_value NUMBER(15,2) NOT NULL,
    cash_value NUMBER(15,2) NOT NULL,
    premiums_to_date NUMBER(15,2) NOT NULL,
    withdrawals_to_date NUMBER(15,2) NOT NULL,
    death_benefit NUMBER(15,2) NOT NULL,
    surrender_charge NUMBER(15,2) NOT NULL
);

CREATE TABLE fund_allocation (
    contract_no NUMBER(10) NOT NULL REFERENCES annuity_policy (contract_no),
    fund_code VARCHAR2(16) NOT NULL,
    fund_name VARCHAR2(80) NOT NULL,
    allocation_pct NUMBER(5,2) NOT NULL CHECK (allocation_pct > 0 AND allocation_pct <= 100),
    fund_units NUMBER(18,6) NOT NULL,
    unit_value NUMBER(15,6) NOT NULL,
    fund_value NUMBER(15,2) NOT NULL,
    PRIMARY KEY (contract_no, fund_code)
);

EXIT;
