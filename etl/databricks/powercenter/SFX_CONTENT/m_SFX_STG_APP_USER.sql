/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_STG_APP_USER */
INSERT OVERWRITE cpw.dbx_d1111_after.users__stg_app_user
SELECT user_id,
       trim(substring(display_name,1,60)) AS display_name,
       lower(trim(substring(email,1,120))) AS email,
       upper(trim(substring(status_cd,1,12))) AS status_cd,
       created_dt
FROM cpw.dbx_d1111_before.users__stg_app_user;
