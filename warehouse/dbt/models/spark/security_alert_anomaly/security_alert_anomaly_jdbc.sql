{{ config(materialized='table', schema='COMPAT', alias='SPARK_ALERT_ANOMALY') }}
select * from {{ ref('security_alert_anomaly') }}
