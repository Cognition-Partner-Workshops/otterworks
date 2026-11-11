/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_STG_DOCUMENT */
INSERT OVERWRITE cpw.dbx_d1111_after.documents__stg_document
SELECT document_id,folder_id,owner_user_id,customer_id,
       trim(substring(document_name,1,120)) AS document_name,
       created_dt,upper(trim(substring(status_cd,1,12))) AS status_cd,
       cast(NULL AS STRING) AS file_type
FROM cpw.dbx_d1111_before.documents__stg_document;

-- run_token=dbx-d1111 expires=2026-11-24 act=scale
