select * exclude (_rn) from (
  select *, row_number() over (partition by id order by _loaded_at desc) as _rn
  from {{ source('raw', 'stores') }}
) where _rn = 1
