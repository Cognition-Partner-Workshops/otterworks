BEGIN
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_dunning_risk.ow_tp_scores (
    tenant_id STRING NOT NULL,
    subscription_id STRING NOT NULL,
    tenant_name STRING,
    tenant_status INT,
    subscription_status INT,
    snapshot_id STRING,
    captured_at STRING,
    as_of DATE,
    rule_version STRING,
    risk_scope STRING,
    paid_invoices BIGINT,
    overdue_invoices BIGINT,
    oldest_overdue_days INT,
    overdue_total DECIMAL(18,2),
    past_sent_attempts BIGINT,
    credit_note_count BIGINT,
    remaining_credit DECIMAL(18,2),
    suspension_eligible BOOLEAN,
    age_points INT,
    payment_points INT,
    dunning_points INT,
    exposure_points INT,
    risk_score INT,
    risk_band STRING
) USING DELTA;

INSERT OVERWRITE ow_tp.ow_tp_dunning_risk.ow_tp_scores
WITH snapshots AS (
    SELECT snapshot_id, from_json(payload, 'STRUCT<
        captured_at: STRING, as_of: DATE,
        tenants: ARRAY<STRUCT<id: STRING, name: STRING, status_cd: INT>>,
        subscriptions: ARRAY<STRUCT<id: STRING, tenant_id: STRING, status_cd: INT,
                                    starts_on: DATE, ends_on: DATE>>,
        invoices: ARRAY<STRUCT<id: STRING, tenant_id: STRING, issued_at: TIMESTAMP_NTZ,
                               total: DECIMAL(18,2), status_cd: INT>>,
        dunning_attempts: ARRAY<STRUCT<id: STRING, tenant_id: STRING, invoice_id: STRING,
                                       attempt_no: INT, scheduled_for: DATE, status_cd: INT>>,
        credit_notes: ARRAY<STRUCT<id: STRING, tenant_id: STRING, issued_on: DATE,
                                   amount: DECIMAL(18,2), remaining_amount: DECIMAL(18,2)>>
    >') AS doc
    FROM ow_tp.ow_tp_dunning_risk.ow_tp_snapshots
), latest AS (
    SELECT * FROM snapshots
    QUALIFY row_number() OVER (ORDER BY doc.captured_at DESC, snapshot_id DESC) = 1
), tenants AS (
    SELECT snapshot_id, doc.captured_at, doc.as_of, inline(doc.tenants) FROM latest
), subscriptions AS (
    SELECT inline(doc.subscriptions) FROM latest
), invoices AS (
    SELECT doc.as_of, inline(doc.invoices) FROM latest
), invoice_features AS (
    SELECT tenant_id,
        count_if(status_cd = 30) AS paid_invoices,
        count_if(status_cd = 40 AND to_date(issued_at) < as_of) AS overdue_invoices,
        coalesce(max(CASE WHEN status_cd = 40 AND to_date(issued_at) < as_of
                          THEN datediff(as_of, to_date(issued_at)) END), 0) AS oldest_overdue_days,
        sum(CASE WHEN status_cd = 40 AND to_date(issued_at) < as_of
                 THEN greatest(total, 0) ELSE 0 END) AS overdue_total
    FROM invoices WHERE to_date(issued_at) <= as_of GROUP BY tenant_id
), attempts AS (
    SELECT doc.as_of, inline(doc.dunning_attempts) FROM latest
), dunning_features AS (
    SELECT d.tenant_id, count(*) AS past_sent_attempts
    FROM attempts d JOIN invoices i ON i.id = d.invoice_id AND i.tenant_id = d.tenant_id
    WHERE d.status_cd = 20 AND d.scheduled_for <= d.as_of AND to_date(i.issued_at) <= d.as_of
    GROUP BY d.tenant_id
), credits AS (
    SELECT doc.as_of, inline(doc.credit_notes) FROM latest
), credit_features AS (
    SELECT tenant_id, count(*) AS credit_note_count,
           sum(greatest(remaining_amount, 0)) AS remaining_credit
    FROM credits WHERE issued_on <= as_of GROUP BY tenant_id
), features AS (
    SELECT t.id AS tenant_id, coalesce(s.id, 'NO_SUBSCRIPTION') AS subscription_id,
        t.name AS tenant_name, t.status_cd AS tenant_status, s.status_cd AS subscription_status,
        t.snapshot_id, t.captured_at, t.as_of,
        'ow_tp_dunning_v1' AS rule_version, 'tenant' AS risk_scope,
        coalesce(i.paid_invoices, 0) AS paid_invoices,
        coalesce(i.overdue_invoices, 0) AS overdue_invoices,
        coalesce(i.oldest_overdue_days, 0) AS oldest_overdue_days,
        cast(coalesce(i.overdue_total, 0) AS DECIMAL(18,2)) AS overdue_total,
        coalesce(d.past_sent_attempts, 0) AS past_sent_attempts,
        coalesce(c.credit_note_count, 0) AS credit_note_count,
        cast(coalesce(c.remaining_credit, 0) AS DECIMAL(18,2)) AS remaining_credit,
        t.status_cd = 10 AND coalesce(i.oldest_overdue_days, 0) >= 14 AS suspension_eligible
    FROM tenants t LEFT JOIN subscriptions s ON s.tenant_id = t.id AND s.starts_on <= t.as_of
    LEFT JOIN invoice_features i ON i.tenant_id = t.id
    LEFT JOIN dunning_features d ON d.tenant_id = t.id
    LEFT JOIN credit_features c ON c.tenant_id = t.id
), components AS (
    SELECT *,
        CASE WHEN oldest_overdue_days >= 14 THEN 40
             WHEN oldest_overdue_days >= 7 THEN 25
             WHEN oldest_overdue_days >= 1 THEN 10 ELSE 0 END AS age_points,
        cast(round(25.0 * overdue_invoices / greatest(paid_invoices + overdue_invoices, 1)) AS INT)
            AS payment_points,
        cast(least(past_sent_attempts, 4) * 5 AS INT) AS dunning_points,
        CASE WHEN overdue_total > 0 THEN cast(round(15.0 * greatest(overdue_total - remaining_credit, 0)
                                                    / overdue_total) AS INT)
             ELSE 0 END AS exposure_points
    FROM features
), scored AS (
    SELECT *, age_points + payment_points + dunning_points + exposure_points AS risk_score
    FROM components
)
SELECT *, CASE WHEN paid_invoices + overdue_invoices + past_sent_attempts = 0 THEN 'insufficient_history'
               WHEN risk_score >= 70 THEN 'high'
               WHEN risk_score >= 35 THEN 'medium' ELSE 'low' END AS risk_band
FROM scored;
END;
