select * exclude (_rn) from (
  select *, row_number() over (partition by id order by updated_at desc, _loaded_at desc) as _rn
  from {{ source('raw', 'returns') }}
) where _rn = 1
