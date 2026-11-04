{{ config(tags=['dq', 'dq_churn_model', 'dq_accepted_range']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Spec parameters: login_points {">=30": 40, "14-29": 25, "7-13": 10, "<7": 0};
-- activity_points {dormant: 30, no baseline: 0, ">=0.75": 40, ">=0.50": 25, ">=0.25": 10, "<0.25": 0};
-- status_points {suspended: 20, active: 0} from admin_users.status in the export that scored the week.
with chosen as (
  select distinct _export_id,
         dateadd(day, -7, date_trunc('week', convert_timezone('UTC', _exported_at)::date))::date as week_start_date,
         _exported_at
  from {{ source('raw_churn_model', 'AUTH_USERS') }}
  where _export_id is not null and _exported_at is not null
  qualify row_number() over (partition by week_start_date order by _exported_at desc, _export_id desc) = 1
), status as (
  select distinct c.week_start_date, a.id as account_id, a.status
  from chosen c join {{ source('raw_churn_model', 'ADMIN_ADMIN_USERS') }} a on a._export_id = c._export_id
)
select m.week_start_date, m.account_id, m.days_since_last_login, m.login_points,
       m.activity_this_week, m.activity_prior_4wk_avg, m.activity_points, m.status_points, s.status
from {{ ref('churn_model') }} m
left join status s on s.week_start_date = m.week_start_date and s.account_id = m.account_id
where m.login_points <> case when m.days_since_last_login >= 30 then 40 when m.days_since_last_login >= 14 then 25
                             when m.days_since_last_login >= 7 then 10 else 0 end
   or m.activity_points <> case when m.activity_prior_4wk_avg = 0 and m.activity_this_week = 0 then 30
                                when m.activity_prior_4wk_avg = 0 then 0
                                when (m.activity_prior_4wk_avg - m.activity_this_week) / m.activity_prior_4wk_avg >= 0.75 then 40
                                when (m.activity_prior_4wk_avg - m.activity_this_week) / m.activity_prior_4wk_avg >= 0.50 then 25
                                when (m.activity_prior_4wk_avg - m.activity_this_week) / m.activity_prior_4wk_avg >= 0.25 then 10
                                else 0 end
   or s.status is null
   or m.status_points <> case when s.status = 'suspended' then 20 else 0 end
