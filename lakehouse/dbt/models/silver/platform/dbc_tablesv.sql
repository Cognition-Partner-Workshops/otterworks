select
    cast(databasename as string) as databasename,
    cast(tablename as string) as tablename,
    {{ legacy_text('tablekind', 1, true) }} as tablekind,
    cast(createtimestamp as timestamp) as createtimestamp,
    cast(lastaccesstimestamp as timestamp) as lastaccesstimestamp,
    cast(accesscount as bigint) as accesscount
from {{ source('bronze_platform', 'dbc_tablesv') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
