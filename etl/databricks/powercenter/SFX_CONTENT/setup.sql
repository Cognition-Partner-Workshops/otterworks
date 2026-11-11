/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_STG_APP_USER */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.users__stg_app_user
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT user_id AS user_id,display_name AS display_name,email AS email,status_cd AS status_cd,created_dt AS created_dt FROM cpw.dbx_d1111_before.users__stg_app_user;

/* run=dbx-d1111 act=scale step=baseline-target-state consumer=m_SFX_STG_APP_USER */
INSERT OVERWRITE cpw.dbx_d1111_after.users__stg_app_user SELECT user_id AS user_id,display_name AS display_name,email AS email,status_cd AS status_cd,created_dt AS created_dt FROM cpw.dbx_d1111_before.users__stg_app_user;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_APP_USER */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.users__app_user
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT user_id AS user_id,display_name AS display_name,email AS email,rtrim(status_cd) AS status_cd,created_dt AS created_dt FROM cpw.dbx_d1111_before.users__app_user;

/* run=dbx-d1111 act=scale step=baseline-target-state consumer=m_SFX_APP_USER */
INSERT OVERWRITE cpw.dbx_d1111_after.users__app_user SELECT user_id AS user_id,display_name AS display_name,email AS email,rtrim(status_cd) AS status_cd,created_dt AS created_dt FROM cpw.dbx_d1111_before.users__app_user;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_APP_USER */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.users__app_user__reject
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT user_id,display_name,email,status_cd,created_dt,cast(NULL AS INT) AS row_type,cast(NULL AS STRING) AS reason FROM cpw.dbx_d1111_before.users__app_user WHERE false;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_STG_DOCUMENT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.documents__stg_document
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT document_id AS document_id,folder_id AS folder_id,owner_user_id AS owner_user_id,customer_id AS customer_id,document_name AS document_name,created_dt AS created_dt,status_cd AS status_cd,file_type AS file_type FROM cpw.dbx_d1111_before.documents__stg_document;

/* run=dbx-d1111 act=scale step=baseline-target-state consumer=m_SFX_STG_DOCUMENT */
INSERT OVERWRITE cpw.dbx_d1111_after.documents__stg_document SELECT document_id AS document_id,folder_id AS folder_id,owner_user_id AS owner_user_id,customer_id AS customer_id,document_name AS document_name,created_dt AS created_dt,status_cd AS status_cd,file_type AS file_type FROM cpw.dbx_d1111_before.documents__stg_document;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_DOCUMENT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.documents__document
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT document_id AS document_id,folder_id AS folder_id,owner_user_id AS owner_user_id,customer_id AS customer_id,document_name AS document_name,created_dt AS created_dt,rtrim(status_cd) AS status_cd,rtrim(file_type) AS file_type FROM cpw.dbx_d1111_before.documents__document;

/* run=dbx-d1111 act=scale step=baseline-target-state consumer=m_SFX_DOCUMENT */
INSERT OVERWRITE cpw.dbx_d1111_after.documents__document SELECT document_id AS document_id,folder_id AS folder_id,owner_user_id AS owner_user_id,customer_id AS customer_id,document_name AS document_name,created_dt AS created_dt,rtrim(status_cd) AS status_cd,rtrim(file_type) AS file_type FROM cpw.dbx_d1111_before.documents__document;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_DOCUMENT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.documents__document__reject
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT document_id,folder_id,owner_user_id,customer_id,document_name,created_dt,status_cd,cast(NULL AS INT) AS row_type,cast(NULL AS STRING) AS reason FROM cpw.dbx_d1111_before.documents__document WHERE false;

/* run=dbx-d1111 act=scale step=ddl consumer=m_SFX_DOC_SHARE */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.documents__doc_share
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')
AS SELECT share_id AS share_id,document_id AS document_id,user_id AS user_id,rtrim(access_level) AS access_level,shared_dt AS shared_dt FROM cpw.dbx_d1111_before.documents__doc_share;

/* run=dbx-d1111 act=scale step=baseline-target-state consumer=m_SFX_DOC_SHARE */
INSERT OVERWRITE cpw.dbx_d1111_after.documents__doc_share SELECT share_id AS share_id,document_id AS document_id,user_id AS user_id,rtrim(access_level) AS access_level,shared_dt AS shared_dt FROM cpw.dbx_d1111_before.documents__doc_share;
