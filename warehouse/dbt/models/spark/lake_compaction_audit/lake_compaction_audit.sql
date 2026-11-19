{{ config(materialized='table') }}

select *
from {{ ref('audit_daily_summary') }}
