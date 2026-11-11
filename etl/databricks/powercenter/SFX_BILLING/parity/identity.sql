/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_GL_JOURNAL_LINE */
SELECT 'left' side,count(*) n,count(DISTINCT journal_line_id) distinct_ids,
min(journal_line_id) minimum,max(journal_line_id) maximum,
max(journal_line_id)-min(journal_line_id)+1 span FROM ${LEFT_TABLE}
UNION ALL
SELECT 'right',count(*),count(DISTINCT journal_line_id),min(journal_line_id),max(journal_line_id),
max(journal_line_id)-min(journal_line_id)+1 FROM ${RIGHT_TABLE};
