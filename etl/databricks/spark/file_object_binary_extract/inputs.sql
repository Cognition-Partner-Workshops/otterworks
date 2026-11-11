-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter for file_object_binary_extract. The job reads two inputs:
--   1. binaryFile over landing/documents/FILE_OBJECT_BLOBS/* (the self-run blob store), and
--   2. landing table documents/FILE_OBJECT
--      (FILE_OBJECT_ID, DOCUMENT_ID, SIZE_BYTES, CHECKSUM, STORAGE_KEY), joined on STORAGE_KEY.
-- Live cpw.dbx_d1111_before.documents__file_object has
--   file_object_id, document_id, object_key, bytes_used, storage_class, created_dt.
--   FILE_OBJECT_ID <- file_object_id
--   DOCUMENT_ID    <- document_id
--   SIZE_BYTES     <- bytes_used
--   CHECKSUM       <- no live equivalent (NULL; not derivable)
--   STORAGE_KEY    <- no live equivalent: object_key addresses a different store
--                     ('workspaces/<n>/documents/<n>/original.<ext>'); statement 2 shows that
--                     no live key is of the form 'documents/FILE_OBJECT_BLOBS/<name>' that the job joins on.
-- The blob content itself is not in Unity Catalog: the run schemas have no volume (statement 3).
/* run=dbx-d1111 act=spark step=inputs consumer=file_object_binary_extract */
SELECT file_object_id AS FILE_OBJECT_ID,
       document_id    AS DOCUMENT_ID,
       bytes_used     AS SIZE_BYTES,
       CAST(NULL AS STRING) AS CHECKSUM,
       CAST(NULL AS STRING) AS STORAGE_KEY
FROM cpw.dbx_d1111_before.documents__file_object;

/* run=dbx-d1111 act=spark step=inputs consumer=file_object_binary_extract */
SELECT count(*) AS live_rows,
       count_if(object_key LIKE 'documents/FILE_OBJECT_BLOBS/%') AS joinable_storage_keys
FROM cpw.dbx_d1111_before.documents__file_object;

/* run=dbx-d1111 act=spark step=inputs consumer=file_object_binary_extract */
SHOW VOLUMES IN cpw.dbx_d1111_before;
