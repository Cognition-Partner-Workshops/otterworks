{{ config(materialized='view') }}
select recon_id, source_count, target_count, difference_count
from {{ ref('audit_recon_final') }} where business_dt = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
