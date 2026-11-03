select * exclude (_rn) from (
  select *, row_number() over (partition by order_id, code order by _loaded_at desc) as _rn
  from {{ source('raw', 'order_fees') }}
) where _rn = 1
