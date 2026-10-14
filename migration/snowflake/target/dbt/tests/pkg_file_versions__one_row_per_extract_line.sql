-- pkg_file_versions has no filter or lookup: every line of file_versions.csv lands exactly once.
with model as (select count(*) as n from {{ ref('stg_file_versions') }}),
extract as (select count(*) as n from {{ source('pkg_file_versions', 'EXT_FILE_VERSIONS') }})
select model.n as model_rows, extract.n as extract_rows
from model cross join extract
where model.n <> extract.n
  and not {{ var('pkg_file_versions_cut_at_business_date', false) }}
