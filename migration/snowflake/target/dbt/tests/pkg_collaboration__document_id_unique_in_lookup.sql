-- LKP Tenant from document keys on stg.stg_documents.id; a duplicate id would fan out the left join.
select "id"
from {{ source('raw', 'STG_DOCUMENTS') }}
group by "id"
having count(*) > 1
