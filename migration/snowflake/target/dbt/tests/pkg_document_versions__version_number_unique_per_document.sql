-- Each document's versions are numbered once: (document_id, version_number) is unique.
select document_id, version_number, count(*) as n
from {{ ref('stg_document_versions') }}
group by document_id, version_number
having count(*) > 1
