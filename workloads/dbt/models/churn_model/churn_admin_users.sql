select * from {{ source('raw_churn_model', 'ADMIN_ADMIN_USERS') }}
where _export_id is not null
qualify row_number() over (
 partition by _export_id, id
 order by _loaded_at desc, _file_name desc, _file_row_number desc
) = 1
