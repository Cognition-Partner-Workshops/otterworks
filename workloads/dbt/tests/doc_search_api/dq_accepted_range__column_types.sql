{{ config(tags=['dq', 'dq_doc_search_api', 'dq_accepted_range']) }}

with expected as (
    select column1 as column_name, column2 as data_type, column3 as character_maximum_length,
        column4 as numeric_precision, column5 as numeric_scale
    from values
        ('WINDOW_END_DATE', 'DATE', null, null, null),
        ('WINDOW_DAYS', 'NUMBER', null, 3, 0),
        ('ACCOUNT_ID', 'TEXT', 36, null, null),
        ('ITEM_TYPE', 'TEXT', 8, null, null),
        ('RANK', 'NUMBER', null, 2, 0),
        ('TERM', 'TEXT', 500, null, null),
        ('DOCUMENT_ID', 'TEXT', 36, null, null),
        ('DOCUMENT_TITLE', 'TEXT', 500, null, null),
        ('SEARCH_COUNT', 'NUMBER', null, 10, 0),
        ('ZERO_RESULT_COUNT', 'NUMBER', null, 10, 0),
        ('LAST_SEARCHED_AT', 'TIMESTAMP_NTZ', null, null, null)
), actual as (
    select column_name, data_type, character_maximum_length, numeric_precision, numeric_scale
    from {{ target.database }}.information_schema.columns
    where table_schema = upper('{{ ref('doc_search_api').schema }}')
        and table_name = upper('{{ ref('doc_search_api').identifier }}')
)
select coalesce(e.column_name, a.column_name) as column_name,
    e.data_type as expected_type, a.data_type as actual_type
from expected e full outer join actual a on e.column_name = a.column_name
where e.column_name is null or a.column_name is null
    or not equal_null(e.data_type, a.data_type)
    or not equal_null(e.character_maximum_length, a.character_maximum_length)
    or not equal_null(e.numeric_precision, a.numeric_precision)
    or not equal_null(e.numeric_scale, a.numeric_scale)
