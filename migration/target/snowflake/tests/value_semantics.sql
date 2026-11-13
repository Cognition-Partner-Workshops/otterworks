select 1 as failure
where {{ warehouse_hash(['cast(null as ' ~ dbt.type_string() ~ ')']) }} = {{ warehouse_hash(["''"]) }}
   or {{ safe_numeric("'invalid'", 18, 4) }} is not null
   or {{ safe_numeric("'1.1234'", 18, 4) }} <> 1.1234
   or {{ empty_string("''", policy='preserve') }} is null
   or {{ empty_string("''", policy='nullify') }} is not null
