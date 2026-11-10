{% set usage = source('billing', 'USAGE_DAILY') %}

with retained_files as (
    select distinct 'pipeline/' || regexp_substr(metadata$filename, '[^/]+$') as src_file
    from @LANDING.LANDING_STAGE/pipeline/
), latest_copy as (
    select 'pipeline/' || regexp_substr(file_name, '[^/]+$') as src_file,
           row_parsed
    from table({{ usage.database }}.information_schema.copy_history(
        table_name => '{{ usage }}',
        start_time => dateadd(day, -14, current_timestamp())
    ))
    where file_name like '%pipeline/%'
    qualify row_number() over (
        partition by src_file order by last_load_time desc
    ) = 1
), actual as (
    select _src_file as src_file, count(*) as row_count
    from {{ usage }}
    where _src_file like 'pipeline/%'
    group by _src_file
)
select coalesce(actual.src_file, latest_copy.src_file) as src_file,
       coalesce(actual.row_count, 0) as row_count, latest_copy.row_parsed
from actual
full outer join latest_copy on actual.src_file = latest_copy.src_file
where latest_copy.row_parsed is not null
  and latest_copy.src_file in (select src_file from retained_files)
  and coalesce(actual.row_count, 0) <> latest_copy.row_parsed
