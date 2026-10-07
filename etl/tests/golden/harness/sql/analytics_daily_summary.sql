-- Derived from the INSERT ... ON CONFLICT (report_date) upsert in
-- etl/scripts/analytics_daily.py (the table is not in scripts/init-db.sql).
-- report_date is the conflict target, so it is the primary key; counters are
-- Python ints, bytes_uploaded is a byte sum and gets BIGINT; updated_at is
-- set with NOW().
CREATE TABLE IF NOT EXISTS analytics_daily_summary (
    report_date        DATE        PRIMARY KEY,
    active_users       INTEGER     NOT NULL DEFAULT 0,
    active_documents   INTEGER     NOT NULL DEFAULT 0,
    active_files       INTEGER     NOT NULL DEFAULT 0,
    total_events       INTEGER     NOT NULL DEFAULT 0,
    documents_created  INTEGER     NOT NULL DEFAULT 0,
    documents_edited   INTEGER     NOT NULL DEFAULT 0,
    comments_added     INTEGER     NOT NULL DEFAULT 0,
    files_uploaded     INTEGER     NOT NULL DEFAULT 0,
    files_shared       INTEGER     NOT NULL DEFAULT 0,
    files_deleted      INTEGER     NOT NULL DEFAULT 0,
    bytes_uploaded     BIGINT      NOT NULL DEFAULT 0,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
