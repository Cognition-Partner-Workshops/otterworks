{{ config(alias='DOCS_TAG_NORMALIZE', tags=['sfx-d1110', 'docs_tag_normalize']) }}

-- Match Python 3.10 strip()/regex whitespace, including Unicode separators.
with whitespace as (
    select concat(chr(9), chr(10), chr(11), chr(12), chr(13), chr(28), chr(29),
                  chr(30), chr(31), chr(32), chr(133), chr(160), chr(5760),
                  chr(8192), chr(8193), chr(8194), chr(8195), chr(8196), chr(8197),
                  chr(8198), chr(8199), chr(8200), chr(8201), chr(8202), chr(8232),
                  chr(8233), chr(8239), chr(8287), chr(12288)) as chars
)
select DOC_TAG_ID, DOCUMENT_ID, TAG,
       regexp_replace(
           lower(trim(coalesce(TAG, ''), whitespace.chars)),
           '[' || whitespace.chars || ']+', '-'
       ) as NORMALIZED_TAG
from {{ source('spark_documents', 'DOC_TAG') }}
cross join whitespace
