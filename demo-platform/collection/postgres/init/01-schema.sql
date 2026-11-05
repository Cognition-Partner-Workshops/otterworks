-- Synthetic collection schema. All data is generated; no real systems, people or organisations.
CREATE SCHEMA collection AUTHORIZATION collection_owner;

CREATE TABLE collection.sources (
    id          integer PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    kind        text NOT NULL CHECK (kind IN ('file-drop', 'api-pull', 'db-extract', 'stream')),
    owner_team  text NOT NULL
);

CREATE TABLE collection.jobs (
    id          integer PRIMARY KEY,
    source_id   integer NOT NULL REFERENCES collection.sources(id),
    name        text NOT NULL UNIQUE,
    schedule    text NOT NULL,
    enabled     boolean NOT NULL DEFAULT true
);

CREATE TABLE collection.job_runs (
    id           bigint PRIMARY KEY,
    job_id       integer NOT NULL REFERENCES collection.jobs(id),
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz,
    status       text NOT NULL CHECK (status IN ('succeeded', 'failed', 'running', 'skipped')),
    rows_loaded  integer NOT NULL DEFAULT 0,
    error_code   text
);
CREATE INDEX job_runs_job_started ON collection.job_runs(job_id, started_at);

CREATE TABLE collection.alerts (
    id           bigint PRIMARY KEY,
    job_id       integer NOT NULL REFERENCES collection.jobs(id),
    raised_at    timestamptz NOT NULL,
    severity     text NOT NULL CHECK (severity IN ('SEV1', 'SEV2', 'SEV3', 'SEV4')),
    summary      text NOT NULL,
    resolved_at  timestamptz
);

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE collection FROM PUBLIC;
