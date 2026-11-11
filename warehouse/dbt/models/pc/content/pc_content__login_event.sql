{{ config(materialized='incremental', incremental_strategy='merge', unique_key='LOGIN_ID', full_refresh=false) }}

{{ pc_content_login_event(source('unt6_pc_src', 'LOGIN_EVENT')) }}
