/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_APP_USER */
MERGE INTO cpw.dbx_d1111_after.users__app_user__reject t
USING (
  SELECT *,cast(1 AS INT) AS row_type,'WRT_8229 target constraint' AS reason
  FROM cpw.dbx_d1111_after.users__stg_app_user
  WHERE user_id IS NULL OR length(display_name)>60 OR length(email)>120 OR length(status_cd)>12
) s ON t.user_id <=> s.user_id AND t.display_name <=> s.display_name
   AND t.email <=> s.email AND t.status_cd <=> s.status_cd AND t.created_dt <=> s.created_dt
WHEN NOT MATCHED THEN INSERT *;

/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_APP_USER */
MERGE INTO cpw.dbx_d1111_after.users__app_user t
USING (
  WITH lkp AS (
    SELECT user_id,row_number() OVER (PARTITION BY user_id ORDER BY user_id) AS rn
    FROM cpw.dbx_d1111_after.users__app_user
  )
  SELECT s.*,CASE WHEN l.user_id IS NULL THEN 0 ELSE 1 END AS row_type
  FROM cpw.dbx_d1111_after.users__stg_app_user s
  LEFT JOIN lkp l ON s.user_id=l.user_id AND l.rn=1
  WHERE coalesce(s.user_id IS NOT NULL AND (length(s.display_name)<=60 OR s.display_name IS NULL)
    AND (length(s.email)<=120 OR s.email IS NULL) AND (length(s.status_cd)<=12 OR s.status_cd IS NULL),false)
) s ON t.user_id=s.user_id
WHEN MATCHED AND s.row_type=1 AND NOT (
  t.display_name <=> s.display_name AND t.email <=> s.email
  AND t.status_cd <=> s.status_cd AND t.created_dt <=> s.created_dt)
  THEN UPDATE SET display_name=s.display_name,email=s.email,status_cd=s.status_cd,created_dt=s.created_dt
WHEN NOT MATCHED AND s.row_type=0 THEN INSERT (user_id,display_name,email,status_cd,created_dt)
  VALUES(s.user_id,s.display_name,s.email,s.status_cd,s.created_dt);

-- run_token=dbx-d1111 expires=2026-11-24 act=scale
