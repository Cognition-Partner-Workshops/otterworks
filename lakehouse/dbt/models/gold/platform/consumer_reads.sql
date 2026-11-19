with reads as (
    select lower(rtrim(username)) as username, rtrim(appid) as appid,
           rtrim(clientid) as clientid, count(*) as read_queries
    from {{ ref('qrylogv') }}
    where starttime >= cast('{{ var("dbql_window_start", "2026-10-11 00:00:00") }}' as timestamp)
      and starttime < cast('{{ var("dbql_window_end", "2026-11-10 00:00:00") }}' as timestamp)
      and upper(rtrim(statementtype)) = 'SELECT' and errorcode = 0
    group by lower(rtrim(username)), rtrim(appid), rtrim(clientid)
)
select username, appid, clientid, read_queries,
       cast(read_queries / 30.00 as decimal(12,2)) as reads_per_day
from reads
order by read_queries desc, username asc nulls last
