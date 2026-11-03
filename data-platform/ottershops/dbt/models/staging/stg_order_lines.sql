select * exclude (_rn) from (
  select *, row_number() over (partition by order_id, line_no order by _loaded_at desc) as _rn
  from {{ source('raw', 'order_lines') }}
) where _rn = 1
