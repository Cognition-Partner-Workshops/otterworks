# Observability maturity

Source/config assessment; not a live readiness certification. Ratings: 1 absent,
2 partial, 3 repeatable baseline, 4 operationally verified.

| Pillar | Rating before → after | Baseline / remaining limitation |
|---|---|---|
| Metrics | 2 → 3 | Existing polyglot exporters; report scrape/monitor path fixed, Redis/Postgres exporters wired, monitor selector labels consistent. Billing/legacy lack metrics; generic rules still assume some nonexistent or differently named signals. |
| Logs | 2 → 2 | Mostly JSON, edge-only EKS Fluent Bit shipping; missing service log groups added. No all-service central search or retention verification. |
| Traces | 2 → 2 | Gateway/audit export OTel; document opt-in. Other services have dependencies/config without initialized exporters. |
| Dashboards | 2 → 3 | Existing service/incident dashboards plus SLO overview and Helm sidecar ConfigMap. JSON validated, visually unverified. |
| Alerting | 2 → 3 | Existing thresholds/incident routing plus paired-window burn alerts, local runbooks, Promtool tests and CI gates. Delivery/escalation not exercised. |
| SLOs | 1 → 3 | Six services, availability + latency definitions, generated SLIs/budgets, 30d objectives. Collab persistence is a proxy; objective agreement and real 30d evidence still needed. |

## What changed / operating instructions

- Edit `observability/slo/slos.yaml`, then run `python3 scripts/gen-slo-rules.py`
  (Python + PyYAML). This updates `slo_rules.yml` and chart copies of SLO,
  generic alert/recording rules and the SLO dashboard. Never edit generated copies.
- Availability: served-request 5xx failure fraction, 99.5% objective. Latency:
  95% within an existing 500ms histogram bucket, not an average of quantiles.
  Auth's Micrometer bucket is explicitly enabled in its application config.
  Collab uses persistence-operation status and completed document-sync timing.
  Gateway excludes `path="other"`; file/auth exclude health/metrics. Document
  and search already exclude probe/scrape endpoints in instrumentation.
- Aggregation preserves tenant namespace and filters jobs per service. Compose
  has no namespace label and remains supported. No traffic/missing data yields no
  SLI, not success; ServiceDown remains separate. Error budgets use traffic-weighted
  raw-counter rates over 30d. See [burn runbook](../runbooks/slo-burn-rate.md).
- Compose loads the same generated rules and automatically provisions dashboard
  JSON from `observability/grafana/dashboards/`. Exporters use local demo DB
  credentials only; use a dedicated read-only Postgres monitoring account outside
  this local setup. No public exporter ports are published.

## Optional shared Kubernetes stack (not installed by this change)

Review `infrastructure/helm/kube-prometheus-stack/values.yaml` before running
`bash scripts/install-monitoring.sh`. It pins the open-source upstream chart
**65.8.1**, Alertmanager **0.28.1**, installs release `prometheus` in `monitoring`,
then the local `observability-rules` chart. All Services remain ClusterIP.
No ingress or external load balancer is created; use approved internal access.

Prerequisites, provisioned through your normal secret-management process:
- Namespace `monitoring`.
- Secret `monitoring-webhooks` there: `devin-url`, `devin-secret`, `slack-url`.
  URLs must be real approved HTTPS receivers; do not commit values.
- Secret `monitoring-grafana-admin`: `admin-user`, `admin-password`.

Routing follows the existing `page: devin` model: page alerts fan out to Devin
(X-Webhook-Secret) and Slack; non-pages/tickets go to Slack, not a ticket tracker.
The Compose incident sink is intentionally not a cluster dependency. Grafana uses
the supplied admin Secret and watches labelled dashboard ConfigMaps; this chart
ships the SLO overview, tenant document charts already ship incident dashboards.

Kubernetes namespace selectors cannot regex-match names. Existing `otterworks-*`
tenant namespaces carry `platform/team: otterworks` from `deploy-tenant.sh`.
The installer labels `monitoring` the same way; these namespaces are watched for
`release: prometheus` ServiceMonitors/PrometheusRules. Any manually created
tenant namespace must get that label. Tenant data is not an authorization boundary
inside the shared Prometheus/Grafana: restrict dashboard access appropriately.

Before production use, add a reviewed PVC/storage class and sizing for the 35d
retention (the baseline retains the upstream ephemeral-storage default), verify
network policies/target discovery, routing credentials, durable history and recovery.
The stack does not install Jaeger, an OTel collector, Loki or AWS metrics exporters.
Existing generic alerts need those source metrics; absent series are not healthy.
Generic rules are packaged unchanged except runbook links; their metric/namespace
normalization remains follow-up work, not a claim of complete tenant isolation.

## Prioritized follow-ups

1. Verify live targets, raw histogram/count labels, alert delivery and dashboards
   in an isolated tenant; agree objectives with service owners. Add SLO data-missing
   alerts and provision durable retention before enforcing release budgets.
2. Normalize service RED metrics and generic recording rules (names/status labels
   differ); replace collab's persistence proxy with end-to-end WebSocket outcomes,
   include failed syncs, and measure billing/legacy `/metrics`.
3. Initialize OTel in auth/file/collab/notification/search/analytics/report;
   standardize W3C propagation, request-ID forwarding and log trace correlation.
4. Extend log shipping to all services; evaluate open-source Loki for Grafana log
   search, retention/redaction and tenant-safe access.
5. Add AWS exporter coverage, missing-data alert tests, on-call ownership/rotation,
   ticket automation and dashboard/data-source smoke tests.

## Local validation

See `.github/workflows/observability.yml`: generator/unit/drift checks, Promtool
config/rules/tests, rendered Alertmanager validation, runbook links, JSON, Helm
lint/render plus kubeconform (`-ignore-missing-schemas` for operator CRDs), and
Compose config. `scripts/check-observability-charts.sh` validates every actual
local Chart.yaml plus the pinned upstream stack; values-only Fluent Bit/ingress
directories are overlays rather than standalone charts. No deploy/apply is run.
