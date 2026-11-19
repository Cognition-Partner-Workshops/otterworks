# SRE triage: read-only signal map

Scope: diagnostics only. Never repair the golden admin-service planted logger bug;
never inject faults into `otterworks-main`. Do not use `page: devin` on SRE alerts
(that starts the separate incident-responder demo). Change requests require approval.

## Access and deployment boundary

Shared release `monitoring/prometheus` and `alertmanager-odl-config` are owned
outside this repository. Do not edit either. Install the
[`sre-observability` chart](../../infrastructure/helm/sre-observability/README.md)
once in monitoring through the approved deployment process. Its webhook is off
until the Secret-backed receiver is provisioned. Alerts use `namespace=monitoring`
for AlertmanagerConfig's OnNamespace strategy, with the **real source namespace**
in `affected_namespace`. Cluster alerts use `affected_namespace=cluster`.

The `monitoring/sre-triage` ServiceAccount has no automatic token mount, Secrets,
exec or write privileges. Obtain a short-lived session from an operator; do not
create tokens from an investigation. AWS access is separate: use an approved
read-only role for CloudWatch Logs, EKS, RDS and PI. RBAC service-proxy GET cannot
limit the inner URL path; see the chart README's security boundary. Never print
raw Alertmanager `/api/v2/status` configuration: it may expose webhook headers.

Automation auth is `X-Webhook-Secret`, not Bearer. The live shared receiver uses
native `http_headers.X-Webhook-Secret.values`, but the current AlertmanagerConfig
CRD exposes no custom header field. This chart therefore requires an explicit
header-relay opt-in before enabling delivery: Secret
`monitoring/alertmanager-sre-webhook` keys `url` (HTTPS relay URL, **not** the
Automation URL) and `webhook-secret` (Bearer credential to the relay, forwarded
as `X-Webhook-Secret`). No relay is deployed here. Until one is provisioned,
leave webhook disabled; see the chart README. Never substitute a CONNECT proxy
header or embed header secret values in chart values.

## Signals and exact read-only queries

Commands assume an authenticated kubectl context for `otterworks-dev` and AWS
region `us-east-1`. Set `NS` from the alert's `affected_namespace`, not its
`namespace` label. These service-proxy URLs work directly through the API server;
no port-forward, pod exec, or proxy process is required.

```sh
export AWS_DEFAULT_REGION=us-east-1
NS=otterworks-main
PROM=/api/v1/namespaces/monitoring/services/http:prometheus-prometheus:9090/proxy
AM=/api/v1/namespaces/monitoring/services/http:prometheus-alertmanager:9093/proxy
JAEGER=/api/v1/namespaces/monitoring/services/http:jaeger:16686/proxy
GRAFANA=/api/v1/namespaces/monitoring/services/http:prometheus-grafana:80/proxy

# Metrics: URL-encode arbitrary PromQL, including braces and plus signs.
QUERY="up{namespace=\"$NS\"}"
ENCODED=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$QUERY")
kubectl get --raw "$PROM/api/v1/query?query=$ENCODED"
kubectl get --raw "$PROM/api/v1/targets"
kubectl get --raw "$PROM/api/v1/rules?type=alert"
kubectl get --raw "$PROM/api/v1/alerts"
# Range query: replace epoch values with incident start/end.
kubectl get --raw "$PROM/api/v1/query_range?query=$ENCODED&start=1795118400&end=1795122000&step=30"

# Active/pending notifications (safe alert payload, not raw status/config).
kubectl get --raw "$AM/api/v2/alerts"
kubectl get --raw "$AM/api/v2/alerts/groups"
kubectl get prometheusrules,servicemonitors -A

# Trace discovery and a slow document-service trace (URL-encoded duration).
kubectl get --raw "$JAEGER/api/services"
kubectl get --raw "$JAEGER/api/traces?service=document-service&lookback=1h&limit=20&minDuration=2s"
# Substitute a traceID from the preceding result.
kubectl get --raw "$JAEGER/api/traces/TRACE_ID"
# Grafana may require its own authentication even through Kubernetes proxy.
kubectl get --raw "$GRAFANA/api/health"
kubectl get --raw "$GRAFANA/api/search?type=dash-db"

# Events, workload state and immediate logs (previous is useful for restarts).
kubectl get pods,deployments,daemonsets,statefulsets -n "$NS" -o wide
kubectl get events -n "$NS" --sort-by=.metadata.creationTimestamp
kubectl describe pod POD -n "$NS"
kubectl logs POD -n "$NS" -c CONTAINER --since=30m --tail=200
kubectl logs POD -n "$NS" -c CONTAINER --previous --tail=200
kubectl describe node NODE
```

