{{ config(materialized='table', full_refresh=false) }}

{{ pc_content_role_grant(source('unt7_pc_src', 'ROLE_GRANT')) }}
