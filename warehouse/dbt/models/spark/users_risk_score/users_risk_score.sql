{{ config(materialized='table', alias='USERS_RISK_SCORE') }}

select
    user_activity_id,
    user_id,
    activity_date,
    login_count,
    action_count,
    1.0::double / (1.0::double + exp(-(
        -2.1::double + login_count * 0.0004::double - action_count * 0.0001::double
    ))) as risk_score
from {{ source('spark_users', 'USER_ACTIVITY_DAILY') }}
