{{ config(materialized='table', alias='SECURITY_ALERT_ANOMALY') }}

with scores as (
    select security_alert_id as alert_id, user_id, score::double as score
    from {{ source('spark_audit', 'SECURITY_ALERT') }}
), moments as (
    select
        sum(score) / greatest(count(*), 1) as mean_score,
        sum(score * score) / greatest(count(*), 1) as mean_square
    from scores
), distribution as (
    select
        mean_score,
        coalesce(nullif(sqrt(greatest(mean_square - mean_score * mean_score, 0.0)), 0.0), 1.0) as stddev
    from moments
)
select alert_id, user_id, score, (score - mean_score) / stddev as z_score
from scores cross join distribution
