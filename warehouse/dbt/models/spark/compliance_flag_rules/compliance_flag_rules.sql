{{ config(materialized='table') }}

select
    coalesce(COMPLIANCE_FLAG_ID, 0)::number(19, 0) as FLAG_ID,
    coalesce(DOCUMENT_ID, 0)::number(19, 0) as DOCUMENT_ID,
    coalesce(SEVERITY, 0)::number(10, 0) as SEVERITY,
    case
        when STATUS = 'closed' then 'resolved'
        when coalesce(SEVERITY, 0) >= 7000 then 'review'
        else 'monitor'
    end as DISPOSITION
from {{ source('spark_audit', 'COMPLIANCE_FLAG') }}
