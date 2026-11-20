-- Replaces lake billing/billing_churn_score: the Python UDF's logistic score in SQL.
select
    s.*,
    1 / (1 + exp(-(-1.8 + 0.04 * (s.CUSTOMER_ID % 50)
        + case when s.STATUS = 'closed' then 1.2 else 0 end))) as CHURN_SCORE
from {{ source('spark_billing', 'SUBSCRIPTION') }} s
