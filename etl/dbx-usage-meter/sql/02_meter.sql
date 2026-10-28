-- Recompute the meter from the snapshot tables. Mirrors pkg_rating.compute_rating:
--   periods      every finalized rating_period, plus, for usage outside them, the part of
--                its calendar month between finalized periods (never overlapping one)
--   subscription the latest-starting one overlapping the period
--   used         units of events whose occurred_at day is in [period_start, period_end]
--   rollover     finalized rollover_units of periods starting in the 3 months before,
--                capped at 2 x included_units
--   billable     max(used - rollover - included, 0); tiers split at 101 units, the
--                second at 1.5 x overage_rate; pro-rated by remaining days when the
--                subscription is suspended (status 20) inside the period
INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_usage_meter
WITH -- ps/pe are the day window for events; ps_ts/pe_ts keep the period's original
-- timestamps for the subscription, rollover and suspension comparisons, which
-- compute_rating makes on full DATE values (an Oracle DATE can carry a time).
-- sp_finalize_rating keys a period by tenant || YYYY-MM-DD (pkg_ow_util.f_md5_uuid), so the
-- meter keeps one period per tenant and start day: the latest-starting one, like the
-- subscription rule.
rp AS (
    SELECT tenant_id, ps_ts, pe_ts, ps, pe
      FROM (SELECT tenant_id, period_start AS ps_ts, period_end AS pe_ts,
                   CAST(period_start AS DATE) AS ps, CAST(period_end AS DATE) AS pe,
                   row_number() OVER (PARTITION BY tenant_id, CAST(period_start AS DATE)
                                      ORDER BY period_start DESC) AS rn
              FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods)
     WHERE rn = 1
),
uncovered AS (
    SELECT DISTINCT u.tenant_id, CAST(u.occurred_at AS DATE) AS d
      FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events u
     WHERE NOT EXISTS (
           SELECT 1 FROM rp
            WHERE rp.tenant_id = u.tenant_id AND CAST(u.occurred_at AS DATE) BETWEEN rp.ps AND rp.pe)
),
-- the part of the event's calendar month that lies between finalized periods
gaps AS (
    SELECT x.tenant_id,
           coalesce(max(CASE WHEN rp.pe < x.d AND rp.pe >= trunc(x.d, 'MM') THEN date_add(rp.pe, 1) END),
                    trunc(x.d, 'MM')) AS period_start,
           coalesce(min(CASE WHEN rp.ps > x.d AND rp.ps <= last_day(x.d) THEN date_sub(rp.ps, 1) END),
                    last_day(x.d)) AS period_end
      FROM uncovered x LEFT JOIN rp ON rp.tenant_id = x.tenant_id
     GROUP BY x.tenant_id, x.d
),
periods AS (
    SELECT tenant_id, ps AS period_start, pe AS period_end, ps_ts, pe_ts FROM rp
    UNION
    SELECT tenant_id, period_start, period_end,
           CAST(period_start AS TIMESTAMP_NTZ), CAST(period_end AS TIMESTAMP_NTZ) FROM gaps
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
       AND rp.period_start < p.ps_ts
       AND rp.period_start >= add_months(p.ps_ts, -3)
      LEFT JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_results rr ON rr.period_id = rp.id
     GROUP BY p.tenant_id, p.period_start
),
sub AS (
    SELECT p.tenant_id, p.period_start, s.id AS subscription_id, s.plan_id, s.status_cd,
           s.suspended_on,
           row_number() OVER (PARTITION BY p.tenant_id, p.period_start
                              ORDER BY s.starts_on DESC) AS rn
      FROM periods p
      JOIN ow_tp.ow_tp_usage_meter.ow_tp_snap_subscriptions s
        ON s.tenant_id = p.tenant_id
       AND s.starts_on <= p.pe_ts
       AND (s.ends_on IS NULL OR s.ends_on >= p.ps_ts)
),
base AS (
    SELECT p.tenant_id, p.period_start, p.period_end, p.ps_ts, p.pe_ts, s.subscription_id, s.plan_id,
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
           -- (period_end - suspended_on + 1) / (period_end - period_start + 1) in days,
           -- fractional like Oracle DATE arithmetic: calendar days plus the wall-clock
           -- time-of-day difference, so no session-timezone or DST shift enters
           CASE WHEN status_cd = 20 AND suspended_on BETWEEN ps_ts AND pe_ts
                THEN (CAST(datediff(CAST(pe_ts AS DATE), CAST(suspended_on AS DATE)) AS DECIMAL(38,18))
                      + (hour(pe_ts) * 3600 + minute(pe_ts) * 60 + second(pe_ts)
                         - hour(suspended_on) * 3600 - minute(suspended_on) * 60 - second(suspended_on)) / 86400 + 1)
                     / (datediff(CAST(pe_ts AS DATE), CAST(ps_ts AS DATE))
                        + (hour(pe_ts) * 3600 + minute(pe_ts) * 60 + second(pe_ts)
                           - hour(ps_ts) * 3600 - minute(ps_ts) * 60 - second(ps_ts)) / 86400 + 1)
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
