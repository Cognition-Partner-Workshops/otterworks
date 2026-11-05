-- Deterministic synthetic seed (fixed seed, fixed time window).
SELECT setseed(0.42);

INSERT INTO collection.sources(id, name, kind, owner_team) VALUES
    (1, 'ledger-file-drop',     'file-drop',  'team-amber'),
    (2, 'orders-api',           'api-pull',   'team-birch'),
    (3, 'inventory-extract',    'db-extract', 'team-cedar'),
    (4, 'clickstream',          'stream',     'team-birch'),
    (5, 'reference-codes',      'file-drop',  'team-amber'),
    (6, 'shipments-api',        'api-pull',   'team-cedar');

INSERT INTO collection.jobs(id, source_id, name, schedule, enabled)
SELECT g, ((g - 1) % 6) + 1, format('collect-%s-%s', (ARRAY['nightly','hourly','daily','weekly'])[((g - 1) % 4) + 1], g),
       (ARRAY['0 2 * * *','0 * * * *','30 6 * * *','0 3 * * 0'])[((g - 1) % 4) + 1], g % 9 <> 0
FROM generate_series(1, 18) AS g;

INSERT INTO collection.job_runs(id, job_id, started_at, finished_at, status, rows_loaded, error_code)
SELECT r.id, r.job_id, r.started_at,
       CASE WHEN r.status = 'running' THEN NULL ELSE r.started_at + make_interval(secs => 30 + floor(random() * 1800)) END,
       r.status,
       CASE WHEN r.status = 'succeeded' THEN floor(random() * 250000)::int ELSE 0 END,
       CASE WHEN r.status = 'failed' THEN (ARRAY['E_TIMEOUT','E_SCHEMA_DRIFT','E_AUTH_EXPIRED','E_FILE_MISSING'])[1 + floor(random() * 4)::int] END
FROM (
    SELECT g AS id, ((g - 1) % 18) + 1 AS job_id,
           timestamptz '2026-10-01 00:00:00+00' + make_interval(hours => g) AS started_at,
           CASE WHEN g = 1440 THEN 'running'
                WHEN random() < 0.08 THEN 'failed'
                WHEN random() < 0.03 THEN 'skipped'
                ELSE 'succeeded' END AS status
    FROM generate_series(1, 1440) AS g
) AS r;

INSERT INTO collection.alerts(id, job_id, raised_at, severity, summary, resolved_at)
SELECT row_number() OVER (ORDER BY jr.id), jr.job_id, jr.finished_at,
       (ARRAY['SEV1','SEV2','SEV3','SEV4'])[1 + floor(random() * 4)::int],
       format('Synthetic: %s failed with %s', j.name, jr.error_code),
       CASE WHEN random() < 0.8 THEN jr.finished_at + make_interval(mins => (5 + floor(random() * 240))::int) END
FROM collection.job_runs jr JOIN collection.jobs j ON j.id = jr.job_id
WHERE jr.status = 'failed';

ANALYZE;
