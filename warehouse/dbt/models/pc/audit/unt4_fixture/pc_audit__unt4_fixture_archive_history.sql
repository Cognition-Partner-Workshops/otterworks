{{ config(materialized='incremental', incremental_strategy='append', full_refresh=false,
          schema='PC_AUDIT_UNT4_FIXTURE',
          enabled=env_var('SFX_UNT4_ARCHIVE_FIXTURE', '0') == '1') }}

{{ pc_audit_event_archive(source('unt4_archive_fixture', 'AUDIT_EVENT')) }}
