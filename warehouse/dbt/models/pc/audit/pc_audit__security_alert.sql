{{ config(materialized='incremental', incremental_strategy='merge', unique_key='ALERT_ID', full_refresh=false) }}

{{ pc_audit_security_alert(source('unt5_pc_src', 'SECURITY_ALERT')) }}
