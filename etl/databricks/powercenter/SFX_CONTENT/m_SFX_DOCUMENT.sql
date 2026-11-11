/* run=dbx-d1111 act=scale step=lookup-guard consumer=m_SFX_DOCUMENT */
SELECT assert_true(count(*)=0,'Ambiguous first-match APP_USER status cache order')
FROM (SELECT user_id FROM cpw.dbx_d1111_before.users__app_user
      WHERE user_id IS NOT NULL GROUP BY user_id
      HAVING count(DISTINCT coalesce(rtrim(status_cd),'<NULL>'))>1);

/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_DOCUMENT */
MERGE INTO cpw.dbx_d1111_after.documents__document__reject t
USING (
  WITH owners AS (
    SELECT user_id,rtrim(status_cd) AS owner_status,
      row_number() OVER (PARTITION BY user_id ORDER BY user_id) AS rn
    FROM cpw.dbx_d1111_before.users__app_user
  )
  SELECT s.document_id,s.folder_id,s.owner_user_id,s.customer_id,s.document_name,s.created_dt,s.status_cd,
    cast(1 AS INT) AS row_type,'WRT_8229 target constraint' AS reason
  FROM cpw.dbx_d1111_before.documents__stg_document s
  LEFT JOIN owners o ON s.owner_user_id=o.user_id AND o.rn=1
  WHERE coalesce(o.owner_status IS NOT NULL,false)
    AND (s.document_id IS NULL OR length(s.document_name)>120 OR length(s.status_cd)>12)
) s ON t.document_id <=> s.document_id AND t.folder_id <=> s.folder_id
 AND t.owner_user_id <=> s.owner_user_id AND t.customer_id <=> s.customer_id
 AND t.document_name <=> s.document_name AND t.created_dt <=> s.created_dt AND t.status_cd <=> s.status_cd
WHEN NOT MATCHED THEN INSERT *;

/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_DOCUMENT */
MERGE INTO cpw.dbx_d1111_after.documents__document t
USING (
  WITH owners AS (
    SELECT user_id,rtrim(status_cd) AS owner_status,
      row_number() OVER (PARTITION BY user_id ORDER BY user_id) AS rn
    FROM cpw.dbx_d1111_before.users__app_user
  ), lkp AS (
    SELECT document_id,row_number() OVER (PARTITION BY document_id ORDER BY document_id) AS rn
    FROM cpw.dbx_d1111_after.documents__document
  )
  SELECT s.document_id,s.folder_id,s.owner_user_id,s.customer_id,s.document_name,s.created_dt,s.status_cd,
    CASE WHEN l.document_id IS NULL THEN 0 ELSE 1 END AS row_type
  FROM cpw.dbx_d1111_before.documents__stg_document s
  LEFT JOIN owners o ON s.owner_user_id=o.user_id AND o.rn=1
  LEFT JOIN lkp l ON s.document_id=l.document_id AND l.rn=1
  WHERE coalesce(o.owner_status IS NOT NULL,false)
    AND s.document_id IS NOT NULL AND (length(s.document_name)<=120 OR s.document_name IS NULL)
    AND (length(s.status_cd)<=12 OR s.status_cd IS NULL)
) s ON t.document_id=s.document_id
WHEN MATCHED AND s.row_type=1 AND NOT (t.folder_id <=> s.folder_id
  AND t.owner_user_id <=> s.owner_user_id AND t.customer_id <=> s.customer_id
  AND t.document_name <=> s.document_name AND t.created_dt <=> s.created_dt AND t.status_cd <=> s.status_cd)
THEN UPDATE SET folder_id=s.folder_id,owner_user_id=s.owner_user_id,customer_id=s.customer_id,
  document_name=s.document_name,created_dt=s.created_dt,status_cd=s.status_cd
WHEN NOT MATCHED AND s.row_type=0 THEN INSERT
  (document_id,folder_id,owner_user_id,customer_id,document_name,created_dt,status_cd)
  VALUES(s.document_id,s.folder_id,s.owner_user_id,s.customer_id,s.document_name,s.created_dt,s.status_cd);
