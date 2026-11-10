with documents as (
    select
        tenant_id,
        'document' as resource_type,
        document_id as resource_id,
        iff(is_deleted = 1, 'purge', 'cold_storage') as retention_action,
        datediff(day, updated_at_utc, {{ business_date() }}) as days_since_update
    from {{ ref('dim_document') }}
    where (is_deleted = 1 and datediff(day, updated_at_utc, {{ business_date() }}) > 30)
       or (is_deleted = 0 and archived = 1 and datediff(day, updated_at_utc, {{ business_date() }}) > 365)
),

files as (
    select
        tenant_id,
        'file' as resource_type,
        file_id as resource_id,
        iff(is_trashed = 1, 'purge', 'cold_storage') as retention_action,
        datediff(day, updated_at_utc, {{ business_date() }}) as days_since_update
    from {{ ref('dim_file') }}
    where (is_trashed = 1 and datediff(day, updated_at_utc, {{ business_date() }}) > 30)
       or (is_trashed = 0 and archived = 1 and datediff(day, updated_at_utc, {{ business_date() }}) > 365)
)

select {{ business_date() }} as business_date, * from documents
union all
select {{ business_date() }} as business_date, * from files
