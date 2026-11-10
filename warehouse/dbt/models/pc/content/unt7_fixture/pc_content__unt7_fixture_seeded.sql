{{ config(materialized='table', full_refresh=false,
          schema='PC_FX_UNT7_ROLE_GRANT', enabled=env_var('SFX_UNT7_ROLE_FIXTURE','0') == '1') }}

{{ pc_content_role_grant(source('unt7_fixture', 'SEEDED_SOURCE'), raw_input=true) }}
