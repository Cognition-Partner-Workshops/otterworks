{{ config(materialized='table', alias='spark__docs_folder_tree_walk') }}
with recursive paths(FOLDER_ID, ROOT_FOLDER_ID, DEPTH, STEP) as (
 select FOLDER_ID, FOLDER_ID, 0, 0 from {{ source('spark_documents', 'FOLDER') }}
 union all
 select p.FOLDER_ID, coalesce(nullif(f.PARENT_FOLDER_ID,0),p.ROOT_FOLDER_ID),
        p.DEPTH+case when f.PARENT_FOLDER_ID is not null then 1 else 0 end, p.STEP+1
 from paths p left join {{ source('spark_documents', 'FOLDER') }} f on f.FOLDER_ID is not distinct from p.ROOT_FOLDER_ID
 where p.STEP<20
)
select FOLDER_ID,ROOT_FOLDER_ID,DEPTH from paths where STEP=20
