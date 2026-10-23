with version_counts as (
    select "file_id" as file_id, count(*) as version_count
    from {{ source('raw', 'STG_FILE_VERSIONS') }}
    group by "file_id"
)

select
    files."id" as file_id,
    files."tenant_id" as tenant_id,
    files."workspace_id" as workspace_id,
    files."owner_id" as owner_id,
    files."name" as file_name,
    files."mime_type" as mime_type,
    files."size_bytes" as size_bytes,
    files."size_mb" as size_mb,
    iff(lower(files."is_trashed"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as is_trashed,
    case
        when files."archived" is null then null
        when lower(files."archived"::varchar) in ('1', 'true', 't', 'yes', 'y') then 1
        else 0
    end as archived,
    coalesce(version_counts.version_count, 0) as version_count,
    files."created_at" as created_at_utc,
    files."updated_at" as updated_at_utc
from {{ source('raw', 'STG_FILES') }} as files
left join version_counts
    on version_counts.file_id = files."id"
where files."created_at" < dateadd(day, 1, {{ business_date() }})
