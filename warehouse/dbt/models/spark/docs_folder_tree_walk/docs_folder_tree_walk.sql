{{ config(materialized='table') }}

with recursive folders as (
    select folder_id, parent_folder_id
    from {{ source('spark_documents', 'FOLDER') }}
), walk (folder_id, root_folder_id, depth, iteration) as (
    select folder_id, folder_id, 0::number(38, 0), 0
    from folders
    union all
    select w.folder_id,
           coalesce(nullif(f.parent_folder_id, 0), w.root_folder_id),
           w.depth + iff(f.parent_folder_id is not null, 1, 0),
           w.iteration + 1
    from walk w
    left join folders f on f.folder_id = w.root_folder_id
    where w.iteration < 20
)
select folder_id, root_folder_id, depth
from walk
where iteration = 20
