-- rpt_tenant_usage_by_region: the dataset of source/reports/rpt_tenant_usage_by_region.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    region_code,
    count(*) as tenant_count,
    sum(api_units) as api_units,
    sum(compute_units) as compute_units,
    sum(bytes_used) as bytes_used
from {{ ref('build_mart_tenant_usage') }}
group by business_date, region_code
