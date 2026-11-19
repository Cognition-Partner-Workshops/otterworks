{{ config(materialized='table', alias='spark__security_alert_anomaly') }}
with alerts as (
 select SECURITY_ALERT_ID as ALERT_ID, USER_ID, SCORE::double as SCORE
 from {{ source('spark_audit', 'SECURITY_ALERT') }}
), moments as (
 select count(*) as N, coalesce(sum(SCORE),0)::double as TOTAL,
        coalesce(sum(SCORE*SCORE),0)::double as SQUARES from alerts
), distribution as (
 select TOTAL/greatest(N,1) as MEAN,
        sqrt(greatest(SQUARES/greatest(N,1)-power(TOTAL/greatest(N,1),2),0)) as SD from moments
)
select a.ALERT_ID,a.USER_ID,a.SCORE,(a.SCORE-d.MEAN)/case when d.SD=0 then 1 else d.SD end as Z_SCORE
from alerts a cross join distribution d
