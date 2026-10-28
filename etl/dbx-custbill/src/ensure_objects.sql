-- ow_tp_custbill_feed / ensure_objects
-- Idempotent DDL for the CUSTBILL feed staging unit. Creates only objects
-- inside the isolated ow_tp.ow_tp_custbill namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_custbill;

CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_custbill.custbill_drop;

-- Staging feed: one row per CBCUST01 65-char detail record, keyed by the
-- invoice_id the extract join carried (lineage back to
-- ow_billing.invoice_header). raw_line keeps the serialized record verbatim;
-- record_tag marks the row class ('DET'); HDR/TRL wrapper rows are dropped
-- at landing, per the unit spec latitude.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_custbill.custbill_feed (
    invoice_id STRING NOT NULL,
    cust_no STRING NOT NULL,
    cust_name STRING,
    period_end DATE,
    total_amt DECIMAL(14, 2),
    currency STRING,
    record_type STRING,
    record_tag STRING NOT NULL,
    raw_line STRING NOT NULL,
    source_file STRING,
    batch_no BIGINT,
    landed_at TIMESTAMP,
    CONSTRAINT custbill_feed_pk PRIMARY KEY (invoice_id)
)
USING DELTA;
