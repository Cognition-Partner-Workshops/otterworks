{{ config(materialized='incremental', incremental_strategy='append',
    pre_hook="{{ clear_changed_dates('churn_users','week_start_date') }}", post_hook="{{ output_grants() }}") }}

with batches as (
 {{ latest_batches(ref('churn_users'), "dateadd(day, -7, date_trunc('week', convert_timezone('UTC', _exported_at)::date))::date") }}
), base as (
 select b.snapshot_date as week_start_date,u.id as account_id,a.status,
 datediff(day,convert_timezone('UTC',coalesce(u.last_login_at,u.created_at))::date,dateadd(day,6,b.snapshot_date)) as days_since_last_login,
 count_if(v.created_at >= b.snapshot_date and v.created_at < dateadd(day,7,b.snapshot_date)) as activity_this_week,
 count_if(v.created_at >= dateadd(day,-28,b.snapshot_date) and v.created_at < b.snapshot_date)/4.0 as activity_prior_4wk_avg
 from batches b join {{ ref('churn_users') }} u on u._export_id=b._export_id
 join {{ ref('churn_admin_users') }} a on a._export_id=b._export_id and a.id=u.id
 left join {{ ref('churn_versions') }} v on v._export_id=b._export_id and v.created_by=u.id
 where a.status <> 'deleted' and u.created_at < dateadd(day,-28,b.snapshot_date)
 group by b.snapshot_date,u.id,a.status,u.last_login_at,u.created_at
), points as (
 select *, (activity_prior_4wk_avg-activity_this_week)/nullif(activity_prior_4wk_avg,0)*100 as drop_pct,
 case when days_since_last_login>=30 then 40 when days_since_last_login>=14 then 25 when days_since_last_login>=7 then 10 else 0 end as login_points,
 case when activity_prior_4wk_avg=0 and activity_this_week=0 then 30
 when activity_prior_4wk_avg=0 then 0
 when drop_pct>=75 then 40 when drop_pct>=50 then 25 when drop_pct>=25 then 10 else 0 end as activity_points,
 case when status='suspended' then 20 else 0 end as status_points
 from base
)
select week_start_date::date as week_start_date,account_id::varchar(36) as account_id,
 days_since_last_login::number(6,0) as days_since_last_login,
 activity_this_week::number(10,0) as activity_this_week,
 activity_prior_4wk_avg::number(10,2) as activity_prior_4wk_avg,
 round(drop_pct,2)::number(7,2) as activity_drop_pct,
 login_points::number(3,0) as login_points,activity_points::number(3,0) as activity_points,
 status_points::number(3,0) as status_points,
 (login_points+activity_points+status_points)::number(3,0) as churn_score,
 (case when churn_score>=60 then 'high' when churn_score>=30 then 'medium' else 'low' end)::varchar(8) as risk_band,
 'rules_v1'::varchar(16) as model_version
from points
