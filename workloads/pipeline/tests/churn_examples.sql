{{ config(tags=['churn_model', 'dq_churn_model']) }}
with expected as (
 select '2026-10-26'::date as week_start_date,column1::varchar(36) as account_id,column2::number(6,0) as days_since_last_login,
 column3::number(10,0) as activity_this_week,column4::number(10,2) as activity_prior_4wk_avg,
 column5::number(7,2) as activity_drop_pct,column6::number(3,0) as login_points,column7::number(3,0) as activity_points,
 column8::number(3,0) as status_points,column9::number(3,0) as churn_score,column10::varchar(8) as risk_band,
 'rules_v1'::varchar(16) as model_version from values
 ('00000000-0000-4000-8000-000000000101',37,1,5.00,80.00,40,40,0,80,'high'),
 ('00000000-0000-4000-8000-000000000102',15,1,2.00,50.00,25,25,0,50,'medium'),
 ('00000000-0000-4000-8000-000000000103',1,3,2.00,-50.00,0,0,20,20,'low')
), actual as (
 select * from {{ ref('weekly_churn_scores') }} where week_start_date='2026-10-26' and account_id in (select account_id from expected)
)
select 'worked_example: unexpected or mismatched row; verify authoritative history before week end' as failure, diff.*
from (select * from actual minus select * from expected) diff
union all
select 'worked_example: missing or mismatched row; requires authoritative history before week end' as failure, diff.*
from (select * from expected minus select * from actual) diff
