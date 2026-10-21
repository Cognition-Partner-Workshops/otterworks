-- Dedicated SQL pool DDL for the policy and claims warehouse.
CREATE TABLE dw.dim_region (
    region_code   VARCHAR(4)  NOT NULL,
    region_name   VARCHAR(40) NOT NULL
) WITH (DISTRIBUTION = REPLICATE, CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.dim_producer (
    producer_code VARCHAR(10) NOT NULL,
    producer_name VARCHAR(80) NOT NULL,
    agency_name   VARCHAR(80) NOT NULL,
    region_code   VARCHAR(4)  NOT NULL
) WITH (DISTRIBUTION = REPLICATE, CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.producer_tier (
    producer_code       VARCHAR(10) NOT NULL,
    tier_name           VARCHAR(20) NOT NULL,
    tier_effective_date DATE        NULL
) WITH (DISTRIBUTION = REPLICATE, HEAP);
GO
CREATE TABLE dw.dim_policy (
    policy_number   VARCHAR(12) NOT NULL,
    holder_first    VARCHAR(40) NOT NULL,
    holder_middle   VARCHAR(40) NULL,
    holder_last     VARCHAR(40) NOT NULL,
    product_code    VARCHAR(8)  NOT NULL,
    region_code     VARCHAR(4)  NOT NULL,
    primary_phone   VARCHAR(20) NULL,
    alt_phone_label VARCHAR(10) NULL,
    alt_phone       VARCHAR(40) NULL
) WITH (DISTRIBUTION = HASH(policy_number), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.ClaimStatusRef (
    status_code VARCHAR(4)  NOT NULL,
    status_desc VARCHAR(40) NOT NULL
) WITH (DISTRIBUTION = REPLICATE, HEAP);
GO
CREATE TABLE stg.producer_feed (
    feed_id         INT           NOT NULL,
    producer_code   VARCHAR(10)   NOT NULL,
    region_code     VARCHAR(4)    NOT NULL,
    policy_count    INT           NOT NULL,
    claim_count     INT           NOT NULL,
    written_premium DECIMAL(12,2) NOT NULL,
    feed_date       DATE          NOT NULL
) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);
GO
CREATE TABLE stg.premium_feed (
    policy_number  CHAR(12)      NOT NULL,
    premium_amount DECIMAL(12,2) NOT NULL,
    effective_date DATE          NOT NULL
) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);
GO
CREATE TABLE stg.claim_feed (
    claim_id      INT           NOT NULL,
    policy_number VARCHAR(12)   NOT NULL,
    status_code   VARCHAR(4)    NOT NULL,
    reopen_date   VARCHAR(10)   NOT NULL,
    claim_amount  DECIMAL(12,2) NOT NULL,
    loss_date     DATE          NOT NULL
) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);
GO
CREATE TABLE audit.claim_event (
    event_id   INT         NOT NULL,
    claim_id   INT         NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    event_at   DATETIME2(3) NOT NULL
) WITH (DISTRIBUTION = HASH(claim_id), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE audit.policy_event (
    event_id      INT         NOT NULL,
    policy_number VARCHAR(12) NOT NULL,
    event_type    VARCHAR(20) NOT NULL,
    event_at      DATETIME2(3) NOT NULL
) WITH (DISTRIBUTION = HASH(policy_number), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.producer_scorecard (
    scorecard_date  DATE          NOT NULL,
    region_code     VARCHAR(4)    NOT NULL,
    producer_code   VARCHAR(10)   NOT NULL,
    producer_name   VARCHAR(80)   NULL,
    agency_name     VARCHAR(80)   NULL,
    tier_name       VARCHAR(20)   NULL,
    policy_count    INT           NULL,
    claim_count     INT           NULL,
    written_premium DECIMAL(14,2) NULL,
    row_status      VARCHAR(10)   NOT NULL
) WITH (DISTRIBUTION = HASH(producer_code), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.claim_fact (
    claim_id      INT           NOT NULL,
    policy_number VARCHAR(12)   NOT NULL,
    status_code   VARCHAR(4)    NOT NULL,
    status_desc   VARCHAR(40)   NULL,
    reopen_date   DATE          NULL,
    claim_amount  DECIMAL(12,2) NOT NULL,
    loss_date     DATE          NOT NULL
) WITH (DISTRIBUTION = HASH(claim_id), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.premium_fact (
    policy_number  VARCHAR(12)   NOT NULL,
    product_code   VARCHAR(8)    NOT NULL,
    region_code    VARCHAR(4)    NOT NULL,
    premium_amount DECIMAL(12,2) NOT NULL,
    effective_date DATE          NOT NULL
) WITH (DISTRIBUTION = HASH(policy_number), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.claim_summary (
    policy_number      VARCHAR(12)   NOT NULL,
    product_code       VARCHAR(8)    NOT NULL,
    claim_count        INT           NOT NULL,
    total_claim_amount DECIMAL(14,2) NOT NULL,
    last_loss_date     DATE          NOT NULL
) WITH (DISTRIBUTION = HASH(policy_number), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.policy_contact (
    policy_number       VARCHAR(12)  NOT NULL,
    holder_display_name VARCHAR(120) NULL,
    contact_label       VARCHAR(40)  NULL,
    primary_phone       VARCHAR(20)  NULL
) WITH (DISTRIBUTION = HASH(policy_number), CLUSTERED COLUMNSTORE INDEX);
GO
CREATE TABLE dw.etl_log (
    proc_name     VARCHAR(60) NOT NULL,
    step          VARCHAR(40) NOT NULL,
    rows_affected INT         NULL,
    logged_at     DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);
GO
