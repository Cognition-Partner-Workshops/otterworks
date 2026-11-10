{{ config(materialized='incremental', incremental_strategy='merge', unique_key='LOGIN_ID', full_refresh=false,
          schema='PC_CONTENT_UNT6_FIXTURE', enabled=env_var('SFX_UNT6_LOGIN_FIXTURE','0') == '1') }}

{{ pc_content_login_event(source('unt6_fixture', 'SEEDED_SOURCE'), raw_input=true) }}
