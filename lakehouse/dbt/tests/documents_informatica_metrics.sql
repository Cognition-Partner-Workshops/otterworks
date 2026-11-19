{{ config(tags=['documents']) }}

select * from {{ ref('infa_metrics') }}
where source_rows < written_rows + rejected_rows
   or transformation_errors > rejected_rows
   or written_rows <> inserted_rows + updated_rows
   or least(source_rows, transformation_errors, written_rows, rejected_rows,
            inserted_rows, updated_rows, rows_before, rows_after) < 0
   or (pipeline = 'stg_document' and rows_after <> written_rows)
   or (pipeline <> 'stg_document' and rows_after <> rows_before + inserted_rows)
