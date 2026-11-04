{{ config(tags=['dq', 'dq_churn_model', 'dq_accepted_range']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Spec: activity_this_week is a row count (>= 0); activity_prior_4wk_avg is rows over 4 weeks / 4
-- (>= 0, a multiple of 0.25); week_start_date is the Monday of the scored week; account_id fits VARCHAR(36).
select week_start_date, account_id, activity_this_week, activity_prior_4wk_avg
from {{ ref('churn_model') }}
where activity_this_week < 0
   or activity_prior_4wk_avg < 0
   or mod(activity_prior_4wk_avg * 4, 1) <> 0
   or dayofweekiso(week_start_date) <> 1
   or length(account_id) > 36
