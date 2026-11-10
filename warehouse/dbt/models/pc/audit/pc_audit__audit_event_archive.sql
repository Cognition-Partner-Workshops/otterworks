{{ config(materialized='incremental', incremental_strategy='append', full_refresh=false) }}

{{ pc_audit_event_archive(ref('pc_audit__audit_event')) }}
