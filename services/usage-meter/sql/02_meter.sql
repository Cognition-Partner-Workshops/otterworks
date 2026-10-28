-- Recompute the meter from the snapshot tables. Mirrors pkg_rating.compute_rating:
--   periods      every finalized rating_period, plus each calendar month with usage
--                not covered by one
--   subscription the latest-starting one overlapping the period
--   used         units of events whose occurred_at day is in [period_start, period_end]
--   rollover     finalized rollover_units of periods starting in the 3 months before,
--                capped at 2 x included_units
--   billable     max(used - rollover - included, 0); tiers split at 101 units, the
--                second at 1.5 x overage_rate; pro-rated by remaining days when the
--                subscription is suspended (status 20) inside the period
INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_usage_meter
WITH periods AS (
    SELECT tenant_id, CAST(period_start AS DATE) AS period_start,
           CAST(period_end AS DATE) AS period_end
      FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods
    UNION
    SELECT u.tenant_id, CAST(date_trunc('MONTH', u.occurred_at) AS DATE),
           last_day(CAST(u.occurred_at AS DATE))
      FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events u
     WHERE NOT EXISTS (
           SELECT 1 FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods rp
            WHERE rp.tenant_id = u.tenant_id
              AND CAST(u.occurred_at AS DATE)
                  BETWEEN CAST(rp.period_start AS DATE) AND CAST(rp.period_end AS DATE))
),
used AS (
    SELECT p.tenant_id, p.period_start, count(u.id) AS event_count,
           coalesce(sum(u.units), 0) AS used
      FROM periods p
      LEFT JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events u
        ON u.tenant_id = p.tenant_id
       AND CAST(u.occurred_at AS DATE) BETWEEN p.period_start AND p.period_end
     GROUP BY p.tenant_id, p.period_start
),
banked AS (
    SELECT p.tenant_id, p.period_start, coalesce(sum(rr.rollover_units), 0) AS prior
      FROM periods p
      LEFT JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods rp
        ON rp.tenant_id = p.tenant_id
       AND rp.period_start < CAST(p.period_start AS TIMESTAMP_NTZ)
       AND rp.period_start >= CAST(add_months(p.period_start, -3) AS TIMESTAMP_NTZ)
      LEFT JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_results rr ON rr.period_id = rp.id
     GROUP BY p.tenant_id, p.period_start
),
sub AS (
    SELECT p.tenant_id, p.period_start, s.id AS subscription_id, s.plan_id, s.status_cd,
           CAST(s.suspended_on AS DATE) AS suspended_on,
           row_number() OVER (PARTITION BY p.tenant_id, p.period_start
                              ORDER BY s.starts_on DESC) AS rn
      FROM periods p
      JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_subscriptions s
        ON s.tenant_id = p.tenant_id
       AND s.starts_on <= CAST(p.period_end AS TIMESTAMP_NTZ)
       AND (s.ends_on IS NULL OR s.ends_on >= CAST(p.period_start AS TIMESTAMP_NTZ))
),
base AS (
    SELECT p.tenant_id, p.period_start, p.period_end, s.subscription_id, s.plan_id,
           s.status_cd, s.suspended_on, pl.code AS plan_code,
           pl.included_units AS included, pl.overage_rate AS rate,
           u.event_count, u.used, b.prior
      FROM periods p
      JOIN used u ON u.tenant_id = p.tenant_id AND u.period_start = p.period_start
      JOIN banked b ON b.tenant_id = p.tenant_id AND b.period_start = p.period_start
      LEFT JOIN sub s ON s.tenant_id = p.tenant_id AND s.period_start = p.period_start AND s.rn = 1
      LEFT JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_plans pl ON pl.id = s.plan_id
),
rated AS (
    SELECT *, least(prior, coalesce(2 * included, prior)) AS rollover FROM base
),
billed AS (
    SELECT *, greatest(coalesce(used - rollover - included, 0), 0) AS billable_raw FROM rated
),
tiered AS (
    SELECT *,
           least(billable_raw, 101) AS first_tier,
           greatest(billable_raw - 101, 0) AS second_tier,
           round(least(billable_raw, 101) * rate
                 + greatest(billable_raw - 101, 0) * rate * 1.5, 2) AS overage_raw,
           CASE WHEN status_cd = 20 AND suspended_on BETWEEN period_start AND period_end
                THEN CAST(datediff(period_end, suspended_on) + 1 AS DECIMAL(38,18))
                     / (datediff(period_end, period_start) + 1)
           END AS factor
      FROM billed
)
SELECT tenant_id, period_start, period_end, subscription_id, plan_id, plan_code,
       event_count, used, included, rollover,
       CAST(CASE WHEN factor IS NULL THEN billable_raw ELSE round(billable_raw * factor) END AS BIGINT),
       first_tier, second_tier,
       CAST(CASE WHEN factor IS NULL THEN overage_raw ELSE round(overage_raw * factor, 2) END AS DECIMAL(12,2)),
       (SELECT max(snapshot_at) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_log)
  FROM tiered;
