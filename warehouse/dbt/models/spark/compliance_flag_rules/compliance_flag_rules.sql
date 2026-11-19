{{ config(materialized='table') }}

select
    cast(COMPLIANCE_FLAG_ID as bigint) as FLAG_ID,
    cast(DOCUMENT_ID as bigint) as DOCUMENT_ID,
    SEVERITY,
    case
        when STATUS = 'closed' then 'resolved'
        when SEVERITY >= 7000 then 'review'
        else 'monitor'
    end as DISPOSITION
from {{ source('spark_audit', 'COMPLIANCE_FLAG') }}
