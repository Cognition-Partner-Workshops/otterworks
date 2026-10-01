-- Synthetic documents for the on-call storm, generated inside Postgres so 200k
-- rows load in seconds. Every id is md5-derived, so a second run inserts
-- nothing and the k6 script computes the same folder ids on its own.
-- Variables (psql -v): owner, documents, folders, versions.
-- No index on documents.folder_id is created here, ever: its absence is the
-- incident.

SET statement_timeout = 0;
SET synchronous_commit = off;
SET client_min_messages = warning;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

INSERT INTO documents (
    id, title, content, content_type, owner_id, folder_id,
    is_deleted, is_template, word_count, version, created_at, updated_at
)
SELECT
    md5('oncall-doc-' || n)::uuid,
    format('%s %s', (ARRAY[
        'Quarterly planning notes', 'Customer call summary', 'Release checklist',
        'Design review', 'Incident follow-up', 'Hiring loop feedback',
        'Budget draft', 'Onboarding guide', 'Sprint retro', 'Vendor comparison'
    ])[1 + n % 10], n),
    format(E'# Notes %s\n\nOwner sync covered scope, dates and open questions. '
           'Action items are tracked in the team board. Revision %s.', n, :versions),
    'text/markdown',
    :'owner'::uuid,
    md5('oncall-folder-' || (n % :folders))::uuid,
    false,
    false,
    24,
    :versions,
    now() - make_interval(mins => 60 * 24 * 180 - n % (60 * 24 * 90)),
    now() - make_interval(mins => n % (60 * 24 * 90))
FROM generate_series(1, :documents) AS n
ON CONFLICT (id) DO UPDATE
    SET owner_id = EXCLUDED.owner_id
    WHERE documents.owner_id IS DISTINCT FROM EXCLUDED.owner_id;

INSERT INTO document_versions (
    id, document_id, version_number, title, content, created_by, created_at
)
SELECT
    md5('oncall-ver-' || n || '-' || v)::uuid,
    md5('oncall-doc-' || n)::uuid,
    v,
    format('Notes %s', n),
    format(E'# Notes %s\n\nRevision %s of the synthetic document.', n, v),
    :'owner'::uuid,
    now() - make_interval(mins => 60 * 24 * 90 - v)
FROM generate_series(1, :documents) AS n
CROSS JOIN generate_series(1, :versions) AS v
ON CONFLICT (id) DO NOTHING;

ANALYZE documents;
ANALYZE document_versions;

SELECT format('documents=%s folders=%s versions=%s owner_documents=%s',
    (SELECT count(*) FROM documents),
    (SELECT count(DISTINCT folder_id) FROM documents WHERE folder_id IS NOT NULL),
    (SELECT count(*) FROM document_versions),
    (SELECT count(*) FROM documents WHERE owner_id = :'owner'::uuid));
