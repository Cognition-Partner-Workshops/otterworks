# Shared SRE observability

Install once in `monitoring`, after the shared prometheus-operator CRDs. This
chart does not own the shared Prometheus release or Alertmanager config Secret.
Prometheus must select this chart's rules/ServiceMonitor; Alertmanager must select
its AlertmanagerConfig. The existing ingress-nginx metrics ClusterIP Service must
expose port `metrics`; ingressMetrics creates only a ServiceMonitor, not a Service.

```sh
helm upgrade --install sre-observability infrastructure/helm/sre-observability -n monitoring
```

Webhook delivery defaults **off**. Before opting in, provision Secret
`monitoring/alertmanager-sre-webhook` through the approved secret manager:

| Key | Content |
|---|---|
| `url` | HTTPS webhook endpoint accepting Alertmanager v4 JSON |
| `token` | Bearer authorization credential (no `Bearer ` prefix) |

Enable with `--set alerting.webhook.enabled=true`. No Secret resource or secret
value is rendered by this chart. Secret name/keys and grouping intervals are
configurable. Never set `page: devin`; it belongs to the incident demo automation.
Rules preserve the source namespace as `affected_namespace`, then set
`namespace: monitoring` for Alertmanager's OnNamespace matching. Cluster-scoped
signals use `affected_namespace: cluster`. Rule thresholds/windows/delays live in
`values.yaml`. Idle deployments with zero desired replicas do not alert.

`sre-triage` does not automount credentials. An operator must provision a
short-lived identity/session separately. Workload and log reads are cluster-wide;
proxy GET is limited by a namespaced Role to the four named monitoring Services.
Kubernetes RBAC **cannot restrict URL paths/query strings inside a service proxy**:
these grants allow all GET paths on those services, not a query-only HTTP allowlist.
If strict query-path enforcement is required, use an authenticated allowlisting
gateway rather than service-proxy RBAC. Do not expose secrets via API GET routes
(notably raw Alertmanager status configuration). No secrets, exec or write grants.

Checks (system Python needs PyYAML; promtool and helm on PATH):

```sh
/usr/bin/python3 infrastructure/helm/sre-observability/tests/check.py
```

Operational queries and per-alert first steps: [SRE triage](../../../docs/runbooks/sre-triage.md).
