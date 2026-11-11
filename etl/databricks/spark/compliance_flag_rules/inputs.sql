/* run=dbx-d1111 act=spark step=inputs consumer=compliance_flag_rules */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT flag_id AS COMPLIANCE_FLAG_ID, document_id AS DOCUMENT_ID,
 flag_type AS FLAG_TYPE, status_cd AS STATUS
FROM cpw.dbx_d1111_before.audit__compliance_flag;
-- BLOCKED: SEVERITY and USER_ID have no equivalent. Do not derive severity from FLAG_TYPE or fabricate a user.
