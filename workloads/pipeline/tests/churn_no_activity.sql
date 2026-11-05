{{ config(tags=['churn_model']) }}
with users as (
 select 'account' as id,'2026-01-01'::timestamp_ntz as created_at,'2026-11-01'::timestamp_ntz as last_login_at
), accounts as (select 'account' as id,'active' as status),
versions as (select null::varchar as created_by,null::timestamp_ntz as created_at where false),
periods as (select '2026-10-26'::date as week_start_date),
report as ({{ churn_scores('users','accounts','versions','periods') }})
select 'no-activity account must receive 30 activity points' as failure
where (select count(*) from report where activity_this_week=0 and activity_prior_4wk_avg=0
 and activity_drop_pct is null and activity_points=30 and churn_score=30 and risk_band='medium')<>1
