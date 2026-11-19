select
    cast(queryid as bigint) as queryid,
    cast(objectdatabasename as string) as objectdatabasename,
    cast(objecttablename as string) as objecttablename,
    {{ legacy_text('objecttype', 1, true) }} as objecttype,
    cast(usagetype as string) as usagetype
from {{ source('bronze_platform', 'dbc_qrylogobjects') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
