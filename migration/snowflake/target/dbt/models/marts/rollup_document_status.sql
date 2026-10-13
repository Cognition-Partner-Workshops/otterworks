-- dbo.usp_rollup_document_status: live documents per workspace split by status.
--
-- The legacy CASE WHEN archived = 1 THEN 'archived' ELSE 'active' END puts every document whose
-- archived flag is NULL (the flag was never set by document-service) into 'active'. This model
-- reports those documents under their own 'unknown' label. Set the var
-- legacy_null_archived_counted_active to true to reproduce the legacy split exactly
-- (gate/out/ledger.md, rollup_document_status).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set legacy_null_active = var('legacy_null_archived_counted_active', false) %}

with documents as (
    select
        tenant_id,
        workspace_id,
        word_count,
        case
            when archived = 1 then 'archived'
            {% if not legacy_null_active -%}
            when archived is null then 'unknown'
            {% endif -%}
            else 'active'
        end as status_label
    from {{ ref('dim_document') }}
    where is_deleted = 0
      and created_at_utc < dateadd(day, 1, {{ business_date() }})
)

select
    {{ business_date() }} as business_date,
    tenant_id,
    workspace_id,
    status_label,
    count(*) as document_count,
    sum(word_count::number(38, 0)) as word_count,
    current_timestamp()::timestamp_ntz as loaded_at
from documents
group by tenant_id, workspace_id, status_label
