with version_counts as (
    select "document_id" as document_id, count(*) as version_count
    from {{ source('raw', 'STG_DOCUMENT_VERSIONS') }}
    group by "document_id"
)

select
    documents."id" as document_id,
    documents."tenant_id" as tenant_id,
    documents."workspace_id" as workspace_id,
    documents."owner_id" as owner_id,
    documents."title" as title,
    documents."content_type" as content_type,
    iff(lower(documents."is_deleted"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as is_deleted,
    iff(lower(documents."is_template"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as is_template,
    case
        when documents."archived" is null then null
        when lower(documents."archived"::varchar) in ('1', 'true', 't', 'yes', 'y') then 1
        else 0
    end as archived,
    documents."word_count" as word_count,
    coalesce(version_counts.version_count, 0) as version_count,
    documents."created_at" as created_at_utc,
    documents."updated_at" as updated_at_utc
from {{ source('raw', 'STG_DOCUMENTS') }} as documents
left join version_counts
    on version_counts.document_id = documents."id"
where documents."created_at" < dateadd(day, 1, {{ business_date() }})
