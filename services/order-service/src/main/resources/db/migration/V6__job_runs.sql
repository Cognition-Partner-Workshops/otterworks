CREATE TABLE job_runs (
    id            BIGSERIAL PRIMARY KEY,
    job           TEXT NOT NULL,
    source        TEXT,
    status        TEXT NOT NULL,
    rows_read     INTEGER NOT NULL DEFAULT 0,
    rows_applied  INTEGER NOT NULL DEFAULT 0,
    message       TEXT,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX job_runs_job_started ON job_runs (job, started_at DESC);
