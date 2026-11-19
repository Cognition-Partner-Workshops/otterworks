# Shared SRE observability

Install once in `monitoring`, after the shared prometheus-operator CRDs. This
chart does not own the shared Prometheus release or Alertmanager config Secret.
Prometheus must select this chart's rules; Alertmanager must select its
AlertmanagerConfig. PR #3297 owns the ingress ServiceMonitor
`ingress-nginx/ingress-nginx-controller` and the `otterworks-reliability`
PrometheusRule (groups `otterworks-slo` and `otterworks-capacity`) for
SLO/capacity/ingress alerts, NodeNotReady and OOMKilled. This chart's
`otterworks.sre` group has 12 complementary alerts and no ServiceMonitor.
Deployment-unavailable warnings exclude t-main core deployments with zero
available replicas, covered by `OtterworksMainCoreServiceUnavailable`.
PR #3297 also owns the report-service and frontend scrape fixes.

```sh
helm upgrade --install sre-observability infrastructure/helm/sre-observability -n monitoring
```

Webhook delivery defaults **off**. Before opting in, provision Secret
`monitoring/alertmanager-sre-webhook` through the approved secret manager:

| Key | Content |
|---|---|
| `url` | HTTPS header-relay endpoint accepting Alertmanager v4 JSON (not the Automation URL) |
| `webhook-secret` | Credential sent to the relay as Bearer; relay forwards it as `X-Webhook-Secret` |

The deployed operator v0.94.1 AlertmanagerConfig CRD has **no custom HTTP header
field**. The shared receiver uses native Alertmanager
`http_headers.X-Webhook-Secret.values`; that cannot be expressed by this CRD.
`proxyConnectHeader` only authenticates HTTP CONNECT proxies, not webhooks.
Closest supported option: Secret-backed Bearer auth to a separately managed
HTTPS relay that verifies the credential, forwards the JSON to the Automation,
and translates the credential into `X-Webhook-Secret`. The relay is not supplied
by this chart; never point this receiver directly at Devin (Bearer is rejected).
Do not put secret header values in chart values or patch shared configuration.

After the relay exists, enable with `--set alerting.webhook.enabled=true
--set alerting.webhook.headerRelay=true`. No Secret resource or secret
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
