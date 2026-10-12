-- ops: run logging, the SQL Agent job catalog and its history, and the
-- watermarks the incremental loads read.
IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');
GO

CREATE TABLE ops.etl_run_log (
    run_id          int IDENTITY(1, 1) PRIMARY KEY,
    object_name     nvarchar(128)  NOT NULL,
    object_type     varchar(20)    NOT NULL,
    business_date   date           NULL,
    status          varchar(20)    NOT NULL,
    rows_read       int            NULL,
    rows_written    int            NULL,
    started_at      datetime2      NOT NULL,
    finished_at     datetime2      NULL,
    host_name       nvarchar(128)  NULL,
    message         nvarchar(4000) NULL
);

CREATE TABLE ops.agent_jobs (
    job_name            nvarchar(128)  NOT NULL,
    step_id             int            NOT NULL,
    step_name           nvarchar(128)  NOT NULL,
    subsystem           varchar(20)    NOT NULL,
    command             nvarchar(max)  NOT NULL,
    on_success_action   varchar(30)    NOT NULL,
    on_fail_action      varchar(30)    NOT NULL,
    schedule_name       nvarchar(128)  NOT NULL,
    schedule_freq       varchar(20)    NOT NULL,
    schedule_detail     nvarchar(200)  NOT NULL,
    active_start_time   int            NOT NULL,
    enabled             bit            NOT NULL,
    owner_login         nvarchar(128)  NOT NULL,
    loaded_at           datetime2      NOT NULL,
    CONSTRAINT pk_agent_jobs PRIMARY KEY (job_name, step_id)
);

CREATE TABLE ops.agent_job_history (
    instance_id     int IDENTITY(1, 1) PRIMARY KEY,
    job_name        nvarchar(128)  NOT NULL,
    step_id         int            NOT NULL,
    step_name       nvarchar(128)  NOT NULL,
    business_date   date           NULL,
    run_status      tinyint        NOT NULL,
    run_date        int            NOT NULL,
    run_time        int            NOT NULL,
    run_duration    int            NOT NULL,
    message         nvarchar(4000) NULL
);

CREATE TABLE ops.parity_watermarks (
    object_name      nvarchar(128)  NOT NULL PRIMARY KEY,
    watermark_column nvarchar(128)  NOT NULL,
    watermark_value  nvarchar(64)   NULL,
    business_date    date           NULL,
    updated_at       datetime2      NOT NULL
);
GO
