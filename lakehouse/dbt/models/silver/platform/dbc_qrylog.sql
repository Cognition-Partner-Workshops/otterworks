select
    cast(procid as int) as procid,
    cast(collecttimestamp as timestamp) as collecttimestamp,
    cast(queryid as bigint) as queryid,
    cast(username as string) as username,
    cast(defaultdatabase as string) as defaultdatabase,
    cast(appid as string) as appid,
    cast(clientid as string) as clientid,
    cast(starttime as timestamp) as starttime,
    cast(firstresptime as timestamp) as firstresptime,
    cast(statementtype as string) as statementtype,
    cast(statementgroup as string) as statementgroup,
    cast(querytext as string) as querytext,
    cast(numresultrows as bigint) as numresultrows,
    cast(ampcputime as decimal(14,6)) as ampcputime,
    cast(totaliocount as bigint) as totaliocount,
    cast(errorcode as int) as errorcode
from {{ source('bronze_platform', 'dbc_qrylog') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
