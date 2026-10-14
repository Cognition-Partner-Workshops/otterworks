-- Each file's versions are numbered 1..n with no gaps (dim_file.version_count is COUNT(*)).
select file_id, count(*) as versions, min(version) as min_version, max(version) as max_version
from {{ ref('stg_file_versions') }}
group by file_id
having min(version) <> 1 or max(version) <> count(*)
