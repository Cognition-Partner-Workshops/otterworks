# Phase 0 / Sprint 1 — SLIs, telemetry baseline, dependency map, journeys

Measurement only: nothing here changes application behavior.

| File | What it is |
|---|---|
| `slo-catalog.yaml` | Every SLI with owner, objective, numerator, denominator, window and workload; `gap` says what blocks an uninstrumented one |
| `../prometheus/slo_recording_rules.yml` | 5m SLI series (`sli:*`) and the gateway burn rate, loaded by `prometheus.yml` |
| `journeys.yaml` | Baseline journeys, the `tests/api` tests that exercise them, fixture rules and data invariants |
| `dependency-map.md` | Source-to-runtime dependency map for t-main, fault concentration, core vs legacy |
| `baseline/` | Day-0 snapshot; the daily ones are kept as workflow artifacts |
| `../../scripts/slo/collect_baseline.py` | Read-only collector (`collect`, `summarize`) |

## The 30-day baseline

The in-cluster Prometheus in `otterworks-dev` keeps **3 days**, so no 30-day history
exists. The baseline starts on **2026-11-20** (day 0 committed under `baseline/`) and
grows by one snapshot a day from `.github/workflows/slo-baseline.yml`, which
port-forwards to Prometheus, runs `collect` (GET queries only) and uploads the JSON as an
artifact kept 90 days. `summarize` sums daily counts (it never averages ratios) and
reports `baseline_complete: true` only after 30 days **with user traffic**.

Day 0 finding: t-main carries only health checks and scrapes (0 user requests through
the gateway), and admin-service, report-service, web-app and admin-dashboard targets are
down. A baseline of t-main alone is therefore not representative; the numbers are only
valid for the workload recorded in each snapshot.

```bash
kubectl -n monitoring port-forward svc/prometheus-prometheus 9090 &
python3 scripts/slo/collect_baseline.py collect --prometheus http://localhost:9090 --namespace otterworks-main
python3 scripts/slo/collect_baseline.py summarize observability/slo/baseline
```

## Decisions for owners before the Phase 0 gate

1. Name a person for each owner role in `slo-catalog.yaml` and ratify or tighten each objective.
2. Platform: raise Prometheus retention to at least 35d or add remote-write.
3. Choose the workload of record: t-main has no users, so either schedule the journeys in
   `journeys.yaml` as synthetic traffic against a dedicated tenant, or baseline a tenant that has real use.
4. Pick an eventing-enabled environment for queue age, DLQ and index freshness SLIs.
5. Sprint 2 label-only instrumentation: gateway per-route labels for folders, templates,
   reports, preferences, settings and socket.io; Auth percentile histograms; Analytics HTTP metrics.

`tests/slo/test_slo_catalog.py` keeps the catalog, rules, journeys and gateway routes consistent.
