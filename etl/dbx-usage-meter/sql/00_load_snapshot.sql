-- Load the CSV snapshot written by `meter.py snapshot` (SELECT-only reads of Lakebase
-- mig-invoicing-w1 / ow_tp_invoicing) and uploaded to the ow_tp_snap_files volume.
-- Column types match the Postgres source.
BEGIN
    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_plans
    SELECT id, code, included_units, overage_rate
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/plans/',
                      format => 'csv', header => true,
                      schema => 'id STRING, code STRING, included_units BIGINT, overage_rate DECIMAL(12,6)');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_tenants
    SELECT id, name
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/tenants/',
                      format => 'csv', header => true,
                      schema => 'id STRING, name STRING');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_subscriptions
    SELECT id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/subscriptions/',
                      format => 'csv', header => true,
                      timestampNTZFormat => 'yyyy-MM-dd HH:mm:ss[.SSSSSS]',
                      schema => 'id STRING, tenant_id STRING, plan_id STRING, starts_on TIMESTAMP_NTZ, ends_on TIMESTAMP_NTZ, status_cd BIGINT, suspended_on TIMESTAMP_NTZ');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events
    SELECT id, tenant_id, occurred_at, units, kind_cd
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/usage_events/',
                      format => 'csv', header => true,
                      timestampNTZFormat => 'yyyy-MM-dd HH:mm:ss[.SSSSSS]',
                      schema => 'id STRING, tenant_id STRING, occurred_at TIMESTAMP_NTZ, units BIGINT, kind_cd BIGINT');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods
    SELECT id, tenant_id, period_start, period_end
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/rating_periods/',
                      format => 'csv', header => true,
                      timestampNTZFormat => 'yyyy-MM-dd HH:mm:ss[.SSSSSS]',
                      schema => 'id STRING, tenant_id STRING, period_start TIMESTAMP_NTZ, period_end TIMESTAMP_NTZ');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_results
    SELECT id, period_id, rollover_units
      FROM read_files('/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/rating_results/',
                      format => 'csv', header => true,
                      schema => 'id STRING, period_id STRING, rollover_units BIGINT');

    INSERT OVERWRITE ow_tp.ow_tp_usage_meter.ow_tp_snap_log
              SELECT current_timestamp(), 'mig-invoicing-w1', 'plans', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_plans
    UNION ALL SELECT current_timestamp(), 'mig-invoicing-w1', 'tenants', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_tenants
    UNION ALL SELECT current_timestamp(), 'mig-invoicing-w1', 'subscriptions', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_subscriptions
    UNION ALL SELECT current_timestamp(), 'mig-invoicing-w1', 'usage_events', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events
    UNION ALL SELECT current_timestamp(), 'mig-invoicing-w1', 'rating_periods', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods
    UNION ALL SELECT current_timestamp(), 'mig-invoicing-w1', 'rating_results', count(*) FROM ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_results;
END;
