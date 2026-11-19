{{ config(materialized='table', alias='spark__doc_share_graph_reach') }}
with recursive paths(USER_ID,DISTANCE) as (
 select 1::bigint, 0
 union all
 select s.SHARED_WITH_USER_ID,p.DISTANCE+1
 from paths p join {{ source('spark_documents', 'DOC_SHARE') }} s on s.OWNER_USER_ID is not distinct from p.USER_ID
 where p.DISTANCE<4
)
select USER_ID,min(DISTANCE) as DISTANCE from paths group by USER_ID
