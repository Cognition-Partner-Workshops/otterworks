-- rpt_seat_utilization: the dataset of source/reports/rpt_seat_utilization.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
-- CAST(seat_count AS decimal(18,4)) / NULLIF(seat_limit, 0) is decimal(29,15) in SQL Server, which
-- truncates the quotient at the 15th decimal; Snowflake's cast rounds, so truncate explicitly.
select
    business_date,
    tenant_id,
    plan_tier,
    seat_count,
    seat_limit,
    trunc(seat_count::number(38, 20) / nullif(seat_limit, 0), 15)::number(29, 15) as utilization
from {{ ref('apply_plan_limits') }}
