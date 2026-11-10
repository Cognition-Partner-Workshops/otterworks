{{ config(materialized='incremental', incremental_strategy='merge', unique_key='ALERT_ID', full_refresh=false,
          schema='PC_AUDIT_UNT5_FIXTURE', enabled=env_var('SFX_UNT5_SECURITY_FIXTURE','0') == '1') }}

{{ pc_audit_security_alert(source('unt5_fixture', 'DUP_WITHIN_ROUTE_SOURCE')) }}
