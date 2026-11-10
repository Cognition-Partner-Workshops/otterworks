{{ config(enabled=env_var('SFX_UNT8_TEAM_FIXTURE','0') == '1', schema='PC_FX_UNT8_TEAM_MEMBER', materialized='incremental', incremental_strategy='merge', unique_key='TEAM_MEMBER_ID', full_refresh=false) }}

{{ pc_content_team_member(source('unt8_fixture','DUP_KEY_SOURCE'), raw_input=true) }}
