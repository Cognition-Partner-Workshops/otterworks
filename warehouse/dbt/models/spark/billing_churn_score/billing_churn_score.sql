{{ config(materialized='table', alias='BILLING_CHURN_SCORE') }}

select
    subscription_id,
    customer_id,
    plan_id,
    start_date,
    end_date,
    status,
    1.0::double / (1.0::double + exp(-(
        -1.8::double + 0.04::double * mod(customer_id, 50)
        + case when status = 'closed' then 1.2::double else 0.0::double end
    ))) as churn_score
from {{ source('spark_billing', 'SUBSCRIPTION') }}
