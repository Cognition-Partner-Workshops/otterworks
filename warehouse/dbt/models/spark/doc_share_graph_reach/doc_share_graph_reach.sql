{{ config(materialized='table') }}

with recursive edges as (
    select distinct owner_user_id, shared_with_user_id
    from {{ source('spark_documents', 'DOC_SHARE') }}
), reach (user_id, distance) as (
    select 1::number(38, 0), 0::number(38, 0)
    union all
    select e.shared_with_user_id, r.distance + 1
    from reach r
    join edges e on e.owner_user_id is not distinct from r.user_id
    where r.distance < 4
)
select user_id, min(distance) as distance
from reach
group by user_id
