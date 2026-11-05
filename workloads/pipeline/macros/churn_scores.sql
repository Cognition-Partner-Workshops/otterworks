{% macro churn_scores(users, accounts, versions, periods) %}
with counts as (
 select p.week_start_date,u.id as account_id,
  datediff(day,coalesce(u.last_login_at,u.created_at)::date,dateadd(day,6,p.week_start_date)) as days_since_last_login,
  coalesce(count_if(v.created_at>=p.week_start_date and v.created_at<dateadd(day,7,p.week_start_date)),0) as activity_this_week,
  coalesce(count_if(v.created_at>=dateadd(day,-28,p.week_start_date) and v.created_at<p.week_start_date),0)/4.0 as activity_prior_4wk_avg,
  coalesce(a.status,'active') as status
 from {{ periods }} p cross join {{ users }} u
 left join {{ accounts }} a on a.id=u.id
 left join {{ versions }} v on v.created_by=u.id
   and v.created_at>=dateadd(day,-28,p.week_start_date) and v.created_at<dateadd(day,7,p.week_start_date)
 where u.created_at<=dateadd(day,-28,p.week_start_date) and coalesce(a.status,'active')<>'deleted'
 group by 1,2,3,6
), drops as (
 select *,100*(activity_prior_4wk_avg-activity_this_week)/nullif(activity_prior_4wk_avg,0) as activity_drop_pct
 from counts
), points as (
 select *,
 case when days_since_last_login>=30 then 40 when days_since_last_login>=14 then 25 when days_since_last_login>=7 then 10 else 0 end as login_points,
 case when activity_prior_4wk_avg=0 and activity_this_week=0 then 30 when activity_prior_4wk_avg=0 then 0
 when activity_drop_pct>=75 then 40 when activity_drop_pct>=50 then 25 when activity_drop_pct>=25 then 10 else 0 end as activity_points,
 case when status='suspended' then 20 else 0 end as status_points
 from drops
), scores as (select *,login_points+activity_points+status_points as churn_score from points)
select week_start_date::date as week_start_date,account_id::varchar(36) as account_id,
 days_since_last_login::number(6,0) as days_since_last_login,activity_this_week::number(10,0) as activity_this_week,
 activity_prior_4wk_avg::number(10,2) as activity_prior_4wk_avg,activity_drop_pct::number(7,2) as activity_drop_pct,
 login_points::number(3,0) as login_points,activity_points::number(3,0) as activity_points,
 status_points::number(3,0) as status_points,churn_score::number(3,0) as churn_score,
 case when churn_score>=60 then 'high' when churn_score>=30 then 'medium' else 'low' end::varchar(8) as risk_band,
 'rules_v1'::varchar(16) as model_version from scores
{% endmacro %}
