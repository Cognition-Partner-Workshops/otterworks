/* run=dbx-d1111 act=spark step=inputs consumer=docs_folder_tree_walk */
-- run_token=dbx-d1111 expires=2026-11-24
-- Landing documents/FOLDER (FOLDER_ID, OWNER_USER_ID, PARENT_FOLDER_ID, FOLDER_NAME).
-- PARENT_FOLDER_ID has no live equivalent: documents__folder and documents__stg_folder carry
-- folder_id, owner_user_id, customer_id, folder_name, created_dt only (warehouse/teradata/ddl/documents/00_tables.sql),
-- and no table in cpw.dbx_d1111_before has a parent column. The job's only logic is the parent walk, so the
-- adapter cannot be completed without fabricating hierarchy. The query below fails by design (first failing result).
SELECT folder_id        AS FOLDER_ID,
       owner_user_id    AS OWNER_USER_ID,
       parent_folder_id AS PARENT_FOLDER_ID,
       folder_name      AS FOLDER_NAME
FROM cpw.dbx_d1111_before.documents__folder
