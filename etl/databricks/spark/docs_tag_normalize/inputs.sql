/* run=dbx-d1111 act=spark step=inputs consumer=docs_tag_normalize */
/* run_token=dbx-d1111 expires=2026-11-24
   Landing DOC_TAG (etl/spark/jobs/py/common/schemas.py) from the live baseline
   (warehouse/teradata/ddl/documents/00_tables.sql SFX_DOCUMENTS.DOC_TAG):
     DOC_TAG_ID  <- tag_id       (BIGINT, unique primary index)
     DOCUMENT_ID <- document_id  (BIGINT)
     TAG         <- tag_name     (VARCHAR(40) CASESPECIFIC)
   created_dt is not part of the landing layout and is not read by the job. */
SELECT
  CAST(tag_id AS BIGINT)      AS DOC_TAG_ID,
  CAST(document_id AS BIGINT) AS DOCUMENT_ID,
  CAST(tag_name AS STRING)    AS TAG
FROM cpw.dbx_d1111_before.documents__doc_tag
