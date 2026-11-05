{{ config(tags=['dq_churn_model']) }}
{% set db = database_for('churn_model') %}
select 'accepted_range: invalid weekly score account=' || coalesce(account_id,'NULL')
  || ' week=' || coalesce(week_start_date::varchar,'NULL') as failure
from {{ ref('weekly_churn_scores') }}
where week_start_date is null or dayofweekiso(week_start_date)<>1 or account_id is null
  or days_since_last_login is null or days_since_last_login not between 0 and 999999
  or activity_this_week is null or activity_this_week not between 0 and 9999999999
  or activity_prior_4wk_avg is null or activity_prior_4wk_avg not between 0 and 99999999.99
  or (activity_prior_4wk_avg=0 and activity_drop_pct is not null)
  or (activity_prior_4wk_avg>0 and (activity_drop_pct is null
    or activity_drop_pct is distinct from round(100*(activity_prior_4wk_avg-activity_this_week)/nullif(activity_prior_4wk_avg,0),2)))
  or activity_drop_pct>100
  or login_points is null or login_points not in (0,10,25,40)
  or login_points is distinct from case when days_since_last_login>=30 then 40
    when days_since_last_login>=14 then 25 when days_since_last_login>=7 then 10 else 0 end
  or activity_points is null or activity_points not in (0,10,25,30,40)
  or activity_points is distinct from case when activity_prior_4wk_avg=0 and activity_this_week=0 then 30
    when activity_prior_4wk_avg=0 then 0 when activity_drop_pct>=75 then 40
    when activity_drop_pct>=50 then 25 when activity_drop_pct>=25 then 10 else 0 end
  or status_points is null or status_points not in (0,20)
  or churn_score is null or churn_score not between 0 and 100
  or churn_score is distinct from login_points+activity_points+status_points
  or risk_band is null or risk_band not in ('low','medium','high')
  or risk_band is distinct from case when churn_score>=60 then 'high' when churn_score>=30 then 'medium' else 'low' end
  or model_version is null or model_version<>'rules_v1'
union all
select 'accepted_range: retained evaluation recall must meet 0.50 with available recall/precision/AUC; '
  || 'run=' || run_id || '; ' || coalesce(cause,'evaluation metrics unavailable or outside accepted bounds') as failure
from {{ db }}.APP.CHURN_MODEL_EVALUATION
where recall is null or recall not between 0.50 and 1 or passed is distinct from true
  or precision is null or precision not between 0 and 1 or auc is null or auc not between 0 and 1
  or n is null or n<1 or positives is null or positives<1 or negatives is null or negatives<0
  or tp is null or tp<0 or fp is null or fp<0 or fn is null or fn<0 or tn is null or tn<0
  or n is distinct from positives+negatives or n is distinct from tp+fp+fn+tn
  or positives is distinct from tp+fn or negatives is distinct from tn+fp
union all
select 'accepted_range: retained evaluation is missing' as failure
where not exists (select 1 from {{ db }}.APP.CHURN_MODEL_EVALUATION)
union all
select 'accepted_range: retained model score invalid run=' || coalesce(s.run_id,'NULL')
  || ' account=' || coalesce(s.account_id,'NULL')
  || case when s.score is null then '; score unavailable: training depends on sufficient source history; '
    || coalesce(e.cause,'no evaluation cause recorded') else '; score must be in [0,1] with account/date/flag present' end as failure
from {{ db }}.APP.CHURN_MODEL_SCORES s
left join {{ db }}.APP.CHURN_MODEL_EVALUATION e on e.run_id=s.run_id
where s.account_id is null or s.prediction_date is null or s.score is null or s.score not between 0 and 1 or s.flagged is null
union all
select 'accepted_range: retained leakage check failed run=' || coalesce(run_id,'NULL') as failure
from {{ db }}.APP.CHURN_LEAKAGE_CHECK
where feature is null or rows_checked is null or rows_checked<1 or violations is distinct from 0 or passed is distinct from true