### Durable logs: CloudWatch Logs Insights

`scripts/install-log-shipping.sh` deploys shared Fluent Bit separately. Its inputs
include **all containers in otterworks-* namespaces**, including startup/error
lines, plus tenant-routed shared ingress access logs. Groups:
`/otterworks/eks/otterworks-dev/<namespace>/<container>` (7d retention).
Ingress gets container name `ingress-nginx`; arbitrary/plain backend logs retain
their original content, so not every line has structured route/status fields.
Use bounded windows; the query APIs below start read-only Insights queries (cost
is based on data scanned). Do not use write/retention/deletion APIs during triage.

```sh
aws logs describe-log-groups --log-group-name-prefix "/otterworks/eks/otterworks-dev/$NS/"
START=$(date -u -d '30 minutes ago' +%s)
END=$(date -u +%s)
QUERY_ID=$(aws logs start-query \
  --log-group-name "/otterworks/eks/otterworks-dev/$NS/document-service" \
  --start-time "$START" --end-time "$END" \
  --query-string 'fields @timestamp, @message, level, trace_id | sort @timestamp desc | limit 100' \
  --query queryId --output text)
aws logs get-query-results --query-id "$QUERY_ID"
# Repeat get-query-results until status is Complete; do not assume first result is final.
```

Useful query strings (choose the appropriate container group):

```text
fields @timestamp, @message | filter @message like /(?i)(error|exception|panic|fatal)/ | sort @timestamp desc | limit 100
fields @timestamp, trace_id, @message | filter trace_id = 'TRACE_ID' | sort @timestamp asc | limit 200
filter ispresent(duration_ms) | stats count(*) as requests, pct(duration_ms,95) as p95_ms by bin(5m), route, client
```

Control-plane logs: `/aws/eks/otterworks-dev/cluster` (API/audit enabled; 7d).
Run the same bounded Insights commands against that group with:

```text
fields @timestamp, verb, objectRef.namespace, objectRef.resource, responseStatus.code, @message | filter responseStatus.code >= 400 | sort @timestamp desc | limit 100
```

### RDS diagnostics

```sh
aws rds describe-db-instances --db-instance-identifier otterworks-postgres-dev \
  --query 'DBInstances[0].{Status:DBInstanceStatus,ResourceId:DbiResourceId,PI:PerformanceInsightsEnabled,Monitoring:MonitoringInterval,Logs:EnabledCloudwatchLogsExports}'
aws rds describe-events --source-type db-instance --source-identifier otterworks-postgres-dev --duration 60
# PI only works when enabled; current audit: disabled, enhanced monitoring interval 0.
DB_RESOURCE_ID=$(aws rds describe-db-instances --db-instance-identifier otterworks-postgres-dev --query 'DBInstances[0].DbiResourceId' --output text)
aws pi get-resource-metrics --service-type RDS --identifier "$DB_RESOURCE_ID" \
  --start-time 2026-11-19T20:00:00Z --end-time 2026-11-19T20:30:00Z \
  --metric-queries '[{"Metric":"db.load.avg"}]' --period-in-seconds 60
aws pi describe-dimension-keys --service-type RDS --identifier "$DB_RESOURCE_ID" \
  --start-time 2026-11-19T20:00:00Z --end-time 2026-11-19T20:30:00Z \
  --metric db.load.avg --group-by '{"Group":"db.wait_event","Limit":10}'
aws logs describe-log-streams --log-group-name /aws/rds/instance/otterworks-postgres-dev/postgresql --order-by LastEventTime --descending --max-items 5
```

