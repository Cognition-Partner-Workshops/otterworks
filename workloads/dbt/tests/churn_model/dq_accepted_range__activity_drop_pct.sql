{{ config(tags=['dq', 'dq_churn_model', 'dq_accepted_range']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Spec: activity_drop_pct = ROUND((prior_avg - this_week) / prior_avg * 100, 2); null when prior_avg = 0;
-- negative means growth, and it can never exceed 100 because this_week >= 0.
select week_start_date, account_id, activity_this_week, activity_prior_4wk_avg, activity_drop_pct
from {{ ref('churn_model') }}
where (activity_prior_4wk_avg = 0 and activity_drop_pct is not null)
   or (activity_prior_4wk_avg <> 0 and (activity_drop_pct is null
       or activity_drop_pct <> round((activity_prior_4wk_avg - activity_this_week) / activity_prior_4wk_avg * 100, 2)
       or activity_drop_pct > 100))
