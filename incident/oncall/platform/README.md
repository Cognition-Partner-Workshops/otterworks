# On-call telemetry platform

The installer configures the shared `monitoring` namespace with Loki, Alloy,
Tempo and Grafana datasources, then adds Tempo to the collector's existing trace
pipeline and merges the storm routes into Alertmanager. Jaeger and the existing
Alertmanager routes and receivers stay configured.

Run from a checkout with access to the intended cluster:

```bash
aws eks update-kubeconfig --name otterworks-dev --region us-east-1
incident/oncall/platform/install.sh
```

Requirements: kubectl, Docker, Python 3, sha256sum and permission to update the
monitoring resources. The installer uses PyYAML, installing the pinned requirement
in a local virtual environment when needed. It validates the proposed Alertmanager
configuration before changing cluster resources. Repeating the install updates the
same resources; configuration checksums trigger rollouts when settings change.

To enable automated pages, supply `ONCALL_DEVIN_WEBHOOK_URL` and
`ONCALL_DEVIN_WEBHOOK_SECRET` through the caller's environment. Set both variables
together. When both are unset, the channel receives the storm and the Devin receiver
is omitted. The merger reads the live Secret in memory, validates through an
isolated amtool container and prints route and receiver names. Its default mode
validates; `--apply` performs the resource-version-guarded update.

Loki retains logs for 24 hours and Tempo retains trace blocks for 24 hours. Both use
emptyDir storage, so replacing a pod discards the stored telemetry. Alloy runs on
each node and ships logs from `otterworks-oncall-.*` and
`otterworks-platform`, with `namespace`, `app` and `pod` labels. Services
use ClusterIP and the manifests create zero PVCs.

## Tenant exporter

The PodMonitor selects `app: oncall-postgres` in both on-call namespaces and
scrapes the sidecar's port named `metrics`. The tenant Postgres manifest must
provide that label and port. The rules use the default exporter metrics
`pg_stat_activity_count` and `pg_stat_activity_max_tx_duration`; the dashboard
also uses `pg_stat_user_tables_seq_scan`, whose collector is enabled by default
in postgres-exporter v0.17.1. The exporter must connect to the tenant's
`otterworks` database to collect its table statistics.

## Collector exporter name

The live collector uses `otlp_grpc/jaeger`, and Tempo uses the same registered
exporter type as `otlp_grpc/tempo`, targeting
`oncall-tempo.monitoring.svc.cluster.local:4317`. The contract's `traces/tempo`
name would select an unregistered exporter type in this collector.

## Local checks

```bash
python3 -m pip install -r incident/oncall/platform/requirements.txt
python3 -m unittest discover -s incident/oncall/platform -p 'test_*.py' -v
python3 incident/oncall/platform/check-contract.py
shellcheck incident/oncall/platform/install.sh scripts/sync-incident-chart-files.sh
ruff check incident/oncall/platform
scripts/sync-incident-chart-files.sh --check
```

The contract check renders both namespaces, checks disabled resources and label
merging, validates rendered rules and dashboard queries with promtool, and lists
the required metrics. For live metric validation, port-forward Prometheus in a
separate terminal and pass `--prometheus http://127.0.0.1:19090`:

```bash
kubectl -n monitoring port-forward svc/prometheus-prometheus 19090:9090
```

The merger tests use a synthetic configuration with fake secrets, validate the
merged configuration with amtool and check that command output contains none of
the fake values. The collector test checks that adding Tempo preserves Jaeger
and the other pipelines.
