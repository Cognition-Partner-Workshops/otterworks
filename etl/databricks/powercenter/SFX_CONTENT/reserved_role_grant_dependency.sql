/* run=dbx-d1111 act=scale step=reserved-dependency consumer=wf_SFX_CONTENT_DAILY */
SELECT assert_true(false,
  'Reserved s_m_SFX_ROLE_GRANT success is unavailable: DOC_SHARE dependency remains unsatisfied');
