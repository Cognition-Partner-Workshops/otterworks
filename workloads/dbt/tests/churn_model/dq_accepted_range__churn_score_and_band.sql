{{ config(tags=['dq', 'dq_churn_model', 'dq_accepted_range']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Spec: churn_score = login_points + activity_points + status_points, range 0-100;
-- risk_band high at >= 60, medium at 30-59, low below 30.
select week_start_date, account_id, login_points, activity_points, status_points, churn_score, risk_band
from {{ ref('churn_model') }}
where churn_score <> login_points + activity_points + status_points
   or churn_score not between 0 and 100
   or risk_band <> case when churn_score >= 60 then 'high' when churn_score >= 30 then 'medium' else 'low' end
