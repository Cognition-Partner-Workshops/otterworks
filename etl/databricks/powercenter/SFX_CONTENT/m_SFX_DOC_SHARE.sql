/* run=dbx-d1111 act=scale step=lookup-guard consumer=m_SFX_DOC_SHARE */
SELECT assert_true(count(*)=0,'Ambiguous first-match ROLE_GRANT cache order')
FROM (SELECT user_id FROM cpw.dbx_d1111_before.users__role_grant
      WHERE user_id IS NOT NULL GROUP BY user_id
      HAVING count(DISTINCT coalesce(rtrim(role_cd),'<NULL>'))>1);

/* run=dbx-d1111 act=scale step=convert consumer=m_SFX_DOC_SHARE */
MERGE INTO cpw.dbx_d1111_after.documents__doc_share t
USING (
  WITH lkp AS (
    SELECT user_id,rtrim(role_cd) AS role_cd,
      row_number() OVER (PARTITION BY user_id ORDER BY user_id) AS rn
    FROM cpw.dbx_d1111_before.users__role_grant
  ), parsed AS (
    SELECT share_id,document_id,s.user_id,upper(trim(substring(access_level,1,12))) AS access_level,
      shared_dt,l.role_cd
    FROM cpw.dbx_d1111_before.documents__stg_doc_share s
    LEFT JOIN lkp l ON s.user_id=l.user_id AND l.rn=1
  )
  SELECT share_id,document_id,user_id,
    CASE WHEN role_cd='ADMIN' THEN 'OWNER'
         WHEN role_cd='EDITOR' AND access_level='VIEW' THEN 'EDIT'
         ELSE access_level END AS access_level,shared_dt FROM parsed
) s ON t.share_id=s.share_id
WHEN MATCHED AND NOT (t.document_id <=> s.document_id AND t.user_id <=> s.user_id
  AND t.access_level <=> s.access_level AND t.shared_dt <=> s.shared_dt)
THEN UPDATE SET document_id=s.document_id,user_id=s.user_id,access_level=s.access_level,shared_dt=s.shared_dt
WHEN NOT MATCHED THEN INSERT *;
