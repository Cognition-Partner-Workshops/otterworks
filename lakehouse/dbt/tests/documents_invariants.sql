{{ config(tags=['documents']) }}

select 'latest_version' as invariant
from {{ ref('doc_version') }} v
join {{ ref('stg_doc_version') }} s on v.document_id = s.document_id
where s.version_ts > v.version_ts
union all
select 'storage_set_duplicates' as invariant
from {{ ref('storage_usage_daily') }}
group by storage_usage_id, customer_id, owner_user_id, usage_dt, bytes_used, object_count
having count(*) > 1
union all
select 'folder_snapshot_count' as invariant
where (select count(*) from {{ ref('folder') }}) <> (select count(*) from {{ ref('stg_folder') }})
union all
select 'document_snapshot_count' as invariant
where (select count(*) from {{ ref('document') }}) <> (select count(*) from {{ ref('stg_document') }})
