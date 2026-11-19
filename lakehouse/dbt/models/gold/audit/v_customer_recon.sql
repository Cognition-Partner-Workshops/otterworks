{{ config(materialized='view') }}
select customer_id, business_dt, source_count, target_count, difference_count
from {{ ref('audit_recon_final') }}
