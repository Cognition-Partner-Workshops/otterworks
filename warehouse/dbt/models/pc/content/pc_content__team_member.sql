{{ config(materialized='incremental', incremental_strategy='merge', unique_key='TEAM_MEMBER_ID', full_refresh=false) }}

{{ pc_content_team_member(source('unt8_pc_src','TEAM_MEMBER')) }}
