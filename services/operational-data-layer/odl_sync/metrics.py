import time
from prometheus_client import Counter, Gauge, Histogram

SOURCES = ('db2', 'oracle', 'postgres')
REASONS = ('connect', 'read', 'transform', 'write')
lag = Gauge('odl_sync_lag_seconds', 'Seconds since last applied source checkpoint', ['source'])
records = Counter('odl_sync_records_total', 'Successfully applied customer records', ['source'])
errors = Counter('odl_sync_errors_total', 'Failed sync attempts', ['source', 'reason'])
read_requests = Counter('odl_read_requests_total', 'Completed read requests', ['route', 'status'])
read_duration = Histogram('odl_read_request_duration_seconds', 'Read request duration', ['route', 'status'],
                          buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, float('inf')))
checkpoints = {}
for source in SOURCES:
    records.labels(source)
    for reason in REASONS:
        errors.labels(source, reason)


def success(source, checkpoint, count):
    records.labels(source).inc(count)
    checkpoints[source] = checkpoint
    lag.labels(source).set_function(lambda s=source: max(0, time.time() - checkpoints[s]))
