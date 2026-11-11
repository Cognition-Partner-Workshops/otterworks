CREATE TABLE payment_inbox (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE payment_ledger (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE payment_validation (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE screening_results (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE payment_status (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE payment_returns (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE account_registry (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE account_addresses (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE account_limits (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE account_closures (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE account_events (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE fee_assessments (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE fee_postings (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE fee_reversals (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE fee_summaries (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE statement_jobs (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE statement_items (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE document_registry (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE statement_deliveries (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE alert_dispatch (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE large_alert_dispatch (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE dispute_cases (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);

CREATE TABLE alert_preferences (
    flow text NOT NULL,
    request_id text NOT NULL,
    account_id text NOT NULL,
    amount numeric(18,2) NOT NULL,
    currency text NOT NULL,
    status text NOT NULL,
    PRIMARY KEY (flow, request_id)
);