Replace the example times with the incident window. RDS PostgreSQL logs are
exported; PI/enhanced monitoring need a separate approved infrastructure change.
Container Insights was absent at audit time; Kubernetes metrics currently live
in Prometheus, not the CloudWatch `ContainerInsights` namespace.

## Per-alert first steps

| Alert | First read-only action |
|---|---|
| SREAppTargetDown | Inspect `/api/v1/targets` lastError, ServiceMonitor path, Service endpoints, pod health. Report-service uses `/actuator/prometheus`; frontends intentionally have no metrics monitor. |
| SREPodCrashLooping / SREPodRestarting | Read pod events and `logs --previous`; preserve planted golden admin-service behavior, classify it rather than fixing it. |
| OtterworksContainerOOMKilled (#3297) | Read last termination state and memory history; distinguish fresh restart from old OOM reason. |
| SREPodNotReady | Inspect pod conditions, events and dependency logs. Completed jobs and absent idle pods should not alert. |
| SREDeploymentUnavailable | Compare desired/available replicas, ReplicaSet events; idle-at-zero is normal. Zero-available t-main core deployments are excluded here and covered by #3297's OtterworksMainCoreServiceUnavailable. |
| OtterworksMainIngressErrorRate (#3297) | Query `nginx_ingress_controller_requests` by namespace/ingress/status; compare gateway and ingress access logs. |
| otterworks-reliability latency/SLO alerts (#3297) | Query `nginx_ingress_controller_request_duration_seconds_bucket`; correlate a slow Jaeger trace with downstream errors/DB events. |
| OtterworksNodeNotReady (#3297) / SRENodePressure | Describe node and events; inspect kube_node_status_condition. No drains, deletes or scaling during triage. |
| SRENodeFilesystemFull | Query node_filesystem_avail_bytes/size_bytes by instance/mountpoint; inspect node events. Do not remove files. |
| SRERuleEvaluationFailures | Read Prometheus rule API and bounded Prometheus pod logs for evaluation errors. |
| SREPrometheusNotificationFailures | Inspect notification errors, dropped count and discovered Alertmanagers; read Prometheus logs. |
| SREAlertmanagerNotificationFailures | Inspect alert delivery counters by receiver/integration and bounded Alertmanager logs; do not print credentials or raw runtime config. |
| SRETelemetryConfigReloadFailed | Read last reload metric and component logs; coordinate with the external shared-monitoring owner, never edit its Secret. |
| SRELogShippingUnavailable | Inspect otterworks-system DaemonSet desired/available and Fluent Bit logs; verify recent CloudWatch streams and IRSA errors. |

## Known prerequisites / checks before rollout

- PR #3297 owns the `ingress-nginx/ingress-nginx-controller` ServiceMonitor,
  report-service/frontend scrape fixes, and the `otterworks-reliability`
  PrometheusRule with `otterworks-slo` and `otterworks-capacity` groups for
  SLO/capacity/ingress alerts, NodeNotReady and OOMKilled. This chart supplies
  12 complementary alerts in `otterworks.sre`, not an ingress monitor.
- Fluent Bit IRSA role `otterworks-fluent-bit-dev` exists. Installation/shipping
  and AWS permissions still need verification after an approved rollout.
- The missing log-shipping alert intentionally fires even with no tenant pods:
  it monitors a platform prerequisite, not an idle tenant.
- Webhook delivery is disabled by default. Test opt-in receiver delivery in a
  separately approved step; no synthetic notification was sent by this change.
- External black-box/dead-man monitoring is still needed when Prometheus or
  Alertmanager itself is completely unavailable. Self-metrics cannot page then.
