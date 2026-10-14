-- Legacy datetime2 values carry microseconds; the seventh digit is zero unless the var keeps it.
{{ config(enabled=not var('pkg_audit_timestamp_full_precision', false)) }}
select audit_id, event_ts_utc
from {{ ref('stg_audit_events') }}
where mod(date_part(nanosecond, event_ts_utc), 1000) <> 0
